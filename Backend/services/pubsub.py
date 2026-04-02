import os
import json
import time
import logging
from google.cloud import pubsub_v1
from google.api_core.exceptions import GoogleAPICallError, ServiceUnavailable
from models.schemas import JobMessage
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

PROJECT_ID = os.getenv("GCP_PROJECT_ID")
TOPIC_ID = os.getenv("PUBSUB_TOPIC", "video-processing")
BUCKET_NAME = os.getenv("GCP_BUCKET_NAME", "video-intelligence-raw")

# Retry configuration
MAX_RETRIES = 3
BACKOFF_BASE_SECONDS = 0.5   # Retry delays: 0.5s, 1.0s, 2.0s


def get_publisher() -> pubsub_v1.PublisherClient:
    return pubsub_v1.PublisherClient()  # ADC


def build_job_message(
    job_id: str,
    gcs_path: str,
    filename: str,
    file_size_bytes: int,
    content_type: str,
) -> JobMessage:
    """
    Construct a validated JobMessage from upload parameters.

    Centralising construction here ensures the worker always receives
    a fully-formed message with the gcsUri pre-built.
    """
    return JobMessage(
        jobId=job_id,
        gcsPath=gcs_path,
        gcsBucket=BUCKET_NAME,
        gcsUri=f"gs://{BUCKET_NAME}/{gcs_path}",
        filename=filename,
        fileSizeMb=round(file_size_bytes / (1024 * 1024), 2),
        contentType=content_type,
        uploadedAt=datetime.now(timezone.utc).isoformat(),
        schemaVersion="1",
    )


def publish_job_message(
    job_id: str,
    gcs_path: str,
    filename: str,
    file_size_bytes: int = 0,
    content_type: str = "video/mp4",
) -> str:
    """
    Publish a validated JobMessage to the video-processing Pub/Sub topic.

    Retries up to MAX_RETRIES times with exponential backoff on transient
    GCP errors. Raises on permanent failure after all retries exhausted.

    Args:
        job_id: Unique job identifier.
        gcs_path: GCS object path (without gs:// prefix).
        filename: Original uploaded filename.
        file_size_bytes: File size in bytes for the message payload.
        content_type: MIME type of the uploaded file.

    Returns:
        The published Pub/Sub message ID.

    Raises:
        RuntimeError: If all retries fail.
    """
    publisher = get_publisher()
    topic_path = publisher.topic_path(PROJECT_ID, TOPIC_ID)

    # Build and validate the message using the Pydantic schema
    message = build_job_message(
        job_id=job_id,
        gcs_path=gcs_path,
        filename=filename,
        file_size_bytes=file_size_bytes,
        content_type=content_type,
    )

    # Serialise to JSON bytes
    message_bytes = message.model_dump_json().encode("utf-8")

    # Message attributes — plaintext key-value pairs visible in GCP console
    # without needing to decode the base64 message body
    attributes = {
        "jobId": job_id,
        "schemaVersion": message.schemaVersion,
        "contentType": content_type,
    }

    last_exception = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            future = publisher.publish(
                topic_path,
                data=message_bytes,
                **attributes,   # Pub/Sub accepts attributes as kwargs
            )
            message_id = future.result(timeout=10)
            logger.info(
                f"[{job_id}] Pub/Sub publish OK on attempt {attempt} "
                f"— message ID: {message_id}"
            )
            return message_id

        except (GoogleAPICallError, ServiceUnavailable) as e:
            last_exception = e
            if attempt < MAX_RETRIES:
                backoff = BACKOFF_BASE_SECONDS * (2 ** (attempt - 1))
                logger.warning(
                    f"[{job_id}] Pub/Sub publish attempt {attempt} failed: {e}. "
                    f"Retrying in {backoff}s..."
                )
                time.sleep(backoff)
            else:
                logger.error(
                    f"[{job_id}] Pub/Sub publish failed after {MAX_RETRIES} attempts: {e}"
                )

        except Exception as e:
            # Non-retryable error — fail immediately
            logger.error(f"[{job_id}] Pub/Sub unexpected error (no retry): {e}")
            raise RuntimeError(f"Pub/Sub publish failed: {e}") from e

    raise RuntimeError(
        f"[{job_id}] Pub/Sub publish failed after {MAX_RETRIES} retries. "
        f"Last error: {last_exception}"
    )