import asyncio
import json
import logging
import os
import sys
from concurrent.futures import TimeoutError
from dotenv import load_dotenv

load_dotenv()
import threading
from google.cloud import pubsub_v1
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
    job_id = message.attributes.get("jobId", "unknown")
    logger.info(f"[{job_id}] Message received")

    job_message = deserialise_message(message)
    if job_message is None:
        logger.error(f"[{job_id}] Malformed message — acking")
        message.ack()
        return

    logger.info(
        f"[{job_id}] JobMessage valid — "
        f"file: {job_message.filename}, uri: {job_message.gcsUri}"
    )

    try:
        firestore.mark_processing_started(job_message.jobId)
    except Exception as e:
        logger.error(f"[{job_id}] mark_processing_started failed: {e} — nacking")
        message.nack()
        return

    # --- Start ack deadline heartbeat ---
    stop_heartbeat = threading.Event()
    heartbeat_thread = _start_ack_heartbeat(
        subscriber=_get_subscriber(),
        subscription_path=_get_subscription_path(),
        ack_id=message.ack_id,
        job_id=job_id,
        stop_event=stop_heartbeat,
    )

    # --- Run the full AI pipeline ---
    try:
        success = asyncio.run(run_pipeline(job_message))
    except Exception as e:
        logger.error(f"[{job_id}] Uncaught orchestrator exception: {e}")
        try:
            firestore.mark_processing_failed(job_message.jobId, str(e))
        except Exception:
            pass
        success = False
    finally:
        # Always stop the heartbeat thread before acking/nacking
        stop_heartbeat.set()

    if success:
        logger.info(f"[{job_id}] Pipeline succeeded — acking")
    else:
        logger.warning(f"[{job_id}] Pipeline failed — acking (failure recorded in Firestore)")

    message.ack()




# How often to extend the ack deadline (seconds)
ACK_EXTENSION_INTERVAL = 60

# How much time to add per extension (seconds)
# Must be <= subscription's max ack deadline (600s)
ACK_EXTENSION_SECONDS = 300


def _start_ack_heartbeat(
    subscriber: pubsub_v1.SubscriberClient,
    subscription_path: str,
    ack_id: str,
    job_id: str,
    stop_event: threading.Event,
) -> threading.Thread:
    """
    Start a background thread that periodically extends the Pub/Sub ack deadline.

    Prevents Pub/Sub from redelivering the message while the AI pipeline runs.
    The thread stops when stop_event is set — call stop_event.set() after
    message.ack() or message.nack() to clean up.

    Args:
        subscriber: The Pub/Sub SubscriberClient.
        subscription_path: Full subscription resource path.
        ack_id: The ack_id of the message being processed.
        job_id: For logging.
        stop_event: threading.Event — set this to stop the heartbeat thread.

    Returns:
        The running Thread — caller does not need to join it explicitly.
    """
    def heartbeat():
        while not stop_event.wait(timeout=ACK_EXTENSION_INTERVAL):
            try:
                subscriber.modify_ack_deadline(
                    request={
                        "subscription": subscription_path,
                        "ack_ids": [ack_id],
                        "ack_deadline_seconds": ACK_EXTENSION_SECONDS,
                    }
                )
                logger.info(
                    f"[{job_id}] Ack deadline extended by {ACK_EXTENSION_SECONDS}s"
                )
            except Exception as e:
                logger.warning(f"[{job_id}] Ack deadline extension failed: {e}")

    thread = threading.Thread(target=heartbeat, daemon=True)
    thread.start()
    return thread


_subscriber_client: pubsub_v1.SubscriberClient | None = None
_subscription_path_cached: str | None = None


def _get_subscriber() -> pubsub_v1.SubscriberClient:
    global _subscriber_client
    if _subscriber_client is None:
        _subscriber_client = pubsub_v1.SubscriberClient()
    return _subscriber_client


def _get_subscription_path() -> str:
    global _subscription_path_cached
    if _subscription_path_cached is None:
        subscriber = _get_subscriber()
        _subscription_path_cached = subscriber.subscription_path(
            PROJECT_ID, SUBSCRIPTION_ID
        )
    return _subscription_path_cached




# ---------------------------------------------------------------------------
# Subscriber entry point
# ---------------------------------------------------------------------------

def main():
    subscriber = _get_subscriber()
    subscription_path = _get_subscription_path()

    logger.info(f"Worker starting — subscribing to: {subscription_path}")

    flow_control = pubsub_v1.types.FlowControl(max_messages=1)

    streaming_pull = subscriber.subscribe(
        subscription_path,
        callback=process_message,
        flow_control=flow_control,
    )

    logger.info("Worker is listening... (Ctrl+C to stop)")

    try:
        streaming_pull.result()
    except KeyboardInterrupt:
        streaming_pull.cancel()
        logger.info("Worker stopped by user")
    except Exception as e:
        streaming_pull.cancel()
        logger.error(f"Worker crashed: {e}")
        raise


if __name__ == "__main__":
    main()