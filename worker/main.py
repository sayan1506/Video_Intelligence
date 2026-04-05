import asyncio
import json
import logging
import os
import sys
from concurrent.futures import TimeoutError
from dotenv import load_dotenv

load_dotenv()

from google.cloud import pubsub_v1
from google.api_core.exceptions import GoogleAPICallError
from pydantic import ValidationError

from models.schemas import JobMessage
from pipeline.orchestrator import run_pipeline
from services import firestore

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("worker")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

PROJECT_ID = os.getenv("GCP_PROJECT_ID")
SUBSCRIPTION_ID = os.getenv("PUBSUB_SUBSCRIPTION", "video-processing-sub")

if not PROJECT_ID:
    logger.error("GCP_PROJECT_ID env var not set — exiting")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Message deserialisation
# ---------------------------------------------------------------------------

def deserialise_message(message: pubsub_v1.types.PubsubMessage) -> JobMessage | None:
    """
    Deserialise and validate a raw Pub/Sub message into a JobMessage.

    Returns None on any deserialisation failure.
    Caller is responsible for deciding whether to ack or nack.
    """
    try:
        payload = json.loads(message.data.decode("utf-8"))
        job_message = JobMessage(**payload)
        return job_message
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode failed: {e} | raw data: {message.data[:200]}")
        return None
    except ValidationError as e:
        logger.error(f"JobMessage validation failed: {e}")
        logger.error(f"Payload keys received: {list(json.loads(message.data).keys())}")
        return None


# ---------------------------------------------------------------------------
# Message processing
# ---------------------------------------------------------------------------

def process_message(message: pubsub_v1.types.PubsubMessage) -> None:
    """
    Pub/Sub streaming pull callback — called once per received message.
    Runs the full AI pipeline synchronously (asyncio.run wraps the async orchestrator).
    """
    job_id = message.attributes.get("jobId", "unknown")
    logger.info(f"[{job_id}] Message received")

    # Deserialise
    job_message = deserialise_message(message)
    if job_message is None:
        logger.error(f"[{job_id}] Malformed message — acking to prevent redelivery loop")
        message.ack()
        return

    logger.info(
        f"[{job_id}] JobMessage valid — "
        f"file: {job_message.filename}, "
        f"uri: {job_message.gcsUri}"
    )

    # Mark processing started in Firestore
    try:
        firestore.mark_processing_started(job_message.jobId)
    except Exception as e:
        logger.error(f"[{job_id}] Firestore mark_processing_started failed: {e} — nacking")
        message.nack()
        return

    # Run the full AI pipeline
    try:
        success = asyncio.run(run_pipeline(job_message))
    except Exception as e:
        logger.error(f"[{job_id}] Orchestrator raised uncaught exception: {e}")
        try:
            firestore.mark_processing_failed(job_message.jobId, str(e))
        except Exception:
            pass
        # Ack anyway — an uncaught exception won't fix itself on redelivery
        message.ack()
        return

    if success:
        logger.info(f"[{job_id}] Pipeline succeeded — acking message")
    else:
        logger.warning(f"[{job_id}] Pipeline returned False (partial/full failure) — acking message")

    # Always ack — failures are handled inside the orchestrator via Firestore status updates
    message.ack()


# ---------------------------------------------------------------------------
# Subscriber entry point
# ---------------------------------------------------------------------------

def main():
    subscriber = pubsub_v1.SubscriberClient()
    subscription_path = subscriber.subscription_path(PROJECT_ID, SUBSCRIPTION_ID)

    logger.info(f"Worker starting — subscribing to: {subscription_path}")
    logger.info(f"Project: {PROJECT_ID}")
    logger.info(f"Subscription: {SUBSCRIPTION_ID}")

    flow_control = pubsub_v1.types.FlowControl(max_messages=1)

    streaming_pull = subscriber.subscribe(
        subscription_path,
        callback=process_message,
        flow_control=flow_control,
    )

    logger.info("Worker is listening... (Ctrl+C to stop)")

    try:
        streaming_pull.result()
    except TimeoutError:
        streaming_pull.cancel()
        streaming_pull.result()
        logger.info("Worker timed out")
    except KeyboardInterrupt:
        streaming_pull.cancel()
        logger.info("Worker stopped by user")
    except Exception as e:
        streaming_pull.cancel()
        logger.error(f"Worker crashed: {e}")
        raise


if __name__ == "__main__":
    main()