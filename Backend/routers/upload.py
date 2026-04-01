from fastapi import APIRouter, UploadFile, File
from models.schemas import UploadResponse
import uuid

router = APIRouter()

@router.post("/upload", response_model=UploadResponse)
async def upload_video(file: UploadFile = File(...)):

    job_id = str(uuid.uuid4())

    return UploadResponse(job_id=job_id, status="pending", message="Video uploaded successfully")