import logging
from fastapi import APIRouter, HTTPException, Depends
from google.api_core.exceptions import GoogleAPICallError, FailedPrecondition
from services import firestore
from middleware.auth import get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)


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
