import os
import uuid
import logging
from fastapi import APIRouter, UploadFile, File, HTTPException
from google.api_core.exceptions import GoogleAPICallError, ServiceUnavailable
from models.schemas import UploadResponse
from services import storage, firestore, pubsub
from utils.validators import (
    check_magic_bytes,
    validate_file_extension,
    MAGIC_BYTES_READ_LENGTH,
)

router = APIRouter()
logger = logging.getLogger(__name__)

MAX_SIZE_MB = int(os.getenv("MAX_VIDEO_SIZE_MB", 500))
ALLOWED_TYPES = os.getenv(
    "ALLOWED_VIDEO_TYPES",
    "video/mp4,video/quicktime,video/avi,video/x-msvideo"
).split(",")


@router.post("/upload", response_model=UploadResponse)
async def upload_video(file: UploadFile = File(...)):

    # --- Validation: MIME type ---
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file.content_type}. "
                   f"Allowed: {', '.join(ALLOWED_TYPES)}"
        )

    # --- Validation: file extension ---
    if not validate_file_extension(file.filename or ""):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file extension for: {file.filename}. "
                   f"Allowed extensions: .mp4, .mov, .avi"
        )

    # --- Validation: magic bytes ---
    # Read just the header — don't buffer the full file
    file_header = await file.read(MAGIC_BYTES_READ_LENGTH)
    if not check_magic_bytes(file_header, file.content_type):
        raise HTTPException(
            status_code=400,
            detail=f"File content does not match declared type {file.content_type}. "
                   f"File may be corrupted or misidentified."
        )
    # Reset stream — next read will start from byte 0 again
    await file.seek(0)

    # --- Validation: file size ---
    if file.size and (file.size / (1024 * 1024)) > MAX_SIZE_MB:
        raise HTTPException(
            status_code=400,
            detail=f"File too large: {file.size / (1024*1024):.1f}MB. "
                   f"Maximum: {MAX_SIZE_MB}MB"
        )

    job_id = str(uuid.uuid4())
    logger.info(f"[{job_id}] Upload started — file: {file.filename}, "
                f"size: {file.size or 'unknown'} bytes")

    # --- Step 1: Create Firestore job document (status: pending) ---
    try:
        # Create job first so /status is queryable immediately
        firestore.create_job(
            job_id=job_id,
            filename=file.filename,
            gcs_path=storage.build_gcs_path(job_id, file.filename)
        )
        logger.info(f"[{job_id}] Firestore job created")
    except (GoogleAPICallError, ServiceUnavailable) as e:
        logger.error(f"[{job_id}] Firestore create_job failed: {e}")
        raise HTTPException(status_code=503, detail="Database unavailable. Try again shortly.")

    # --- Step 2: Stream file to GCS with progress callback ---
    async def on_progress(percent: int):
        """Update Firestore uploadProgress after each chunk."""
        try:
            firestore.update_upload_progress(job_id, percent)
        except Exception as e:
            # Don't fail the upload if a progress update fails
            logger.warning(f"[{job_id}] Progress update failed at {percent}%: {e}")

    try:
        gcs_path = await storage.upload_to_gcs(file, job_id, progress_callback=on_progress)
        logger.info(f"[{job_id}] GCS upload complete: {gcs_path}")
    except (GoogleAPICallError, ServiceUnavailable) as e:
        logger.error(f"[{job_id}] GCS upload failed: {e}")
        firestore.update_job_status(job_id, "failed", error=f"GCS upload failed: {e}")
        raise HTTPException(status_code=503, detail="Storage unavailable. Try again shortly.")
    except Exception as e:
        logger.error(f"[{job_id}] GCS upload unexpected error: {e}")
        firestore.update_job_status(job_id, "failed", error=str(e))
        raise HTTPException(status_code=500, detail="Upload failed unexpectedly.")
    
    # --- Step 2b: Generate signed URL and write to Firestore ---
    try:
        video_url = storage.get_signed_url(gcs_path, expiration_minutes=120)
        firestore.write_video_url(job_id, video_url)
        logger.info(f"[{job_id}] Signed URL written to Firestore")
    except Exception as e:
        # Non-fatal — video URL can be regenerated later
        # Don't block the upload response over a URL generation failure
        logger.warning(f"[{job_id}] Signed URL generation failed: {e}")


    # --- Step 3: Mark upload complete, update GCS path in Firestore ---
    try:
        firestore.update_job_status(job_id, "pending", progress=25)
        firestore.update_upload_progress(job_id, 100)
    except Exception as e:
        logger.warning(f"[{job_id}] Post-upload Firestore update failed: {e}")

    # --- Step 4: Publish Pub/Sub message to trigger the worker ---
    try:
        pubsub.publish_job_message(
            job_id=job_id,
            gcs_path=gcs_path,
            filename=file.filename,
            file_size_bytes=file.size or 0,   
            content_type=file.content_type,
        )
        logger.info(f"[{job_id}] Pub/Sub message published")
    except (GoogleAPICallError, ServiceUnavailable) as e:
        logger.error(f"[{job_id}] Pub/Sub publish failed: {e}")
        logger.warning(f"[{job_id}] File uploaded + job created but worker not notified")
        # Don't fail the request — job is recoverable
    except Exception as e:
        logger.error(f"[{job_id}] Pub/Sub unexpected error: {e}")

    return UploadResponse(
        jobId=job_id,
        status="pending",
        message="Video uploaded successfully"
    )