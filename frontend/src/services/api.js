import axios from 'axios'

const BASE_URL = import.meta.env.VITE_API_BASE_URL

const api = axios.create({
  baseURL: BASE_URL,
  timeout: 60000,  // 60s — enough for signed URL requests and confirm calls
})

/**
 * Request a resumable upload URI from the backend.
 * Corresponds to POST /upload-url on the backend.
 *
 * @param {string} filename
 * @param {string} contentType
 * @param {number} fileSizeBytes - File size in bytes (pass file.size directly)
 */
export async function getUploadUrl(filename, contentType, fileSizeBytes) {
  const response = await api.post('/upload-url', null, {
    params: {
      filename,
      content_type: contentType,
      file_size_bytes: fileSizeBytes,
    }
  })
  return response.data  // { jobId, uploadUrl (resumable URI), gcsPath }
}

/**
 * Upload a file directly to GCS using the signed PUT URL.
 * This call goes to GCS, not to the backend — bypasses Cloud Run entirely.
 */
const UPLOAD_CHUNK_SIZE = 8 * 1024 * 1024; // 8MB — must be multiple of 256KB

/**
 * Upload a file to GCS using a resumable upload session URI.
 *
 * The backend's POST /upload-url now returns a resumable upload URI from GCS.
 * This function uploads the file in 8MB chunks using Content-Range headers.
 *
 * Intermediate chunks receive HTTP 308 Resume Incomplete from GCS — this is
 * expected and not an error. Only the final chunk receives HTTP 200.
 *
 * @param {string} uploadUrl - Resumable upload URI from GCS (returned by POST /upload-url)
 * @param {File} file - The File object to upload
 * @param {function(number): void} onProgress - Called with percent complete (0–100)
 */
export async function uploadToGcs(uploadUrl, file, onProgress) {
  const CHUNK_SIZE = 8 * 1024 * 1024;
  let offset = 0;

  while (offset < file.size) {
    const end = Math.min(offset + CHUNK_SIZE, file.size);
    const chunk = file.slice(offset, end);
    const isLastChunk = end >= file.size;
    const contentRange = `bytes ${offset}-${end - 1}/${file.size}`;

    await new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open('PUT', uploadUrl);
      xhr.setRequestHeader('Content-Type', file.type);
      xhr.setRequestHeader('Content-Range', contentRange);

      xhr.onload = () => {
        // 308 = intermediate chunk OK, 200/201 = final chunk OK
        if (xhr.status === 308 || xhr.status === 200 || xhr.status === 201) {
          resolve();
        } else {
          reject(new Error(`Chunk upload failed: HTTP ${xhr.status}`));
        }
      };

      xhr.onerror = () => reject(new Error('Chunk upload network error'));

      xhr.send(chunk);
    });

    offset = end;
    if (onProgress) {
      onProgress(Math.round((offset / file.size) * 100));
    }
  }
}

/**
 * Confirm the GCS upload is complete and trigger the AI worker via Pub/Sub.
 * Corresponds to POST /upload-confirm on the backend.
 */
export async function confirmUpload(jobId, gcsPath, filename, contentType) {
  const response = await api.post('/upload-confirm', null, {
    params: {
      job_id: jobId,
      gcs_path: gcsPath,
      filename,
      content_type: contentType,
    }
  })
  return response.data
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
 * Fetch a fresh signed video URL for the player.
 * Corresponds to GET /video-url/{jobId} on the backend.
 * Called on every ResultPage load — replaces the stale URL pattern.
 */
export async function getVideoUrl(jobId) {
  const response = await api.get(`/video-url/${jobId}`)
  return response.data.videoUrl
}

/**
 * Health check — useful for debugging connectivity issues.
 */
export async function healthCheck() {
  const response = await api.get('/health')
  return response.data  // { status: "ok", service: "vidiq-api" }
}