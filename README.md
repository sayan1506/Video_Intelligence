# VidIQ — AI Video Intelligence

VidIQ turns a video upload into a full AI intelligence report. Upload a video (up to 2 GB), and within a couple of minutes you get back a word-level transcript with clickable timestamps, detected scenes with content labels, auto-generated chapters, key highlights, sentiment analysis, an executive summary, multi-language translation, and — for Pro users — natural-language Q&A over the transcript (RAG).

It is a three-service system on Google Cloud: a **frontend** SPA, a **backend** API, and an **AI worker**, glued together by Cloud Storage, Pub/Sub, and Firestore.

---

## What it does

Three AI pipelines run on each video:

- **Speech-to-Text v2** — word-level transcript with timestamps. Long videos are split into 5-minute chunks and transcribed in parallel; videos over 30 min use 8 kHz extraction.
- **Video Intelligence** — shot-change detection and label detection (person, laptop, whiteboard, …) per scene.
- **Vertex AI Gemini 2.5 Flash** — reads transcript + scenes and produces a summary, chapters, highlights, sentiment, and action items. Also handles transcript translation and powers RAG Q&A.

Results land in an interactive dashboard: a Video.js player with scene markers, a summary card with chapter navigation, a searchable transcript (click a word to seek), a scene panel, and a Q&A panel.

---

## Architecture

Videos **never pass through the backend** — the browser uploads directly to Cloud Storage. The backend is a thin control plane; all heavy AI work happens in the worker.

```
                          ┌──────────────────────────────────────────────┐
                          │                Google Cloud                   │
                          │                                               │
  ┌──────────┐   HTTPS    │   ┌───────────┐         ┌─────────────────┐   │
  │ Frontend │◄──────────►│   │  Backend  │────────►│   Firestore     │   │
  │ (React,  │            │   │ (FastAPI, │◄────────│ jobs / results  │   │
  │  Firebase│  1. /upload-url│  Cloud Run)│        │ summaries/users │   │
  │  Hosting)│            │   └─────┬─────┘         └────────▲────────┘   │
  └────┬─────┘            │         │                        │            │
       │                  │  3. publish JobMessage           │ 5. write   │
       │ 2. resumable     │         ▼                        │  results   │
       │    upload        │   ┌───────────┐  4. consume ┌────┴────────┐   │
       └─────────────────►│   │  Pub/Sub  │────────────►│   Worker    │   │
       (direct to GCS)    │   │  topic +  │             │ (Python,    │   │
       ┌──────────────┐   │   │   sub     │             │  Cloud Run, │   │
       │ Cloud Storage │◄──┼──┤           │             │  ffmpeg)    │   │
       │ raw + processed│  │   └───────────┘             └──────┬──────┘   │
       └──────────────┘   │         ▲                          │          │
              ▲           │         │      ┌───────────────────┼───────┐  │
              │           │         └──────┤ Speech-to-Text v2  │       │  │
              └───────────┼────────────────┤ Video Intelligence │ AI    │  │
              (read video) │                │ Vertex AI (Gemini, │ APIs  │  │
                          │                │ embeddings)        │       │  │
                          │                └────────────────────┴───────┘  │
                          └──────────────────────────────────────────────┘
```

### End-to-end flow

1. Frontend requests a resumable upload URI — `POST /upload-url`. Backend validates the file, enforces the monthly quota, and creates the `jobs/{jobId}` document.
2. Browser uploads the video **directly to Cloud Storage** in 8 MB chunks (resumable protocol).
3. Frontend calls `POST /upload-confirm`; backend publishes a `JobMessage` to the Pub/Sub topic.
4. Worker (a Pub/Sub subscriber) consumes the message and runs all pipelines — concurrent STT + Video Intelligence, then Gemini, then embeddings.
5. Worker writes results to Firestore (transcript as a chunked subcollection) and deletes the raw video.
6. Frontend polls `GET /status/{jobId}` until `completed`, then loads `GET /result/{jobId}` and renders the dashboard.

---

## Tech stack

| Layer | Technology |
|-------|------------|
| Frontend | React 19, Vite, Tailwind CSS v4, React Router v7, Video.js, Axios |
| Backend API | FastAPI (Python 3.11), Uvicorn — Cloud Run |
| AI Worker | Python 3.11, ffmpeg — Cloud Run (Pub/Sub subscriber) |
| AI APIs | Speech-to-Text v2, Video Intelligence API, Vertex AI Gemini 2.5 Flash, `text-embedding-004` |
| Auth | Firebase Authentication (Google Sign-In) |
| Storage | Google Cloud Storage |
| Database | Firestore (Native mode + vector search) |
| Queue | Pub/Sub |
| Payments | Razorpay subscriptions |
| Hosting | Firebase Hosting (frontend), Cloud Run (backend + worker), Artifact Registry (images) |

All GCP access uses **Application Default Credentials** — there are no service-account JSON key files anywhere in the code.

---

## Folder structure

```
Video_Intelligence/
├── Backend/                 # FastAPI REST API (Cloud Run) — see Backend/README.md
│   ├── main.py              #   App entry, CORS, router registration
│   ├── routers/             #   upload, status, result, jobs, thumbnail, qa, quota, billing, admin
│   ├── services/            #   storage (GCS), firestore, pubsub
│   ├── middleware/auth.py   #   Firebase token verification
│   ├── models/schemas.py    #   Pydantic models + progress map
│   ├── utils/               #   validators, logging
│   └── tests/               #   pytest + Hypothesis
│
├── worker/                  # AI processing worker (Cloud Run) — see worker/README.md
│   ├── main.py              #   Pub/Sub subscriber loop, idempotency, ack heartbeat
│   ├── pipeline/            #   orchestrator, speech_to_text, video_intelligence, gemini, embeddings
│   ├── services/            #   firestore, storage
│   ├── models/schemas.py    #   JobMessage, WordTimestamp, Scene
│   └── tests/               #   pytest + Hypothesis
│
├── frontend/                # React/Vite SPA (Firebase Hosting) — see frontend/README.md
│   ├── src/
│   │   ├── pages/           #   Landing, Upload, Status, Result, Dashboard, Pricing, Admin, Share
│   │   ├── components/      #   player, panels, cards, toggles
│   │   ├── contexts/        #   AuthContext, ThemeContext
│   │   ├── hooks/           #   useJobStatus, useVideoSync
│   │   ├── lib/             #   firebase, exporters (SRT/VTT/PDF)
│   │   └── services/api.js  #   Axios client
│   └── firebase.json        #   Hosting config
│
└── README.md                # This file
```

Each service has its own README with full detail — start there for endpoint tables, pipeline stages, and per-service env vars.

---

## How the pieces connect

- **Frontend ↔ Backend:** HTTPS + Firebase ID tokens (Axios interceptor attaches the bearer token). The backend verifies tokens with the Firebase Admin SDK.
- **Frontend ↔ Cloud Storage:** the browser uploads video bytes directly via a resumable URI; the backend only issues the URI.
- **Backend → Pub/Sub → Worker:** the backend publishes a validated `JobMessage`; the worker is a pull subscriber (`max_messages=1`) with an idempotency guard and an ack-deadline heartbeat for long jobs.
- **Backend ↔ Worker (shared state):** they never call each other directly. They communicate through **Firestore** — the worker writes `results/`, `summaries/`, and transcript chunks; the backend reads them. Both share an identical progress-stage map.
- **RAG Q&A:** the worker embeds transcript chunks into Firestore `Vector` fields; the backend runs COSINE `find_nearest` search at query time and feeds the top chunks to Gemini.

### Firestore collections

| Collection | Written by | Contents |
|------------|-----------|----------|
| `jobs/{jobId}` | backend + worker | status, progress, ownership, `isPublic`, timestamps, cost estimates, thumbnail path |
| `results/{jobId}` | worker | scenes, labels, `detectedLanguage`, `transcriptChunkCount` |
| `results/{jobId}/transcript_chunks/{i}` | worker | 300-word transcript chunks + 768-dim embedding vectors |
| `summaries/{jobId}` | worker | summary, chapters, highlights, sentiment, action items, translated transcript |
| `users/{uid}` | backend | plan, Razorpay subscription id, monthly job counters |

---

## Quick start

You need a GCP project with Storage, Firestore, Pub/Sub, Speech-to-Text, Video Intelligence, and Vertex AI APIs enabled; a Pub/Sub topic + subscription; a GCS bucket (with CORS allowing your frontend origin); and a Firebase project with Google Sign-In. Authenticate ADC once:

```bash
gcloud auth application-default login
```

Run the three services in three terminals.

**1. Backend** (`Backend/`)
```bash
python -m venv venv && venv\Scripts\Activate.ps1   # Windows PowerShell
pip install -r requirements.txt
cp .env.example .env                                # fill in values
uvicorn main:app --reload --port 8080
```

**2. Worker** (`worker/`) — requires `ffmpeg` on PATH
```bash
python -m venv venv && venv\Scripts\Activate.ps1
pip install -r requirements.txt
# create .env with GCP_PROJECT_ID, PUBSUB_SUBSCRIPTION, GCP_BUCKET_NAME, GCP_SERVICE_ACCOUNT_EMAIL
python main.py
```

**3. Frontend** (`frontend/`) — requires Node 18+
```bash
npm install
cp .env.example .env                                # set VITE_API_BASE_URL + Firebase vars
npm run dev                                         # http://localhost:5173
```

Open http://localhost:5173, sign in with Google, and upload a video. Watch progress on the status page, then explore the result dashboard.

---

## Environment setup

Each service reads its own config; see the per-service READMEs for full tables. The essentials:

**Backend** (`.env` / `env.yaml`) — `GCP_PROJECT_ID`, `GCP_BUCKET_NAME`, `PUBSUB_TOPIC`, `GCP_SERVICE_ACCOUNT_EMAIL`, `ALLOWED_ORIGINS`, `FRONTEND_BASE_URL`, plan limits, `ADMIN_UID`, and Razorpay keys.

**Worker** (`.env` / `env.yaml`) — `GCP_PROJECT_ID`, `PUBSUB_SUBSCRIPTION`, `GCP_BUCKET_NAME`, `GCP_SERVICE_ACCOUNT_EMAIL`, `GCP_REGION`.

**Frontend** (`.env` / `.env.production`) — `VITE_API_BASE_URL`, `VITE_POLL_INTERVAL_MS`, and the six `VITE_FIREBASE_*` values.

> **Security:** the committed `Backend/env.yaml` contains live Razorpay credentials and a webhook secret. Rotate them and move secrets to Secret Manager — `VITE_*` values are public by design, but server-side secrets must never be committed.

---

## Deployment

- **Backend & Worker → Cloud Run.** Build images with Cloud Build → Artifact Registry, then `gcloud run deploy` with the service account and `--env-vars-file env.yaml`. The worker needs `--min-instances 1` (it's an always-pulling subscriber) plus extra CPU/memory for ffmpeg. Full commands are in `Backend/README.md` and `worker/README.md`.
- **Frontend → Firebase Hosting.** `npm run build` then `firebase deploy --only hosting` (serves `dist/` with an SPA rewrite).

---

## Testing

| Service | Command | Coverage |
|---------|---------|----------|
| Backend | `pytest` | Access control, job creation, public sharing, optional-auth, QA, validators (incl. Hypothesis) |
| Worker | `pytest` | Orchestrator routing, STT chunking/sample rate, Gemini + translation parsers, embeddings, pipeline regression |
| Frontend | `npm test` | Components, theme, exporters, share page (Vitest + fast-check) |
