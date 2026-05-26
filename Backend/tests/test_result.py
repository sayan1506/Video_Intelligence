from unittest.mock import patch
from datetime import datetime, timezone
from httpx import AsyncClient, ASGITransport

from main import app
from middleware.auth import get_optional_user

# Fixed test user for authenticated owner tests
TEST_USER = {"uid": "test-owner-uid", "email": "owner@test.com", "name": "Test Owner"}


async def _override_get_optional_user_authenticated():
    """Override that returns a fixed authenticated user."""
    return TEST_USER


async def _override_get_optional_user_unauthenticated():
    """Override that returns None (unauthenticated)."""
    return None


def make_job_doc(job_id: str, status: str = "completed", user_id: str = "test-owner-uid", is_public: bool = False) -> dict:
    now = datetime.now(timezone.utc)
    doc = {
        "jobId": job_id,
        "status": status,
        "progress": 100 if status == "completed" else 50,
        "videoUrl": "https://signed.url/video.mp4",
        "processingTime": 72,
        "processingStartedAt": now,
        "processingCompletedAt": now,
        "userId": user_id,
        "isPublic": is_public,
        "gcsPath": f"uploads/{user_id}/{job_id}/video.mp4",
    }
    return doc


def make_results_doc(job_id: str) -> dict:
    return {
        "jobId": job_id,
        "transcript": [
            {"word": "Hello", "startTime": 0.4, "endTime": 0.8, "speaker": 1},
            {"word": "world", "startTime": 0.9, "endTime": 1.2, "speaker": 1},
        ],
        "scenes": [
            {"startTime": 0.0, "endTime": 5.2, "labels": ["person", "indoor"]},
            {"startTime": 5.2, "endTime": 12.0, "labels": ["laptop", "technology"]},
        ],
        "labels": ["person", "indoor", "laptop", "technology"],
    }


def make_summary_doc(job_id: str) -> dict:
    return {
        "jobId": job_id,
        "summary": "This is a stub summary for testing.",
        "chapters": [
            {"title": "Introduction", "startTime": 0, "endTime": 60},
            {"title": "Main content", "startTime": 60, "endTime": 120},
        ],
        "highlights": [
            {"timestamp": 2.6, "description": "Scene featuring person"},
        ],
        "sentiment": "neutral",
        "actionItems": [],
    }


class TestGetResult:

    async def test_completed_job_returns_200_with_full_response(self, client: AsyncClient):
        job_id = "test-result-001"

        app.dependency_overrides[get_optional_user] = _override_get_optional_user_authenticated
        try:
            with patch("routers.result.firestore.get_job", return_value=make_job_doc(job_id)), \
                 patch("routers.result.firestore.get_result", return_value=make_results_doc(job_id)), \
                 patch("routers.result.firestore.get_summary", return_value=make_summary_doc(job_id)):

                response = await client.get(f"/result/{job_id}")

            assert response.status_code == 200
            data = response.json()
            assert data["jobId"] == job_id
            assert data["status"] == "completed"
        finally:
            app.dependency_overrides.pop(get_optional_user, None)

    async def test_result_contains_transcript_and_scenes(self, client: AsyncClient):
        job_id = "test-result-002"

        app.dependency_overrides[get_optional_user] = _override_get_optional_user_authenticated
        try:
            with patch("routers.result.firestore.get_job", return_value=make_job_doc(job_id)), \
                 patch("routers.result.firestore.get_result", return_value=make_results_doc(job_id)), \
                 patch("routers.result.firestore.get_summary", return_value=make_summary_doc(job_id)):

                response = await client.get(f"/result/{job_id}")

            data = response.json()
            assert len(data["transcript"]) == 2
            assert data["transcript"][0]["word"] == "Hello"
            assert data["transcript"][0]["startTime"] == 0.4
            assert len(data["scenes"]) == 2
            assert "person" in data["scenes"][0]["labels"]
            assert data["labels"] == ["person", "indoor", "laptop", "technology"]
        finally:
            app.dependency_overrides.pop(get_optional_user, None)

    async def test_result_contains_summary_fields(self, client: AsyncClient):
        job_id = "test-result-003"

        app.dependency_overrides[get_optional_user] = _override_get_optional_user_authenticated
        try:
            with patch("routers.result.firestore.get_job", return_value=make_job_doc(job_id)), \
                 patch("routers.result.firestore.get_result", return_value=make_results_doc(job_id)), \
                 patch("routers.result.firestore.get_summary", return_value=make_summary_doc(job_id)):

                response = await client.get(f"/result/{job_id}")

            data = response.json()
            assert data["summary"] == "This is a stub summary for testing."
            assert len(data["chapters"]) == 2
            assert data["chapters"][0]["title"] == "Introduction"
            assert len(data["highlights"]) == 1
            assert data["sentiment"] == "neutral"
            assert data["actionItems"] == []
        finally:
            app.dependency_overrides.pop(get_optional_user, None)

    async def test_pending_job_returns_400(self, client: AsyncClient):
        job_id = "test-result-pending"

        app.dependency_overrides[get_optional_user] = _override_get_optional_user_authenticated
        try:
            with patch("routers.result.firestore.get_job",
                       return_value=make_job_doc(job_id, status="pending")), \
                 patch("routers.result.firestore.get_result", return_value=None), \
                 patch("routers.result.firestore.get_summary", return_value=None):

                response = await client.get(f"/result/{job_id}")

            assert response.status_code == 400
            assert "not completed yet" in response.json()["detail"]
            assert "pending" in response.json()["detail"]
        finally:
            app.dependency_overrides.pop(get_optional_user, None)

    async def test_processing_job_returns_400(self, client: AsyncClient):
        job_id = "test-result-processing"

        app.dependency_overrides[get_optional_user] = _override_get_optional_user_authenticated
        try:
            with patch("routers.result.firestore.get_job",
                       return_value=make_job_doc(job_id, status="processing")), \
                 patch("routers.result.firestore.get_result", return_value=None), \
                 patch("routers.result.firestore.get_summary", return_value=None):

                response = await client.get(f"/result/{job_id}")

            assert response.status_code == 400
            assert "processing" in response.json()["detail"]
        finally:
            app.dependency_overrides.pop(get_optional_user, None)

    async def test_unknown_job_returns_404(self, client: AsyncClient):
        with patch("routers.result.firestore.get_job", return_value=None):
            response = await client.get("/result/nonexistent-job")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    async def test_missing_summary_doc_returns_200_with_null_summary(self, client: AsyncClient):
        """
        Summary doc may be absent if Gemini stage failed.
        Result should still return 200 with transcript and scenes intact.
        """
        job_id = "test-result-no-summary"

        app.dependency_overrides[get_optional_user] = _override_get_optional_user_authenticated
        try:
            with patch("routers.result.firestore.get_job", return_value=make_job_doc(job_id)), \
                 patch("routers.result.firestore.get_result", return_value=make_results_doc(job_id)), \
                 patch("routers.result.firestore.get_summary", return_value=None):

                response = await client.get(f"/result/{job_id}")

            assert response.status_code == 200
            data = response.json()
            assert data["summary"] is None
            assert data["chapters"] is None
            # But transcript and scenes should still be present
            assert len(data["transcript"]) == 2
            assert len(data["scenes"]) == 2
        finally:
            app.dependency_overrides.pop(get_optional_user, None)

    async def test_missing_results_doc_returns_200_with_null_transcript(self, client: AsyncClient):
        """
        Results doc may be absent if worker Phase 1 partially failed.
        Should still return 200 — job is completed, just with null AI fields.
        """
        job_id = "test-result-no-results"

        app.dependency_overrides[get_optional_user] = _override_get_optional_user_authenticated
        try:
            with patch("routers.result.firestore.get_job", return_value=make_job_doc(job_id)), \
                 patch("routers.result.firestore.get_result", return_value=None), \
                 patch("routers.result.firestore.get_summary", return_value=make_summary_doc(job_id)):

                response = await client.get(f"/result/{job_id}")

            assert response.status_code == 200
            data = response.json()
            assert data["transcript"] is None
            assert data["scenes"] is None
            # But summary should still be present
            assert data["summary"] is not None
        finally:
            app.dependency_overrides.pop(get_optional_user, None)

    async def test_firestore_error_returns_503(self, client: AsyncClient):
        from google.api_core.exceptions import ServiceUnavailable

        with patch("routers.result.firestore.get_job") as mock_get:
            mock_get.side_effect = ServiceUnavailable("Firestore unavailable")
            response = await client.get("/result/any-job-id")

        assert response.status_code == 503
        assert "unavailable" in response.json()["detail"].lower()

    async def test_video_url_in_result_response(self, client: AsyncClient):
        job_id = "test-result-url"

        app.dependency_overrides[get_optional_user] = _override_get_optional_user_authenticated
        try:
            with patch("routers.result.firestore.get_job", return_value=make_job_doc(job_id)), \
                 patch("routers.result.firestore.get_result", return_value=make_results_doc(job_id)), \
                 patch("routers.result.firestore.get_summary", return_value=make_summary_doc(job_id)):

                response = await client.get(f"/result/{job_id}")

            assert response.json()["videoUrl"] == "https://signed.url/video.mp4"
        finally:
            app.dependency_overrides.pop(get_optional_user, None)

    async def test_result_includes_is_public_and_share_url_when_public(self, client: AsyncClient):
        """When isPublic=true, response includes isPublic=true and a shareUrl."""
        job_id = "test-result-public"

        app.dependency_overrides[get_optional_user] = _override_get_optional_user_authenticated
        try:
            with patch("routers.result.firestore.get_job", return_value=make_job_doc(job_id, is_public=True)), \
                 patch("routers.result.firestore.get_result", return_value=make_results_doc(job_id)), \
                 patch("routers.result.firestore.get_summary", return_value=make_summary_doc(job_id)):

                response = await client.get(f"/result/{job_id}")

            assert response.status_code == 200
            data = response.json()
            assert data["isPublic"] is True
            assert data["shareUrl"] == f"https://video-intelligence-v1.web.app/share/{job_id}"
        finally:
            app.dependency_overrides.pop(get_optional_user, None)

    async def test_result_includes_is_public_false_and_null_share_url_when_private(self, client: AsyncClient):
        """When isPublic=false, response includes isPublic=false and shareUrl=null."""
        job_id = "test-result-private"

        app.dependency_overrides[get_optional_user] = _override_get_optional_user_authenticated
        try:
            with patch("routers.result.firestore.get_job", return_value=make_job_doc(job_id, is_public=False)), \
                 patch("routers.result.firestore.get_result", return_value=make_results_doc(job_id)), \
                 patch("routers.result.firestore.get_summary", return_value=make_summary_doc(job_id)):

                response = await client.get(f"/result/{job_id}")

            assert response.status_code == 200
            data = response.json()
            assert data["isPublic"] is False
            assert data["shareUrl"] is None
        finally:
            app.dependency_overrides.pop(get_optional_user, None)

    async def test_non_owner_private_job_returns_404(self, client: AsyncClient):
        """Non-owner accessing a private job gets 404."""
        job_id = "test-result-nonowner"

        # Authenticate as a different user
        async def override_different_user():
            return {"uid": "different-user-uid", "email": "other@test.com", "name": "Other"}

        app.dependency_overrides[get_optional_user] = override_different_user
        try:
            with patch("routers.result.firestore.get_job", return_value=make_job_doc(job_id, is_public=False)):
                response = await client.get(f"/result/{job_id}")

            assert response.status_code == 404
            assert "not found" in response.json()["detail"].lower()
        finally:
            app.dependency_overrides.pop(get_optional_user, None)

    async def test_non_owner_public_completed_job_returns_200(self, client: AsyncClient):
        """Non-owner accessing a public completed job gets 200."""
        job_id = "test-result-public-nonowner"

        async def override_different_user():
            return {"uid": "different-user-uid", "email": "other@test.com", "name": "Other"}

        app.dependency_overrides[get_optional_user] = override_different_user
        try:
            with patch("routers.result.firestore.get_job", return_value=make_job_doc(job_id, is_public=True)), \
                 patch("routers.result.firestore.get_result", return_value=make_results_doc(job_id)), \
                 patch("routers.result.firestore.get_summary", return_value=make_summary_doc(job_id)):

                response = await client.get(f"/result/{job_id}")

            assert response.status_code == 200
            data = response.json()
            assert data["isPublic"] is True
            assert data["shareUrl"] is not None
        finally:
            app.dependency_overrides.pop(get_optional_user, None)

    async def test_unauthenticated_public_completed_job_returns_200(self, client: AsyncClient):
        """Unauthenticated user accessing a public completed job gets 200."""
        job_id = "test-result-public-unauth"

        app.dependency_overrides[get_optional_user] = _override_get_optional_user_unauthenticated
        try:
            with patch("routers.result.firestore.get_job", return_value=make_job_doc(job_id, is_public=True)), \
                 patch("routers.result.firestore.get_result", return_value=make_results_doc(job_id)), \
                 patch("routers.result.firestore.get_summary", return_value=make_summary_doc(job_id)):

                response = await client.get(f"/result/{job_id}")

            assert response.status_code == 200
        finally:
            app.dependency_overrides.pop(get_optional_user, None)

    async def test_unauthenticated_private_job_returns_404(self, client: AsyncClient):
        """Unauthenticated user accessing a private job gets 404."""
        job_id = "test-result-private-unauth"

        app.dependency_overrides[get_optional_user] = _override_get_optional_user_unauthenticated
        try:
            with patch("routers.result.firestore.get_job", return_value=make_job_doc(job_id, is_public=False)):
                response = await client.get(f"/result/{job_id}")

            assert response.status_code == 404
        finally:
            app.dependency_overrides.pop(get_optional_user, None)

    async def test_unauthenticated_public_non_completed_job_returns_404(self, client: AsyncClient):
        """Unauthenticated user accessing a public but non-completed job gets 404."""
        job_id = "test-result-public-processing"

        app.dependency_overrides[get_optional_user] = _override_get_optional_user_unauthenticated
        try:
            with patch("routers.result.firestore.get_job", return_value=make_job_doc(job_id, status="processing", is_public=True)):
                response = await client.get(f"/result/{job_id}")

            assert response.status_code == 404
        finally:
            app.dependency_overrides.pop(get_optional_user, None)

    async def test_legacy_job_no_is_public_field_treated_as_private(self, client: AsyncClient):
        """Legacy jobs without isPublic field are treated as private."""
        job_id = "test-result-legacy"

        # Create a job doc without isPublic field (legacy)
        now = datetime.now(timezone.utc)
        legacy_job = {
            "jobId": job_id,
            "status": "completed",
            "progress": 100,
            "videoUrl": "https://signed.url/video.mp4",
            "processingTime": 72,
            "processingStartedAt": now,
            "processingCompletedAt": now,
            "userId": "some-other-user",
            # No isPublic field — legacy job
        }

        app.dependency_overrides[get_optional_user] = _override_get_optional_user_unauthenticated
        try:
            with patch("routers.result.firestore.get_job", return_value=legacy_job):
                response = await client.get(f"/result/{job_id}")

            assert response.status_code == 404
        finally:
            app.dependency_overrides.pop(get_optional_user, None)


class TestGetVideoUrl:
    """Tests for GET /video-url/{job_id} endpoint access control."""

    async def test_authenticated_owner_public_job_returns_200(self, client: AsyncClient):
        """Owner accessing their own public job gets a signed video URL."""
        job_id = "test-video-url-owner-public"

        app.dependency_overrides[get_optional_user] = _override_get_optional_user_authenticated
        try:
            with patch("routers.result.firestore.get_job", return_value=make_job_doc(job_id, is_public=True)), \
                 patch("services.storage.get_signed_url", return_value="https://storage.googleapis.com/signed-video-url"):

                response = await client.get(f"/video-url/{job_id}")

            assert response.status_code == 200
            data = response.json()
            assert data["videoUrl"] == "https://storage.googleapis.com/signed-video-url"
        finally:
            app.dependency_overrides.pop(get_optional_user, None)

    async def test_authenticated_owner_private_job_returns_200(self, client: AsyncClient):
        """Owner accessing their own private job gets a signed video URL."""
        job_id = "test-video-url-owner-private"

        app.dependency_overrides[get_optional_user] = _override_get_optional_user_authenticated
        try:
            with patch("routers.result.firestore.get_job", return_value=make_job_doc(job_id, is_public=False)), \
                 patch("services.storage.get_signed_url", return_value="https://storage.googleapis.com/signed-video-url"):

                response = await client.get(f"/video-url/{job_id}")

            assert response.status_code == 200
            data = response.json()
            assert data["videoUrl"] == "https://storage.googleapis.com/signed-video-url"
        finally:
            app.dependency_overrides.pop(get_optional_user, None)

    async def test_unauthenticated_public_completed_job_returns_200(self, client: AsyncClient):
        """Unauthenticated user accessing a public completed job gets a signed video URL."""
        job_id = "test-video-url-unauth-public"

        app.dependency_overrides[get_optional_user] = _override_get_optional_user_unauthenticated
        try:
            with patch("routers.result.firestore.get_job", return_value=make_job_doc(job_id, is_public=True)), \
                 patch("services.storage.get_signed_url", return_value="https://storage.googleapis.com/signed-video-url"):

                response = await client.get(f"/video-url/{job_id}")

            assert response.status_code == 200
            data = response.json()
            assert data["videoUrl"] == "https://storage.googleapis.com/signed-video-url"
        finally:
            app.dependency_overrides.pop(get_optional_user, None)

    async def test_unauthenticated_private_job_returns_404(self, client: AsyncClient):
        """Unauthenticated user accessing a private job gets 404."""
        job_id = "test-video-url-unauth-private"

        app.dependency_overrides[get_optional_user] = _override_get_optional_user_unauthenticated
        try:
            with patch("routers.result.firestore.get_job", return_value=make_job_doc(job_id, is_public=False)):
                response = await client.get(f"/video-url/{job_id}")

            assert response.status_code == 404
            assert "not found" in response.json()["detail"].lower()
        finally:
            app.dependency_overrides.pop(get_optional_user, None)

    async def test_non_owner_public_completed_job_returns_200(self, client: AsyncClient):
        """Non-owner accessing a public completed job gets a signed video URL."""
        job_id = "test-video-url-nonowner-public"

        async def override_different_user():
            return {"uid": "different-user-uid", "email": "other@test.com", "name": "Other"}

        app.dependency_overrides[get_optional_user] = override_different_user
        try:
            with patch("routers.result.firestore.get_job", return_value=make_job_doc(job_id, is_public=True)), \
                 patch("services.storage.get_signed_url", return_value="https://storage.googleapis.com/signed-video-url"):

                response = await client.get(f"/video-url/{job_id}")

            assert response.status_code == 200
            data = response.json()
            assert data["videoUrl"] == "https://storage.googleapis.com/signed-video-url"
        finally:
            app.dependency_overrides.pop(get_optional_user, None)

    async def test_non_owner_private_job_returns_404(self, client: AsyncClient):
        """Non-owner accessing a private job gets 404."""
        job_id = "test-video-url-nonowner-private"

        async def override_different_user():
            return {"uid": "different-user-uid", "email": "other@test.com", "name": "Other"}

        app.dependency_overrides[get_optional_user] = override_different_user
        try:
            with patch("routers.result.firestore.get_job", return_value=make_job_doc(job_id, is_public=False)):
                response = await client.get(f"/video-url/{job_id}")

            assert response.status_code == 404
            assert "not found" in response.json()["detail"].lower()
        finally:
            app.dependency_overrides.pop(get_optional_user, None)

    async def test_unauthenticated_public_non_completed_job_returns_404(self, client: AsyncClient):
        """Unauthenticated user accessing a public but non-completed job gets 404."""
        job_id = "test-video-url-unauth-processing"

        app.dependency_overrides[get_optional_user] = _override_get_optional_user_unauthenticated
        try:
            with patch("routers.result.firestore.get_job", return_value=make_job_doc(job_id, status="processing", is_public=True)):
                response = await client.get(f"/video-url/{job_id}")

            assert response.status_code == 404
            assert "not found" in response.json()["detail"].lower()
        finally:
            app.dependency_overrides.pop(get_optional_user, None)

    async def test_legacy_job_no_is_public_field_treated_as_private(self, client: AsyncClient):
        """Legacy jobs without isPublic field are treated as private."""
        job_id = "test-video-url-legacy"

        now = datetime.now(timezone.utc)
        legacy_job = {
            "jobId": job_id,
            "status": "completed",
            "progress": 100,
            "videoUrl": "https://signed.url/video.mp4",
            "processingTime": 72,
            "processingStartedAt": now,
            "processingCompletedAt": now,
            "userId": "some-other-user",
            "gcsPath": f"uploads/some-other-user/{job_id}/video.mp4",
            # No isPublic field — legacy job
        }

        app.dependency_overrides[get_optional_user] = _override_get_optional_user_unauthenticated
        try:
            with patch("routers.result.firestore.get_job", return_value=legacy_job):
                response = await client.get(f"/video-url/{job_id}")

            assert response.status_code == 404
            assert "not found" in response.json()["detail"].lower()
        finally:
            app.dependency_overrides.pop(get_optional_user, None)

    async def test_nonexistent_job_returns_404(self, client: AsyncClient):
        """Requesting video URL for a non-existent job returns 404."""
        with patch("routers.result.firestore.get_job", return_value=None):
            response = await client.get("/video-url/nonexistent-job")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
