import axios from 'axios'

const BASE_URL = import.meta.env.VITE_API_BASE_URL

const api = axios.create({
  baseURL: BASE_URL,
  timeout: 30000,
})

/**
 * Request a signed PUT URL for direct browser-to-GCS upload.
 * Corresponds to POST /upload-url on the backend.
 */
export async function getUploadUrl(filename, contentType, fileSizeMb) {
  const response = await api.post('/upload-url', {
    filename,
    contentType,
    fileSizeMb,
  })
  return response.data  // { jobId, uploadUrl }
}

/**
 * Upload a file directly to GCS using the signed PUT URL.
 * This call goes to GCS, not to the backend — bypasses Cloud Run entirely.
 */
export async function uploadToGcs(uploadUrl, file, onProgress) {
  await axios.put(uploadUrl, file, {
    headers: { 'Content-Type': file.type },
    onUploadProgress: (progressEvent) => {
      if (onProgress && progressEvent.total) {
        const percent = Math.round((progressEvent.loaded / progressEvent.total) * 100)
        onProgress(percent)
      }
    },
  })
}

/**
 * Confirm the GCS upload is complete and trigger the AI worker via Pub/Sub.
 * Corresponds to POST /upload-confirm on the backend.
 */
export async function confirmUpload(jobId) {
  const response = await api.post('/upload-confirm', { jobId })
  return response.data  // { jobId, status, message }
}

/**
 * Poll the current job status.
 * Corresponds to GET /status/{jobId} on the backend.
 */
export async function getStatus(jobId) {
  const response = await api.get(`/status/${jobId}`)
  return response.data
  // { jobId, status, progress, stage, uploadProgress, videoUrl, createdAt, updatedAt }
}

/**
 * Fetch the full AI results for a completed job.
 * Corresponds to GET /result/{jobId} on the backend.
 */
export async function getResult(jobId) {
  const response = await api.get(`/result/${jobId}`)
  return response.data
  // Full ResultResponse: transcript, scenes, labels, summary, chapters, highlights, sentiment, actionItems
}

/**
 * Health check — useful for debugging connectivity issues.
 */
export async function healthCheck() {
  const response = await api.get('/health')
  return response.data  // { status: "ok", service: "vidiq-api" }
}