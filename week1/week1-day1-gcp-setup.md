# Day 1 — GCP Project Setup & Billing

**Goal:** End the day with a GCP project live, all required APIs enabled, and a service account key ready for local development.

---

## Step 1 — Create a new GCP project

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Click the project dropdown at the top → **New Project**
3. Set the project name: `video-intelligence-v1`
4. Note the auto-generated **Project ID** (you'll use this in every config file)
5. Click **Create** and wait for provisioning (~30 seconds)

---

## Step 2 — Enable billing & activate the free trial

1. In the left sidebar → **Billing**
2. Link or create a billing account
3. If you haven't already, activate the **$300 free trial credit** — this covers all of V1
4. Set a budget alert so you don't get surprised:
   - Billing → **Budgets & alerts** → Create budget
   - Set amount: `$50`
   - Alert at: 50%, 90%, 100%
   - This is a safety net — the full project should stay well under $107

---

## Step 3 — Enable required APIs

Go to **APIs & Services → Library** and search for and enable each of the following:

| API | What it's for |
|-----|---------------|
| Cloud Storage API | Store uploaded videos and processed output |
| Cloud Firestore API | Job metadata and AI results database |
| Cloud Pub/Sub API | Async message queue between backend and worker |
| Cloud Run API | Host the FastAPI backend and AI worker |
| Cloud Build API | Build Docker images for Cloud Run deployment |
| Video Intelligence API | Scene detection, label detection, object tracking |
| Cloud Speech-to-Text API | Full transcript with word-level timestamps |
| Vertex AI API | Gemini 1.5 Pro for summary, chapters, highlights |

> **Tip:** You can enable all of them in one go by searching each name, clicking on it, and hitting **Enable**. Some may already be enabled by default.

---

## Step 4 — Create a service account

This is the identity your backend code uses to talk to GCP services.

### Create the account

1. Go to **IAM & Admin → Service Accounts**
2. Click **Create Service Account**
3. Name: `video-intelligence-sa`
4. Description: `Service account for VidIQ backend and worker`
5. Click **Create and Continue**

### Assign roles

Add the following roles (click **Add Another Role** for each):

| Role | Why it's needed |
|------|-----------------|
| Storage Admin | Upload/download videos from Cloud Storage |
| Cloud Datastore User | Read/write Firestore documents |
| Pub/Sub Editor | Publish messages to the processing topic |
| Vertex AI User | Call Gemini via Vertex AI |
| Speech-to-Text Editor | Call the Speech-to-Text API |
| Video Intelligence User | Call the Video Intelligence API |

Click **Done** when all roles are assigned.

### Download the JSON key

1. Click on the service account you just created
2. Go to the **Keys** tab
3. **Add Key → Create new key → JSON**
4. Save the downloaded file as `service-account.json`
5. Place it in your `backend/` folder (you'll create this on Day 4)

> **Security note:** Never commit `service-account.json` to Git. Add it to `.gitignore` immediately when you set up the repo.

---

## End-of-day checklist

- [ ] GCP project created with a noted Project ID
- [ ] Billing linked and $300 free trial activated
- [ ] Budget alert set at $50
- [ ] All 8 APIs enabled
- [ ] Service account `video-intelligence-sa` created
- [ ] All 6 roles assigned to the service account
- [ ] `service-account.json` downloaded and stored safely

---

## What's next

**Day 2** — Cloud Storage bucket creation, Firestore collections setup, and testing GCP access from your local machine using the service account key.
