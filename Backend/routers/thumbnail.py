import logging
from fastapi import APIRouter, HTTPException, Depends
from google.api_core.exceptions import GoogleAPICallError
from services import firestore
from services import storage as storage_service
from middleware.auth import get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/thumbnail-url/{job_id}")
async def get_thumbnail_url(
    job_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Generate a fresh signed GCS URL for the job's thumbnail image.

    The thumbnail is extracted by the worker at 10% of video duration and
    stored at processed/{jobId}/thumbnail.jpg. This endpoint generates a
    short-lived signed URL using the same self-impersonation pattern as
    GET /video-url.

    Returns:
        200 { "thumbnailUrl": "<signed_url>" }
        404 if job doesn't exist, isn't owned by the caller, or has no thumbnail yet
        500 if URL generation fails
    """
    try:
        job = firestore.get_job(job_id)
    except Exception as e:
        logger.error(f"[{job_id}] get_thumbnail_url — Firestore read failed: {e}")
        raise HTTPException(status_code=503, detail="Database unavailable.")

    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found.")

    # Ownership check
    job_owner = job.get("userId", "")
    if job_owner and job_owner != current_user["uid"]:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found.")

    thumbnail_gcs_path = job.get("thumbnailGcsPath")
    if not thumbnail_gcs_path:
        raise HTTPException(
            status_code=404,
            detail="Thumbnail not available yet. Processing may still be in progress.",
        )

    try:
        # 1-hour expiry is sufficient for dashboard card display
        thumbnail_url = storage_service.get_signed_url(
            thumbnail_gcs_path,
            expiration_minutes=60,
        )
    except Exception as e:
        logger.error(f"[{job_id}] get_thumbnail_url — signed URL generation failed: {e}")
        raise HTTPException(status_code=500, detail="Could not generate thumbnail URL.")

    return {"thumbnailUrl": thumbnail_url}
