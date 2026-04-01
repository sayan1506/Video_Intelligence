import os
import uuid
from fastapi import APIRouter, UploadFile, File, HTTPException
from models.schemas import UploadResponse
from services import storage, firestore, pubsub

router = APIRouter()

MAX_SIZE_MB = int(os.getenv("MAX_VIDEO_SIZE_MB", 500))
ALLOWED_TYPES = os.getenv(
    "ALLOWED_VIDEO_TYPES",
    "video/mp4,video/quicktime,video/avi"
).split(",")


@router.post("/upload", response_model=UploadResponse)
async def upload_video(file: UploadFile = File(...)):

    # Validate file type
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file.content_type}. Allowed: {ALLOWED_TYPES}"
        )

    # Validate file size (read size without consuming the stream)
    contents = await file.read()
    size_mb = len(contents) / (1024 * 1024)
    if size_mb > MAX_SIZE_MB:
        raise HTTPException(
            status_code=400,
            detail=f"File too large: {size_mb:.1f}MB. Maximum allowed: {MAX_SIZE_MB}MB"
        )

    # Reset stream position after size check
    await file.seek(0)

    job_id = str(uuid.uuid4())

    try:
        # 1. Stream file to GCS
        gcs_path = await storage.upload_to_gcs(file, job_id)

        # 2. Create Firestore job document
        firestore.create_job(
            job_id=job_id,
            filename=file.filename,
            gcs_path=gcs_path
        )

        # 3. Publish Pub/Sub message to trigger the worker
        pubsub.publish_job_message(
            job_id=job_id,
            gcs_path=gcs_path,
            filename=file.filename
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Upload pipeline failed: {str(e)}"
        )

    return UploadResponse(
        job_id=job_id,     # ← match the field name
        status="pending",
        message="Video uploaded successfully"
    )