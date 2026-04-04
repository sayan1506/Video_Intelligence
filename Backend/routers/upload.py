import os
import uuid
import logging
import datetime
from fastapi import APIRouter, UploadFile, File, HTTPException, Header
from typing import Optional
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


# ---------------------------------------------------------------------------
# Step 1 — Client requests a signed upload URL
# ---------------------------------------------------------------------------
@router.post("/upload-url")
async def request_upload_url(
    filename: str,
    content_type: str = "video/mp4",
    file_size_bytes: int = 0,
    # Client sends the first 12 bytes of the file as a hex string for magic bytes check
    x_file_header: Optional[str] = Header(default=None),
):
    """
    Returns a signed GCS PUT URL. The video is never sent through Cloud Run.

    Client must:
    1. Read the first 12 bytes of the file
    2. Send them as hex string in X-File-Header header
    3. PUT the full file to the returned uploadUrl
    4. Call POST /upload-confirm when done
    """

    # --- Validation: MIME type ---
    if content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {content_type}. Allowed: {', '.join(ALLOWED_TYPES)}"
        )

    # --- Validation: file extension ---
    if not validate_file_extension(filename or ""):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file extension for: {filename}. Allowed: .mp4, .mov, .avi"
        )

    # --- Validation: file size (client-declared) ---
    if file_size_bytes and (file_size_bytes / (1024 * 1024)) > MAX_SIZE_MB:
        raise HTTPException(
            status_code=400,
            detail=f"File too large: {file_size_bytes / (1024*1024):.1f}MB. Maximum: {MAX_SIZE_MB}MB"
        )

    # --- Validation: magic bytes (sent by client as hex header) ---
    if x_file_header:
        try:
            file_header = bytes.fromhex(x_file_header)
            if not check_magic_bytes(file_header, content_type):
                raise HTTPException(
                    status_code=400,
                    detail=f"File content does not match declared type {content_type}."
                )
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid X-File-Header format.")

    job_id = str(uuid.uuid4())
    gcs_path = storage.build_gcs_path(job_id, filename)

    logger.info(f"[{job_id}] Upload URL requested — file: {filename}, size: {file_size_bytes} bytes")

    # --- Create Firestore job immediately so /status works ---
    try:
        firestore.create_job(job_id=job_id, filename=filename, gcs_path=gcs_path)
        logger.info(f"[{job_id}] Firestore job created")
    except (GoogleAPICallError, ServiceUnavailable) as e:
        logger.error(f"[{job_id}] Firestore create_job failed: {e}")
        raise HTTPException(status_code=503, detail="Database unavailable. Try again shortly.")

    # --- Generate signed PUT URL (15 min expiry — enough for large uploads) ---
    try:
        upload_url = storage.get_signed_upload_url(
            gcs_path=gcs_path,
            content_type=content_type,
            expiration_minutes=15,
        )
    except Exception as e:
        logger.error(f"[{job_id}] Signed upload URL generation failed: {e}")
        firestore.update_job_status(job_id, "failed", error="Could not generate upload URL")
        raise HTTPException(status_code=500, detail="Could not generate upload URL.")

    return {
        "jobId": job_id,
        "uploadUrl": upload_url,   # Client PUTs video here
        "gcsPath": gcs_path,
    }


# ---------------------------------------------------------------------------
# Step 2 — Client confirms the direct GCS upload completed
# ---------------------------------------------------------------------------
@router.post("/upload-confirm", response_model=UploadResponse)
async def confirm_upload(
    job_id: str,
    gcs_path: str,
    filename: str,
    file_size_bytes: int = 0,
    content_type: str = "video/mp4",
):
    """
    Called after the client's direct PUT to GCS succeeds.
    Generates signed read URL, updates Firestore, triggers worker.
    """
    logger.info(f"[{job_id}] Upload confirmed — triggering pipeline")

    # --- Generate signed read URL for the video player ---
    try:
        video_url = storage.get_signed_url(gcs_path, expiration_minutes=120)
        firestore.write_video_url(job_id, video_url)
        logger.info(f"[{job_id}] Signed read URL written to Firestore")
    except Exception as e:
        logger.warning(f"[{job_id}] Signed URL generation failed (non-fatal): {e}")

    # --- Mark job as pending, ready for worker ---
    try:
        firestore.update_job_status(job_id, "pending", progress=25)
        firestore.update_upload_progress(job_id, 100)
    except Exception as e:
        logger.warning(f"[{job_id}] Post-upload Firestore update failed: {e}")

    # --- Publish Pub/Sub to trigger worker ---
    try:
        pubsub.publish_job_message(
            job_id=job_id,
            gcs_path=gcs_path,
            filename=filename,
            file_size_bytes=file_size_bytes,
            content_type=content_type,
        )
        logger.info(f"[{job_id}] Pub/Sub message published")
    except (GoogleAPICallError, ServiceUnavailable) as e:
        logger.error(f"[{job_id}] Pub/Sub publish failed: {e}")
        # Non-fatal — job is recoverable via dead letter queue
    except Exception as e:
        logger.error(f"[{job_id}] Pub/Sub unexpected error: {e}")

    return UploadResponse(
        jobId=job_id,
        status="pending",
        message="Video uploaded successfully"
    )