import os
from google.cloud import storage
from fastapi import UploadFile


BUCKET_NAME = os.getenv("GCP_BUCKET_NAME", "video-intelligence-raw")


def get_storage_client() -> storage.Client:
    return storage.Client()  # ADC


async def upload_to_gcs(file: UploadFile, job_id: str) -> str:
    """
    Stream an uploaded file directly to GCS.
    Returns the GCS path (not the full URL) — e.g. raw-videos/{jobId}/{filename}
    """
    client = get_storage_client()
    bucket = client.bucket(BUCKET_NAME)

    destination_path = f"raw-videos/{job_id}/{file.filename}"
    blob = bucket.blob(destination_path)

    # Read the file content and upload
    contents = await file.read()
    blob.upload_from_string(
        contents,
        content_type=file.content_type
    )

    return destination_path


def get_video_url(gcs_path: str) -> str:
    """
    Returns a public GCS URL for the given path.
    Note: bucket must allow public read, or use signed URLs in production.
    """
    return f"https://storage.googleapis.com/{BUCKET_NAME}/{gcs_path}"

def get_signed_url(gcs_path: str, expiration_minutes: int = 60) -> str:
    """
    Returns a time-limited signed URL — useful for result responses
    where you don't want to make the bucket fully public.
    """
    import datetime
    client = get_storage_client()
    bucket = client.bucket(BUCKET_NAME)
    blob = bucket.blob(gcs_path)

    url = blob.generate_signed_url(
        expiration=datetime.timedelta(minutes=expiration_minutes),
        method="GET",
        version="v4"
    )
    return url