import os
import uuid
import logging
from fastapi import APIRouter, UploadFile, File, HTTPException
from google.api_core.exceptions import GoogleAPICallError, ServiceUnavailable
from models.schemas import UploadResponse
from services import storage, firestore, pubsub

router = APIRouter()
logger = logging.getLogger(__name__)

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
            detail=f"Unsupported file type: {file.content_type}. Allowed: {', '.join(ALLOWED_TYPES)}"
        )

    # Validate file size
    contents = await file.read()
    size_mb = len(contents) / (1024 * 1024)
    if size_mb > MAX_SIZE_MB:
        raise HTTPException(
            status_code=400,
            detail=f"File too large: {size_mb:.1f}MB. Maximum: {MAX_SIZE_MB}MB"
        )
    await file.seek(0)

    job_id = str(uuid.uuid4())

    # Step 1 — GCS upload
    try:
        gcs_path = await storage.upload_to_gcs(file, job_id)
        logger.info(f"[{job_id}] GCS upload OK: {gcs_path}")
    except (GoogleAPICallError, ServiceUnavailable) as e:
        logger.error(f"[{job_id}] GCS upload failed: {e}")
        raise HTTPException(status_code=503, detail="Storage service unavailable. Try again shortly.")
    except Exception as e:
        logger.error(f"[{job_id}] GCS upload unexpected error: {e}")
        raise HTTPException(status_code=500, detail="Upload failed unexpectedly.")

    # Step 2 — Firestore job creation
    try:
        firestore.create_job(job_id=job_id, filename=file.filename, gcs_path=gcs_path)
        logger.info(f"[{job_id}] Firestore job created")
    except (GoogleAPICallError, ServiceUnavailable) as e:
        logger.error(f"[{job_id}] Firestore write failed: {e}")
        raise HTTPException(status_code=503, detail="Database service unavailable. Try again shortly.")
    except Exception as e:
        logger.error(f"[{job_id}] Firestore unexpected error: {e}")
        raise HTTPException(status_code=500, detail="Job creation failed unexpectedly.")

    # Step 3 — Pub/Sub publish
    try:
        pubsub.publish_job_message(job_id=job_id, gcs_path=gcs_path, filename=file.filename)
        logger.info(f"[{job_id}] Pub/Sub message published")
    except (GoogleAPICallError, ServiceUnavailable) as e:
        logger.error(f"[{job_id}] Pub/Sub publish failed: {e}")
        # Job is already in Firestore — don't fail the whole request.
        # Worker can be re-triggered manually if needed.
        logger.warning(f"[{job_id}] File uploaded and job created but worker not notified.")
    except Exception as e:
        logger.error(f"[{job_id}] Pub/Sub unexpected error: {e}")

    return UploadResponse(
        jobId=job_id,
        status="pending",
        message="Video uploaded successfully"
    )