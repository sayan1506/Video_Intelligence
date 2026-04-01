from google.cloud import storage, firestore

PROJECT_ID = "video-intelligence-v1"
BUCKET_NAME = "video-intelligence-raw"

# --- Test 1: Cloud Storage ---
print("Testing Cloud Storage...")
storage_client = storage.Client(project=PROJECT_ID)
bucket = storage_client.bucket(BUCKET_NAME)

blob = bucket.blob("raw-videos/connection-test.txt")
blob.upload_from_string("hello from local machine")
print(f"  Upload OK — gs://{BUCKET_NAME}/raw-videos/connection-test.txt")

blob.delete()
print("  Cleanup OK — test file deleted")

# --- Test 2: Firestore ---
print("\nTesting Firestore...")
db = firestore.Client(project=PROJECT_ID)

doc_ref = db.collection("jobs").document("local-test-001")
doc_ref.set({
    "jobId": "local-test-001",
    "status": "pending",
    "filename": "test.mp4",
})
print("  Write OK — document created in jobs collection")

doc = doc_ref.get()
print(f"  Read OK — status: {doc.to_dict()['status']}")

doc_ref.delete()
print("  Cleanup OK — test document deleted")

print("\nAll tests passed.")



import json
from google.cloud import pubsub_v1

PROJECT_ID = "video-intelligence-v1"
TOPIC_ID = "video-processing"
SUBSCRIPTION_ID = "video-processing-sub"

# --- Test 3: Pub/Sub publish ---
print("Testing Pub/Sub publish...")
publisher = pubsub_v1.PublisherClient()
topic_path = publisher.topic_path(PROJECT_ID, TOPIC_ID)

message_data = {
    "jobId": "test-job-pubsub-001",
    "gcsPath": "raw-videos/test-job-pubsub-001/test.mp4",
    "filename": "test.mp4",
    "uploadedAt": "2024-01-01T00:00:00Z"
}

future = publisher.publish(
    topic_path,
    data=json.dumps(message_data).encode("utf-8")
)
message_id = future.result()
print(f"  Publish OK — message ID: {message_id}")

# --- Test 4: Pub/Sub pull and ack ---
import time
time.sleep(2)  # small delay to avoid propagation lag

print("Testing Pub/Sub pull...")
subscriber = pubsub_v1.SubscriberClient()
subscription_path = subscriber.subscription_path(PROJECT_ID, SUBSCRIPTION_ID)

response = subscriber.pull(
    request={
        "subscription": subscription_path,
        "max_messages": 1,
    }
)

if not response.received_messages:
    print("  No messages received — try running again in a few seconds")
else:
    received = response.received_messages[0]
    payload = json.loads(received.message.data.decode("utf-8"))
    print(f"  Pull OK — received jobId: {payload['jobId']}")

    subscriber.acknowledge(
        request={
            "subscription": subscription_path,
            "ack_ids": [received.ack_id],
        }
    )
    print("  Ack OK — message acknowledged")

print("\nPub/Sub test complete.")



import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

from services.storage import upload_to_gcs, get_video_url
from services.firestore import create_job, get_job, update_job_status
from services.pubsub import publish_job_message

TEST_JOB_ID = "scratch-test-day5"

# --- Test storage (using a fake UploadFile-like object) ---
print("Testing storage service...")

class FakeUploadFile:
    filename = "scratch-test.mp4"
    content_type = "video/mp4"
    async def read(self):
        return b"fake video content for testing"
    async def seek(self, pos):
        pass

gcs_path = asyncio.run(upload_to_gcs(FakeUploadFile(), TEST_JOB_ID))
print(f"  Upload OK — {gcs_path}")

# --- Test Firestore service ---
print("Testing Firestore service...")
create_job(TEST_JOB_ID, "scratch-test.mp4", gcs_path)
print("  Create OK")

job = get_job(TEST_JOB_ID)
print(f"  Read OK — status: {job['status']}")

update_job_status(TEST_JOB_ID, "processing", progress=10)
job = get_job(TEST_JOB_ID)
print(f"  Update OK — status: {job['status']}, progress: {job.get('progress')}")

# --- Test Pub/Sub service ---
print("Testing Pub/Sub service...")
msg_id = publish_job_message(TEST_JOB_ID, gcs_path, "scratch-test.mp4")
print(f"  Publish OK — message ID: {msg_id}")

print("\nAll Day 5 service tests passed.")