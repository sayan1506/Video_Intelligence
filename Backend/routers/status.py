import logging
from fastapi import APIRouter, HTTPException, Depends
from google.api_core.exceptions import GoogleAPICallError
from models.schemas import StatusResponse, progress_to_stage
from services import firestore
from middleware.auth import get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/status/{job_id}", response_model=StatusResponse)
async def get_status(job_id: str, current_user: dict = Depends(get_current_user)):
    try:
        job = firestore.get_job(job_id)
    except (GoogleAPICallError, Exception) as e:
        logger.error(f"[{job_id}] Firestore read failed: {e}")
        raise HTTPException(status_code=503, detail="Database service unavailable.")

    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found.")

    # Ownership check — return 404 to avoid leaking job existence
    job_owner = job.get("userId", "")
    if job_owner and job_owner != current_user["uid"]:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found.")

    progress = job.get("progress", 0)
    status = job["status"]

    return StatusResponse(
        jobId=job["jobId"],
        status=status,
        progress=progress,
        stage=progress_to_stage(progress, status),   # ← derive from progress + status
        uploadProgress=job.get("uploadProgress", 0),
        videoUrl=job.get("videoUrl"),
        createdAt=job.get("createdAt"),
        updatedAt=job.get("updatedAt"),
    )