# Feature: public-share-links
# Property 1: Access control decision is correct for all actor/job combinations
# Validates: Requirements 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8, 5.9

import pytest
from unittest.mock import patch, MagicMock

from hypothesis import given, settings, strategies as st, assume
from httpx import AsyncClient, ASGITransport

from main import app
from middleware.auth import get_optional_user


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Actor types
actor_type_strategy = st.sampled_from(["unauthenticated", "owner", "non_owner"])

# isPublic values
is_public_strategy = st.booleans()

# Job status: completed or non-completed
job_status_strategy = st.sampled_from(["completed", "pending", "uploading", "processing", "failed"])

# Job existence
job_exists_strategy = st.booleans()

# UIDs: non-empty strings of letters, digits, and hyphens
uid_strategy = st.text(
    min_size=1,
    max_size=64,
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="-_"),
)

# Job IDs: non-empty alphanumeric strings with hyphens (URL-safe)
job_id_strategy = st.text(
    min_size=1,
    max_size=50,
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="-_"),
)

# Endpoint to test
endpoint_strategy = st.sampled_from(["result", "video-url"])


# ---------------------------------------------------------------------------
# Helper: determine expected HTTP status
# ---------------------------------------------------------------------------

def expected_status_code(actor_type, job_exists, is_public, job_status, endpoint):
    """
    Determine the expected HTTP status code based on the access control matrix.

    Access control rules:
      - If job doesn't exist → 404
      - If actor is owner → access granted (but result endpoint returns 400 for non-completed)
      - If job exists AND isPublic=true AND status=completed → access granted
      - All other cases → 404

    Post-access-control checks:
      - For /result endpoint: owner accessing non-completed job → 400
      - For /video-url endpoint: requires gcsPath to be present (we always provide it for completed jobs)
    """
    if not job_exists:
        return 404

    # Owner access
    if actor_type == "owner":
        if endpoint == "result" and job_status != "completed":
            # Owner passes access control but result endpoint checks completion status
            return 400
        elif endpoint == "video-url" and job_status != "completed":
            # Owner passes access control but video-url also needs gcsPath;
            # for non-completed jobs we won't have gcsPath set
            return 404
        else:
            return 200

    # Non-owner or unauthenticated
    if is_public and job_status == "completed":
        return 200
    else:
        return 404


# ---------------------------------------------------------------------------
# Property 1: Access control decision is correct for all actor/job combinations
# Validates: Requirements 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8, 5.9
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@settings(max_examples=100, deadline=None)
@given(
    actor_type=actor_type_strategy,
    is_public=is_public_strategy,
    job_status=job_status_strategy,
    job_exists=job_exists_strategy,
    owner_uid=uid_strategy,
    caller_uid=uid_strategy,
    job_id=job_id_strategy,
    endpoint=endpoint_strategy,
)
async def test_property1_access_control_decision_matrix(
    actor_type,
    is_public,
    job_status,
    job_exists,
    owner_uid,
    caller_uid,
    job_id,
    endpoint,
):
    """
    Property 1: Access control decision is correct for all actor/job combinations

    For any combination of actor (unauthenticated, authenticated owner,
    authenticated non-owner) and job state (isPublic true/false, status
    completed/non-completed, exists/non-existent), the GET /result/{job_id}
    and GET /video-url/{job_id} endpoints SHALL return 200 if and only if:
    (a) the actor is the job owner, OR (b) the job exists AND isPublic is true
    AND status is "completed". In all other cases, the endpoint SHALL return 404.

    Note: For owner accessing non-completed jobs, the result endpoint returns
    400 (not 200) because it checks completion status after access control passes.
    The video-url endpoint also requires gcsPath to be present.

    **Validates: Requirements 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8, 5.9**
    """
    # Ensure non-owner has a different UID from owner
    if actor_type == "non_owner":
        assume(caller_uid != owner_uid)

    # Build the mock job document
    mock_job = None
    if job_exists:
        mock_job = {
            "jobId": job_id,
            "userId": owner_uid,
            "status": job_status,
            "isPublic": is_public,
            "gcsPath": f"gs://bucket/{job_id}.mp4" if job_status == "completed" else None,
            "videoUrl": f"https://storage.googleapis.com/{job_id}.mp4",
            "processingTime": 120,
            "processingStartedAt": "2024-01-01T00:00:00Z",
            "processingCompletedAt": "2024-01-01T00:02:00Z",
        }

    # Determine the user context based on actor type
    if actor_type == "unauthenticated":
        mock_user = None
    elif actor_type == "owner":
        mock_user = {"uid": owner_uid, "email": "owner@test.com", "name": "Owner"}
    else:  # non_owner
        mock_user = {"uid": caller_uid, "email": "other@test.com", "name": "Other"}

    # Override the optional auth dependency
    async def override_get_optional_user():
        return mock_user

    app.dependency_overrides[get_optional_user] = override_get_optional_user

    try:
        # Mock Firestore calls
        with patch("routers.result.firestore.get_job", return_value=mock_job):
            # For result endpoint, also mock get_result and get_summary
            # Use correct field names matching Pydantic schemas
            mock_result_doc = {
                "transcript": [{"word": "hello", "startTime": 0.0, "endTime": 0.5, "speaker": 0}],
                "scenes": [{"startTime": 0.0, "endTime": 10.0, "labels": ["scene1"]}],
                "labels": ["test"],
            } if job_exists and job_status == "completed" else None

            mock_summary_doc = {
                "summary": "Test summary",
                "chapters": [{"title": "Ch1", "startTime": 0, "endTime": 10}],
                "highlights": [{"timestamp": 2.5, "description": "A highlight"}],
                "sentiment": "positive",
                "actionItems": ["item1"],
            } if job_exists and job_status == "completed" else None

            with patch("routers.result.firestore.get_result", return_value=mock_result_doc):
                with patch("routers.result.firestore.get_summary", return_value=mock_summary_doc):
                    # For video-url endpoint, mock the storage service
                    with patch("services.storage.get_signed_url", return_value="https://signed-url.example.com/video"):
                        async with AsyncClient(
                            transport=ASGITransport(app=app),
                            base_url="http://test",
                        ) as client:
                            url = f"/{endpoint}/{job_id}"
                            response = await client.get(url)

        # Determine expected status
        expected = expected_status_code(actor_type, job_exists, is_public, job_status, endpoint)

        assert response.status_code == expected, (
            f"Expected {expected} but got {response.status_code} for "
            f"actor={actor_type}, job_exists={job_exists}, is_public={is_public}, "
            f"status={job_status}, endpoint=/{endpoint}/{job_id}"
        )

    finally:
        app.dependency_overrides.pop(get_optional_user, None)
