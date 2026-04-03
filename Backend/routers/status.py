import logging
from fastapi import APIRouter, HTTPException
from google.api_core.exceptions import GoogleAPICallError
from models.schemas import StatusResponse
from services import firestore

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/status/{job_id}", response_model=StatusResponse)
async def get_status(job_id: str):
    try:
        job = firestore.get_job(job_id)
    except (GoogleAPICallError, Exception) as e:
        logger.error(f"[{job_id}] Firestore read failed: {e}")
        raise HTTPException(status_code=503, detail="Database service unavailable.")

    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found.")

    return StatusResponse(
        jobId=job["jobId"],
        status=job["status"],
        progress=job.get("progress", 0),
        uploadProgress=job.get("uploadProgress", 0),
        videoUrl=job.get("videoUrl"),   
        createdAt=job.get("createdAt"),
        updatedAt=job.get("updatedAt"),
    )