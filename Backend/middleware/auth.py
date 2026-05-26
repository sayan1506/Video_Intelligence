import os
import logging
from functools import lru_cache

import firebase_admin
from firebase_admin import auth as firebase_auth, credentials
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

logger = logging.getLogger(__name__)

# ── Firebase Admin SDK initialisation ────────────────────────────────────────
# Initialised once at module load via ADC — no JSON key file.
# On Cloud Run the attached service account is used automatically.
# Locally, `gcloud auth application-default login` provides credentials.

_firebase_app: firebase_admin.App | None = None


def _get_firebase_app() -> firebase_admin.App:
    """
    Return the singleton Firebase Admin app, initialising it on first call.

    Uses ADC (Application Default Credentials) — no service account JSON key.
    The GCP_PROJECT_ID env var is used to scope the app to the correct project.
    """
    global _firebase_app
    if _firebase_app is None:
        project_id = os.getenv("GCP_PROJECT_ID")
        # credentials.ApplicationDefault() resolves via ADC — same as all other
        # Google Cloud clients in this project (Firestore, Storage, Pub/Sub).
        cred = credentials.ApplicationDefault()
        _firebase_app = firebase_admin.initialize_app(
            cred,
            options={"projectId": project_id},
        )
        logger.info(f"Firebase Admin SDK initialised (project: {project_id})")
    return _firebase_app


# ── HTTP Bearer scheme ────────────────────────────────────────────────────────
# auto_error=False so we can return a clean 401 rather than FastAPI's default
# 403 when the header is missing.
_bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> dict:
    """
    FastAPI dependency — verifies the Firebase ID token in the Authorization header.

    Usage:
        @router.get("/protected")
        async def endpoint(current_user = Depends(get_current_user)):
            ...

    Returns:
        Decoded token dict with at minimum:
            uid       — Firebase UID (stable, unique per user)
            email     — user's email address
            name      — display name (may be absent for some providers)

    Raises:
        HTTP 401 if the header is missing or the token is invalid/expired.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    try:
        _get_firebase_app()  # ensure initialised
        decoded = firebase_auth.verify_id_token(token)
    except firebase_auth.ExpiredIdTokenError:
        logger.warning("Firebase token expired")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired. Please sign in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except firebase_auth.InvalidIdTokenError as e:
        logger.warning(f"Firebase token invalid: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        logger.error(f"Firebase token verification failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return {
        "uid": decoded["uid"],
        "email": decoded.get("email", ""),
        "name": decoded.get("name", ""),
    }


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> dict | None:
    """
    FastAPI dependency — returns decoded user dict if valid Bearer token present,
    None otherwise. Never raises HTTP errors — silent fallback to None.

    Usage:
        @router.get("/public-or-private")
        async def endpoint(user = Depends(get_optional_user)):
            if user is None:
                # unauthenticated access
            else:
                # authenticated access

    Returns:
        Decoded token dict with uid, email, name — or None.
    """
    if credentials is None:
        return None

    token = credentials.credentials
    if not token:
        return None

    try:
        _get_firebase_app()  # ensure initialised
        decoded = firebase_auth.verify_id_token(token)
    except Exception:
        # Any verification failure (expired, invalid, malformed) → None
        return None

    return {
        "uid": decoded["uid"],
        "email": decoded.get("email", ""),
        "name": decoded.get("name", ""),
    }


async def get_current_admin(current_user: dict = Depends(get_current_user)) -> dict:
    """
    Admin-only dependency. Raises 403 if the authenticated user is not the admin UID.
    Stack: get_current_admin → get_current_user → Firebase token verification.
    The admin UID is read from ADMIN_UID env var at call time (not module load).
    """
    admin_uid = os.getenv("ADMIN_UID", "")
    if not admin_uid:
        raise HTTPException(status_code=500, detail="Admin not configured.")
    if current_user["uid"] != admin_uid:
        raise HTTPException(status_code=403, detail="Admin access required.")
    return current_user
