# Day 3 — Pub/Sub Topic & Subscription Setup

**Goal:** End the day with a Pub/Sub topic and subscription created, and a tested publish → pull message round-trip confirmed from your local machine.

---

## Background — what Pub/Sub is doing here

Think of it like RabbitMQ. The **backend** (FastAPI) is the producer — when a video is uploaded, it drops a message onto the queue saying "hey, process this job." The **worker** (Cloud Run service you'll build in Week 3) is the consumer — it pulls that message, runs the AI pipelines, and acks it when done.

The topic is the queue. The subscription is the worker's handle to pull from it. You're setting both up today so the backend can start publishing messages by Day 5.

```
FastAPI backend  ──publish──►  topic: video-processing  ◄──pull──  AI Worker
                                         │
                               subscription: video-processing-sub
```

---

## Step 1 — Create the Pub/Sub topic

1. In the GCP console, go to **Pub/Sub → Topics**
2. Click **Create Topic**
3. Configure as follows:

| Setting | Value |
|---------|-------|
| Topic ID | `video-processing` |
| Add a default subscription | Leave unchecked — you'll create it manually |
| Message retention | 7 days (default is fine) |
| Encryption | Google-managed (default) |

4. Click **Create**

---

## Step 2 — Create the pull subscription

1. Click into the `video-processing` topic you just created
2. Click **Create Subscription**
3. Configure as follows:

| Setting | Value |
|---------|-------|
| Subscription ID | `video-processing-sub` |
| Delivery type | Pull |
| Acknowledgement deadline | `600` seconds |
| Message retention duration | 7 days |
| Retry policy | Retry after exponential backoff delay |
| Expiration | Never expire |

4. Click **Create**

> **Why 600 seconds for the ack deadline?** Your AI worker will run Video Intelligence, Speech-to-Text, and Gemini concurrently — on a 5–10 minute video this can easily take 2–3 minutes. If the worker doesn't ack within the deadline, Pub/Sub assumes it crashed and re-delivers the message. 600 seconds gives plenty of headroom.

---

## Step 3 — Install the Pub/Sub client library

```bash
pip install google-cloud-pubsub
```

Then freeze to keep `requirements.txt` updated:

```bash
pip freeze > requirements.txt
```

---

## Step 4 — Test the full publish → pull round-trip locally

Add a new section to your existing `scratch.py` file from Day 2:

```python
import json
import base64
from google.cloud import pubsub_v1

PROJECT_ID = "your-project-id"   # replace with your actual project ID
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

    # Acknowledge the message so it doesn't get re-delivered
    subscriber.acknowledge(
        request={
            "subscription": subscription_path,
            "ack_ids": [received.ack_id],
        }
    )
    print("  Ack OK — message acknowledged")

print("\nPub/Sub test complete.")
```

### Run it

```bash
python scratch.py
```

Expected output for the new section:

```
Testing Pub/Sub publish...
  Publish OK — message ID: 12345678901234
Testing Pub/Sub pull...
  Pull OK — received jobId: test-job-pubsub-001
  Ack OK — message acknowledged

Pub/Sub test complete.
```

> **If you get "No messages received":** There's sometimes a 1–2 second propagation delay between publish and pull. Add `import time; time.sleep(2)` between the publish and pull blocks and run again.

---

## Step 5 — Verify in the GCP console

After a successful test run, confirm everything looks clean in the console:

1. Go to **Pub/Sub → Subscriptions → video-processing-sub**
2. Check the **Metrics** tab — you should see:
   - 1 message published
   - 1 message delivered
   - 0 undelivered messages (ack was successful)

If you see undelivered messages sitting there, re-run the pull + ack portion of the script.

---

## Common errors and fixes

| Error | Likely cause | Fix |
|-------|-------------|-----|
| `403 PERMISSION_DENIED` on publish | Service account missing Pub/Sub Editor role | Re-check IAM roles from Day 1 |
| `404 Resource not found` | Topic or subscription ID typo | Double-check IDs in GCP console |
| `No messages received` | Propagation delay | Add a `time.sleep(2)` before the pull call |
| `DeadlineExceeded` on pull | No messages in the subscription | Publish first, then pull in the same run |

---

## End-of-day checklist

- [ ] Pub/Sub topic `video-processing` created
- [ ] Subscription `video-processing-sub` created with 600s ack deadline
- [ ] `google-cloud-pubsub` installed and added to `requirements.txt`
- [ ] `scratch.py` publishes a test message successfully
- [ ] `scratch.py` pulls and acks the message successfully
- [ ] GCP console shows 0 undelivered messages on the subscription

---

## What's next

**Day 4** — FastAPI project scaffold. You'll create the full `backend/` folder structure, write `main.py` with stub routes for all three endpoints, and wire up Pydantic schemas so the API is runnable locally.
