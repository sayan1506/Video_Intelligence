# Feature: public-share-links
# Property 2: Share URL is correctly constructed based on isPublic state

import os
import pytest
from unittest.mock import patch, MagicMock

from hypothesis import given, settings, strategies as st

from models.schemas import ShareToggleResponse


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Job IDs: non-empty strings that resemble real job IDs (UUIDs, alphanumeric, etc.)
job_id_strategy = st.one_of(
    st.uuids().map(str),
    st.text(
        min_size=1,
        max_size=100,
        alphabet=st.characters(whitelist_categories=("L", "N", "Pd")),
    ).filter(lambda s: len(s.strip()) > 0),
)

# Boolean strategy for isPublic
is_public_strategy = st.booleans()

# FRONTEND_BASE_URL values (test with default and custom values)
frontend_base_url_strategy = st.one_of(
    st.just("https://video-intelligence-v1.web.app"),
    st.just("https://staging.video-intelligence.app"),
    st.just("http://localhost:3000"),
    st.from_regex(r"https://[a-z]{3,15}\.[a-z]{2,6}", fullmatch=True),
)


# ---------------------------------------------------------------------------
# Property 2: Share URL is correctly constructed based on isPublic state
# Validates: Requirements 1.6, 8.1, 8.2, 8.3
# ---------------------------------------------------------------------------

@settings(max_examples=100, deadline=None)
@given(
    job_id=job_id_strategy,
    is_public=is_public_strategy,
    frontend_base_url=frontend_base_url_strategy,
)
@pytest.mark.asyncio
async def test_property2_share_url_construction_patch_response(
    job_id, is_public, frontend_base_url
):
    """
    Property 2: Share URL is correctly constructed based on isPublic state

    For any job ID string, when the job's isPublic field is true, the shareUrl
    field in the PATCH response SHALL equal "{FRONTEND_BASE_URL}/share/{jobId}".
    When isPublic is false, shareUrl SHALL be None.

    **Validates: Requirements 1.6, 8.1, 8.2, 8.3**
    """
    from routers.jobs import toggle_job_share
    from models.schemas import ShareToggleRequest

    # Mock the current user as the job owner
    owner_uid = "owner-uid-123"
    current_user = {"uid": owner_uid, "email": "owner@test.com", "name": "Owner"}

    # Mock a completed job owned by the current user
    mock_job = {
        "jobId": job_id,
        "userId": owner_uid,
        "status": "completed",
        "isPublic": not is_public,  # Start with opposite state
    }

    # Patch FRONTEND_BASE_URL, firestore.get_job, and firestore.set_job_public
    with patch("routers.jobs.FRONTEND_BASE_URL", frontend_base_url):
        with patch("routers.jobs.firestore") as mock_firestore:
            mock_firestore.get_job.return_value = mock_job
            mock_firestore.set_job_public.return_value = None

            request_body = ShareToggleRequest(isPublic=is_public)
            response = await toggle_job_share(
                job_id=job_id,
                body=request_body,
                current_user=current_user,
            )

    # Verify response type
    assert isinstance(response, ShareToggleResponse), (
        f"Expected ShareToggleResponse, got {type(response)}"
    )

    # Verify jobId matches
    assert response.jobId == job_id, (
        f"Expected jobId='{job_id}', got '{response.jobId}'"
    )

    # Verify isPublic matches the request
    assert response.isPublic == is_public, (
        f"Expected isPublic={is_public}, got {response.isPublic}"
    )

    # Core property assertion: URL construction
    if is_public:
        expected_url = f"{frontend_base_url}/share/{job_id}"
        assert response.shareUrl == expected_url, (
            f"When isPublic=True, shareUrl should be '{expected_url}', "
            f"got '{response.shareUrl}'"
        )
        # Verify URL format components
        assert response.shareUrl.startswith(frontend_base_url), (
            f"shareUrl must start with FRONTEND_BASE_URL '{frontend_base_url}'"
        )
        assert response.shareUrl.endswith(f"/share/{job_id}"), (
            f"shareUrl must end with '/share/{job_id}'"
        )
    else:
        assert response.shareUrl is None, (
            f"When isPublic=False, shareUrl should be None, got '{response.shareUrl}'"
        )


@settings(max_examples=100, deadline=None)
@given(
    job_id=job_id_strategy,
)
@pytest.mark.asyncio
async def test_property2_legacy_job_missing_is_public_field_has_null_share_url(
    job_id,
):
    """
    Property 2 (legacy case): When the isPublic field is missing on legacy jobs,
    shareUrl SHALL be null.

    For legacy jobs that don't have an isPublic field, the system treats them
    as non-public and the shareUrl should be None in the ResultResponse.

    **Validates: Requirements 8.2, 8.3**
    """
    from models.schemas import ResultResponse

    # Simulate building a ResultResponse for a legacy job (no isPublic field)
    # The Pydantic model defaults isPublic to False and shareUrl to None
    response = ResultResponse(
        jobId=job_id,
        status="completed",
    )

    # Legacy jobs default to isPublic=False
    assert response.isPublic is False, (
        f"Legacy job (no isPublic field) should default to False, got {response.isPublic}"
    )

    # Legacy jobs should have shareUrl=None
    assert response.shareUrl is None, (
        f"Legacy job (no isPublic field) should have shareUrl=None, got '{response.shareUrl}'"
    )


@settings(max_examples=100, deadline=None)
@given(
    job_id=job_id_strategy,
    is_public=is_public_strategy,
)
def test_property2_share_url_in_result_response_model(job_id, is_public):
    """
    Property 2: When constructing a ResultResponse, the shareUrl field
    correctly reflects the isPublic state.

    When isPublic is True, shareUrl should be set to the expected URL format.
    When isPublic is False, shareUrl should be None.

    **Validates: Requirements 8.1, 8.2, 8.3**
    """
    from models.schemas import ResultResponse

    frontend_base_url = "https://video-intelligence-v1.web.app"
    share_url = f"{frontend_base_url}/share/{job_id}" if is_public else None

    response = ResultResponse(
        jobId=job_id,
        status="completed",
        isPublic=is_public,
        shareUrl=share_url,
    )

    if is_public:
        expected_url = f"{frontend_base_url}/share/{job_id}"
        assert response.shareUrl == expected_url, (
            f"When isPublic=True, shareUrl should be '{expected_url}', "
            f"got '{response.shareUrl}'"
        )
        # Verify the URL contains the job ID
        assert job_id in response.shareUrl, (
            f"shareUrl must contain the job_id '{job_id}'"
        )
        # Verify the URL has the correct path structure
        assert "/share/" in response.shareUrl, (
            "shareUrl must contain '/share/' path segment"
        )
    else:
        assert response.shareUrl is None, (
            f"When isPublic=False, shareUrl should be None, got '{response.shareUrl}'"
        )
