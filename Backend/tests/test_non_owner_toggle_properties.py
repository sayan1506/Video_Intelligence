# Feature: public-share-links
# Property 7: Non-owner toggle requests are always rejected
# Validates: Requirements 1.3

import pytest
from unittest.mock import patch, MagicMock

from hypothesis import given, settings, strategies as st, assume
from httpx import AsyncClient, ASGITransport

from main import app
from middleware.auth import get_current_user


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# UIDs: non-empty strings of letters, digits, and hyphens (Firebase UID-like)
uid_strategy = st.text(
    min_size=1,
    max_size=64,
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="-_"),
)

# Job IDs: non-empty alphanumeric strings with hyphens
job_id_strategy = st.text(
    min_size=1,
    max_size=50,
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="-_"),
)

# Job statuses: any valid status the system uses
job_status_strategy = st.sampled_from(["pending", "uploading", "processing", "completed", "failed"])

# isPublic values in the request body
is_public_strategy = st.booleans()

# The job's current isPublic state
job_is_public_strategy = st.booleans()


# ---------------------------------------------------------------------------
# Property 7: Non-owner toggle requests are always rejected
# Validates: Requirements 1.3
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@settings(max_examples=100, deadline=None)
@given(
    owner_uid=uid_strategy,
    caller_uid=uid_strategy,
    job_id=job_id_strategy,
    job_status=job_status_strategy,
    job_is_public=job_is_public_strategy,
    request_is_public=is_public_strategy,
)
async def test_property7_non_owner_toggle_always_rejected(
    owner_uid,
    caller_uid,
    job_id,
    job_status,
    job_is_public,
    request_is_public,
):
    """
    Property 7: Non-owner toggle requests are always rejected

    For any authenticated user whose UID differs from the job's userId field,
    a PATCH request to /jobs/{job_id}/share SHALL return HTTP 404 regardless
    of the request body content or the job's current state.

    Validates: Requirements 1.3
    """
    # Ensure caller is NOT the owner
    assume(caller_uid != owner_uid)

    # Mock the authenticated user (the non-owner caller)
    caller_user = {"uid": caller_uid, "email": "caller@test.com", "name": "Caller"}

    # Mock the job document in Firestore (owned by owner_uid)
    mock_job = {
        "userId": owner_uid,
        "status": job_status,
        "isPublic": job_is_public,
        "filename": "test.mp4",
    }

    async def override_get_current_user():
        return caller_user

    app.dependency_overrides[get_current_user] = override_get_current_user

    try:
        with patch("routers.jobs.firestore.get_job", return_value=mock_job):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.patch(
                    f"/jobs/{job_id}/share",
                    json={"isPublic": request_is_public},
                )

        # Non-owner MUST always get 404 (never 403, to avoid confirming job existence)
        assert response.status_code == 404, (
            f"Expected 404 for non-owner, got {response.status_code}. "
            f"owner_uid={owner_uid!r}, caller_uid={caller_uid!r}, "
            f"job_status={job_status!r}, job_is_public={job_is_public!r}, "
            f"request_is_public={request_is_public!r}"
        )

        # Verify the error message matches the expected format
        detail = response.json().get("detail", "")
        assert "not found" in detail.lower(), (
            f"Expected 'not found' in error detail, got: {detail!r}"
        )
    finally:
        app.dependency_overrides.pop(get_current_user, None)
