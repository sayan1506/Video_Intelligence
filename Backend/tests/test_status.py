from unittest.mock import patch
from datetime import datetime, timezone
from httpx import AsyncClient


def make_job_doc(job_id: str, status: str = "pending", progress: int = 0) -> dict:
    """Build a fake Firestore job document for mocking."""
    now = datetime.now(timezone.utc)
    return {
        "jobId": job_id,
        "status": status,
        "progress": progress,
        "uploadProgress": 100,
        "videoUrl": "https://signed.url/video.mp4",
        "filename": "test.mp4",
        "gcsPath": f"raw-videos/{job_id}/test.mp4",
        "createdAt": now,
        "updatedAt": now,
        "processingTime": 0,
        "errorMessage": "",
    }


class TestGetStatus:

    async def test_known_job_returns_200(self, client: AsyncClient):
        job_id = "test-job-001"

        with patch("routers.status.firestore.get_job",
                   return_value=make_job_doc(job_id)):
            response = await client.get(f"/status/{job_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["jobId"] == job_id
        assert data["status"] == "pending"
        assert data["progress"] == 0

    async def test_status_response_includes_video_url(self, client: AsyncClient):
        job_id = "test-job-002"

        with patch("routers.status.firestore.get_job",
                   return_value=make_job_doc(job_id, status="pending")):
            response = await client.get(f"/status/{job_id}")

        assert response.status_code == 200
        assert response.json()["videoUrl"] == "https://signed.url/video.mp4"

    async def test_status_values_cycle_correctly(self, client: AsyncClient):
        for status in ["pending", "processing", "completed", "failed"]:
            with patch("routers.status.firestore.get_job",
                       return_value=make_job_doc("job-x", status=status)):
                response = await client.get("/status/job-x")

            assert response.status_code == 200
            assert response.json()["status"] == status

    async def test_unknown_job_returns_404(self, client: AsyncClient):
        with patch("routers.status.firestore.get_job", return_value=None):
            response = await client.get("/status/nonexistent-job-id")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    async def test_firestore_error_returns_503(self, client: AsyncClient):
        from google.api_core.exceptions import ServiceUnavailable

        with patch("routers.status.firestore.get_job") as mock_get:
            mock_get.side_effect = ServiceUnavailable("Firestore unavailable")
            response = await client.get("/status/any-job-id")

        assert response.status_code == 503
        assert "unavailable" in response.json()["detail"].lower()

    async def test_progress_field_is_integer(self, client: AsyncClient):
        with patch("routers.status.firestore.get_job",
                   return_value=make_job_doc("job-y", progress=25)):
            response = await client.get("/status/job-y")

        assert isinstance(response.json()["progress"], int)
        assert response.json()["progress"] == 25


class TestHealthEndpoint:

    async def test_health_returns_200(self, client: AsyncClient):
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
        assert response.json()["service"] == "vidiq-api"