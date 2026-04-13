import os
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any

from google.cloud import firestore
from google.api_core.exceptions import FailedPrecondition

logger = logging.getLogger(__name__)

# ── Singleton client ──────────────────────────────────────────────────────────
_db: firestore.Client | None = None


def get_db() -> firestore.Client:
    global _db
    if _db is None:
        project_id = os.getenv("GCP_PROJECT_ID")
        _db = firestore.Client(project=project_id)
    return _db


# ── Progress stage map ────────────────────────────────────────────────────────
# Must match backend/services/firestore.py exactly — both files share the same
# contract. If you add a stage here, add it there too.
PROGRESS_STAGES: Dict[str, int] = {
    "pending":     0,
    "uploading":   10,
    "processing":  25,
    "stt_done":    50,
    "vi_done":     75,
    "gemini_done": 90,
    "completed":   100,
}


def progress_for_stage(stage: str) -> int:
    """Return the canonical progress integer for a named pipeline stage."""
    return PROGRESS_STAGES.get(stage, 0)


# ── Job status helpers ────────────────────────────────────────────────────────

def update_job_status(job_id: str, status: str, progress: int | None = None) -> None:
    """
    Update job status and optionally progress.

    progress defaults to None so callers that only want to update status
    don't accidentally reset progress to 0.
    """
    db = get_db()
    update_data: Dict[str, Any] = {
        "status": status,
        "updatedAt": datetime.now(timezone.utc),
    }
    if progress is not None:
        update_data["progress"] = progress

    db.collection("jobs").document(job_id).update(update_data)
    logger.info(f"[{job_id}] Status → {status}" + (f", progress → {progress}" if progress is not None else ""))


def mark_processing_started(job_id: str) -> None:
    """Mark a job as started — status=processing, progress=25."""
    db = get_db()
    now = datetime.now(timezone.utc)
    db.collection("jobs").document(job_id).update({
        "status": "processing",
        "progress": progress_for_stage("processing"),
        "processingStartedAt": now,
        "updatedAt": now,
    })
    logger.info(f"[{job_id}] Firestore status → processing")


def mark_processing_completed(job_id: str, processing_time_seconds: int) -> None:
    """Mark a job as completed — status=completed, progress=100."""
    db = get_db()
    now = datetime.now(timezone.utc)
    db.collection("jobs").document(job_id).update({
        "status": "completed",
        "progress": progress_for_stage("completed"),
        "processingCompletedAt": now,
        "processingTime": processing_time_seconds,
        "updatedAt": now,
    })
    logger.info(f"[{job_id}] Firestore status → completed ({processing_time_seconds}s)")


def mark_processing_failed(job_id: str, error_message: str) -> None:
    """Mark a job as failed — status=failed with error message."""
    db = get_db()
    db.collection("jobs").document(job_id).update({
        "status": "failed",
        "errorMessage": error_message,
        "updatedAt": datetime.now(timezone.utc),
    })
    logger.warning(f"[{job_id}] Firestore status → failed: {error_message}")


def get_job(job_id: str) -> dict | None:
    """
    Fetch a single job document by ID. Returns the document as a dict,
    or None if it doesn't exist. Used by scratch.py for test verification.
    """
    db = get_db()
    doc = db.collection("jobs").document(job_id).get()
    return doc.to_dict() if doc.exists else None


# ── Result writers (added Week 3, Day 3) ─────────────────────────────────────

def write_results(
    job_id: str,
    transcript: List[Dict[str, Any]],
    scenes: List[Dict[str, Any]],
) -> None:
    """
    Write AI pipeline outputs to results/{jobId} in Firestore.

    Called by the orchestrator after both STT and Video Intelligence complete.
    The backend GET /result endpoint reads from this collection.

    Flattens all unique labels across scenes into a top-level `labels` array
    for easy querying without a collection group query.

    Args:
        job_id:     Used as the document ID in the results collection.
        transcript: List of WordTimestamp dicts from the STT pipeline.
        scenes:     List of Scene dicts from the Video Intelligence pipeline.
    """

    MAX_WORDS = 8000
    if len(transcript) > MAX_WORDS:
        logger.warning(f"[{job_id}] Transcript truncated from {len(transcript)} to {MAX_WORDS} words")
        transcript = transcript[:MAX_WORDS]

    db = get_db()

    all_labels = list({
        label
        for scene in scenes
        for label in scene.get("labels", [])
    })

    doc_data = {
        "jobId": job_id,
        "transcript": transcript,
        "scenes": scenes,
        "labels": all_labels,
        "writtenAt": datetime.now(timezone.utc),
    }

    db.collection("results").document(job_id).set(doc_data)
    logger.info(
        f"[{job_id}] Results written — "
        f"transcript words: {len(transcript)}, "
        f"scenes: {len(scenes)}, "
        f"unique labels: {len(all_labels)}"
    )


def write_summary(
    job_id: str,
    summary_data: Dict[str, Any],
) -> None:
    """
    Write Gemini summary output to summaries/{jobId} in Firestore.

    Called after the Gemini pipeline completes (stub in Week 3, real in Week 4).
    Firestore creates the summaries collection automatically on first write —
    no manual collection setup needed.

    Args:
        job_id:       Used as the document ID in the summaries collection.
        summary_data: Dict with keys: summary, chapters, highlights,
                      sentiment, actionItems.
    """
    db = get_db()

    doc_data = {
        "jobId": job_id,
        "writtenAt": datetime.now(timezone.utc),
        **summary_data,
    }

    db.collection("summaries").document(job_id).set(doc_data)
    logger.info(f"[{job_id}] Summary written to Firestore")






def write_gemini_usage(
    job_id: str,
    input_tokens: int,
    output_tokens: int,
) -> None:
    """
    Write Gemini token usage to the job document for cost tracking.

    Called by generate_summary() after every successful Gemini API call.
    Enables per-job cost visibility in the Firestore console and
    makes it easy to identify unexpectedly expensive jobs.

    Approximate cost (Gemini 1.5 Pro, prompts <= 128K tokens):
      Input:  $3.50 per 1M tokens  →  $0.0000035 per token
      Output: $10.50 per 1M tokens →  $0.0000105 per token

    Args:
        job_id: The job to update.
        input_tokens: Prompt token count from response.usage_metadata.
        output_tokens: Candidates token count from response.usage_metadata.
    """
    from datetime import datetime, timezone
    db = get_db()

    # Estimated cost in USD — informational only, not billed directly
    estimated_cost_usd = round(
        (input_tokens * 0.0000035) + (output_tokens * 0.0000105),
        6
    )

    db.collection("jobs").document(job_id).update({
        "geminiInputTokens": input_tokens,
        "geminiOutputTokens": output_tokens,
        "geminiEstimatedCostUsd": estimated_cost_usd,
        "updatedAt": datetime.now(timezone.utc),
    })