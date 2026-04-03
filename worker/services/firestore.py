import os
from google.cloud import firestore
from datetime import datetime, timezone
from typing import List



def get_db() -> firestore.Client:
    project_id = os.getenv("GCP_PROJECT_ID")  # read at call time
    return firestore.Client(project=project_id)  # ADC


def create_job(job_id: str, filename: str, gcs_path: str) -> dict:
    db = get_db()
    now = datetime.now(timezone.utc)

    job_data = {
        "jobId": job_id,
        "status": "pending",
        "filename": filename,
        "gcsPath": gcs_path,
        "videoUrl": "",
        "uploadProgress": 0,
        "progress": 0,
        "createdAt": now,
        "updatedAt": now,
        "processingStartedAt": None,    # ← set by worker when it starts
        "processingCompletedAt": None,  # ← set by worker when done
        "processingTime": 0,            # ← seconds, computed by worker
        "errorMessage": "",
    }

    db.collection("jobs").document(job_id).set(job_data)
    return job_data


def get_job(job_id: str) -> dict | None:
    """
    Fetch a job document by ID. Returns None if not found.
    """
    db = get_db()
    doc = db.collection("jobs").document(job_id).get()

    if not doc.exists:
        return None

    return doc.to_dict()


def update_job_status(job_id: str, status: str, progress: int = 0, error: str = "") -> None:
    """
    Update just the status, progress, and updatedAt fields of a job.
    Used by the worker in Week 3 — wiring it here now for completeness.
    """
    db = get_db()
    update_data = {
        "status": status,
        "progress": progress,
        "updatedAt": datetime.now(timezone.utc)
    }

    if error:
        update_data["errorMessage"] = error

    db.collection("jobs").document(job_id).update(update_data)



def update_upload_progress(job_id: str, upload_progress: int) -> None:
    """
    Update the uploadProgress field of a job document.

    Called by the progress_callback during chunked GCS upload.
    Kept as a lightweight update — only touches two fields.

    Args:
        job_id: The job to update.
        upload_progress: Integer 0–100 representing GCS upload completion.
    """
    from datetime import datetime, timezone
    db = get_db()
    db.collection("jobs").document(job_id).update({
        "uploadProgress": upload_progress,
        "updatedAt": datetime.now(timezone.utc)
    })



def write_video_url(job_id: str, video_url: str) -> None:
    """
    Write the signed GCS video URL to the job document.

    Called immediately after GCS upload completes.
    The frontend reads this from GET /status/{jobId} to feed
    the Video.js player in Week 6.

    Args:
        job_id: The job to update.
        video_url: The signed HTTPS URL for the uploaded video.
    """
    
    db = get_db()
    db.collection("jobs").document(job_id).update({
        "videoUrl": video_url,
        "updatedAt": datetime.now(timezone.utc),
    })



def mark_processing_started(job_id: str) -> None:
    """
    Mark a job as started processing.
    Called by the worker at the beginning of the AI pipeline.

    Sets status → "processing", progress → 25,
    and records processingStartedAt timestamp.
    """
    from datetime import datetime, timezone
    db = get_db()
    now = datetime.now(timezone.utc)
    db.collection("jobs").document(job_id).update({
        "status": "processing",
        "progress": 25,
        "processingStartedAt": now,
        "updatedAt": now,
    })


def mark_processing_completed(job_id: str, processing_time_seconds: int) -> None:
    """
    Mark a job as completed.
    Called by the worker after all AI pipelines finish and results are written.

    Sets status → "completed", progress → 100,
    and records processingCompletedAt + processingTime.
    """
    from datetime import datetime, timezone
    db = get_db()
    now = datetime.now(timezone.utc)
    db.collection("jobs").document(job_id).update({
        "status": "completed",
        "progress": 100,
        "processingCompletedAt": now,
        "processingTime": processing_time_seconds,
        "updatedAt": now,
    })


def mark_processing_failed(job_id: str, error_message: str) -> None:
    """
    Mark a job as failed.
    Called by the worker if any AI pipeline raises an unrecoverable error.

    Sets status → "failed" and records the error message for debugging.
    """
    from datetime import datetime, timezone
    db = get_db()
    now = datetime.now(timezone.utc)
    db.collection("jobs").document(job_id).update({
        "status": "failed",
        "errorMessage": error_message,
        "updatedAt": now,
    })






def list_recent_jobs(limit: int = 20) -> List[dict]:
    """
    Fetch the most recently created jobs, newest first.

    Used by the frontend history page (Week 5) and for admin debugging.
    Requires a Firestore composite index on (createdAt DESC) — Firestore
    will log an index creation URL the first time this query runs if
    the index doesn't exist yet.

    Args:
        limit: Maximum number of jobs to return (default 20, max 100).

    Returns:
        List of job document dicts ordered by createdAt descending.
    """
    db = get_db()
    limit = min(limit, 100)   # Hard cap to prevent runaway reads

    docs = (
        db.collection("jobs")
        .order_by("createdAt", direction=firestore.Query.DESCENDING)
        .limit(limit)
        .stream()
    )

    return [doc.to_dict() for doc in docs]