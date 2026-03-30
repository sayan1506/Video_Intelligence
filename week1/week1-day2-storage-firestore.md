# Day 2 — Cloud Storage + Firestore Configuration

**Goal:** End the day with a GCS bucket created, Firestore collections set up, and local Python access confirmed for both services.

---

## Step 1 — Create the Cloud Storage bucket

1. In the GCP console, go to **Cloud Storage → Buckets**
2. Click **Create**
3. Configure as follows:

| Setting | Value |
|---------|-------|
| Name | `video-intelligence-raw` |
| Region | `us-central1` (single region — cheapest for V1) |
| Storage class | Standard |
| Public access | Enforce public access prevention (keep OFF by default) |
| Access control | Uniform |

4. Click **Create**

### Enable versioning (safety net)

1. Click into your new bucket
2. Go to the **Protection** tab
3. Under **Object versioning** → click **Enable**

> This lets you recover accidentally overwritten videos during development. Disable before production to avoid extra storage costs.

---

## Step 2 — Create the bucket folder structure

GCS doesn't have real folders, but you can simulate them with placeholder objects.

1. Inside the bucket, click **Create folder**
2. Create: `raw-videos`
3. Create: `processed`

Your bucket structure should now look like:

```
video-intelligence-raw/
├── raw-videos/
└── processed/
```

> The worker will create sub-folders like `raw-videos/{jobId}/` automatically at upload time. You're just establishing the top-level structure now.

---

## Step 3 — Set up Firestore (Native mode)

1. In the GCP console, go to **Firestore**
2. Click **Create Database**
3. Select **Native mode** (not Datastore mode — it's not compatible with the real-time listeners you'll use later)
4. Region: `us-central1`
5. Click **Create Database**

### Create the three collections

Once Firestore is ready, manually create the collections:

**Collection 1: `jobs`**
1. Click **Start collection**
2. Collection ID: `jobs`
3. Add a test document with ID `test-job-001`:

| Field | Type | Value |
|-------|------|-------|
| jobId | string | `test-job-001` |
| status | string | `pending` |
| filename | string | `test.mp4` |
| createdAt | timestamp | (now) |

**Collection 2: `results`**
1. Click **Start collection**
2. Collection ID: `results`
3. Add a placeholder document with ID `placeholder` and one field: `note` = `placeholder`

**Collection 3: `summaries`**
1. Same as above — collection ID: `summaries`, placeholder document

> You only need real documents in `jobs` for testing. The `results` and `summaries` collections just need to exist so Firestore registers them.

---

## Step 4 — Test access from your local machine

Now verify that your `service-account.json` from Day 1 actually works.

### Install the required packages

```bash
pip install google-cloud-storage google-cloud-firestore
```

### Create a test script `scratch.py`

```python
import os
from google.cloud import storage, firestore

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "./service-account.json"

PROJECT_ID = "your-project-id"   # replace with your actual project ID
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
print("Testing Firestore...")
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
```

### Run it

```bash
python scratch.py
```

Expected output:

```
Testing Cloud Storage...
  Upload OK — gs://video-intelligence-raw/raw-videos/connection-test.txt
  Cleanup OK — test file deleted
Testing Firestore...
  Write OK — document created in jobs collection
  Read OK — status: pending
  Cleanup OK — test document deleted

All tests passed.
```

### Common errors and fixes

| Error | Likely cause | Fix |
|-------|-------------|-----|
| `DefaultCredentialsError` | Wrong path to JSON key | Double-check the `GOOGLE_APPLICATION_CREDENTIALS` path |
| `403 Forbidden` on Storage | Service account missing Storage Admin role | Re-check IAM roles from Day 1 Step 4 |
| `403 Forbidden` on Firestore | Service account missing Datastore User role | Same — re-check IAM |
| `NotFound` on bucket | Bucket name typo | Confirm bucket name in GCP console |

---

## End-of-day checklist

- [ ] GCS bucket `video-intelligence-raw` created in `us-central1`
- [ ] Object versioning enabled on the bucket
- [ ] Folder structure created: `raw-videos/` and `processed/`
- [ ] Firestore database created in Native mode
- [ ] Three collections created: `jobs`, `results`, `summaries`
- [ ] Test document added to `jobs` collection
- [ ] `scratch.py` runs clean — Storage upload/delete and Firestore write/read both pass

---

## What's next

**Day 3** — Pub/Sub topic and subscription creation, and testing the full publish → pull message round-trip locally.
