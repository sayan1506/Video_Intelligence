import os
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any

from google.cloud import firestore
from google.cloud.firestore_v1.vector import Vector
from google.cloud.firestore_v1.base_vector_query import DistanceMeasure
from google.api_core.exceptions import FailedPrecondition

logger = logging.getLogger(__name__)

# ── Singleton client ──────────────────────────────────────────────────────────
# Instantiated once at module load. Cloud Run spins up one process per instance;
# reusing a single client avoids repeated gRPC channel setup on every call.
# ADC resolves via the attached service account — no JSON key needed.
_db: firestore.Client | None = None


def get_db() -> firestore.Client:
    global _db
    if _db is None:
        project_id = os.getenv("GCP_PROJECT_ID")
        _db = firestore.Client(project=project_id)
    return _db


# ── Progress stage map ────────────────────────────────────────────────────────
# Single source of truth for what "progress" means at each stage.
# Worker and backend both read from this — no magic numbers scattered around.
PROGRESS_STAGES: Dict[str, int] = {
    "pending":    0,
    "uploading":  10,
    "processing": 25,
    "stt_done":   50,
    "vi_done":    75,
    "gemini_done": 90,
    "completed":  100,
}


def progress_for_stage(stage: str) -> int:
    """Return the canonical progress integer for a named pipeline stage."""
    return PROGRESS_STAGES.get(stage, 0)


# ── Job lifecycle ─────────────────────────────────────────────────────────────

def create_job(
    job_id: str,
    filename: str,
    gcs_path: str,
    user_id: str = "",
    user_email: str = "",
) -> str:
    """
    Create a new job document in Firestore.

    Returns the job_id (string) rather than the raw document dict so callers
    are never handed a dict containing non-JSON-serialisable datetime objects.

    Args:
        job_id:     Unique job identifier (UUID).
        filename:   Original filename uploaded by the user.
        gcs_path:   GCS object path for the raw video.
        user_id:    Firebase UID of the owning user (V2.0+).
        user_email: User's email address — for display in admin dashboard.
    """
    db = get_db()
    now = datetime.now(timezone.utc)

    job_data = {
        "jobId": job_id,
        "status": "pending",
        "filename": filename,
        "gcsPath": gcs_path,
        "videoUrl": "",
        "uploadProgress": 0,
        "progress": progress_for_stage("pending"),
        "createdAt": now,
        "updatedAt": now,
        "processingStartedAt": None,
        "processingCompletedAt": None,
        "processingTime": 0,
        "errorMessage": "",
        # V2.0 — ownership fields
        "userId": user_id,
        "userEmail": user_email,
        # Public share links — default to private
        "isPublic": False,
    }

    db.collection("jobs").document(job_id).set(job_data)
    logger.info(f"[{job_id}] Job document created — file: {filename}, user: {user_id or 'anonymous'}")
    return job_id


def get_job(job_id: str) -> dict | None:
    """Fetch a job document by ID. Returns None if not found."""
    db = get_db()
    doc = db.collection("jobs").document(job_id).get()
    return doc.to_dict() if doc.exists else None


def update_job_status(job_id: str, status: str, progress: int | None = None, error: str = "") -> None:
    """
    Update job status and optionally progress.

    progress defaults to None (not written) rather than 0, preventing
    silent progress resets when callers omit the argument.
    Pass progress explicitly, or let the stage helpers below handle it.
    """
    db = get_db()
    update_data: Dict[str, Any] = {
        "status": status,
        "updatedAt": datetime.now(timezone.utc),
    }

    if progress is not None:
        update_data["progress"] = progress

    if error:
        update_data["errorMessage"] = error

    db.collection("jobs").document(job_id).update(update_data)


def update_upload_progress(job_id: str, upload_progress: int) -> None:
    """
    Update the uploadProgress field of a job document.
    Called by the progress_callback during chunked GCS upload.
    """
    db = get_db()
    db.collection("jobs").document(job_id).update({
        "uploadProgress": upload_progress,
        "updatedAt": datetime.now(timezone.utc),
    })





def set_job_public(job_id: str, is_public: bool) -> None:
    """Update isPublic field and updatedAt timestamp on a job document."""
    db = get_db()
    db.collection("jobs").document(job_id).update({
        "isPublic": is_public,
        "updatedAt": datetime.now(timezone.utc),
    })


def mark_processing_started(job_id: str) -> None:
    """
    Mark a job as started.
    Sets status → "processing", progress → 25 (from stage map),
    and records processingStartedAt.
    """
    db = get_db()
    now = datetime.now(timezone.utc)
    db.collection("jobs").document(job_id).update({
        "status": "processing",
        "progress": progress_for_stage("processing"),
        "processingStartedAt": now,
        "updatedAt": now,
    })


def mark_processing_completed(job_id: str, processing_time_seconds: int) -> None:
    """
    Mark a job as completed.
    Sets status → "completed", progress → 100 (from stage map),
    and records processingCompletedAt + processingTime.
    """
    db = get_db()
    now = datetime.now(timezone.utc)
    db.collection("jobs").document(job_id).update({
        "status": "completed",
        "progress": progress_for_stage("completed"),
        "processingCompletedAt": now,
        "processingTime": processing_time_seconds,
        "updatedAt": now,
    })


def mark_processing_failed(job_id: str, error_message: str) -> None:
    """
    Mark a job as failed.
    Sets status → "failed" and records the error message for debugging.
    """
    db = get_db()
    db.collection("jobs").document(job_id).update({
        "status": "failed",
        "errorMessage": error_message,
        "updatedAt": datetime.now(timezone.utc),
    })


def list_recent_jobs(limit: int = 20) -> List[dict]:
    """
    Fetch the most recently created jobs, newest first.

    Requires a Firestore composite index on (createdAt DESC).
    Firestore will raise FailedPrecondition (not just log) if the index
    doesn't exist — that exception is caught and re-raised with an
    actionable message so it surfaces cleanly in Cloud Logging.

    Args:
        limit: Maximum jobs to return (default 20, capped at 100).
    """
    db = get_db()
    limit = min(limit, 100)

    try:
        docs = (
            db.collection("jobs")
            .order_by("createdAt", direction=firestore.Query.DESCENDING)
            .limit(limit)
            .stream()
        )
        return [doc.to_dict() for doc in docs]

    except FailedPrecondition as e:
        # Firestore requires a composite index for this query.
        # Check Cloud Logging for the index creation URL.
        logger.error(
            f"list_recent_jobs() failed — Firestore composite index missing. "
            f"Check Cloud Logging for the index creation URL. Original error: {e}"
        )
        raise


def list_user_jobs(user_id: str, limit: int = 20) -> List[dict]:
    """
    Fetch the most recently created jobs for a specific user, newest first.

    Requires a Firestore composite index on (userId ASC, createdAt DESC).
    Create it in the Firebase console or via the index creation URL that
    appears in Cloud Logging when this query first runs without the index.

    Args:
        user_id: Firebase UID to filter by.
        limit:   Maximum jobs to return (default 20, capped at 100).
    """
    db = get_db()
    limit = min(limit, 100)

    try:
        docs = (
            db.collection("jobs")
            .where("userId", "==", user_id)
            .order_by("createdAt", direction=firestore.Query.DESCENDING)
            .limit(limit)
            .stream()
        )
        return [doc.to_dict() for doc in docs]

    except FailedPrecondition as e:
        logger.error(
            f"list_user_jobs() failed — Firestore composite index on "
            f"(userId ASC, createdAt DESC) is missing. "
            f"Check Cloud Logging for the index creation URL. Original error: {e}"
        )
        raise



def get_result(job_id: str) -> dict | None:
    """
    Fetch the AI pipeline results document for a completed job.

    Handles two storage formats transparently:

    New format (V1.1+):
        transcriptChunkCount field is present. Transcript is stored as a
        subcollection (transcript_chunks/). Assembled here and injected into
        the returned dict as data["transcript"].

    Old format (V1.0):
        transcript stored as a flat array directly in the document.
        data["transcript"] already exists — nothing to do.

    Returns:
        Dict with keys: transcript, scenes, labels — or None if not found.
        transcript is always a flat list regardless of storage format.
    """
    db = get_db()
    doc = db.collection("results").document(job_id).get()

    if not doc.exists:
        return None

    data = doc.to_dict()

    # ── New format: transcript stored as subcollection chunks ──────────────
    chunk_count = data.get("transcriptChunkCount")
    if chunk_count is not None and chunk_count > 0:
        transcript = get_transcript_chunks(job_id, chunk_count)
        data["transcript"] = transcript
        logger.info(f"[{job_id}] Loaded chunked transcript — {len(transcript)} words")

    # ── Old format: transcript is a flat array in the document ─────────────
    # data["transcript"] already exists as a list — nothing to do.
    # Handles all pre-V1.1 completed jobs gracefully.
    elif "transcript" not in data:
        logger.warning(f"[{job_id}] Result document has neither transcript nor chunks")
        data["transcript"] = []

    return data


def get_summary(job_id: str) -> dict | None:
    """
    Fetch the Gemini summary document for a completed job.

    Reads from the summaries/{jobId} collection written by the worker Gemini stage.
    Returns None if not found — summary may not exist if Gemini pipeline failed
    or if this is a legacy job from before Week 4.

    Args:
        job_id: The job identifier.

    Returns:
        Dict with keys: summary, chapters, highlights, sentiment, actionItems — or None.
    """
    db = get_db()
    doc = db.collection("summaries").document(job_id).get()

    if not doc.exists:
        return None

    return doc.to_dict()




def get_transcript_chunks(job_id: str, chunk_count: int) -> list:
    """
    Assemble a full transcript from subcollection chunks.

    Reads transcript_chunks/0 through transcript_chunks/{chunk_count-1}
    and concatenates their word arrays in order.

    Called by get_result() when the result document has a transcriptChunkCount
    field (i.e. new-format jobs written by the V1.1 worker).

    Args:
        job_id:      The job identifier.
        chunk_count: Number of chunks to fetch — read from transcriptChunkCount
                     in the parent results document.

    Returns:
        Flat list of WordTimestamp dicts, assembled in order.
        Returns [] if any chunk is missing (defensive — logs a warning).
    """
    db = get_db()
    chunk_ref = (
        db.collection("results")
        .document(job_id)
        .collection("transcript_chunks")
    )

    transcript = []

    for i in range(chunk_count):
        doc = chunk_ref.document(str(i)).get()
        if not doc.exists:
            logger.warning(
                f"[{job_id}] Transcript chunk {i} missing "
                f"(expected {chunk_count} chunks) — transcript may be incomplete"
            )
            continue
        words = doc.to_dict().get("words", [])
        transcript.extend(words)

    logger.info(
        f"[{job_id}] Transcript assembled — "
        f"{len(transcript)} words from {chunk_count} chunks"
    )
    return transcript


# ---------------------------------------------------------------------------
# PAY-1 — User and billing helpers
# ---------------------------------------------------------------------------

def get_or_create_user(user_id: str, email: str) -> dict:
    """
    Get the users/{userId} document, creating it with free plan defaults on first call.
    Called by billing endpoints when a user interacts with the payment flow for the first time.
    """
    db = get_db()
    ref = db.collection("users").document(user_id)
    doc = ref.get()
    if doc.exists:
        return doc.to_dict()
    now = datetime.now(timezone.utc)
    user_data = {
        "userId": user_id,
        "email": email,
        "razorpayCustomerId": "",
        "razorpaySubscriptionId": "",
        "plan": "free",
        "planExpiresAt": None,
        "monthlyJobCount": 0,
        "monthlyJobResetAt": now,
        "createdAt": now,
    }
    ref.set(user_data)
    logger.info(f"[{user_id}] users doc created (plan: free)")
    return user_data


def update_user(user_id: str, fields: dict) -> None:
    """
    Partial update on users/{userId}.
    Used by webhook handlers to set plan, razorpaySubscriptionId, planExpiresAt.
    """
    db = get_db()
    fields["updatedAt"] = datetime.now(timezone.utc)
    db.collection("users").document(user_id).update(fields)
    logger.info(f"[{user_id}] update_user: {list(fields.keys())}")


def get_user_by_razorpay_subscription(subscription_id: str) -> dict | None:
    """
    Look up a user document by razorpaySubscriptionId.
    Used exclusively in webhook handlers where we only have the Razorpay subscription ID.
    Returns None if no user is found.
    """
    db = get_db()
    docs = list(
        db.collection("users")
        .where("razorpaySubscriptionId", "==", subscription_id)
        .limit(1)
        .stream()
    )
    return docs[0].to_dict() if docs else None


def get_user_plan(user_id: str) -> str:
    """
    Return the user's current plan ('free' or 'pro').
    Defaults to 'free' if no user doc exists — safe for legacy users pre-Phase 2.
    """
    db = get_db()
    doc = db.collection("users").document(user_id).get()
    if not doc.exists:
        return "free"
    return doc.to_dict().get("plan", "free")


def get_user_job_count_this_month(user_id: str) -> int:
    """
    Count jobs created by this user in the current calendar month (UTC).
    Used in upload.py to enforce monthly video limits per plan.
    """
    db = get_db()
    now = datetime.now(timezone.utc)
    start_of_month = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
    try:
        docs = list(
            db.collection("jobs")
            .where("userId", "==", user_id)
            .where("createdAt", ">=", start_of_month)
            .stream()
        )
        return len(docs)
    except Exception as e:
        logger.error(f"[{user_id}] get_user_job_count_this_month failed: {e}")
        return 0   # fail open — don't block upload on quota read failure


def get_quota_status(user_id: str) -> dict:
    """
    Return a single dict with everything the frontend needs to render quota UI:
      - plan:          'free' or 'pro'
      - jobsThisMonth: count of jobs created this calendar month (UTC)
      - monthlyLimit:  the plan's job limit for this month
      - resetDate:     ISO-8601 UTC datetime string for the 1st of next month

    Called by GET /quota. Combines get_user_plan() and
    get_user_job_count_this_month() in a single service call.

    Returns a safe default (free plan, 0 used) on any Firestore error.
    """
    db = get_db()

    # Read plan from users doc
    try:
        user_doc = db.collection("users").document(user_id).get()
        plan = user_doc.to_dict().get("plan", "free") if user_doc.exists else "free"
    except Exception as e:
        logger.error(f"[{user_id}] get_quota_status: users read failed: {e}")
        plan = "free"

    # Read this month's job count
    jobs_this_month = get_user_job_count_this_month(user_id)

    # Resolve limit from env vars (same source as upload.py)
    free_limit = int(os.getenv("FREE_PLAN_MONTHLY_LIMIT", "5"))
    pro_limit = int(os.getenv("PRO_PLAN_MONTHLY_LIMIT", "50"))
    plan_limits = {"free": free_limit, "pro": pro_limit}
    monthly_limit = plan_limits.get(plan, free_limit)

    # Compute reset date (1st of next month, UTC)
    now_utc = datetime.now(timezone.utc)
    if now_utc.month == 12:
        reset_dt = now_utc.replace(year=now_utc.year + 1, month=1, day=1,
                                   hour=0, minute=0, second=0, microsecond=0)
    else:
        reset_dt = now_utc.replace(month=now_utc.month + 1, day=1,
                                   hour=0, minute=0, second=0, microsecond=0)

    return {
        "plan": plan,
        "jobsThisMonth": jobs_this_month,
        "monthlyLimit": monthly_limit,
        "resetDate": reset_dt.isoformat(),
    }


# ---------------------------------------------------------------------------
# A3 — Admin helpers
# ---------------------------------------------------------------------------

def get_admin_stats() -> dict:
    """
    Aggregate stats across ALL jobs in the collection.
    Called only by the admin route — no userId filter.
    Returns counts by status, total cost, average processing time,
    and per-user breakdown (top 20 users by job count).
    """
    db = get_db()
    all_jobs = list(db.collection("jobs").stream())

    total = len(all_jobs)
    by_status = {}
    total_cost = 0.0
    total_processing_time = 0
    processing_time_count = 0
    user_counts = {}

    for doc in all_jobs:
        data = doc.to_dict()
        status = data.get("status", "unknown")
        by_status[status] = by_status.get(status, 0) + 1

        cost = data.get("totalEstimatedCostUsd", 0.0) or 0.0
        total_cost += cost

        pt = data.get("processingTime")
        if pt:
            total_processing_time += pt
            processing_time_count += 1

        uid = data.get("userId", "anonymous")
        email = data.get("userEmail", uid)
        if uid not in user_counts:
            user_counts[uid] = {"email": email, "jobCount": 0, "totalCost": 0.0}
        user_counts[uid]["jobCount"] += 1
        user_counts[uid]["totalCost"] = round(user_counts[uid]["totalCost"] + cost, 4)

    avg_processing_time = (
        round(total_processing_time / processing_time_count, 1)
        if processing_time_count > 0 else 0
    )

    top_users = sorted(
        [{"userId": k, **v} for k, v in user_counts.items()],
        key=lambda x: x["jobCount"],
        reverse=True,
    )[:20]

    return {
        "totalJobs": total,
        "byStatus": by_status,
        "totalEstimatedCostUsd": round(total_cost, 4),
        "avgProcessingTimeSeconds": avg_processing_time,
        "topUsers": top_users,
    }


def list_all_jobs(limit: int = 50) -> list:
    """
    List the most recent jobs across ALL users.
    Used by the admin jobs table. Returns newest first.
    No userId filter — admin sees everything.
    """
    db = get_db()
    try:
        docs = list(
            db.collection("jobs")
            .order_by("createdAt", direction=firestore.Query.DESCENDING)
            .limit(limit)
            .stream()
        )
        jobs = []
        for doc in docs:
            data = doc.to_dict()
            jobs.append({
                "jobId": data.get("jobId"),
                "filename": data.get("filename"),
                "status": data.get("status"),
                "userId": data.get("userId", "anonymous"),
                "userEmail": data.get("userEmail", ""),
                "processingTime": data.get("processingTime"),
                "totalEstimatedCostUsd": data.get("totalEstimatedCostUsd"),
                "sttEstimatedCostUsd": data.get("sttEstimatedCostUsd"),
                "viEstimatedCostUsd": data.get("viEstimatedCostUsd"),
                "geminiEstimatedCostUsd": data.get("geminiEstimatedCostUsd"),
                "createdAt": data.get("createdAt").isoformat() if data.get("createdAt") else None,
                "errorMessage": data.get("errorMessage"),
            })
        return jobs
    except Exception as e:
        logger.error(f"list_all_jobs failed: {e}")
        return []


# ---------------------------------------------------------------------------
# QA — Vector search helpers
# ---------------------------------------------------------------------------

def get_transcript_chunk_count(job_id: str) -> int:
    """
    Return the number of transcript chunks for a job.

    Reads the transcriptChunkCount field from the results/{jobId} document.
    Returns 0 if the document doesn't exist or the field is missing.

    Args:
        job_id: The job identifier.

    Returns:
        Integer count of transcript chunks (0 if unavailable).
    """
    db = get_db()
    doc = db.collection("results").document(job_id).get()
    if not doc.exists:
        return 0
    return doc.to_dict().get("transcriptChunkCount", 0)


def search_transcript_chunks(job_id: str, query_vector: list, top_k: int = 4) -> list:
    """
    Perform vector similarity search over transcript chunks.

    Uses Firestore find_nearest() with COSINE distance to find the top-K
    most semantically similar transcript chunks to the query embedding.

    Args:
        job_id:       The job identifier.
        query_vector: 768-dimensional embedding vector for the query.
        top_k:        Number of nearest chunks to return (default 4).

    Returns:
        List of dicts with keys: chunkIndex, startTime, endTime, text.
        Text is assembled by joining the words array from each chunk.
    """
    db = get_db()
    collection = (
        db.collection("results")
        .document(job_id)
        .collection("transcript_chunks")
    )

    results = collection.find_nearest(
        vector_field="embedding",
        query_vector=Vector(query_vector),
        distance_measure=DistanceMeasure.COSINE,
        limit=top_k,
    )

    chunks = []
    for doc in results.stream():
        data = doc.to_dict()
        words = data.get("words", [])
        text = " ".join(w["word"] for w in words)
        start_time = words[0]["startTime"] if words else 0.0
        end_time = words[-1]["endTime"] if words else 0.0
        chunks.append({
            "chunkIndex": data.get("chunkIndex", 0),
            "startTime": start_time,
            "endTime": end_time,
            "text": text,
        })

    return chunks
