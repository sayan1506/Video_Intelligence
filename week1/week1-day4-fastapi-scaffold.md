# Day 4 — FastAPI Project Scaffold (Local)

**Goal:** End the day with a runnable FastAPI app locally — full folder structure created, all three endpoints responding with stub data, Pydantic schemas defined, and environment variables loading correctly.

---

## Background — what you're building today

Days 1–3 were pure GCP infrastructure. Today is the first day you write application code. The goal is **not** to connect to any GCP service yet — that's Day 5. Today is purely about getting the skeleton right: folder structure, routing, schemas, and config loading.

By the end of today, hitting `POST /upload`, `GET /status/{jobId}`, and `GET /result/{jobId}` should return valid stub JSON. The app should be runnable with a single `uvicorn` command.

---

## Step 1 — Set up the project folder and virtual environment

Navigate to your project root and create the backend folder:

```powershell
cd C:\Users\sayan\OneDrive\Desktop\Video_Intelligence
mkdir backend
cd backend
```

Create and activate a virtual environment:

```powershell
python -m venv venv
venv\Scripts\activate
```

> Always activate the venv before doing any work in this folder. You'll know it's active when you see `(venv)` in your terminal prompt.

---

## Step 2 — Install dependencies

```bash
pip install fastapi uvicorn python-dotenv google-cloud-storage google-cloud-firestore google-cloud-pubsub pydantic
```

Freeze to `requirements.txt` immediately:

```bash
pip freeze > requirements.txt
```

---

## Step 3 — Create the folder structure

From inside `backend/`, run these commands to scaffold the full directory:

```powershell
# Create package folders
mkdir routers, services, middleware, models

# Create __init__.py in each
New-Item routers\__init__.py, services\__init__.py, middleware\__init__.py, models\__init__.py -ItemType File

# Create router files
New-Item routers\upload.py, routers\status.py, routers\result.py -ItemType File

# Create service files
New-Item services\storage.py, services\firestore.py, services\pubsub.py -ItemType File

# Create remaining files
New-Item middleware\auth.py, models\schemas.py, main.py -ItemType File
```

Your folder should now look like this:

```
backend/
├── main.py
├── requirements.txt
├── .env
├── service-account.json        ← from Day 1 (never commit this)
├── routers/
│   ├── __init__.py
│   ├── upload.py
│   ├── status.py
│   └── result.py
├── services/
│   ├── __init__.py
│   ├── storage.py
│   ├── firestore.py
│   └── pubsub.py
├── middleware/
│   ├── __init__.py
│   └── auth.py
└── models/
    ├── __init__.py
    └── schemas.py
```

---

## Step 4 — Create the `.env` file

Create `backend/.env` with all the environment variables the app needs:

```env
GCP_PROJECT_ID=your-project-id
GCP_BUCKET_NAME=video-intelligence-raw
PUBSUB_TOPIC=video-processing
FIRESTORE_DATABASE=(default)
GOOGLE_APPLICATION_CREDENTIALS=./service-account.json
MAX_VIDEO_SIZE_MB=500
ALLOWED_VIDEO_TYPES=video/mp4,video/quicktime,video/avi
```

> Replace `your-project-id` with your actual GCP Project ID from Day 1.

---

## Step 5 — Create a `.gitignore`

Before anything else, make sure secrets never get committed:

```gitignore
# Secrets
.env
service-account.json

# Python
venv/
__pycache__/
*.pyc
*.pyo
.pytest_cache/

# IDE
.vscode/
.idea/
```

---

## Step 6 — Write `models/schemas.py`

Define Pydantic models for all three API responses:

```python
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


# --- Upload ---

class UploadResponse(BaseModel):
    jobId: str
    status: str
    message: str


# --- Status ---

class StatusResponse(BaseModel):
    jobId: str
    status: str          # pending | processing | completed | failed
    progress: int        # 0-100
    createdAt: Optional[datetime] = None
    updatedAt: Optional[datetime] = None


# --- Result sub-models ---

class WordTimestamp(BaseModel):
    word: str
    startTime: float
    endTime: float
    speaker: int

class Scene(BaseModel):
    startTime: float
    endTime: float
    labels: List[str]

class Chapter(BaseModel):
    title: str
    startTime: int
    endTime: int

class Highlight(BaseModel):
    timestamp: float
    description: str


# --- Result ---

class ResultResponse(BaseModel):
    jobId: str
    status: str
    videoUrl: Optional[str] = None
    transcript: Optional[List[WordTimestamp]] = None
    scenes: Optional[List[Scene]] = None
    summary: Optional[str] = None
    chapters: Optional[List[Chapter]] = None
    highlights: Optional[List[Highlight]] = None
    sentiment: Optional[str] = None
    processingTime: Optional[int] = None
```

---

## Step 7 — Write stub routers

### `routers/upload.py`

```python
from fastapi import APIRouter, UploadFile, File
from models.schemas import UploadResponse
import uuid

router = APIRouter()

@router.post("/upload", response_model=UploadResponse)
async def upload_video(file: UploadFile = File(...)):
    # Stub — will be replaced on Day 5 with real GCS + Firestore + Pub/Sub logic
    job_id = str(uuid.uuid4())
    return UploadResponse(
        jobId=job_id,
        status="pending",
        message="Video uploaded successfully"
    )
```

### `routers/status.py`

```python
from fastapi import APIRouter
from models.schemas import StatusResponse

router = APIRouter()

@router.get("/status/{job_id}", response_model=StatusResponse)
async def get_status(job_id: str):
    # Stub — will be replaced on Day 5 with real Firestore lookup
    return StatusResponse(
        jobId=job_id,
        status="pending",
        progress=0
    )
```

### `routers/result.py`

```python
from fastapi import APIRouter
from models.schemas import ResultResponse

router = APIRouter()

@router.get("/result/{job_id}", response_model=ResultResponse)
async def get_result(job_id: str):
    # Stub — will return real Firestore data once worker is built in Week 3
    return ResultResponse(
        jobId=job_id,
        status="completed",
        summary="This is a stub summary. Real data arrives in Week 3.",
        sentiment="positive",
        processingTime=0
    )
```

---

## Step 8 — Write `main.py`

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from routers import upload, status, result

load_dotenv()

app = FastAPI(
    title="VidIQ API",
    description="AI Video Intelligence backend",
    version="1.0.0"
)

# CORS — allow local Vite dev server (Week 5) and production frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",   # Vite dev server
        "http://localhost:3000",   # fallback
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers
app.include_router(upload.router)
app.include_router(status.router)
app.include_router(result.router)


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "vidiq-api"}
```

---

## Step 9 — Run and verify

Start the app:

```bash
uvicorn main:app --reload --port 8000
```

You should see:

```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

Open your browser and visit `http://127.0.0.1:8000/docs` — FastAPI auto-generates a Swagger UI. Use it to test each endpoint:

**`GET /health`**
```json
{ "status": "ok", "service": "vidiq-api" }
```

**`POST /upload`** (attach any small file in Swagger UI)
```json
{
  "jobId": "3f7a1b2c-...",
  "status": "pending",
  "message": "Video uploaded successfully"
}
```

**`GET /status/{job_id}`** (use any string as job_id)
```json
{
  "jobId": "abc123",
  "status": "pending",
  "progress": 0,
  "createdAt": null,
  "updatedAt": null
}
```

**`GET /result/{job_id}`**
```json
{
  "jobId": "abc123",
  "status": "completed",
  "summary": "This is a stub summary. Real data arrives in Week 3.",
  "sentiment": "positive",
  "processingTime": 0
}
```

---

## Important note on authentication

You'll notice the `.env` file still has `GOOGLE_APPLICATION_CREDENTIALS=./service-account.json`. This is fine for local development today. However, on Day 6 when you deploy to Cloud Run, you will **not** bundle the key file into the container — you'll attach the service account directly to the Cloud Run service and use ADC (`google.auth.default()`) instead.

The service files you write on Day 5 should use ADC from day one:

```python
# Day 5 pattern — use this, not os.environ["GOOGLE_APPLICATION_CREDENTIALS"]
from google.auth import default
credentials, project = default()
```

This way the same code works locally (reads from `GOOGLE_APPLICATION_CREDENTIALS`) and on Cloud Run (reads from the attached service account) with zero changes.

---

## Common errors and fixes

| Error | Likely cause | Fix |
|-------|-------------|-----|
| `ModuleNotFoundError: No module named 'fastapi'` | venv not activated | Run `venv\Scripts\activate` first |
| `ModuleNotFoundError: No module named 'routers'` | Running uvicorn from wrong directory | Make sure you're inside `backend/` when you run the command |
| `422 Unprocessable Entity` on `/upload` | No file attached to the request | Use Swagger UI at `/docs` — it handles multipart correctly |
| `ImportError` on dotenv | Package not installed | `pip install python-dotenv` |
| Port already in use | Something else on 8000 | Use `--port 8001` or kill the other process |

---

## End-of-day checklist

- [ ] Virtual environment created and activated
- [ ] All dependencies installed and frozen to `requirements.txt`
- [ ] Full folder structure created with all `__init__.py` files
- [ ] `.env` file created with all variables populated
- [ ] `.gitignore` in place — `service-account.json` and `.env` excluded
- [ ] `models/schemas.py` defines all Pydantic response models
- [ ] All three stub routers created
- [ ] `main.py` mounts all routers with CORS configured
- [ ] `uvicorn main:app --reload` starts without errors
- [ ] All four endpoints tested and responding via Swagger UI at `/docs`

---

## What's next

**Day 5** — Replace the stubs. You'll write the real `services/storage.py`, `services/firestore.py`, and `services/pubsub.py` helpers, then wire them into the upload and status routers so that `POST /upload` actually writes to GCS, creates a Firestore job document, and fires a Pub/Sub message.
