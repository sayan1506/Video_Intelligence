from fastapi import APIRouter
from models.schemas import StatusResponse


router = APIRouter()

@router.get("/status/{job_id}", response_model=StatusResponse)
async def get_status(job_id: str):

    return StatusResponse(job_id=job_id, status="pending", progress=0)