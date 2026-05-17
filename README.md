# VidIQ — AI Video Intelligence

VidIQ is a full-stack web application that takes a video upload and returns a comprehensive AI-generated intelligence report. Upload a video, wait a couple of minutes, and get back a full transcript with clickable timestamps, detected scenes with labels, auto-generated chapters, key highlights, sentiment analysis, and an executive summary — all on a clean interactive dashboard.

---

## What it does

You upload a video (up to 2GB). The app processes it through three AI pipelines running in the background:

- **Speech-to-Text** — produces a word-level transcript with timestamps (parallel chunked processing for long videos)
- **Video Intelligence** — detects scene changes and labels visible content (person, laptop, whiteboard, etc.)
- **Gemini 2.5 Flash** — reads the transcript and scene data and generates a summary, chapters, highlights, sentiment classification, and action items

Results are displayed in a four-panel dashboard: a video player with scene markers on the timeline, a summary card with chapter navigation, a searchable transcript panel where clicking any word seeks the video, and a scene analysis panel showing detected labels per scene.

---

## Tech stack

| Layer | Technology |
|-------|------------|
| Frontend | React (Vite), TailwindCSS, shadcn/ui, Video.js |
| Backend API | FastAPI (Python), Google Cloud Run |
| AI Worker | Python, Google Cloud Run, ffmpeg |
| AI APIs | Video Intelligence API, Speech-to-Text v2, Vertex AI Gemini 2.5 Flash |
| Storage | Google Cloud Storage |
| Database | Firestore (Native mode) |
| Queue | Pub/Sub |
| Hosting | Firebase Hosting |

---

## Architecture

Videos never pass through the backend server. The upload flow is:

1. Frontend requests a resumable upload URI from the backend (`POST /upload-url`)
2. Browser uploads the video directly to Cloud Storage in 8MB chunks (resumable upload protocol)
3. Frontend calls `POST /upload-confirm` — backend triggers Pub/Sub
4. The AI worker picks up the message and runs all three pipelines concurrently
5. Results are written to Firestore (transcript stored as chunked subcollection)
6. Frontend polls `GET /status/{jobId}` until complete, then loads `GET /result/{jobId}`

---

## V1.1 — What shipped

V1.1 was a 6-week iteration focused on correctness, performance, and scale. All items delivered:

| Item | Week | What it does |
|------|------|-------------|
| BF-2: Fresh signed video URL | 1 | `GET /video-url/{jobId}` generates a fresh signed URL on every ResultPage load — video playback never expires |
| BF-4: Pub/Sub idempotency + heartbeat | 1 | Worker checks Firestore before processing; extends ack deadline every 60s — no double-processing on long videos |
| BF-1 + BF-3: Chunked transcript | 2 | Transcript stored as Firestore subcollection (`transcript_chunks/`) — no 1MB limit, no truncation, full transcript for any video length |
| PERF-1: Parallel chunked STT | 3 | ffmpeg splits audio into 5-min chunks, all submitted to STT concurrently — near-linear speedup |
| SCALE-1: Resumable uploads (2GB) | 4 | GCS resumable upload protocol replaces signed PUT URL — supports up to 2GB, survives network interruptions |
| PERF-3: Skip VI for audio-only | 5 | Audio files (mp3, wav, m4a, etc.) skip Video Intelligence entirely — faster processing, lower cost |
| PERF-4: Adaptive ffmpeg sample rate | 5 | Videos > 30min use 8kHz sample rate; ≤ 30min use 16kHz — smaller FLAC files for long content |
| PERF-2: Gemini connection warm-up | 6 | `ping_gemini()` at worker startup pre-establishes gRPC channel — eliminates ~6s cold-start latency |

**Result:** Processing speed improved from ~0.5x to ~0.3x video length. Upload limit increased from 100MB to 2GB. Full transcripts preserved for 2+ hour videos with no data loss.

---

## Project structure

```
Video_Intelligence/
├── Backend/          # FastAPI REST API (Cloud Run)
│   ├── routers/      # upload-url, upload-confirm, status, result, video-url
│   ├── services/     # GCS, Firestore, Pub/Sub helpers
│   └── models/       # Pydantic schemas
├── worker/           # AI processing worker (Cloud Run)
│   ├── pipeline/     # speech_to_text, video_intelligence, gemini, orchestrator
│   ├── services/     # GCS, Firestore helpers
│   └── tests/        # 98 unit + integration + property-based tests
└── frontend/         # React/Vite app (Firebase Hosting)
    └── src/
        ├── pages/    # UploadPage, StatusPage, ResultPage
        └── components/
```

---

## GCP services used

- **Cloud Run** — backend API and AI worker (two separate services, worker with `--min-instances 1`)
- **Cloud Storage** — raw video uploads and processed pipeline outputs
- **Pub/Sub** — async queue between backend and worker (with ack deadline heartbeat)
- **Firestore** — job metadata, chunked transcripts, scenes, summaries
- **Video Intelligence API** — shot detection and label annotation
- **Speech-to-Text v2** — batch audio transcription with word timestamps (parallel chunked)
- **Vertex AI** — Gemini 2.5 Flash for summary generation
- **Firebase Hosting** — React frontend
- **Artifact Registry** — Docker image storage for Cloud Run services

---

## Built as a learning project

This is a structured multi-week build designed to get practical experience with GCP's AI services, Cloud Run deployment, async processing pipelines, and full-stack development. The entire codebase uses Application Default Credentials — no service account JSON keys anywhere in the code.
