# VidIQ — AI Video Intelligence

VidIQ is a full-stack web application that takes a video upload and returns a comprehensive AI-generated intelligence report. Upload a video, wait a couple of minutes, and get back a full transcript with clickable timestamps, detected scenes with labels, auto-generated chapters, key highlights, sentiment analysis, and an executive summary — all on a clean interactive dashboard.

---

## What it does

You upload a video. The app processes it through three AI pipelines running in the background:

- **Speech-to-Text** — produces a word-level transcript with timestamps
- **Video Intelligence** — detects scene changes and labels visible content (person, laptop, whiteboard, etc.)
- **Gemini 1.5 Pro** — reads the transcript and scene data and generates a summary, chapters, highlights, sentiment classification, and action items

Results are displayed in a four-panel dashboard: a video player with scene markers on the timeline, a summary card with chapter navigation, a searchable transcript panel where clicking any word seeks the video, and a scene analysis panel showing detected labels per scene.

---

## Tech stack

| Layer | Technology |
|-------|------------|
| Frontend | React (Vite), TailwindCSS, shadcn/ui, Video.js |
| Backend API | FastAPI (Python), Google Cloud Run |
| AI Worker | Python, Google Cloud Run, ffmpeg |
| AI APIs | Video Intelligence API, Speech-to-Text v2, Vertex AI Gemini 1.5 Pro |
| Storage | Google Cloud Storage |
| Database | Firestore (Native mode) |
| Queue | Pub/Sub |
| Hosting | Firebase Hosting |

---

## Architecture

Videos never pass through the backend server. The upload flow is:

1. Frontend requests a signed PUT URL from the backend (`POST /upload-url`)
2. Browser uploads the video directly to Cloud Storage
3. Frontend calls `POST /upload-confirm` — backend triggers Pub/Sub
4. The AI worker picks up the message and runs all three pipelines concurrently
5. Results are written to Firestore
6. Frontend polls `GET /status/{jobId}` until complete, then loads `GET /result/{jobId}`

---

## Project structure

```
Video_Intelligence/
├── backend/          # FastAPI REST API (Cloud Run)
│   ├── routers/      # upload-url, upload-confirm, status, result
│   ├── services/     # GCS, Firestore, Pub/Sub helpers
│   └── models/       # Pydantic schemas
├── worker/           # AI processing worker (Cloud Run)
│   ├── pipeline/     # speech_to_text, video_intelligence, gemini, orchestrator
│   └── services/     # GCS, Firestore helpers
└── frontend/         # React/Vite app (Firebase Hosting)
    └── src/
        ├── pages/    # UploadPage, StatusPage, ResultPage
        └── components/
```

---

## GCP services used

- **Cloud Run** — backend API and AI worker (two separate services)
- **Cloud Storage** — raw video uploads and processed pipeline outputs
- **Pub/Sub** — async queue between backend and worker
- **Firestore** — job metadata, transcripts, scenes, summaries
- **Video Intelligence API** — shot detection and label annotation
- **Speech-to-Text v2** — batch audio transcription with word timestamps
- **Vertex AI** — Gemini 1.5 Pro for summary generation
- **Firebase Hosting** — React frontend

---

## Built as a learning project

This is a structured multi-week build designed to get practical experience with GCP's AI services, Cloud Run deployment, async processing pipelines, and full-stack development. The entire codebase uses Application Default Credentials — no service account JSON keys anywhere in the code.
