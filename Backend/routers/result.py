import os
import logging
from fastapi import APIRouter, HTTPException, Depends
from google.api_core.exceptions import GoogleAPICallError
from models.schemas import ResultResponse, WordTimestamp, Scene, Chapter, Highlight
from services import firestore
from middleware.auth import get_optional_user

router = APIRouter()
logger = logging.getLogger(__name__)

FRONTEND_BASE_URL = os.environ.get("FRONTEND_BASE_URL", "https://video-intelligence-v1.web.app")


@router.get("/result/{job_id}", response_model=ResultResponse)
async def get_result(job_id: str, current_user: dict | None = Depends(get_optional_user)):
    """
    Return the full AI results for a completed job.

    Merges data from three Firestore collections:
      - jobs/{jobId}      → metadata, videoUrl, timestamps
      - results/{jobId}   → transcript, scenes, labels (from worker Phase 1)
      - summaries/{jobId} → summary, chapters, highlights (from worker Phase 2)

    Access control:
      - Authenticated owner → allow (any isPublic value, any status)
      - Authenticated non-owner → allow only if isPublic=true AND status=completed
      - Unauthenticated → allow only if isPublic=true AND status=completed
      - All other cases → 404

    Returns:
      200 with full ResultResponse when access is granted.
      404 if job not found, not accessible, or not completed for public access.
      503 if Firestore is unavailable.
    """

    # --- Read job metadata ---
    try:
        job = firestore.get_job(job_id)
    except (GoogleAPICallError, Exception) as e:
        logger.error(f"[{job_id}] Firestore get_job failed: {e}")
        raise HTTPException(status_code=503, detail="Database service unavailable.")

    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found.")

    # --- Access control ---
    job_owner = job.get("userId", "")
    # Legacy jobs without isPublic field are treated as private (false)
    is_public = job.get("isPublic", False)
    job_status = job.get("status", "")

    # Determine if the current user is the owner
    # Legacy jobs (no userId field) are accessible to any authenticated user
    is_owner = (
        current_user is not None
        and (not job_owner or job_owner == current_user["uid"])
    )

    if is_owner:
        # Owner can access regardless of isPublic value
        pass
    elif is_public and job_status == "completed":
        # Public completed jobs are accessible to anyone (authenticated non-owner or unauthenticated)
        pass
    else:
        # All other cases: non-owner private, unauthenticated private, non-completed public
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found.")

    status = job["status"]

    # Only return results for completed jobs (owner may see non-completed status error)
    if status != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Job {job_id} is not completed yet. Current status: {status}"
        )

    # --- Read AI pipeline results ---
    try:
        results_doc = firestore.get_result(job_id)
    except (GoogleAPICallError, Exception) as e:
        logger.error(f"[{job_id}] Firestore get_result failed: {e}")
        raise HTTPException(status_code=503, detail="Database service unavailable.")

    # --- Read Gemini summary ---
    try:
        summary_doc = firestore.get_summary(job_id)
    except (GoogleAPICallError, Exception) as e:
        logger.warning(f"[{job_id}] Firestore get_summary failed (non-fatal): {e}")
        summary_doc = None

    # --- Parse transcript from results doc ---
    transcript = None
    if results_doc and results_doc.get("transcript"):
        try:
            transcript = [
                WordTimestamp(**word)
                for word in results_doc["transcript"]
            ]
        except Exception as e:
            logger.warning(f"[{job_id}] Transcript parse failed: {e}")
            transcript = None

    # --- Parse scenes from results doc ---
    scenes = None
    if results_doc and results_doc.get("scenes"):
        try:
            scenes = [
                Scene(**scene)
                for scene in results_doc["scenes"]
            ]
        except Exception as e:
            logger.warning(f"[{job_id}] Scenes parse failed: {e}")
            scenes = None

    # --- Parse chapters from summary doc ---
    chapters = None
    if summary_doc and summary_doc.get("chapters"):
        try:
            chapters = [
                Chapter(**chapter)
                for chapter in summary_doc["chapters"]
            ]
        except Exception as e:
            logger.warning(f"[{job_id}] Chapters parse failed: {e}")

    # --- Parse highlights from summary doc ---
    highlights = None
    if summary_doc and summary_doc.get("highlights"):
        try:
            highlights = [
                Highlight(**highlight)
                for highlight in summary_doc["highlights"]
            ]
        except Exception as e:
            logger.warning(f"[{job_id}] Highlights parse failed: {e}")

    logger.info(
        f"[{job_id}] Result served — "
        f"words: {len(transcript) if transcript else 0}, "
        f"scenes: {len(scenes) if scenes else 0}"
    )

    return ResultResponse(
        jobId=job["jobId"],
        status=status,

        # Job metadata
        videoUrl=job.get("videoUrl"),
        processingTime=job.get("processingTime"),
        processingStartedAt=job.get("processingStartedAt"),
        processingCompletedAt=job.get("processingCompletedAt"),

        # Pipeline results (may be None if partial failure)
        transcript=transcript,
        scenes=scenes,
        labels=results_doc.get("labels") if results_doc else None,

        # Summary (may be None if Gemini stage failed or not yet run)
        summary=summary_doc.get("summary") if summary_doc else None,
        chapters=chapters,
        highlights=highlights,
        sentiment=summary_doc.get("sentiment") if summary_doc else None,
        actionItems=summary_doc.get("actionItems") if summary_doc else None,

        # C1 — Cost tracking
        sttAudioMinutes=job.get("sttAudioMinutes"),
        sttEstimatedCostUsd=job.get("sttEstimatedCostUsd"),
        viVideoMinutes=job.get("viVideoMinutes"),
        viEstimatedCostUsd=job.get("viEstimatedCostUsd"),
        geminiInputTokens=job.get("geminiInputTokens"),
        geminiOutputTokens=job.get("geminiOutputTokens"),
        geminiEstimatedCostUsd=job.get("geminiEstimatedCostUsd"),
        totalEstimatedCostUsd=job.get("totalEstimatedCostUsd"),

        # Job ownership
        userId=job.get("userId"),

        # Public share fields
        isPublic=is_public,
        shareUrl=f"{FRONTEND_BASE_URL}/share/{job_id}" if is_public else None,
    )


@router.get("/video-url/{job_id}")
async def get_video_url(job_id: str, current_user: dict | None = Depends(get_optional_user)):
    """
    Generate a fresh signed GCS URL for the video player.

    Access control (same as /result/{job_id}):
      - Authenticated owner → allow (any isPublic value)
      - Authenticated non-owner + isPublic=true + status=completed → allow
      - Unauthenticated + isPublic=true + status=completed → allow
      - Otherwise → 404

    Returns:
        200 { "videoUrl": "<signed_url>" }
        404 if job doesn't exist or access denied
        500 if URL generation fails
    """
    # Read job to get gcsPath
    try:
        job = firestore.get_job(job_id)
    except Exception as e:
        logger.error(f"[{job_id}] get_video_url — Firestore read failed: {e}")
        raise HTTPException(status_code=503, detail="Database unavailable.")

    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found.")

    # Access control logic (same as get_result)
    job_owner = job.get("userId", "")
    is_public = job.get("isPublic", False)
    job_status = job.get("status", "")

    # Legacy jobs (no userId field) are accessible to any authenticated user
    is_owner = (
        current_user is not None
        and (not job_owner or job_owner == current_user["uid"])
    )

    if is_owner:
        # Owner can always access their own jobs
        pass
    elif is_public and job_status == "completed":
        # Public completed jobs are accessible to anyone (authenticated non-owner or unauthenticated)
        pass
    else:
        # All other cases: non-owner private, unauthenticated private, non-completed public
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found.")

    gcs_path = job.get("gcsPath")
    if not gcs_path:
        raise HTTPException(status_code=404, detail="Video path not found for this job.")

    # Generate fresh signed URL — 7 days max for GCS v4 signed URLs
    try:
        from services import storage as storage_service
        video_url = storage_service.get_signed_url(gcs_path, expiration_minutes=10080)  # 7 days
    except Exception as e:
        logger.error(f"[{job_id}] get_video_url — signed URL generation failed: {e}")
        raise HTTPException(status_code=500, detail="Could not generate video URL.")

    return {"videoUrl": video_url}