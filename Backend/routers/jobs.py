import os
import logging
from fastapi import APIRouter, HTTPException, Depends
from google.api_core.exceptions import GoogleAPICallError, FailedPrecondition
from services import firestore
from middleware.auth import get_current_user
from models.schemas import ShareToggleRequest, ShareToggleResponse

router = APIRouter()
logger = logging.getLogger(__name__)

FRONTEND_BASE_URL = os.environ.get("FRONTEND_BASE_URL", "https://video-intelligence-v1.web.app")


@router.get("/jobs")
async def list_jobs(
    limit: int = 20,
    current_user: dict = Depends(get_current_user),
):
    """
    Return the authenticated user's jobs, newest first.

    Requires a Firestore composite index on (userId ASC, createdAt DESC).
    If the index is missing, Firestore raises FailedPrecondition — the error
    message in Cloud Logging contains the direct URL to create the index.

    Query params:
        limit: max jobs to return (1–100, default 20)

    Returns:
        { "jobs": [ <job doc>, ... ] }
    """
    limit = max(1, min(limit, 100))

    try:
        jobs = firestore.list_user_jobs(user_id=current_user["uid"], limit=limit)
    except FailedPrecondition as e:
        logger.error(f"list_jobs — Firestore index missing for user {current_user['uid']}: {e}")
        raise HTTPException(
            status_code=503,
            detail=(
                "Database index not ready. "
                "Check Cloud Logging for the Firestore index creation URL."
            ),
        )
    except (GoogleAPICallError, Exception) as e:
        logger.error(f"list_jobs — Firestore error for user {current_user['uid']}: {e}")
        raise HTTPException(status_code=503, detail="Database service unavailable.")

    logger.info(f"list_jobs — returned {len(jobs)} jobs for user {current_user['uid']}")
    return {"jobs": jobs}


@router.patch("/jobs/{job_id}/share")
async def toggle_job_share(
    job_id: str,
    body: ShareToggleRequest,
    current_user: dict = Depends(get_current_user),
) -> ShareToggleResponse:
    """
    Toggle public sharing for a completed job.

    Only the job owner can toggle visibility. The job must have status "completed".

    Returns the new share state and the public share URL (when isPublic=true).
    """
    # Fetch job and verify ownership
    job = firestore.get_job(job_id)
    if job is None or job.get("userId") != current_user["uid"]:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found.")

    # Only completed jobs can be shared
    if job.get("status") != "completed":
        raise HTTPException(status_code=400, detail="Only completed jobs can be shared.")

    # Update the isPublic field in Firestore
    try:
        firestore.set_job_public(job_id, body.isPublic)
    except Exception as e:
        logger.error(f"toggle_job_share — Firestore set_job_public failed for job {job_id}: {e}")
        raise HTTPException(status_code=503, detail="Database service unavailable.")

    # Construct share URL
    share_url = f"{FRONTEND_BASE_URL}/share/{job_id}" if body.isPublic else None

    logger.info(f"toggle_job_share — job {job_id} isPublic={body.isPublic} by user {current_user['uid']}")

    return ShareToggleResponse(
        jobId=job_id,
        isPublic=body.isPublic,
        shareUrl=share_url,
    )
