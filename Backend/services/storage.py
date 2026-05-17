import os
import logging
from google.cloud import storage
from fastapi import UploadFile
import datetime
import google.auth
import google.auth.transport.requests
from google.auth import impersonated_credentials

SERVICE_ACCOUNT_EMAIL = os.getenv("GCP_SERVICE_ACCOUNT_EMAIL")

logger = logging.getLogger(__name__)

BUCKET_NAME = os.getenv("GCP_BUCKET_NAME")

if not BUCKET_NAME:
    raise RuntimeError("GCP_BUCKET_NAME environment variable is not set")

# Chunk size for streaming uploads — 8MB balances memory usage vs GCS API calls.
# GCS requires chunks to be multiples of 256KB for resumable uploads.
# 8MB = 8 * 1024 * 1024 = 8388608 bytes
CHUNK_SIZE = 8 * 1024 * 1024




def get_storage_client() -> storage.Client:
    return storage.Client()  # ADC — no credentials arg


def build_gcs_path(job_id: str, filename: str) -> str:
    """Consistent GCS path format used across backend and worker."""
    return f"raw-videos/{job_id}/{filename}"


def initiate_resumable_upload(
    job_id: str,
    filename: str,
    content_type: str,
) -> str:
    """
    Initiate a GCS resumable upload session and return the upload URI.

    The URI is returned directly to the browser. The browser then PUTs
    chunks to storage.googleapis.com using this URI — the API never
    touches the file bytes.

    Uses ADC (no impersonation) — the service account has Storage Object
    Admin on the bucket, which is sufficient to create resumable uploads.

    Args:
        job_id:       Used to build the GCS path.
        filename:     Original filename — preserved in the GCS object name.
        content_type: MIME type declared by the client (e.g. "video/mp4").

    Returns:
        Resumable upload URI (https://storage.googleapis.com/upload/storage/v1/b/...).
        The browser PUTs chunks to this URI with Content-Range headers.
    """
    client = get_storage_client()
    bucket = client.bucket(BUCKET_NAME)
    gcs_path = build_gcs_path(job_id, filename)
    blob = bucket.blob(gcs_path)

    resumable_url = blob.create_resumable_upload_session(
        content_type=content_type,
    )

    logger.info(f"[{job_id}] Resumable upload session initiated → {gcs_path}")
    return resumable_url




async def upload_to_gcs(
    file: UploadFile,
    job_id: str,
    progress_callback=None
) -> str:
    """
    Stream an uploaded file to GCS in 8MB chunks.

    Args:
        file: FastAPI UploadFile object.
        job_id: Unique job identifier — used as the GCS folder name.
        progress_callback: Optional async callable(percent: int) called after
                           each chunk. Used to update Firestore upload progress.

    Returns:
        The GCS object path (not the full gs:// URI).
    """
    client = get_storage_client()
    bucket = client.bucket(BUCKET_NAME)
    destination_path = build_gcs_path(job_id, file.filename)
    blob = bucket.blob(destination_path)

    # Get total file size for progress calculation.
    # file.size is set by FastAPI from Content-Length if present.
    total_size = file.size or 0

    logger.info(f"[{job_id}] Starting chunked GCS upload → {destination_path}")

    bytes_uploaded = 0

    # blob.open("wb") initiates a GCS resumable upload session.
    # Resumable uploads survive transient network failures automatically.
    with blob.open("wb", chunk_size=CHUNK_SIZE) as gcs_stream:
        while True:
            chunk = await file.read(CHUNK_SIZE)
            if not chunk:
                break

            gcs_stream.write(chunk)
            bytes_uploaded += len(chunk)

            if progress_callback and total_size > 0:
                percent = min(int((bytes_uploaded / total_size) * 100), 100)
                await progress_callback(percent)

    logger.info(f"[{job_id}] GCS upload complete — {bytes_uploaded} bytes")
    return destination_path


def get_signed_url(gcs_path: str, expiration_minutes: int = 120) -> str:
    source_credentials, project = google.auth.default()
    source_credentials.refresh(google.auth.transport.requests.Request())

    target_credentials = impersonated_credentials.Credentials(
        source_credentials=source_credentials,
        target_principal=SERVICE_ACCOUNT_EMAIL,
        target_scopes=["https://www.googleapis.com/auth/cloud-platform"],
        lifetime=300,
    )

    client = get_storage_client()
    bucket = client.bucket(BUCKET_NAME)
    blob = bucket.blob(gcs_path)

    url = blob.generate_signed_url(
        expiration=datetime.timedelta(minutes=expiration_minutes),
        method="GET",
        version="v4",
        credentials=target_credentials,
    )
    return url



def delete_gcs_object(gcs_path: str) -> None:
    """Delete a GCS object. Used for cleanup on failed jobs."""
    client = get_storage_client()
    bucket = client.bucket(BUCKET_NAME)
    blob = bucket.blob(gcs_path)
    blob.delete()
    logger.info(f"Deleted GCS object: {gcs_path}")



