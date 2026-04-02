# VidIQ Backend

FastAPI backend for the VidIQ AI video intelligence application.

## Tech stack

- **Framework:** FastAPI (Python 3.11)
- **Deployment:** Google Cloud Run
- **Auth:** ADC (Application Default Credentials) — no key files

## Local setup

### Prerequisites
- Python 3.11+
- GCP project with required APIs enabled (see project docs)
- `service-account.json` from GCP IAM (never commit this)
- `gcloud` CLI installed and authenticated

### Install

```bash
python -m venv venv
venv\Scripts\activate        # Windows PowerShell
pip install -r requirements.txt
```

### Environment variables

Copy `.env.example` to `.env` and fill in your values:

```env
GCP_PROJECT_ID=your-project-id
GCP_BUCKET_NAME=video-intelligence-raw
PUBSUB_TOPIC=video-processing
FIRESTORE_DATABASE=(default)
GOOGLE_APPLICATION_CREDENTIALS=./service-account.json
MAX_VIDEO_SIZE_MB=500
ALLOWED_VIDEO_TYPES=video/mp4,video/quicktime,video/avi
```

### Run locally

```bash
uvicorn main:app --reload --port 8000
```

API docs available at: http://127.0.0.1:8000/docs

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | /health | Health check |
| POST | /upload | Upload a video file |
| GET | /status/{jobId} | Get job processing status |
| GET | /result/{jobId} | Get AI results for a completed job |

## Deploy to Cloud Run

```bash
# Build and push image
gcloud builds submit \
  --tag us-central1-docker.pkg.dev/YOUR_PROJECT/video-api/backend:v1

# Deploy
gcloud run deploy vidiq-api \
  --image us-central1-docker.pkg.dev/YOUR_PROJECT/video-api/backend:v1 \
  --region us-central1 \
  --service-account video-intelligence-sa@YOUR_PROJECT.iam.gserviceaccount.com
```

## Project structure

```
backend/
├── main.py                 # FastAPI app entry point
├── routers/                # Route handlers
├── services/               # GCP service helpers (Storage, Firestore, Pub/Sub)
├── middleware/             # Auth middleware (JWT in V2)
├── models/                 # Pydantic request/response schemas
└── utils/                  # Logging config
```

---