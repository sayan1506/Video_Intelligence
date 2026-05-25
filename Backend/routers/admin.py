import logging
from fastapi import APIRouter, Depends
from middleware.auth import get_current_admin
from services import firestore

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/admin/stats")
async def admin_stats(current_admin: dict = Depends(get_current_admin)):
    """
    Aggregated stats across all jobs.
    Returns: total jobs, by-status counts, total cost, avg processing time, top users.
    Only accessible by the Firebase UID matching ADMIN_UID env var.
    """
    logger.info(f"Admin stats requested by {current_admin['uid']}")
    return firestore.get_admin_stats()


@router.get("/admin/jobs")
async def admin_jobs(
    limit: int = 50,
    current_admin: dict = Depends(get_current_admin),
):
    """
    List the most recent jobs across all users (newest first).
    limit: max 50. Used to populate the admin jobs table.
    """
    logger.info(f"Admin jobs requested by {current_admin['uid']} (limit={limit})")
    jobs = firestore.list_all_jobs(limit=min(limit, 50))
    return {"jobs": jobs}
