# Backend/routers/quota.py

import logging
from fastapi import APIRouter, HTTPException, Depends
from google.api_core.exceptions import GoogleAPICallError
from services import firestore
from middleware.auth import get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/quota")
async def get_quota(current_user: dict = Depends(get_current_user)):
    """
    Return the current user's quota status.

    Response shape:
        {
          "plan": "free" | "pro",
          "jobsThisMonth": int,
          "monthlyLimit": int,
          "resetDate": "2026-06-01T00:00:00+00:00"
        }

    Called by the Dashboard and UploadPage to display quota usage.
    Errors in reading Firestore degrade gracefully to safe defaults
    inside get_quota_status(). Only unexpected exceptions bubble up as 503.
    """
    try:
        status = firestore.get_quota_status(current_user["uid"])
        return status
    except (GoogleAPICallError, Exception) as e:
        logger.error(f"[{current_user['uid']}] get_quota failed: {e}")
        raise HTTPException(status_code=503, detail="Could not read quota status.")
