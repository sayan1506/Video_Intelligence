# AI Video Intelligence App — V1 Product Prompt

## Overview

Build a full-stack AI-powered web application called **VidIQ** (or any suitable name) that allows users to upload a video and receive a comprehensive AI-generated intelligence report. The report includes a full transcript with clickable timestamps, scene & label detection, auto-generated chapters, key highlights, and an executive summary — all displayed on a clean, interactive dashboard.

The application is built on **Google Cloud Platform (GCP)** and uses a modern async processing pipeline so users never wait for a response. Video processing happens entirely in the background.

---

## Tech Stack

### Frontend
- **Framework**: React (Vite)
- **Styling**: TailwindCSS + shadcn/ui
- **Video Player**: Video.js
- **Charts/Visuals**: Recharts
- **Hosting**: Firebase Hosting

### Backend
- **Framework**: FastAPI (Python)
- **Deployment**: Google Cloud Run
- **Auth**: API Key middleware (JWT in V2)

### GCP Services
| Service | Purpose |
|---|---|
| Cloud Storage | Store raw uploaded videos + processed output |
| Pub/Sub | Async message queue to trigger AI pipeline |
| Cloud Run (Backend) | Host FastAPI REST API |
| Cloud Run (Worker) | Dedicated AI processing worker |
| Firestore | Store job metadata + AI results |
| Video Intelligence API | Scene detection, label detection, object tracking |
| Speech-to-Text API | Full transcript with word-level timestamps |
| Vertex AI Gemini 1.5 Pro | Summary, chapters, highlights, insights |
| Firebase Hosting | Serve React frontend |
| Cloud Logging | Error tracking + job lifecycle logs |

---

## Core User Flow

```
1. User opens the app
2. User uploads a video file (mp4, mov, avi — max 500MB for V1)
3. Backend immediately returns a Job ID → user sees "Processing..." screen
4. In the background:
   a. Video saved to Cloud Storage
   b. Pub/Sub message fired → AI Worker picks it up
   c. Worker runs 3 AI pipelines in parallel:
      - Video Intelligence API (scenes, labels, objects)
      - Speech-to-Text API (transcript + timestamps)
      - Vertex AI Gemini (summary, chapters, highlights)
   d. All results written to Firestore
5. Frontend polls Firestore every 3 seconds using the Job ID
6. When status = "completed" → Dashboard auto-renders with all results
```

---

## Backend API — Endpoints

### `POST /upload`
- Accepts multipart video file upload
- Validates file type and size
- Streams file directly to GCS bucket (`raw-videos/`)
- Creates a Firestore job document with status `pending`
- Publishes a Pub/Sub message: `{ jobId, gcsPath, filename, uploadedAt }`
- Returns: `{ jobId, status: "pending", message: "Video uploaded successfully" }`

### `GET /status/{jobId}`
- Returns current job status from Firestore
- Status values: `pending` → `processing` → `completed` | `failed`
- Returns: `{ jobId, status, progress: 0-100, createdAt, updatedAt }`

### `GET /result/{jobId}`
- Returns full AI results from Firestore once status = `completed`
- Returns:
```json
{
  "jobId": "abc123",
  "status": "completed",
  "videoUrl": "https://storage.googleapis.com/...",
  "transcript": [
    { "word": "Hello", "startTime": 0.0, "endTime": 0.4, "speaker": 1 }
  ],
  "scenes": [
    { "startTime": 0.0, "endTime": 12.5, "labels": ["person", "outdoor", "laptop"] }
  ],
  "summary": "This video covers...",
  "chapters": [
    { "title": "Introduction", "startTime": 0, "endTime": 90 },
    { "title": "Main Demo", "startTime": 90, "endTime": 300 }
  ],
  "highlights": [
    { "timestamp": 32.5, "description": "Key point mentioned about pricing" }
  ],
  "sentiment": "positive",
  "processingTime": 47
}
```

---

## AI Worker — Pipeline Details

The worker is a **separate Cloud Run service** that subscribes to the Pub/Sub topic `video-processing`.

### On receiving a message:
1. Update Firestore job status → `processing`
2. Download video metadata from GCS (not the full file — APIs read from GCS directly)
3. Fire all 3 API calls **concurrently** using `asyncio.gather()`:

### Pipeline A — Video Intelligence API
- Annotate video from GCS URI
- Extract: shot change detection, label annotations per segment, object tracking
- Output: list of scenes with timestamps + detected labels + confidence scores

### Pipeline B — Speech-to-Text API
- Use `LongRunningRecognize` for videos > 1 minute
- Enable: word-level timestamps, speaker diarization (up to 2 speakers for V1), automatic punctuation
- Language: `en-US` (multi-language in V2)
- Output: full transcript array with per-word timestamps + speaker tags

### Pipeline C — Vertex AI Gemini 1.5 Pro
- Input: transcript text + scene labels + video duration
- System prompt instructs Gemini to return **strict JSON** with:
  - `summary`: 3-5 sentence executive overview
  - `chapters`: array of `{ title, startTime, endTime }` based on transcript flow
  - `highlights`: array of `{ timestamp, description }` for key moments
  - `sentiment`: overall tone (`positive` / `neutral` / `negative`)
  - `actionItems`: list of tasks mentioned (useful for meeting videos)

4. Merge all 3 outputs → write to Firestore `results` collection
5. Update Firestore job status → `completed`
6. On any failure → update status → `failed`, log error to Cloud Logging

---

## Frontend Pages & Components

### Page 1 — Upload Page (`/`)
- Full-page drag & drop zone
- File type + size validation on client side
- Upload progress bar (chunked upload)
- On success → redirect to `/status/{jobId}`

### Page 2 — Processing Status Page (`/status/{jobId}`)
- Animated processing indicator
- Step-by-step progress display:
  - [x] Video uploaded
  - [ ] Transcribing audio...
  - [ ] Detecting scenes...
  - [ ] Generating summary...
- Polls `GET /status/{jobId}` every 3 seconds
- On `completed` → auto-redirects to `/result/{jobId}`

### Page 3 — Results Dashboard (`/result/{jobId}`)
Split into 4 panels:

#### Panel 1 — Video Player + Timeline
- Video.js player with custom controls
- Scene boundary markers on the timeline scrubber
- Click any scene marker → video jumps to that timestamp
- Highlight markers shown as yellow dots on timeline

#### Panel 2 — AI Summary Card
- Executive summary paragraph
- Detected sentiment badge (Positive / Neutral / Negative)
- Auto-generated chapters list with jump-to buttons
- Key highlights list with clickable timestamps

#### Panel 3 — Full Transcript
- Word-by-word transcript rendered in scrollable panel
- Each word/sentence is **clickable** → video jumps to that timestamp
- Speaker labels shown (Speaker 1 / Speaker 2)
- Search bar to find specific words in transcript
- Transcript auto-scrolls to follow video playback position

#### Panel 4 — Scene & Label Analysis
- List of detected scenes with time range
- Label chips per scene (e.g. "person", "laptop", "outdoor")
- Confidence percentage shown per label
- Click a scene → video jumps to it

---

## Firestore Data Model

### Collection: `jobs`
```
jobs/{jobId}
  - jobId: string
  - status: "pending" | "processing" | "completed" | "failed"
  - filename: string
  - gcsPath: string
  - videoUrl: string
  - createdAt: timestamp
  - updatedAt: timestamp
  - processingTime: number (seconds)
  - errorMessage: string (if failed)
```

### Collection: `results`
```
results/{jobId}
  - transcript: array of word objects
  - scenes: array of scene objects
  - labels: array of label objects
```

### Collection: `summaries`
```
summaries/{jobId}
  - summary: string
  - chapters: array
  - highlights: array
  - sentiment: string
  - actionItems: array
```

---

## Cloud Storage Bucket Structure

```
raw-videos/
  {jobId}/{filename}.mp4          ← original uploaded video

processed/
  {jobId}/transcript.json         ← raw Speech-to-Text output
  {jobId}/video_intelligence.json ← raw Video Intelligence output
  {jobId}/gemini_output.json      ← raw Gemini response
```

---

## Environment Variables

### Backend (.env)
```
GCP_PROJECT_ID=your-project-id
GCP_BUCKET_NAME=video-intelligence-raw
PUBSUB_TOPIC=video-processing
FIRESTORE_DATABASE=(default)
GOOGLE_APPLICATION_CREDENTIALS=./service-account.json
MAX_VIDEO_SIZE_MB=500
ALLOWED_VIDEO_TYPES=video/mp4,video/quicktime,video/avi
```

### Frontend (.env)
```
VITE_API_BASE_URL=https://your-cloud-run-url.a.run.app
VITE_FIREBASE_API_KEY=...
VITE_FIREBASE_PROJECT_ID=...
VITE_POLL_INTERVAL_MS=3000
```

---

## Folder Structure

### Backend
```
backend/
├── main.py                  # FastAPI app entry point
├── routers/
│   ├── upload.py            # POST /upload
│   ├── status.py            # GET /status/{jobId}
│   └── result.py            # GET /result/{jobId}
├── services/
│   ├── storage.py           # GCS upload/download helpers
│   ├── firestore.py         # Firestore read/write helpers
│   └── pubsub.py            # Pub/Sub publish helper
├── middleware/
│   └── auth.py              # API key validation
├── models/
│   └── schemas.py           # Pydantic request/response models
├── Dockerfile
└── requirements.txt
```

### Worker
```
worker/
├── main.py                  # Pub/Sub subscriber entry point
├── pipeline/
│   ├── orchestrator.py      # asyncio.gather() runner
│   ├── video_intelligence.py # GCP Video Intelligence API calls
│   ├── speech_to_text.py    # GCP Speech-to-Text API calls
│   └── gemini.py            # Vertex AI Gemini calls
├── services/
│   ├── storage.py           # GCS helpers
│   └── firestore.py         # Firestore write helpers
├── Dockerfile
└── requirements.txt
```

### Frontend
```
frontend/
├── src/
│   ├── pages/
│   │   ├── UploadPage.jsx
│   │   ├── StatusPage.jsx
│   │   └── ResultPage.jsx
│   ├── components/
│   │   ├── VideoPlayer.jsx
│   │   ├── TranscriptPanel.jsx
│   │   ├── SummaryCard.jsx
│   │   ├── ScenePanel.jsx
│   │   └── UploadDropzone.jsx
│   ├── hooks/
│   │   ├── useJobStatus.js   # polling hook
│   │   └── useVideoSync.js   # transcript ↔ video sync
│   ├── services/
│   │   └── api.js            # axios API calls
│   └── App.jsx
├── .env
└── vite.config.js
```

---

## GCP Estimated Cost (V1 — Development + Testing)

| Service | Usage | Est. Cost |
|---|---|---|
| Cloud Storage | ~5GB stored + transfers | ~$5–10 |
| Video Intelligence API | ~100 videos × 3 min avg | ~$20–40 |
| Speech-to-Text API | ~300 min total | ~$10–15 |
| Vertex AI Gemini 1.5 Pro | ~500K tokens | ~$15–25 |
| Cloud Run (2 services) | Light usage | ~$5–10 |
| Pub/Sub | Negligible | ~$1–2 |
| Firestore | < 1GB + reads/writes | ~$2–5 |
| Firebase Hosting | Free tier | $0 |
| **Total** | | **~$58–107** |

Well within the $300 free trial budget.

---

## V1 Scope Boundaries (What is NOT included)

- No user authentication (V2)
- No YouTube URL input — file upload only (V2)
- No PDF export of results (V2)
- No multi-language support — English only (V2)
- No "chat with your video" feature (V2)
- No multi-video comparison (V2)
- Max video length: 10 minutes (V1 limit)
- Max file size: 500MB

---

## Week-by-Week Build Plan

| Week | Focus |
|---|---|
| Week 1 | GCP setup, Cloud Storage + Firestore config, FastAPI skeleton |
| Week 2 | Upload endpoint + GCS streaming + Pub/Sub publisher |
| Week 3 | AI Worker — Speech-to-Text + Video Intelligence pipelines |
| Week 4 | Gemini integration + result merging + Firestore writes |
| Week 5 | React frontend — Upload page + Status page |
| Week 6 | Results Dashboard — Video player + Transcript panel + Summary card |
| Week 7 | Polish, bug fixes, Cloud Run deployment, Firebase Hosting deploy |
