import os
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any

from google.cloud import firestore
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