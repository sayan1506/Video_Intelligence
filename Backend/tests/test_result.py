from unittest.mock import patch
from datetime import datetime, timezone
from httpx import AsyncClient


def make_job_doc(job_id: str, status: str = "completed") -> dict:
    now = datetime.now(timezone.utc)
    return {
        "jobId": job_id,
        "status": status,
        "progress": 100 if status == "completed" else 50,
        "videoUrl": "https://signed.url/video.mp4",
        "processingTime": 72,
        "processingStartedAt": now,
        "processingCompletedAt": now,
    }


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

        with patch("routers.result.firestore.get_job", return_value=make_job_doc(job_id)), \
             patch("routers.result.firestore.get_result", return_value=make_results_doc(job_id)), \
             patch("routers.result.firestore.get_summary", return_value=make_summary_doc(job_id)):

            response = await client.get(f"/result/{job_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["jobId"] == job_id
        assert data["status"] == "completed"

    async def test_result_contains_transcript_and_scenes(self, client: AsyncClient):
        job_id = "test-result-002"

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

    async def test_result_contains_summary_fields(self, client: AsyncClient):
        job_id = "test-result-003"

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

    async def test_pending_job_returns_400(self, client: AsyncClient):
        job_id = "test-result-pending"

        with patch("routers.result.firestore.get_job",
                   return_value=make_job_doc(job_id, status="pending")), \
             patch("routers.result.firestore.get_result", return_value=None), \
             patch("routers.result.firestore.get_summary", return_value=None):

            response = await client.get(f"/result/{job_id}")

        assert response.status_code == 400
        assert "not completed yet" in response.json()["detail"]
        assert "pending" in response.json()["detail"]

    async def test_processing_job_returns_400(self, client: AsyncClient):
        job_id = "test-result-processing"

        with patch("routers.result.firestore.get_job",
                   return_value=make_job_doc(job_id, status="processing")), \
             patch("routers.result.firestore.get_result", return_value=None), \
             patch("routers.result.firestore.get_summary", return_value=None):

            response = await client.get(f"/result/{job_id}")

        assert response.status_code == 400
        assert "processing" in response.json()["detail"]

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

    async def test_missing_results_doc_returns_200_with_null_transcript(self, client: AsyncClient):
        """
        Results doc may be absent if worker Phase 1 partially failed.
        Should still return 200 — job is completed, just with null AI fields.
        """
        job_id = "test-result-no-results"

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

    async def test_firestore_error_returns_503(self, client: AsyncClient):
        from google.api_core.exceptions import ServiceUnavailable

        with patch("routers.result.firestore.get_job") as mock_get:
            mock_get.side_effect = ServiceUnavailable("Firestore unavailable")
            response = await client.get("/result/any-job-id")

        assert response.status_code == 503
        assert "unavailable" in response.json()["detail"].lower()

    async def test_video_url_in_result_response(self, client: AsyncClient):
        job_id = "test-result-url"

        with patch("routers.result.firestore.get_job", return_value=make_job_doc(job_id)), \
             patch("routers.result.firestore.get_result", return_value=make_results_doc(job_id)), \
             patch("routers.result.firestore.get_summary", return_value=make_summary_doc(job_id)):

            response = await client.get(f"/result/{job_id}")

        assert response.json()["videoUrl"] == "https://signed.url/video.mp4"