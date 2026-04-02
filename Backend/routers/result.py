import logging
from fastapi import APIRouter, HTTPException
from google.api_core.exceptions import GoogleAPICallError
from models.schemas import ResultResponse
from services import firestore

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/result/{job_id}", response_model=ResultResponse)
async def get_result(job_id: str):
    try:
        job = firestore.get_job(job_id)
    except (GoogleAPICallError, Exception) as e:
        logger.error(f"[{job_id}] Firestore read failed: {e}")
        raise HTTPException(status_code=503, detail="Database service unavailable.")

    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found.")

    if job["status"] != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Job {job_id} is not completed yet. Current status: {job['status']}"
        )

    # Results will be populated by the worker in Week 3
    # For now return the job metadata + empty result fields
    return ResultResponse(
        jobId=job["jobId"],
        status=job["status"],
        videoUrl=job.get("videoUrl"),
        processingTime=job.get("processingTime", 0)
    )