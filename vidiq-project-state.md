# VidIQ — Project State Document
## Weeks 1–4 Complete | Weeks 5–7 Remaining

**GCP Project ID:** `video-intelligence-v1`
**Service Account:** `video-intelligence-sa@video-intelligence-v1.iam.gserviceaccount.com`
**Backend URL:** `https://vidiq-api-172064784971.us-central1.run.app`
**Local project path:** `C:\Users\sayan\OneDrive\Desktop\Video_Intelligence`
**Environment:** Windows / PowerShell
**Auth constraint:** ADC-only — no JSON key files anywhere in code. Org-level policy `iam.disableServiceAccountKeyCreation` enforced. `GOOGLE_APPLICATION_CREDENTIALS` only in `.env` for local dev; Cloud Run uses attached service account.

---

## What has been built (Weeks 1–4)

### Infrastructure (Week 1)

**GCP resources created and confirmed working:**
- Artifact Registry repo: `video-api` in `us-central1`
- GCS bucket: `video-intelligence-raw` with `raw-videos/` and `processed/` folders, versioning enabled, CORS configured (GET + HEAD + OPTIONS + PUT, `localhost:5173` and production origins)
- Firestore: Native mode, `us-central1`, collections `jobs`, `results`, `summaries`
- Pub/Sub topic: `video-processing` / subscription: `video-processing-sub` (600s ack deadline, pull)
- Cloud Run backend: `vidiq-api` (latest: v8/v9/v10 depending on last deploy — check `gcloud run services describe vidiq-api`)
- Cloud Run worker: `vidiq-worker` (latest: v3, `--min-instances 1`, `--memory 1Gi`, `--no-allow-unauthenticated`)

---

### Backend — FastAPI (Weeks 1–4, deployed on Cloud Run)

**Folder:** `backend/`

#### Upload architecture — IMPORTANT deviation from original spec

The original spec had `POST /upload` accepting multipart file data. This was replaced with a two-step signed URL flow to bypass Cloud Run's 32MB request limit:

1. `POST /upload-url` — validates metadata (filename, contentType, fileSizeMb), creates Firestore job document, returns signed PUT URL for direct browser→GCS upload
2. `POST /upload-confirm` — called after browser PUT to GCS, generates signed read URL, writes `videoUrl` to Firestore, publishes Pub/Sub message

Videos never pass through Cloud Run. The browser uploads directly to GCS.

#### File: `backend/routers/upload.py`
- `POST /upload-url` endpoint — validates file metadata, creates Firestore job, returns `{ jobId, uploadUrl }`
- `POST /upload-confirm` endpoint — generates signed URL, writes to Firestore, triggers Pub/Sub
- Magic bytes validation via `utils/validators.py` was built but validation now happens client-side since the file goes direct to GCS
- Full error handling with structured logging per job ID

#### File: `backend/routers/status.py`
- `GET /status/{job_id}` — reads from Firestore `jobs` collection
- Returns `StatusResponse` with: `jobId`, `status`, `progress`, `stage` (human-readable label), `uploadProgress`, `videoUrl`, `createdAt`, `updatedAt`
- `stage` field derived from `progress_to_stage(progress, status)` in `models/schemas.py`
- 404 on unknown job, 503 on Firestore failure

#### File: `backend/routers/result.py`
- `GET /result/{job_id}` — reads from THREE Firestore collections and merges:
  - `jobs/{jobId}` → metadata (status, videoUrl, processingTime, timestamps)
  - `results/{jobId}` → transcript, scenes, labels (from worker Phase 1)
  - `summaries/{jobId}` → summary, chapters, highlights, sentiment, actionItems (from worker Phase 2)
- Returns 400 if job not completed, 404 if job not found
- Missing `results` or `summaries` doc returns 200 with null fields (not 500) — partial failure tolerance

#### File: `backend/services/firestore.py` — FULLY REWRITTEN
Key architectural decisions locked in:
- **Singleton `_db` client** — module-level `_db: firestore.Client | None = None`, one gRPC channel per process
- **`PROGRESS_STAGES` dict + `progress_for_stage()`** — single source of truth for progress integers
- **`update_job_status()` progress param is `int | None`** — field only written when explicitly passed, prevents silent progress resets
- **`create_job()` returns `job_id` string** — not the raw dict (which had non-JSON-serialisable datetimes)
- **`list_recent_jobs()` has `FailedPrecondition` exception handling** — missing composite index gives a clean error
- Functions present: `get_db()`, `create_job()`, `get_job()`, `get_result()`, `get_summary()`, `update_job_status()`, `update_upload_progress()`, `write_video_url()`, `mark_processing_started()`, `mark_processing_completed()`, `mark_processing_failed()`, `list_recent_jobs()`

#### File: `backend/services/storage.py`
- `get_signed_upload_url()` — signed PUT URL for direct browser→GCS upload, uses impersonated credentials (self-impersonation pattern)
- `get_signed_url()` — signed GET URL for video playback, uses impersonated credentials
- **CRITICAL:** `compute_engine.Credentials` fails on Cloud Run even with Token Creator role. Must use `impersonated_credentials` (self-impersonation). Token Creator role granted at project level AND as self-binding on the SA itself.
- `upload_to_gcs()` — chunked streaming upload (8MB chunks), kept for backend-side uploads if needed
- `write_processed_json()` — writes JSON to `processed/{jobId}/` in GCS

#### File: `backend/services/pubsub.py`
- `publish_job_message()` — publishes validated `JobMessage` Pydantic model
- Message attributes: `jobId`, `schemaVersion`, `contentType` (visible in GCP console without decoding)
- Retry logic: up to 3 retries with exponential backoff (0.5s, 1.0s, 2.0s) on `GoogleAPICallError`

#### File: `backend/models/schemas.py` — FINAL V1 CONTRACT
```python
# These field names are locked — frontend depends on them
class WordTimestamp: word, startTime (float), endTime (float), speaker (int=1)
class Scene: startTime (float), endTime (float), labels (List[str])
class Chapter: title (str), startTime (int), endTime (int)
class Highlight: timestamp (float), description (str)
class JobMessage: jobId, gcsPath, gcsBucket, gcsUri, filename, fileSizeMb, contentType, uploadedAt, schemaVersion
class UploadUrlRequest: filename, contentType, fileSizeMb
class UploadUrlResponse: jobId, uploadUrl
class UploadConfirmRequest: jobId
class UploadResponse: jobId, status, message
class StatusResponse: jobId, status, progress, stage, uploadProgress, videoUrl, createdAt, updatedAt
class ResultResponse: jobId, status, videoUrl, processingTime, processingStartedAt, processingCompletedAt, transcript, scenes, labels, summary, chapters, highlights, sentiment, actionItems
PROGRESS_STAGES = {0: "Queued", 10: "Uploading video...", 25: "Queued for processing", 50: "Transcribing audio...", 75: "Detecting scenes...", 90: "Generating summary...", 100: "Completed"}
```

#### File: `backend/utils/validators.py`
- `check_magic_bytes()` — validates file binary content against known video signatures (MP4, MOV, AVI)
- `validate_file_extension()` — extension allow-list check
- `MAGIC_BYTES_READ_LENGTH = 12`

#### File: `backend/utils/logging_config.py`
- `CloudRunFormatter` — JSON structured logs in Cloud Run, readable plain text locally
- Detects Cloud Run via `K_SERVICE` env var
- Called from `main.py` via `setup_logging()`

#### File: `backend/main.py`
- FastAPI app with CORS for `localhost:5173` and production Firebase Hosting domain
- Mounts all routers, calls `setup_logging()` on startup

#### Tests: `backend/tests/`
- `test_upload.py` — upload endpoint tests with mocked GCP services
- `test_status.py` — status endpoint tests
- `test_result.py` — result endpoint tests including partial failure cases
- `test_validators.py` — magic bytes and extension validation unit tests
- `test_schemas.py` — `progress_to_stage()` function tests
- **Mock patch paths:** `routers.upload.firestore`, `routers.upload.storage`, `routers.upload.pubsub`
- **Total: 44 tests passing, ~0.23s**
- Uses `httpx.AsyncClient` with `ASGITransport` (not a live server)
- `pytest.ini` has `asyncio_mode = auto`

#### GCS CORS note
- `gsutil cors get gs://video-intelligence-raw` — shows real config
- `gcloud storage describe gs://video-intelligence-raw` — shows null (known GCP display bug, ignore)
- Current CORS allows: GET, HEAD, OPTIONS, PUT from localhost:5173 and production origins
- Range request headers included: `Content-Type`, `Content-Length`, `Accept-Ranges`, `Content-Range`, `Range`

---

### Worker — AI Processing Service (Weeks 3–4, deployed on Cloud Run)

**Folder:** `worker/`

#### File: `worker/main.py`
- Streaming Pub/Sub pull subscriber (`pubsub_v1.SubscriberClient().subscribe()`)
- `FlowControl(max_messages=1)` — one job at a time
- `process_message()` callback: deserialises `JobMessage`, calls `asyncio.run(run_pipeline(job_message))`
- Ack deadline heartbeat: background thread calls `modify_ack_deadline()` every 60s (extends by 300s) while pipeline runs
- `stop_heartbeat` threading.Event in `finally` block — heartbeat always cleaned up
- Module-level `_subscriber_client` singleton shared between subscriber and heartbeat
- Malformed messages: acked immediately to prevent infinite redelivery loop
- Firestore failures on `mark_processing_started`: nacked for redelivery

#### File: `worker/pipeline/speech_to_text.py` — DEVIATED FROM ORIGINAL SPEC
Original spec: `speech_v1` `LongRunningRecognize` with speaker diarization.
Actual implementation (required to handle AAC audio in MP4):
- **`speech_v2`** (`google.cloud.speech_v2`) `BatchRecognize`
- **ffmpeg audio extraction pipeline:** downloads MP4 from GCS → extracts mono 16kHz FLAC → uploads to `processed/{jobId}/audio.flac` → sends FLAC URI to Speech-to-Text
- Uses `ExplicitDecodingConfig(encoding=FLAC, sample_rate_hertz=16000, audio_channel_count=1)`
- **Speaker diarization removed** — not supported in STT v2 `BatchRecognize`; `WordTimestamp.speaker` defaults to `1`
- `parse_transcript_response()` iterates all results, not just last one
- `FFMPEG_PATH` uses `shutil.which("ffmpeg")` for Cloud Run compatibility
- ffmpeg installed in worker Dockerfile via `apt-get install -y ffmpeg`
- Raw STT output written to `processed/{jobId}/transcript.json`

#### File: `worker/pipeline/video_intelligence.py`
- `analyse_video(gcs_uri)` — reads original MP4 directly from GCS URI (no download needed)
- Features: `SHOT_CHANGE_DETECTION` + `LABEL_DETECTION` (`SHOT_AND_FRAME_MODE`)
- `_find_labels_for_shot()` — interval overlap matching for both `segment_label_annotations` and `shot_label_annotations`
- `_seconds_from_offset()` — converts protobuf Duration (`.seconds` + `.microseconds`) to float
- `LABEL_CONFIDENCE_THRESHOLD = 0.6`, `MAX_LABELS_PER_SCENE = 10`
- Retry logic: `_poll_operation_with_retry()` wraps `operation.result()`, up to 2 retries on `ServiceUnavailable`/`DeadlineExceeded`
- Raw VI output written to `processed/{jobId}/video_intelligence.json`

#### File: `worker/pipeline/gemini.py` — REAL VERTEX AI (Week 4 complete)
- `get_gemini_model()` — lazy init, `vertexai.init(project, location="us-central1")` + `GenerativeModel("gemini-1.5-pro")`
- `GENERATION_CONFIG` — `temperature=0.2`, `max_output_tokens=2048`, `response_mime_type="application/json"`
- `build_transcript_text()` — flattens word list to string, truncates at `MAX_TRANSCRIPT_WORDS = 8000`
- `build_scene_summary()` — formats scenes as numbered list, capped at `MAX_SCENES_IN_PROMPT = 30`
- `build_prompt()` — system role + input sections + output schema + constraints
- `_call_gemini_with_retry()` — retries on `ServiceUnavailable`/`ResourceExhausted`, returns `None` on SAFETY block, logs token usage
- `parse_gemini_response()` — handles all four failure modes: JSON parse failure (returns fallback), missing fields (safe defaults), wrong types (coercion via `int(float(...))`), invalid sentiment (normalisation + near-match mapping)
- `generate_summary(transcript, scenes, duration_seconds, job_id)` — full pipeline: build → call → parse, never raises
- `_FALLBACK_SUMMARY` — returned on any unrecoverable Gemini failure
- `ALLOWED_SENTIMENTS = {"positive", "neutral", "negative"}`
- Token usage written to Firestore via `write_gemini_usage()` after each call

#### File: `worker/pipeline/orchestrator.py`
- `run_pipeline(job_message)` — three-phase async pipeline
- **Phase 1 (concurrent):** `asyncio.gather(transcribe(), analyse_video(), return_exceptions=True)`
  - Progress wrappers: `_run_stt_with_progress()` sets progress=50 on completion, `_run_vi_with_progress()` sets progress=60
  - Partial failure handling: single pipeline fail logs warning and continues, both fail marks job failed and returns False
- **Phase 2 (sequential):** `generate_summary()` from Gemini — non-fatal if it fails
- **Phase 3:** `write_results()` then `write_summary()` to Firestore, then `mark_processing_completed()`
- Progress sequence: 25 → 35 → 50 (STT done) → 60 (VI done) → 75 → 90 → 100

#### File: `worker/services/firestore.py`
- All helpers from backend `firestore.py` plus worker-specific writes:
- `write_results(job_id, transcript, scenes)` — writes to `results/{jobId}` collection
- `write_summary(job_id, summary_data)` — writes to `summaries/{jobId}` collection
- `write_gemini_usage(job_id, input_tokens, output_tokens)` — writes token counts + estimated cost to `jobs/{jobId}`

#### File: `worker/services/storage.py`
- `write_processed_json(job_id, filename, data)` — writes JSON to `processed/{jobId}/` in GCS
- GCS helpers copied from backend, same ADC pattern

#### File: `worker/models/schemas.py`
- `JobMessage` Pydantic model — must stay in sync with `backend/models/schemas.py` manually (same fields)
- `WordTimestamp`, `Scene` models

#### GCS structure after full pipeline run:
```
video-intelligence-raw/
  raw-videos/{jobId}/video.mp4              ← browser PUT directly to GCS
  processed/{jobId}/audio.flac              ← ffmpeg extraction (STT pipeline)
  processed/{jobId}/transcript.json         ← raw STT v2 output
  processed/{jobId}/video_intelligence.json ← raw Video Intelligence output
```

#### Worker Dockerfile:
- `python:3.11-slim` base
- `apt-get install -y --no-install-recommends ffmpeg`
- Entrypoint: `python main.py` (not uvicorn — worker is not an HTTP server)
- No `EXPOSE` — pulls from Pub/Sub, no inbound HTTP

#### Worker tests: `worker/tests/`
- `test_gemini_parser.py` — 30+ tests covering all parser failure modes
- `valid_response()` helper builds baseline JSON with keyword overrides

---

### Firestore data model (live in production)

```
jobs/{jobId}
  jobId, status, filename, gcsPath, videoUrl
  uploadProgress (0-100), progress (0-100), stage (string)
  createdAt, updatedAt, processingStartedAt, processingCompletedAt, processingTime
  errorMessage, geminiInputTokens, geminiOutputTokens, geminiEstimatedCostUsd

results/{jobId}
  jobId, transcript (WordTimestamp array), scenes (Scene array), labels (string array), writtenAt

summaries/{jobId}
  jobId, summary, chapters, highlights, sentiment, actionItems, writtenAt
```

---

### Frontend scaffold (Week 4 Day 7)

**Folder:** `frontend/`

**Installed and confirmed working:**
- Vite + React template
- TailwindCSS configured with content scanning `src/**/*.{js,ts,jsx,tsx}`
- `react-router-dom` with three routes: `/`, `/status/:jobId`, `/result/:jobId`
- `axios` with `api.js` service layer pointing to Cloud Run backend
- `video.js` installed
- `lucide-react`, `clsx`, `tailwind-merge`, `class-variance-authority` (shadcn/ui foundation)

**`src/services/api.js` — complete API layer:**
- `getUploadUrl(filename, contentType, fileSizeMb)` → `POST /upload-url`
- `uploadToGcs(uploadUrl, file, onProgress)` → PUT directly to GCS (not to backend)
- `confirmUpload(jobId)` → `POST /upload-confirm`
- `getStatus(jobId)` → `GET /status/{jobId}`
- `getResult(jobId)` → `GET /result/{jobId}`
- `healthCheck()` → `GET /health`

**Current page stubs (empty placeholders):**
- `UploadPage.jsx` — has connectivity test confirming API reachability, to be replaced
- `StatusPage.jsx` — reads `useParams().jobId`, renders placeholder
- `ResultPage.jsx` — reads `useParams().jobId`, renders placeholder

**CORS confirmed:** `localhost:5173` → Cloud Run backend responds without CORS errors

---

## What remains to be built (Weeks 5–7)

### Week 5 — React frontend: Upload Page + Status Page

#### Upload Page (`/`)
Full-page drag-and-drop zone with:
- Client-side file type validation (MIME + extension)
- Client-side file size validation (< 500MB)
- Chunked upload using the two-step flow:
  1. `getUploadUrl()` → get signed PUT URL
  2. `uploadToGcs()` → PUT directly to GCS with `onUploadProgress` callback
  3. `confirmUpload()` → trigger backend processing
- Upload progress bar updating from `onUploadProgress`
- On success → redirect to `/status/{jobId}` via `useNavigate()`
- Error states: wrong file type, file too large, API failure

#### Status Page (`/status/:jobId`)
- Polls `getStatus(jobId)` every `VITE_POLL_INTERVAL_MS` (3000ms) using `useJobStatus` hook
- Animated processing indicator (spinner or progress bar)
- Step-by-step progress display mapping to `stage` field from API:
  - ✓ Video uploaded (always checked when on this page)
  - ○/✓ Transcribing audio... (progress >= 50)
  - ○/✓ Detecting scenes... (progress >= 75)
  - ○/✓ Generating summary... (progress >= 90)
- Auto-redirects to `/result/{jobId}` when `status === "completed"`
- Shows error state when `status === "failed"` with `errorMessage`
- `useJobStatus` hook: manages polling interval, clears on unmount, handles 404

#### Hook: `useJobStatus.js`
- `useEffect` with `setInterval` at poll interval
- Clears interval on unmount and on status reaching terminal state (completed/failed)
- Returns `{ status, progress, stage, videoUrl, error, isLoading }`

---

### Week 6 — Results Dashboard: 4-panel layout

#### Panel 1 — Video Player + Timeline (`VideoPlayer.jsx`)
- Video.js player initialised with `videoUrl` from result
- Custom controls with scene boundary markers on the scrubber timeline
- Scene markers rendered as vertical ticks at `scene.startTime / videoDuration * 100%` width position
- Click any scene marker → `player.currentTime(scene.startTime)`
- Highlight markers as yellow dots at corresponding timeline positions
- Exposes `seekTo(seconds)` callback for transcript and scene panel clicks
- `useVideoSync` hook: tracks current playback time, updates every 250ms

#### Panel 2 — AI Summary Card (`SummaryCard.jsx`)
- Executive summary paragraph
- Sentiment badge: green (positive), gray (neutral), red (negative)
- Chapters list — each chapter is a button, click calls `seekTo(chapter.startTime)`
- Highlights list — each highlight shows timestamp + description, click calls `seekTo(highlight.timestamp)`
- `actionItems` list if non-empty

#### Panel 3 — Full Transcript (`TranscriptPanel.jsx`)
- Word-by-word rendering from `transcript` array
- Each word is a `<span>` with `onClick={() => seekTo(word.startTime)}`
- Active word highlighted based on current video time (from `useVideoSync`)
- Auto-scroll: `useEffect` watching current time, scrolls active word into view
- Search bar: filter/highlight matching words in transcript
- Speaker labels: group consecutive words by `word.speaker` into speaker blocks

#### Panel 4 — Scene & Label Analysis (`ScenePanel.jsx`)
- List of scenes with time range (`startTime`s – `endTime`s)
- Label chips per scene (coloured badges)
- Click scene → `seekTo(scene.startTime)`
- Labels from `result.labels` (flat unique list) shown as a summary at top

#### Hook: `useVideoSync.js`
- Wraps Video.js `player.on("timeupdate")` event
- Returns `currentTime` as state, updated every 250ms
- Used by TranscriptPanel for active word highlight and auto-scroll

#### Result Page layout (`ResultPage.jsx`)
- Fetches result with `getResult(jobId)` on mount
- Two-column grid (or responsive stacked layout):
  - Left column: VideoPlayer (top) + SummaryCard (below)
  - Right column: TranscriptPanel (top) + ScenePanel (below)
- Passes `seekTo` callback down from VideoPlayer to all panels via prop or context

---

### Week 7 — Polish, deployment, Firebase Hosting

#### Polish and bug fixes
- Loading states for all panels while result is fetching
- Error boundaries for each panel
- Empty state handling (no transcript, no scenes, no summary)
- Mobile responsive layout
- Page titles and meta tags

#### Firebase Hosting deployment
1. `firebase init hosting` in `frontend/`
2. Configure `firebase.json` with `public: "dist"`, SPA rewrite rule for React Router
3. `npm run build` → `firebase deploy`
4. Update backend CORS `allow_origins` to include Firebase Hosting domain
5. Update `frontend/.env.production` with production `VITE_API_BASE_URL`

#### Final Cloud Run polish
- Backend: ensure all endpoints have proper error messages
- Worker: confirm `--min-instances 1` is maintaining always-on status
- Review Cloud Logging for any recurring errors
- Final cost review against $300 budget

---

## Key architectural decisions and gotchas for future reference

**Authentication:**
- ADC everywhere — `GOOGLE_APPLICATION_CREDENTIALS` only in `.env` for local dev
- Cloud Run: attach service account via `--service-account` flag, not JSON keys
- Signed URLs on Cloud Run: must use `impersonated_credentials` (self-impersonation). `compute_engine.Credentials` fails even with Token Creator role. Token Creator granted at project level AND as self-binding on the SA.

**Upload flow:**
- `POST /upload-url` + browser PUT to GCS + `POST /upload-confirm` (not a single multipart upload)
- Signed PUT URL has 15-minute expiry
- Signed GET URL for video playback has 120-minute expiry

**Speech-to-Text:**
- STT v2 `BatchRecognize` is required for GCS URI input with MP4 files
- ffmpeg must extract audio: MP4 → mono 16kHz FLAC → upload to GCS → pass FLAC URI to STT
- Speaker diarization not available in STT v2 `BatchRecognize` — `speaker` field defaults to `1`

**Firestore:**
- `update_job_status()` `progress` param is `int | None` — only writes progress field when explicitly passed
- `create_job()` returns `job_id` string (not the job dict)
- CORS verification: use `gsutil cors get` not `gcloud storage describe` (latter shows null — known bug)

**Pub/Sub:**
- Stale messages from earlier test runs can accumulate — flush with `gcloud pubsub subscriptions seek ... --time=...`
- Worker acks malformed messages immediately, nacks Firestore failures (for redelivery)
- Ack deadline heartbeat extends deadline every 60s during long pipeline runs

**Gemini:**
- `response_mime_type="application/json"` in `GenerationConfig` forces raw JSON (no markdown fences)
- `temperature=0.2` for deterministic structured output
- `parse_gemini_response()` never raises — always returns a usable dict with fallback values
- Token usage written to `jobs/{jobId}` as `geminiInputTokens`, `geminiOutputTokens`, `geminiEstimatedCostUsd`

**Testing:**
- Backend tests mock at the router import level: `routers.upload.firestore` not `services.firestore`
- Worker parser tests use `valid_response(**overrides)` helper pattern
- `asyncio_mode = auto` in `pytest.ini` — no `@pytest.mark.asyncio` needed

---

## Environment variables reference

### `backend/.env`
```env
GCP_PROJECT_ID=video-intelligence-v1
GCP_BUCKET_NAME=video-intelligence-raw
PUBSUB_TOPIC=video-processing
FIRESTORE_DATABASE=(default)
GOOGLE_APPLICATION_CREDENTIALS=./service-account.json
MAX_VIDEO_SIZE_MB=500
ALLOWED_VIDEO_TYPES=video/mp4,video/quicktime,video/avi
```

### `worker/.env`
```env
GCP_PROJECT_ID=video-intelligence-v1
GCP_BUCKET_NAME=video-intelligence-raw
PUBSUB_SUBSCRIPTION=video-processing-sub
FIRESTORE_DATABASE=(default)
GOOGLE_APPLICATION_CREDENTIALS=../backend/service-account.json
```

### `frontend/.env`
```env
VITE_API_BASE_URL=https://vidiq-api-172064784971.us-central1.run.app
VITE_POLL_INTERVAL_MS=3000
```

---

## Remaining V1 scope (from original spec — not yet built)

- Upload Page: drag-and-drop zone, file validation UI, upload progress bar
- Status Page: animated processing indicator, step-by-step stage display, auto-redirect on completion
- Result Dashboard: all four panels (VideoPlayer, SummaryCard, TranscriptPanel, ScenePanel)
- `useJobStatus` polling hook
- `useVideoSync` video time tracking hook
- Firebase Hosting deployment
- Mobile responsive layout
- Loading/error/empty states for all panels

## What is explicitly NOT in V1 scope

- User authentication (V2)
- YouTube URL input (V2)
- PDF export (V2)
- Multi-language support (V2)
- Chat with your video (V2)
- Multi-video comparison (V2)
- Speaker diarization (was in spec, removed due to STT v2 limitation — V2)
