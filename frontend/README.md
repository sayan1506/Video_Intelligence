# VidIQ Frontend

React single-page app for VidIQ — the user-facing surface for uploading videos, watching processing progress, and exploring the AI intelligence report (transcript, scenes, summary, chapters, highlights, Q&A). It talks to the FastAPI backend over HTTP and authenticates users with Firebase.

## Tech stack

- **Framework:** React 19 + Vite
- **Routing:** React Router v7
- **Styling:** Tailwind CSS v4 (`@tailwindcss/vite`), with a custom light/dark "gold" theme
- **Auth:** Firebase Authentication (Google Sign-In)
- **HTTP:** Axios — a request interceptor attaches the Firebase ID token to every call
- **Video:** Video.js
- **Exports:** `jspdf` for PDF; SRT/VTT generated in-browser
- **Payments:** Razorpay Checkout (loaded via `<script>` in `index.html`)
- **Icons:** lucide-react
- **Testing:** Vitest + Testing Library + fast-check (property-based)
- **Hosting:** Firebase Hosting

## App structure & state

`src/main.jsx` wraps the app in two context providers:

- **`ThemeProvider`** (`contexts/ThemeContext.jsx`) — light/dark mode, persisted to `localStorage` (`vidiq-theme`), toggles the `dark` class on `<html>`. Defaults to dark.
- **`AuthProvider`** (`contexts/AuthContext.jsx`) — exposes `user`, `loading`, `signIn()`, `signOut()`, `getToken()`. Wraps Firebase `onAuthStateChanged`.

`App.jsx` defines the routes. Protected routes are wrapped in `<PrivateRoute>`, which redirects unauthenticated users to `/` (and shows a spinner while auth state resolves).

## Pages / routes

| Route | Component | Access | Purpose |
|-------|-----------|--------|---------|
| `/` | `LandingPage` | public | Marketing landing + Google sign-in entry |
| `/pricing` | `PricingPage` | public | Free vs Pro plans; triggers Razorpay checkout |
| `/billing/success` | `BillingSuccessPage` | public | Post-payment page; polls `GET /billing/status` until plan flips to `pro` |
| `/share/:jobId` | `SharePage` | public | Read-only view of a publicly shared result |
| `/dashboard` | `DashboardPage` | private | The user's jobs, quota usage, thumbnails |
| `/upload` | `UploadPage` | private | Drag-and-drop upload (up to 2 GB) with progress |
| `/status/:jobId` | `StatusPage` | private | Live processing progress (polls `GET /status/{id}`) |
| `/result/:jobId` | `ResultPage` | private | Full result dashboard: player, summary, transcript, scenes, Q&A |
| `/admin` | `AdminDashboard` | private (admin UID) | Aggregate stats + all-jobs table; UID-gated client-side, 403-gated server-side |

### Key components
`VideoPlayer`, `TranscriptPanel`, `ScenePanel`, `SummaryCard`, `ProcessingStats`, `QAPanel`, `JobCard`, `UploadDropzone`, `ShareToggle`, `CopyLinkButton`, `ThemeToggle`.

### Hooks & libs
- `hooks/useJobStatus.js` — polls `GET /status/{id}` on `VITE_POLL_INTERVAL_MS` (default 3 s), stops on `completed`/`failed`.
- `hooks/useVideoSync.js` — syncs the player with transcript/scene clicks (seek-to-timestamp).
- `lib/exporters.js` — pure functions for SRT/VTT timecode generation and PDF export.
- `lib/firebase.js` — Firebase app init + Google provider.
- `services/api.js` — all backend calls, with the auth-token interceptor.

## Upload flow (client side)

Videos go **directly to Cloud Storage**, never through the backend:

1. `getUploadUrl()` → `POST /upload-url` returns a resumable GCS upload URI.
2. `uploadToGcs()` PUTs the file to GCS in 8 MB chunks with `Content-Range` headers (308 between chunks, 200 on the last). On the final chunk a CORS-blocked 200 is treated as success.
3. `confirmUpload()` → `POST /upload-confirm` tells the backend to enqueue the worker job.
4. The app navigates to `/status/:jobId` and polls until processing completes.

## Firebase config

Firebase is configured entirely through Vite env vars (`import.meta.env.VITE_FIREBASE_*`) in `src/lib/firebase.js`. No config is hard-coded. Get the values from the Firebase console → Project settings → Your apps.

Required:
```
VITE_FIREBASE_API_KEY
VITE_FIREBASE_AUTH_DOMAIN
VITE_FIREBASE_PROJECT_ID
VITE_FIREBASE_STORAGE_BUCKET
VITE_FIREBASE_MESSAGING_SENDER_ID
VITE_FIREBASE_APP_ID
```

Hosting is configured in `firebase.json` — it serves `dist/` and rewrites all paths to `/index.html` (SPA fallback for client-side routing).

## Environment variables

Copy `.env.example` to `.env` (or `.env.local`) for development; use `.env.production` for builds.

| Variable | Example | Purpose |
|----------|---------|---------|
| `VITE_API_BASE_URL` | `https://vidiq-api-…run.app` | Backend base URL (Axios `baseURL`) |
| `VITE_POLL_INTERVAL_MS` | `3000` | Status-polling interval |
| `VITE_FIREBASE_API_KEY` | — | Firebase web API key |
| `VITE_FIREBASE_AUTH_DOMAIN` | `your-project.firebaseapp.com` | Firebase auth domain |
| `VITE_FIREBASE_PROJECT_ID` | `video-intelligence-v1` | Firebase project id |
| `VITE_FIREBASE_STORAGE_BUCKET` | `your-project.appspot.com` | Firebase storage bucket |
| `VITE_FIREBASE_MESSAGING_SENDER_ID` | — | Firebase messaging sender id |
| `VITE_FIREBASE_APP_ID` | — | Firebase app id |

> Vite only exposes vars prefixed with `VITE_` to client code. Everything here ships to the browser — never put secrets in these files. `.env.production.example` is committed as a template; real values go in the uncommitted `.env.production`.

## Run locally

### Prerequisites
- Node.js 18+ (Vite 8) and npm
- A running backend (local or deployed) reachable at `VITE_API_BASE_URL`
- A Firebase project with Google Sign-In enabled

### Setup & dev server

```bash
npm install
cp .env.example .env          # then fill in values
npm run dev
```

Dev server runs at http://localhost:5173 (this origin must be in the backend's `ALLOWED_ORIGINS` and the GCS bucket CORS config).

### Tests & lint

```bash
npm test          # vitest --run
npm run lint      # eslint
```

## Build & deploy

```bash
# Build production bundle into dist/
npm run build

# Preview the production build locally
npm run preview

# Deploy to Firebase Hosting (uses firebase.json)
firebase deploy --only hosting
```

`npm run build` reads `.env.production`, so set `VITE_API_BASE_URL` and the Firebase vars there before building. The build output lands in `dist/`, which `firebase.json` serves with an SPA rewrite to `/index.html`.

## Project structure

```
frontend/
├── index.html               # Loads Razorpay checkout + Google Fonts; mounts /src/main.jsx
├── src/
│   ├── main.jsx             # Root render; wraps app in ThemeProvider + AuthProvider
│   ├── App.jsx              # Routes + PrivateRoute guard
│   ├── pages/               # One component per route (see table above)
│   ├── components/          # Player, panels, cards, toggles, dropzone
│   ├── contexts/            # AuthContext, ThemeContext
│   ├── hooks/               # useJobStatus, useVideoSync
│   ├── lib/                 # firebase, exporters (SRT/VTT/PDF), utils
│   ├── services/api.js      # Axios client + all backend calls
│   ├── index.css / App.css  # Tailwind + theme styles
│   └── __tests__/           # Vitest + fast-check property tests
├── firebase.json            # Hosting config (serves dist/, SPA rewrite)
├── vite.config.js           # Vite + React + Tailwind plugins; Vitest config
└── package.json
```
