from fastapi import APIRouter, HTTPException
from models.schemas import StatusResponse
from services import firestore

router = APIRouter()


@router.get("/status/{job_id}", response_model=StatusResponse)
async def get_status(job_id: str):
    job = firestore.get_job(job_id)

    if job is None:
        raise HTTPException(
            status_code=404,
            detail=f"Job {job_id} not found"
        )

    return StatusResponse(
        job_id=job["jobId"],
        status=job["status"],
        progress=job.get("progress", 0),
        createdAt=job.get("createdAt"),
        updatedAt=job.get("updatedAt")
    )