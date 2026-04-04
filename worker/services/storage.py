import os
import logging
from google.cloud import storage
from fastapi import UploadFile
import datetime
import google.auth
import google.auth.transport.requests
from google.auth import impersonated_credentials
import json
import asyncio

logger = logging.getLogger(__name__)

BUCKET_NAME = os.getenv("GCP_BUCKET_NAME", "video-intelligence-raw")

# Chunk size for streaming uploads — 8MB balances memory usage vs GCS API calls.
# GCS requires chunks to be multiples of 256KB for resumable uploads.
# 8MB = 8 * 1024 * 1024 = 8388608 bytes
CHUNK_SIZE = 8 * 1024 * 1024


def get_storage_client() -> storage.Client:
    return storage.Client()  # ADC — no credentials arg


def build_gcs_path(job_id: str, filename: str) -> str:
    """Consistent GCS path format used across backend and worker."""
    return f"raw-videos/{job_id}/{filename}"


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
        target_principal="video-intelligence-sa@video-intelligence-v1.iam.gserviceaccount.com",
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



PROCESSED_PREFIX = "processed"


async def write_processed_json(
    job_id: str,
    filename: str,
    data: dict,
) -> str:
    """
    Write a JSON-serialisable dict to GCS under processed/{jobId}/{filename}.

    Used to persist raw API responses for debugging and reprocessing
    without re-calling expensive AI APIs.

    Args:
        job_id: Job identifier — used as the GCS folder name.
        filename: File name, e.g. "transcript.json", "video_intelligence.json".
        data: Dict to serialise and write.

    Returns:
        GCS object path, e.g. processed/{jobId}/transcript.json
    """
    client = get_storage_client()
    bucket = client.bucket(BUCKET_NAME)

    destination_path = f"{PROCESSED_PREFIX}/{job_id}/{filename}"
    blob = bucket.blob(destination_path)

    # Run the synchronous GCS write in a thread pool to avoid blocking the event loop
    json_bytes = json.dumps(data, indent=2, default=str).encode("utf-8")

    await asyncio.get_event_loop().run_in_executor(
        None,
        lambda: blob.upload_from_string(json_bytes, content_type="application/json"),
    )

    return destination_path