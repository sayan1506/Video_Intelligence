# VidIQ Worker

The AI processing engine for VidIQ. It is a long-lived **Pub/Sub subscriber** (not an HTTP server) that runs on Google Cloud Run with `--min-instances 1`. It consumes one `JobMessage` at a time, runs the full multi-stage AI pipeline on the uploaded video, and writes results back to Firestore.

The backend never does AI work — it only enqueues jobs. Everything heavy happens here.

## Tech stack

- **Runtime:** Python 3.11, plain `python main.py` (no web framework for the main loop)
- **Media:** `ffmpeg` / `ffprobe` (installed in the Docker image) for audio extraction, chunk splitting, and thumbnail capture
- **Cloud credentials:** Application Default Credentials (ADC) — no service-account JSON key files
- **GCP services:** Pub/Sub (subscriber), Cloud Storage, Firestore (Native mode + vector search), Speech-to-Text v2, Video Intelligence API, Vertex AI (Gemini 2.5 Flash + `text-embedding-004`)
- **Deployment:** Google Cloud Run (containerised via the included Dockerfile)

## What it processes

The worker subscribes to the Pub/Sub subscription and processes `JobMessage` payloads published by the backend after a confirmed upload. Each message carries:

```
jobId, gcsPath, gcsBucket, gcsUri, filename, fileSizeMb, contentType, uploadedAt, schemaVersion
```

### Pipeline stages (per job)

Progress is written to the `jobs/{jobId}` Firestore doc as the job advances (`processing` → `25 → 35 → 50/60 → 75 → 90 → completed`).

1. **Audio-only detection** — if `contentType` is an audio MIME type (`audio/mpeg`, `audio/wav`, `audio/mp4`, etc.), Video Intelligence and thumbnail extraction are skipped; only STT runs.
2. **Phase 1 — Speech-to-Text + Video Intelligence (concurrent for video).**
   - **STT v2 (`speech_to_text.py`):** downloads the video, extracts mono FLAC via ffmpeg, transcribes with word-level timestamps. Videos longer than 5 minutes are split into 5-minute chunks, uploaded, and transcribed **in parallel**; results are merged with corrected absolute timestamps. Videos over 30 minutes use 8 kHz (vs 16 kHz) extraction to shrink FLAC size. Diarization runs only on the short whole-file path. Detected language (BCP-47) is captured on the whole-file path.
   - **Video Intelligence (`video_intelligence.py`):** shot-change detection + label detection straight from the GCS URI (no download). Builds per-scene label lists filtered by confidence ≥ 0.6, top 10 labels each.
3. **Thumbnail (video only):** ffmpeg grabs a frame at ~10% of duration, uploads to `processed/{jobId}/thumbnail.jpg`. Best-effort — never fails the job.
4. **Phase 2 — Gemini summary (`gemini.py`):** Gemini 2.5 Flash reads the transcript + scene data and returns strict JSON: `summary`, `chapters`, `highlights`, `sentiment`, `actionItems`. The parser tolerates malformed output and falls back to safe defaults. Token usage and estimated cost are written to the job doc.
5. **Phase 3 — Write results:** transcript is stored as a `transcript_chunks/` subcollection (300 words/chunk) under `results/{jobId}` to bypass Firestore's 1 MB document limit; scenes, labels, and `detectedLanguage` go in the parent doc.
6. **Translation (conditional):** if `detectedLanguage` is non-English, Gemini translates the transcript to English; the result is written to `summaries/{jobId}.translatedTranscript`.
7. **Phase 4 — Embeddings (`embeddings.py`):** each transcript chunk is embedded with `text-embedding-004` (768-dim, `RETRIEVAL_DOCUMENT`) and written back to the chunk doc as a Firestore `Vector`, enabling the backend's RAG Q&A search. Non-fatal.
8. **Cleanup:** the raw video is deleted from GCS (processed artifacts are kept). The job is marked `completed` with total processing time and a combined cost estimate.

### Reliability behavior

- **Idempotency guard:** before doing work, the worker checks Firestore — if the job is already `processing`/`completed`/`failed`, the duplicate message is acked and skipped. Prevents double-processing on Pub/Sub redelivery.
- **Ack deadline heartbeat:** a background thread extends the Pub/Sub ack deadline every 60 s (by 300 s) while the pipeline runs, so long videos don't get redelivered mid-processing.
- **Flow control:** `max_messages=1` — one job per instance at a time.
- **Gemini warm-up:** `ping_gemini()` at startup pre-establishes the gRPC channel, removing ~6 s of cold-start latency from the first real job.
- **Graceful shutdown:** `SIGTERM` cancels the streaming pull and closes the subscriber cleanly.
- **Health server:** a tiny `HTTPServer` on `$PORT` answers `GET /` with `ok` so Cloud Run's health checks pass even though the worker isn't an API.
- **Retries:** transient `ServiceUnavailable` / `DeadlineExceeded` / `ResourceExhausted` errors are retried with backoff in STT polling, Video Intelligence polling, and Gemini calls.

## Queue / trigger mechanism

The backend publishes to a Pub/Sub **topic**; the worker subscribes to a **subscription** on that topic.

```
Backend ──publish──► Pub/Sub topic (video-processing)
                          │
                          └──► subscription (video-processing-sub) ──pull──► Worker
```

`process_message` deserialises and validates the payload into a `JobMessage` (Pydantic). Malformed messages are acked and dropped (logged). Valid messages run through `run_pipeline`. The message is acked after the pipeline finishes — success or recorded failure both ack (failures are persisted in Firestore, not retried via the queue).

## Environment variables

Production values are supplied via Cloud Run (see `env.yaml`). For local runs, set these in a `.env` file (loaded by `python-dotenv`).

| Variable | Required | Example | Purpose |
|----------|----------|---------|---------|
| `GCP_PROJECT_ID` | yes | `video-intelligence-v1` | GCP project for all clients (worker exits if unset) |
| `PUBSUB_SUBSCRIPTION` | yes | `video-processing-sub` | Subscription the worker pulls from (worker exits if unset) |
| `GCP_BUCKET_NAME` | yes | `video-intelligence-raw` | Bucket for raw video + processed artifacts |
| `FIRESTORE_DATABASE` | no | `(default)` | Firestore database id |
| `GCP_SERVICE_ACCOUNT_EMAIL` | yes | `…-sa@…iam.gserviceaccount.com` | Used for signed-URL impersonation in storage helpers |
| `GCP_REGION` | no | `us-central1` | Vertex AI location for Gemini + embeddings |
| `PORT` | no | `8080` | Port for the health-check HTTP server |

## Run locally

### Prerequisites
- Python 3.11+
- `ffmpeg` and `ffprobe` on your `PATH`
- `gcloud` CLI authenticated for ADC: `gcloud auth application-default login`
- A real Pub/Sub subscription you can pull from, plus access to Storage, Firestore, STT, Video Intelligence, and Vertex AI

### Setup

```powershell
python -m venv venv
venv\Scripts\Activate.ps1        # Windows PowerShell
pip install -r requirements.txt
```

Create a `.env` with at least `GCP_PROJECT_ID`, `PUBSUB_SUBSCRIPTION`, `GCP_BUCKET_NAME`, and `GCP_SERVICE_ACCOUNT_EMAIL`.

### Start the worker

```bash
python main.py
```

It logs `Worker is listening...` and blocks, processing messages as they arrive. Upload a video through the frontend/backend (or publish a `JobMessage` manually) to trigger a job. Stop with `Ctrl+C`.

### Tests

```bash
pytest
```

The suite covers orchestrator routing (audio-only vs video, translation decisions), STT chunking and adaptive sample rate, the Gemini JSON parser, translation parsing, language extraction, embeddings, and full-pipeline regression — including Hypothesis property-based tests.

## Project structure

```
worker/
├── main.py                      # Pub/Sub subscriber loop, idempotency guard,
│                                # ack heartbeat, health server, Gemini warm-up, SIGTERM
├── pipeline/
│   ├── orchestrator.py          # run_pipeline — sequences all stages
│   ├── speech_to_text.py        # STT v2: whole-file + parallel chunked, adaptive rate
│   ├── video_intelligence.py    # Shot detection + label annotation
│   ├── gemini.py                # Summary generation + transcript translation
│   └── embeddings.py            # text-embedding-004 vectors → Firestore
├── services/
│   ├── firestore.py             # Job status, results/summaries writers, chunks, vectors
│   └── storage.py               # GCS download/upload, signed URLs, processed JSON
├── models/
│   └── schemas.py               # JobMessage, WordTimestamp, Scene, progress map
├── tests/                       # pytest + Hypothesis
├── Dockerfile                   # installs ffmpeg; CMD ["python", "main.py"]
├── env.yaml                     # Cloud Run env vars
└── requirements.txt
```

## Deploy to Cloud Run

The worker is a pull subscriber, so it must stay warm. Deploy with at least one always-on instance and enough CPU/memory for ffmpeg + concurrent STT.

```bash
# Build & push
gcloud builds submit \
  --tag us-central1-docker.pkg.dev/video-intelligence-v1/video-api/worker:latest

# Deploy — keep one instance warm so the subscriber is always pulling
gcloud run deploy vidiq-worker \
  --image us-central1-docker.pkg.dev/video-intelligence-v1/video-api/worker:latest \
  --region us-central1 \
  --service-account video-intelligence-sa@video-intelligence-v1.iam.gserviceaccount.com \
  --env-vars-file env.yaml \
  --min-instances 1 \
  --no-cpu-throttling \
  --memory 4Gi \
  --cpu 2
```

The Docker image installs `ffmpeg` (not in `python:3.11-slim`) and runs `python main.py`. The attached service account provides ADC at runtime and needs roles for Pub/Sub subscriber, Storage object admin, Firestore user, Speech-to-Text + Video Intelligence usage, and Vertex AI user.
