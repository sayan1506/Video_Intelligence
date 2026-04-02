import os
from google.cloud import firestore
from datetime import datetime, timezone



def get_db() -> firestore.Client:
    project_id = os.getenv("GCP_PROJECT_ID")  # read at call time
    return firestore.Client(project=project_id)  # ADC


def create_job(job_id: str, filename: str, gcs_path: str) -> dict:
    """
    Create a new job document in the jobs collection with status: pending.
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
        "progress": 0,
        "createdAt": now,
        "updatedAt": now,
        "processingTime": 0,
        "errorMessage": ""
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