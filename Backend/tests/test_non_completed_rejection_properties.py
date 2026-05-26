# Feature: public-share-links
# Property 3: Only completed jobs can be toggled to public

import pytest
from unittest.mock import patch, MagicMock

from hypothesis import given, settings, strategies as st
from httpx import AsyncClient, ASGITransport

from main import app
from middleware.auth import get_current_user


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Non-completed statuses that should always be rejected
non_completed_statuses = st.sampled_from(["pending", "uploading", "processing", "failed"])

# Random isPublic values (both true and false should be rejected for non-completed jobs)
is_public_values = st.booleans()

# Job IDs: non-empty alphanumeric strings (simulating UUIDs or similar)
job_id_strategy = st.text(
    min_size=1,
    max_size=50,
    alphabet=st.characters(whitelist_categories=("L", "N")),
)

# Owner UID
owner_uid_strategy = st.text(
    min_size=1,
    max_size=128,
    alphabet=st.characters(whitelist_categories=("L", "N")),
)


# ---------------------------------------------------------------------------
# Property 3: Only completed jobs can be toggled to public
# Validates: Requirements 1.7
# ---------------------------------------------------------------------------

@settings(max_examples=100, deadline=None)
@given(
    status=non_completed_statuses,
    is_public=is_public_values,
    job_id=job_id_strategy,
    owner_uid=owner_uid_strategy,
)
@pytest.mark.asyncio
async def test_property3_non_completed_jobs_rejected(status, is_public, job_id, owner_uid):
    """
    Property 3: Only completed jobs can be toggled to public

    For any job whose status is not "completed" (i.e., status is one of
    pending, uploading, processing, failed), a PATCH request to
    /jobs/{job_id}/share SHALL return HTTP 400 regardless of the isPublic
    value in the request body.

    **Validates: Requirements 1.7**
    """
    # Mock the job document: owned by the caller but NOT completed
    mock_job = {
        "jobId": job_id,
        "userId": owner_uid,
        "status": status,
        "isPublic": False,
    }

    # Mock the authenticated user (owner of the job)
    mock_user = {"uid": owner_uid, "email": "owner@test.com", "name": "Owner"}

    # Override the auth dependency to bypass real Firebase token verification
    async def override_get_current_user():
        return mock_user

    app.dependency_overrides[get_current_user] = override_get_current_user

    try:
        with patch("routers.jobs.firestore.get_job", return_value=mock_job):
            with patch("routers.jobs.firestore.set_job_public") as mock_set_public:
                async with AsyncClient(
                    transport=ASGITransport(app=app),
                    base_url="http://test",
                ) as client:
                    response = await client.patch(
                        f"/jobs/{job_id}/share",
                        json={"isPublic": is_public},
                    )

                # Core assertion: non-completed jobs MUST return 400
                assert response.status_code == 400, (
                    f"Expected 400 for status='{status}', isPublic={is_public}, "
                    f"but got {response.status_code}. Response: {response.json()}"
                )

                # Verify the error message matches the expected format
                detail = response.json().get("detail", "")
                assert detail == "Only completed jobs can be shared.", (
                    f"Expected error message 'Only completed jobs can be shared.' "
                    f"but got '{detail}' for status='{status}'"
                )

                # Verify set_job_public was NOT called (job should be rejected before update)
                mock_set_public.assert_not_called()
    finally:
        # Clean up dependency override
        app.dependency_overrides.pop(get_current_user, None)
