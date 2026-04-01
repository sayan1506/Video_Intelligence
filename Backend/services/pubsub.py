import os
import json
from google.cloud import pubsub_v1
from datetime import datetime, timezone



def get_publisher() -> pubsub_v1.PublisherClient:
    return pubsub_v1.PublisherClient()  # ADC


def publish_job_message(job_id: str, gcs_path: str, filename: str) -> str:
    """
    Publish a job message to the video-processing Pub/Sub topic.
    Returns the published message ID.
    """
    publisher = get_publisher()
    project_id = os.getenv("GCP_PROJECT_ID")   # read at call time
    topic_id = os.getenv("PUBSUB_TOPIC", "video-processing")
    topic_path = publisher.topic_path(project_id, topic_id)

    message_data = {
        "jobId": job_id,
        "gcsPath": gcs_path,
        "filename": filename,
        "uploadedAt": datetime.now(timezone.utc).isoformat()
    }

    future = publisher.publish(
        topic_path,
        data=json.dumps(message_data).encode("utf-8")
    )

    message_id = future.result()  # blocks until published — fast (<100ms)
    return message_id