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