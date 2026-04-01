from fastapi import APIRouter
from models.schemas import ResultResponse

router = APIRouter()

@router.get("/result/{job_id}", response_model=ResultResponse)

async def get_result(job_id: str):

    return ResultResponse(
        jobId=job_id,
        status="completed",
        summary="This is a stub summary. Real data arrives in Week 3.",
        sentiment="positive",
        processingTime=0
    )