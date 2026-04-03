# from google.cloud import storage, firestore

# PROJECT_ID = "video-intelligence-v1"
# BUCKET_NAME = "video-intelligence-raw"

# # --- Test 1: Cloud Storage ---
# print("Testing Cloud Storage...")
# storage_client = storage.Client(project=PROJECT_ID)
# bucket = storage_client.bucket(BUCKET_NAME)

# blob = bucket.blob("raw-videos/connection-test.txt")
# blob.upload_from_string("hello from local machine")
# print(f"  Upload OK — gs://{BUCKET_NAME}/raw-videos/connection-test.txt")

# blob.delete()
# print("  Cleanup OK — test file deleted")

# # --- Test 2: Firestore ---
# print("\nTesting Firestore...")
# db = firestore.Client(project=PROJECT_ID)

# doc_ref = db.collection("jobs").document("local-test-001")
# doc_ref.set({
#     "jobId": "local-test-001",
#     "status": "pending",
#     "filename": "test.mp4",
# })
# print("  Write OK — document created in jobs collection")

# doc = doc_ref.get()
# print(f"  Read OK — status: {doc.to_dict()['status']}")

# doc_ref.delete()
# print("  Cleanup OK — test document deleted")

# print("\nAll tests passed.")



# import json
# from google.cloud import pubsub_v1

# PROJECT_ID = "video-intelligence-v1"
# TOPIC_ID = "video-processing"
# SUBSCRIPTION_ID = "video-processing-sub"

# # --- Test 3: Pub/Sub publish ---
# print("Testing Pub/Sub publish...")
# publisher = pubsub_v1.PublisherClient()
# topic_path = publisher.topic_path(PROJECT_ID, TOPIC_ID)

# message_data = {
#     "jobId": "test-job-pubsub-001",
#     "gcsPath": "raw-videos/test-job-pubsub-001/test.mp4",
#     "filename": "test.mp4",
#     "uploadedAt": "2024-01-01T00:00:00Z"
# }

# future = publisher.publish(
#     topic_path,
#     data=json.dumps(message_data).encode("utf-8")
# )
# message_id = future.result()
# print(f"  Publish OK — message ID: {message_id}")

# # --- Test 4: Pub/Sub pull and ack ---
# import time
# time.sleep(2)  # small delay to avoid propagation lag

# print("Testing Pub/Sub pull...")
# subscriber = pubsub_v1.SubscriberClient()
# subscription_path = subscriber.subscription_path(PROJECT_ID, SUBSCRIPTION_ID)

# response = subscriber.pull(
#     request={
#         "subscription": subscription_path,
#         "max_messages": 1,
#     }
# )

# if not response.received_messages:
#     print("  No messages received — try running again in a few seconds")
# else:
#     received = response.received_messages[0]
#     payload = json.loads(received.message.data.decode("utf-8"))
#     print(f"  Pull OK — received jobId: {payload['jobId']}")

#     subscriber.acknowledge(
#         request={
#             "subscription": subscription_path,
#             "ack_ids": [received.ack_id],
#         }
#     )
#     print("  Ack OK — message acknowledged")

# print("\nPub/Sub test complete.")



# import asyncio
# import os
# from dotenv import load_dotenv

# load_dotenv()

# from services.storage import upload_to_gcs, get_signed_url
# from services.firestore import create_job, get_job, update_job_status
# from services.pubsub import publish_job_message

# TEST_JOB_ID = "scratch-test-day5"

# # --- Test storage (using a fake UploadFile-like object) ---
# print("Testing storage service...")

# class FakeUploadFile:
#     def __init__(self):
#         self.content = b"fake video content for testing " * 100
#         self.filename = "scratch-test.mp4"
#         self.content_type = "video/mp4"
#         self.size = len(self.content)
#         self._pos = 0

#     async def read(self, size=-1):
#         if size == -1:
#             chunk = self.content[self._pos:]
#         else:
#             chunk = self.content[self._pos:self._pos + size]
#         self._pos += len(chunk)
#         return chunk

#     async def seek(self, pos):
#         self._pos = pos

# gcs_path = asyncio.run(upload_to_gcs(FakeUploadFile(), TEST_JOB_ID))
# print(f"  Upload OK — {gcs_path}")

# # --- Test Firestore service ---
# print("Testing Firestore service...")
# create_job(TEST_JOB_ID, "scratch-test.mp4", gcs_path)
# print("  Create OK")

# job = get_job(TEST_JOB_ID)
# print(f"  Read OK — status: {job['status']}")

# update_job_status(TEST_JOB_ID, "processing", progress=10)
# job = get_job(TEST_JOB_ID)
# print(f"  Update OK — status: {job['status']}, progress: {job.get('progress')}")

# # --- Test Pub/Sub service ---
# print("Testing Pub/Sub service...")
# msg_id = publish_job_message(TEST_JOB_ID, gcs_path, "scratch-test.mp4")
# print(f"  Publish OK — message ID: {msg_id}")

# print("\nAll Day 5 service tests passed.")




# import asyncio
# from dotenv import load_dotenv
# load_dotenv()

# from utils.validators import check_magic_bytes, validate_file_extension

# print("Testing magic bytes validator...")

# # Test 1: Valid MP4 header
# mp4_header = b'\x00\x00\x00\x20' + b'ftyp' + b'isom' + b'\x00' * 4
# result = check_magic_bytes(mp4_header, "video/mp4")
# print(f"  MP4 magic bytes: {'PASS' if result else 'FAIL'}")

# # Test 2: Fake MP4 (text file pretending to be video)
# fake_header = b'This is just a text file, not a video at all!!'
# result = check_magic_bytes(fake_header, "video/mp4")
# print(f"  Fake MP4 rejected: {'PASS' if not result else 'FAIL'}")

# # Test 3: AVI header
# avi_header = b'RIFF' + b'\x00' * 8
# result = check_magic_bytes(avi_header, "video/avi")
# print(f"  AVI magic bytes: {'PASS' if result else 'FAIL'}")

# # Test 4: Extension validation
# print(f"  .mp4 extension: {'PASS' if validate_file_extension('video.mp4') else 'FAIL'}")
# print(f"  .exe extension: {'PASS' if not validate_file_extension('bad.exe') else 'FAIL'}")
# print(f"  no extension:   {'PASS' if not validate_file_extension('noext') else 'FAIL'}")

# print("\nValidator tests complete.")


# # Test chunked upload with a real file
# # Replace the path below with a real small .mp4 on your machine
# import os
# from services.storage import upload_to_gcs, CHUNK_SIZE

# TEST_VIDEO_PATH = r""  # ← update this

# if os.path.exists(TEST_VIDEO_PATH):
#     print(f"\nTesting chunked upload with real file...")
#     print(f"  Chunk size: {CHUNK_SIZE / (1024*1024):.0f}MB")

#     class RealFileUpload:
#         def __init__(self, path):
#             self.path = path
#             self.filename = os.path.basename(path)
#             self.content_type = "video/mp4"
#             self.size = os.path.getsize(path)
#             self._pos = 0
#             self._data = open(path, "rb").read()

#         async def read(self, size=-1):
#             if size == -1:
#                 chunk = self._data[self._pos:]
#             else:
#                 chunk = self._data[self._pos:self._pos + size]
#             self._pos += len(chunk)
#             return chunk

#         async def seek(self, pos):
#             self._pos = pos

#     progress_log = []

#     async def on_progress(percent):
#         progress_log.append(percent)
#         print(f"  Upload progress: {percent}%", end="\r")

#     async def run_upload():
#         fake_file = RealFileUpload(TEST_VIDEO_PATH)
#         job_id = "scratch-w2d1-chunked"
#         gcs_path = await upload_to_gcs(fake_file, job_id, progress_callback=on_progress)
#         return gcs_path

#     gcs_path = asyncio.run(run_upload())
#     print(f"\n  Chunked upload OK → {gcs_path}")
#     print(f"  Progress callbacks fired: {len(progress_log)} times")
# else:
#     print(f"\nSkipping real file test — update TEST_VIDEO_PATH in scratch.py")




# import json
# import time
# from dotenv import load_dotenv
# load_dotenv()

# import os

# from google.cloud import pubsub_v1
# from models.schemas import JobMessage
# from services.pubsub import publish_job_message, build_job_message

# PROJECT_ID = os.getenv("GCP_PROJECT_ID")
# SUBSCRIPTION_ID = "video-processing-sub"

# print("Testing Pub/Sub round-trip with JobMessage schema...")

# # --- Publish ---
# TEST_JOB_ID = "scratch-w2d2-pubsub"
# TEST_GCS_PATH = f"raw-videos/{TEST_JOB_ID}/test.mp4"

# msg_id = publish_job_message(
#     job_id=TEST_JOB_ID,
#     gcs_path=TEST_GCS_PATH,
#     filename="test.mp4",
#     file_size_bytes=52428800,   # 50MB dummy
#     content_type="video/mp4",
# )
# print(f"  Publish OK — message ID: {msg_id}")

# # Allow a moment for propagation
# time.sleep(2)

# # --- Pull and deserialise ---
# subscriber = pubsub_v1.SubscriberClient()
# subscription_path = subscriber.subscription_path(PROJECT_ID, SUBSCRIPTION_ID)

# response = subscriber.pull(
#     request={"subscription": subscription_path, "max_messages": 1}
# )

# if not response.received_messages:
#     print("  No message received — try increasing the sleep duration")
# else:
#     received = response.received_messages[0]
#     raw_payload = json.loads(received.message.data.decode("utf-8"))

#     # Deserialise into Pydantic model
#     job_message = JobMessage(**raw_payload)

#     print(f"  Pull OK — jobId: {job_message.jobId}")
#     print(f"  Schema version: {job_message.schemaVersion}")
#     print(f"  GCS URI: {job_message.gcsUri}")
#     print(f"  File size: {job_message.fileSizeMb}MB")
#     print(f"  Attributes: {dict(received.message.attributes)}")

#     # Validate round-trip integrity
#     assert job_message.jobId == TEST_JOB_ID, "jobId mismatch!"
#     assert job_message.gcsBucket == os.getenv("GCP_BUCKET_NAME"), "gcsBucket mismatch!"
#     assert job_message.gcsUri.startswith("gs://"), "gcsUri missing gs:// prefix!"
#     assert received.message.attributes.get("jobId") == TEST_JOB_ID, "Attribute jobId mismatch!"
#     print("  All assertions passed — schema round-trip verified")

#     # Ack the message
#     subscriber.acknowledge(
#         request={
#             "subscription": subscription_path,
#             "ack_ids": [received.ack_id],
#         }
#     )
#     print("  Ack OK")

# # --- Test retry logic (simulate a bad topic) ---
# print("\nTesting retry logic...")
# from services.pubsub import MAX_RETRIES, BACKOFF_BASE_SECONDS
# print(f"  MAX_RETRIES: {MAX_RETRIES}")
# print(f"  Backoff schedule: "
#       f"{[BACKOFF_BASE_SECONDS * (2**i) for i in range(MAX_RETRIES)]}s")
# print("  (Retry logic verified by config — live failure test would need a bad topic)")

# print("\nPub/Sub Day 2 tests complete.")









import os
from dotenv import load_dotenv
load_dotenv()

from services.storage import get_signed_url, build_gcs_path
from services.firestore import write_video_url, get_job

print("Testing signed URL generation...")

# Use the GCS path from a previous scratch test upload
# Replace with a real path from your GCS bucket
TEST_JOB_ID = "scratch-w2d1-chunked"
TEST_GCS_PATH = build_gcs_path(TEST_JOB_ID, "test-video.mp4")

try:
    signed_url = get_signed_url(TEST_GCS_PATH, expiration_minutes=15)
    print(f"  Signed URL generated OK")
    print(f"  URL starts with https://: {'PASS' if signed_url.startswith('https://') else 'FAIL'}")
    print(f"  URL contains X-Goog-Signature: {'PASS' if 'X-Goog-Signature' in signed_url else 'FAIL'}")
    print(f"  Full URL (first 120 chars): {signed_url[:120]}...")
except Exception as e:
    print(f"  Signed URL generation FAILED: {e}")
    print("  Check: Token Creator role granted? Correct GCS path?")

print("\nTesting Firestore videoUrl write...")

try:
    write_video_url(TEST_JOB_ID, signed_url)
    job = get_job(TEST_JOB_ID)
    stored_url = job.get("videoUrl", "")
    print(f"  Write OK — videoUrl stored in Firestore")
    print(f"  URL matches: {'PASS' if stored_url == signed_url else 'FAIL'}")
except Exception as e:
    print(f"  Firestore write FAILED: {e}")

print("\nManual browser test:")
print(f"  Copy the signed URL above and paste it into a browser tab.")
print(f"  The video should play directly — no login required.")
print(f"  If you see a 403: the URL expired or the file path is wrong.")
print(f"  If you see a CORS error: re-check Step 5 CORS config was applied.")

print("\nDay 3 tests complete.")