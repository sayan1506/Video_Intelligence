import logging
from fastapi import APIRouter, HTTPException
from google.api_core.exceptions import GoogleAPICallError
from models.schemas import ResultResponse, WordTimestamp, Scene, Chapter, Highlight
from services import firestore

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/result/{job_id}", response_model=ResultResponse)
async def get_result(job_id: str):
    """
    Return the full AI results for a completed job.

    Merges data from three Firestore collections:
      - jobs/{jobId}      → metadata, videoUrl, timestamps
      - results/{jobId}   → transcript, scenes, labels (from worker Phase 1)
      - summaries/{jobId} → summary, chapters, highlights (from worker Phase 2)

    Returns:
      200 with full ResultResponse when job is completed.
      400 if job exists but is not yet completed (still processing or failed).
      404 if the job ID doesn't exist at all.
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

    status = job["status"]

    # Only return results for completed jobs
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
    )