import json
import logging
import sys
import os
from dotenv import load_dotenv

load_dotenv()

from google.cloud import pubsub_v1
from pydantic import ValidationError

# Worker shares the JobMessage schema with the backend.
# In a real monorepo you'd share a common package.
# For now, copy models/schemas.py into worker/ or add a sys.path adjustment:
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..', 'backend"))
from models.schemas import JobMessage

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

PROJECT_ID = os.getenv("GCP_PROJECT_ID")
SUBSCRIPTION_ID = os.getenv("PUBSUB_SUBSCRIPTION", "video-processing-sub")


def deserialise_message(message: pubsub_v1.types.PubsubMessage) -> JobMessage | None:
    """
    Deserialise a raw Pub/Sub message into a validated JobMessage.

    Returns None if deserialisation fails — caller should nack the message
    so it gets redelivered (or moves to dead-letter queue in V2).
    """
    try:
        payload = json.loads(message.data.decode("utf-8"))
        job_message = JobMessage(**payload)
        return job_message
    except (json.JSONDecodeError, ValidationError) as e:
        logger.error(f"Failed to deserialise Pub/Sub message: {e}")
        logger.error(f"Raw message data: {message.data}")
        return None


def process_message(message: pubsub_v1.types.PubsubMessage) -> None:
    """
    Pub/Sub message callback — called for each received message.
    Week 3 will replace the print statement with real AI pipeline calls.
    """
    job_message = deserialise_message(message)

    if job_message is None:
        # Malformed message — ack it so it doesn't loop forever
        logger.error("Acking malformed message to prevent infinite redelivery")
        message.ack()
        return

    logger.info(
        f"[{job_message.jobId}] Message received — "
        f"file: {job_message.filename}, "
        f"size: {job_message.fileSizeMb}MB, "
        f"gcsUri: {job_message.gcsUri}"
    )

    # TODO (Week 3): Call orchestrator.run(job_message) here
    # For now just ack to clear the subscription
    message.ack()
    logger.info(f"[{job_message.jobId}] Message acked (worker stub)")


def main():
    subscriber = pubsub_v1.SubscriberClient()
    subscription_path = subscriber.subscription_path(PROJECT_ID, SUBSCRIPTION_ID)

    logger.info(f"Worker listening on {subscription_path}...")

    streaming_pull = subscriber.subscribe(subscription_path, callback=process_message)

    try:
        streaming_pull.result()   # Blocks indefinitely
    except KeyboardInterrupt:
        streaming_pull.cancel()
        logger.info("Worker stopped by user")


if __name__ == "__main__":
    main()