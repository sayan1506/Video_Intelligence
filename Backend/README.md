# VidIQ Backend

FastAPI REST API for the VidIQ AI video intelligence platform. It runs on Google Cloud Run and acts as the control plane: it issues direct-to-GCS upload URLs, tracks job state in Firestore, triggers the AI worker via Pub/Sub, serves processed results, handles billing (Razorpay), per-user quotas, public share links, and RAG Q&A over transcripts.

Videos never flow through this service — the browser uploads directly to Cloud Storage using a resumable upload session that the backend hands out.

## Tech stack

- **Framework:** FastAPI (Python 3.11), served by Uvicorn
- **Auth:** Firebase Authentication — ID tokens verified with the Firebase Admin SDK
- **Cloud credentials:** Application Default Credentials (ADC) — no service-account JSON key files
- **GCP services:** Cloud Storage, Firestore (Native mode), Pub/Sub, Vertex AI (Gemini + embeddings)
- **Payments:** Razorpay subscriptions
- **Deployment:** Google Cloud Run (containerised via the included Dockerfile)

## Architecture role

```
Browser ──► Backend (this service) ──► Firestore        (job metadata, results, users)
   │              │
   │              ├──► Cloud Storage   (issues resumable upload URI)
   │              └──► Pub/Sub topic   (publishes JobMessage → worker)
   │
   └────────► Cloud Storage (direct resumable upload, bypasses backend)
```

The backend writes the initial job document, then publishes a `JobMessage` to the Pub/Sub topic. The separate **worker** service consumes that message, runs the AI pipelines, and writes results back to Firestore. The backend reads those results when the frontend requests them.

## API endpoints

All authenticated routes expect an `Authorization: Bearer <Firebase ID token>` header. Routes marked *optional auth* are publicly reachable but return richer data (or owner-only access) when a valid token is present.

### Health
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/health` | none | Liveness check — returns `{"status": "ok", "service": "vidiq-api"}` |

### Upload
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/upload-url` | required | Validates MIME type, extension, declared size, and (optional) magic-bytes header; enforces the monthly plan quota; creates the Firestore job; returns a resumable GCS upload URI (`{jobId, uploadUrl, gcsPath}`) |
| POST | `/upload-confirm` | required | Called after the browser finishes its direct GCS upload. Marks the job pending and publishes the `JobMessage` to Pub/Sub to trigger the worker |

`POST /upload-url` accepts `filename`, `content_type`, `file_size_bytes` as query params and an optional `X-File-Header` header (first 12 bytes of the file, hex-encoded) for server-side magic-bytes validation.

### Status & results
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/status/{job_id}` | required (owner) | Current status, numeric progress, derived stage label, upload progress, timestamps. Returns 404 to non-owners to avoid leaking job existence |
| GET | `/result/{job_id}` | optional | Full result: transcript, scenes, labels, summary, chapters, highlights, sentiment, action items, cost breakdown, detected language, translated transcript. Owner sees any status; non-owners/anonymous only if `isPublic && completed` |
| GET | `/video-url/{job_id}` | optional | Fresh signed GCS URL (7-day expiry) for the video player; same access rules as `/result` |
| GET | `/thumbnail-url/{job_id}` | required (owner) | Signed URL (1-hour expiry) for the worker-extracted thumbnail at `processed/{jobId}/thumbnail.jpg` |

### Jobs & sharing
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/jobs?limit=` | required | The caller's jobs, newest first (1–100, default 20). Needs a Firestore composite index on `(userId ASC, createdAt DESC)` |
| PATCH | `/jobs/{job_id}/share` | required (owner) | Toggle `isPublic` for a completed job; returns the public share URL when enabled |

### Q&A (RAG)
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/qa/{job_id}` | required (Pro) | Embeds the question (`text-embedding-004`, `RETRIEVAL_QUERY`), runs Firestore COSINE vector search over `transcript_chunks`, and answers with Gemini 2.5 Flash. Returns the answer plus source timestamps. 402 for non-Pro users |

### Quota
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/quota` | required | `{plan, jobsThisMonth, monthlyLimit, resetDate}` — used by the dashboard and upload page |

### Billing (Razorpay)
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/billing/create-checkout-session` | required | Creates (or reuses) a Razorpay subscription for the Pro plan; returns `{subscriptionId, keyId}` for the browser checkout widget |
| POST | `/billing/webhook` | none (HMAC-verified) | Razorpay lifecycle events. Verifies the `X-Razorpay-Signature` HMAC-SHA256 against `RAZORPAY_WEBHOOK_SECRET`. Upgrades/downgrades the user plan |
| GET | `/billing/status` | required | Returns `{plan}` — polled by the success page until the webhook flips `free → pro` |

### Admin
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/admin/stats` | required (admin UID) | Aggregate stats across all jobs: counts by status, total estimated cost, avg processing time, top 20 users |
| GET | `/admin/jobs?limit=` | required (admin UID) | Recent jobs across all users (max 50) |

Admin access is gated by the `ADMIN_UID` env var; non-matching UIDs get 403.

## Environment variables

Copy `.env.example` to `.env` for local development. In production these are supplied via Cloud Run (see `env.yaml`).

| Variable | Required | Example / default | Purpose |
|----------|----------|-------------------|---------|
| `GCP_PROJECT_ID` | yes | `video-intelligence-v1` | GCP project for all clients |
| `GCP_BUCKET_NAME` | yes | `video-intelligence-raw` | Storage bucket for raw + processed objects |
| `PUBSUB_TOPIC` | yes | `video-processing` | Topic the worker subscribes to |
| `FIRESTORE_DATABASE` | no | `(default)` | Firestore database id |
| `GCP_SERVICE_ACCOUNT_EMAIL` | yes | `…-sa@…iam.gserviceaccount.com` | Principal impersonated to mint v4 signed URLs |
| `GCP_REGION` | no | `us-central1` | Vertex AI location for QA embeddings/Gemini |
| `MAX_VIDEO_SIZE_MB` | no | `500` (prod uses `2048`) | Server-side upload size cap |
| `ALLOWED_VIDEO_TYPES` | no | `video/mp4,video/quicktime,…` | Accepted MIME types |
| `ALLOWED_ORIGINS` | no | `http://localhost:5173,…` | Comma-separated CORS allowlist |
| `FRONTEND_BASE_URL` | no | `https://video-intelligence-v1.web.app` | Used to construct public share URLs |
| `FREE_PLAN_MONTHLY_LIMIT` | no | `5` | Monthly video limit for the free plan |
| `PRO_PLAN_MONTHLY_LIMIT` | no | `50` | Monthly video limit for the Pro plan |
| `ADMIN_UID` | yes (for admin) | Firebase UID | Single admin user allowed on `/admin/*` |
| `FIREBASE_PROJECT_ID` | no | `video-intelligence-v1` | Firebase project for token verification |
| `RAZORPAY_KEY_ID` | yes (for billing) | `rzp_live_…` | Razorpay API key id |
| `RAZORPAY_KEY_SECRET` | yes (for billing) | secret | Razorpay API secret |
| `RAZORPAY_PRO_PLAN_ID` | yes (for billing) | `plan_…` | Razorpay plan id for the Pro subscription |
| `RAZORPAY_WEBHOOK_SECRET` | yes (for billing) | secret | HMAC secret for webhook signature verification |

> **Security note:** `env.yaml` in this directory currently contains live Razorpay credentials and the webhook secret. Treat these as exposed, rotate them, and move secrets to Secret Manager rather than committing them.

## Run locally

### Prerequisites
- Python 3.11+
- `gcloud` CLI authenticated for ADC: `gcloud auth application-default login`
- Access to the GCP project with Storage, Firestore, Pub/Sub, and Vertex AI APIs enabled

### Setup

```powershell
python -m venv venv
venv\Scripts\Activate.ps1        # Windows PowerShell
pip install -r requirements.txt
cp .env.example .env             # then fill in values
```

### Start the server

```bash
uvicorn main:app --reload --port 8080
```

Interactive API docs (Swagger UI): http://127.0.0.1:8080/docs

### Tests

```bash
pytest
```

The suite uses `pytest` plus Hypothesis property-based tests covering access control, job creation, public sharing, optional-auth behavior, QA, and validators.

## Project structure

```
Backend/
├── main.py                 # FastAPI app, CORS, router registration, /health
├── routers/                # One module per feature area
│   ├── upload.py           #   POST /upload-url, /upload-confirm
│   ├── status.py           #   GET /status/{id}
│   ├── result.py           #   GET /result/{id}, /video-url/{id}
│   ├── jobs.py             #   GET /jobs, PATCH /jobs/{id}/share
│   ├── thumbnail.py        #   GET /thumbnail-url/{id}
│   ├── qa.py               #   POST /qa/{id}  (RAG)
│   ├── quota.py            #   GET /quota
│   ├── billing.py          #   Razorpay checkout, webhook, status
│   └── admin.py            #   GET /admin/stats, /admin/jobs
├── services/               # GCP integration helpers
│   ├── storage.py          #   Resumable uploads, signed URLs (impersonation)
│   ├── firestore.py        #   Jobs, results, users, quota, vector search, admin
│   └── pubsub.py           #   Publishes validated JobMessage with retry
├── middleware/
│   └── auth.py             #   Firebase token verification dependencies
├── models/
│   └── schemas.py          #   Pydantic request/response models + progress map
├── utils/
│   ├── validators.py       #   Magic-bytes + extension validation
│   └── logging_config.py   #   Structured JSON logs on Cloud Run
├── tests/                  # pytest + Hypothesis
├── Dockerfile
├── env.yaml                # Cloud Run env vars (see security note above)
└── requirements.txt
```

## Deploy to Cloud Run

Build and push the image (Artifact Registry), then deploy with the env vars from `env.yaml`:

```bash
# Build & push
gcloud builds submit \
  --tag us-central1-docker.pkg.dev/video-intelligence-v1/video-api/backend:latest

# Deploy
gcloud run deploy vidiq-api \
  --image us-central1-docker.pkg.dev/video-intelligence-v1/video-api/backend:latest \
  --region us-central1 \
  --service-account video-intelligence-sa@video-intelligence-v1.iam.gserviceaccount.com \
  --env-vars-file env.yaml \
  --allow-unauthenticated
```

The container listens on `$PORT` (default 8080) and starts Uvicorn via the Dockerfile `CMD`. The attached service account supplies ADC at runtime — no key files are mounted. It needs roles for Storage object admin, Firestore user, Pub/Sub publisher, Vertex AI user, and token creator (for signed-URL impersonation).
