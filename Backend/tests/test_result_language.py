"""
Integration tests for Backend API multi-language support fields.

Tests that the GET /result/{job_id} endpoint correctly returns:
- detectedLanguage from results doc (Req 4.3)
- null when detectedLanguage is missing (Req 4.4)
- translatedTranscript from summary doc (Req 4.5)
- null when translatedTranscript fails to parse (Req 4.6)
- null when translatedTranscript is missing (Req 4.7)
"""

from unittest.mock import patch
from datetime import datetime, timezone
from httpx import AsyncClient

from main import app
from middleware.auth import get_optional_user


# Fixed test user for authenticated owner tests
TEST_USER = {"uid": "test-owner-uid", "email": "owner@test.com", "name": "Test Owner"}


async def _override_get_optional_user_authenticated():
    """Override that returns a fixed authenticated user."""
    return TEST_USER


def make_job_doc(job_id: str) -> dict:
    """Create a minimal completed job doc owned by TEST_USER."""
    now = datetime.now(timezone.utc)
    return {
        "jobId": job_id,
        "status": "completed",
        "progress": 100,
        "videoUrl": "https://signed.url/video.mp4",
        "processingTime": 72,
        "processingStartedAt": now,
        "processingCompletedAt": now,
        "userId": TEST_USER["uid"],
        "isPublic": False,
        "gcsPath": f"uploads/{TEST_USER['uid']}/{job_id}/video.mp4",
    }


def make_results_doc(job_id: str, detected_language: str | None = None) -> dict:
    """Create a results doc, optionally including detectedLanguage."""
    doc = {
        "jobId": job_id,
        "transcript": [
            {"word": "Hello", "startTime": 0.4, "endTime": 0.8, "speaker": 1},
            {"word": "world", "startTime": 0.9, "endTime": 1.2, "speaker": 1},
        ],
        "scenes": [
            {"startTime": 0.0, "endTime": 5.2, "labels": ["person", "indoor"]},
        ],
        "labels": ["person", "indoor"],
    }
    if detected_language is not None:
        doc["detectedLanguage"] = detected_language
    return doc


def make_summary_doc(job_id: str, translated_transcript: list | None = None) -> dict:
    """Create a summary doc, optionally including translatedTranscript."""
    doc = {
        "jobId": job_id,
        "summary": "Test summary.",
        "chapters": [
            {"title": "Introduction", "startTime": 0, "endTime": 60},
        ],
        "highlights": [
            {"timestamp": 2.6, "description": "Scene featuring person"},
        ],
        "sentiment": "neutral",
        "actionItems": [],
    }
    if translated_transcript is not None:
        doc["translatedTranscript"] = translated_transcript
    return doc


class TestResultLanguageFields:
    """Integration tests for detectedLanguage and translatedTranscript API fields."""

    async def test_api_returns_detected_language_from_results_doc(self, client: AsyncClient):
        """
        Req 4.3: WHEN the results/{jobId} document contains a detectedLanguage field,
        THE Backend_API SHALL include the value in the ResultResponse.
        """
        job_id = "test-lang-001"

        app.dependency_overrides[get_optional_user] = _override_get_optional_user_authenticated
        try:
            with patch("routers.result.firestore.get_job", return_value=make_job_doc(job_id)), \
                 patch("routers.result.firestore.get_result", return_value=make_results_doc(job_id, detected_language="hi-IN")), \
                 patch("routers.result.firestore.get_summary", return_value=make_summary_doc(job_id)):

                response = await client.get(f"/result/{job_id}")

            assert response.status_code == 200
            data = response.json()
            assert data["detectedLanguage"] == "hi-IN"
        finally:
            app.dependency_overrides.pop(get_optional_user, None)

    async def test_api_returns_null_when_detected_language_missing(self, client: AsyncClient):
        """
        Req 4.4: WHEN the results/{jobId} document does not contain a detectedLanguage field,
        THE Backend_API SHALL return null for the detectedLanguage field.
        """
        job_id = "test-lang-002"

        app.dependency_overrides[get_optional_user] = _override_get_optional_user_authenticated
        try:
            # results doc without detectedLanguage field
            with patch("routers.result.firestore.get_job", return_value=make_job_doc(job_id)), \
                 patch("routers.result.firestore.get_result", return_value=make_results_doc(job_id)), \
                 patch("routers.result.firestore.get_summary", return_value=make_summary_doc(job_id)):

                response = await client.get(f"/result/{job_id}")

            assert response.status_code == 200
            data = response.json()
            assert data["detectedLanguage"] is None
        finally:
            app.dependency_overrides.pop(get_optional_user, None)

    async def test_api_returns_translated_transcript_from_summary_doc(self, client: AsyncClient):
        """
        Req 4.5: WHEN the summaries/{jobId} document contains a translatedTranscript field,
        THE Backend_API SHALL parse the array into a list of WordTimestamp objects and
        include it in the ResultResponse.
        """
        job_id = "test-lang-003"
        translated = [
            {"word": "Hello", "startTime": 0.4, "endTime": 0.6, "speaker": 1},
            {"word": "my", "startTime": 0.6, "endTime": 0.8, "speaker": 1},
            {"word": "name", "startTime": 0.9, "endTime": 1.0, "speaker": 1},
            {"word": "is", "startTime": 1.0, "endTime": 1.1, "speaker": 1},
            {"word": "Sayan", "startTime": 1.1, "endTime": 1.2, "speaker": 1},
        ]

        app.dependency_overrides[get_optional_user] = _override_get_optional_user_authenticated
        try:
            with patch("routers.result.firestore.get_job", return_value=make_job_doc(job_id)), \
                 patch("routers.result.firestore.get_result", return_value=make_results_doc(job_id, detected_language="hi-IN")), \
                 patch("routers.result.firestore.get_summary", return_value=make_summary_doc(job_id, translated_transcript=translated)):

                response = await client.get(f"/result/{job_id}")

            assert response.status_code == 200
            data = response.json()
            assert data["translatedTranscript"] is not None
            assert len(data["translatedTranscript"]) == 5
            assert data["translatedTranscript"][0]["word"] == "Hello"
            assert data["translatedTranscript"][0]["startTime"] == 0.4
            assert data["translatedTranscript"][0]["endTime"] == 0.6
            assert data["translatedTranscript"][0]["speaker"] == 1
            assert data["translatedTranscript"][4]["word"] == "Sayan"
        finally:
            app.dependency_overrides.pop(get_optional_user, None)

    async def test_api_handles_parse_failure_gracefully(self, client: AsyncClient):
        """
        Req 4.6: IF the translatedTranscript field fails to parse,
        THEN THE Backend_API SHALL log a warning and return null for the field.
        """
        job_id = "test-lang-004"
        # Malformed entries: missing required fields (word, startTime, endTime)
        malformed_transcript = [
            {"word": "Hello", "startTime": 0.4},  # missing endTime
            {"startTime": 0.6, "endTime": 0.8},  # missing word
            {"invalid_key": "bad_data"},  # completely wrong schema
        ]

        app.dependency_overrides[get_optional_user] = _override_get_optional_user_authenticated
        try:
            with patch("routers.result.firestore.get_job", return_value=make_job_doc(job_id)), \
                 patch("routers.result.firestore.get_result", return_value=make_results_doc(job_id, detected_language="hi-IN")), \
                 patch("routers.result.firestore.get_summary", return_value=make_summary_doc(job_id, translated_transcript=malformed_transcript)):

                response = await client.get(f"/result/{job_id}")

            assert response.status_code == 200
            data = response.json()
            # Should gracefully return null instead of crashing
            assert data["translatedTranscript"] is None
        finally:
            app.dependency_overrides.pop(get_optional_user, None)

    async def test_api_returns_null_when_translated_transcript_missing(self, client: AsyncClient):
        """
        Req 4.7: WHEN the summaries/{jobId} document does not contain a translatedTranscript field,
        THE Backend_API SHALL return null for the translatedTranscript field.
        """
        job_id = "test-lang-005"

        app.dependency_overrides[get_optional_user] = _override_get_optional_user_authenticated
        try:
            # summary doc without translatedTranscript field
            with patch("routers.result.firestore.get_job", return_value=make_job_doc(job_id)), \
                 patch("routers.result.firestore.get_result", return_value=make_results_doc(job_id, detected_language="en-IN")), \
                 patch("routers.result.firestore.get_summary", return_value=make_summary_doc(job_id)):

                response = await client.get(f"/result/{job_id}")

            assert response.status_code == 200
            data = response.json()
            assert data["translatedTranscript"] is None
        finally:
            app.dependency_overrides.pop(get_optional_user, None)

    async def test_api_returns_detected_language_empty_string(self, client: AsyncClient):
        """
        When detectedLanguage is stored as empty string, API should return it as-is.
        """
        job_id = "test-lang-006"

        app.dependency_overrides[get_optional_user] = _override_get_optional_user_authenticated
        try:
            with patch("routers.result.firestore.get_job", return_value=make_job_doc(job_id)), \
                 patch("routers.result.firestore.get_result", return_value=make_results_doc(job_id, detected_language="")), \
                 patch("routers.result.firestore.get_summary", return_value=make_summary_doc(job_id)):

                response = await client.get(f"/result/{job_id}")

            assert response.status_code == 200
            data = response.json()
            assert data["detectedLanguage"] == ""
        finally:
            app.dependency_overrides.pop(get_optional_user, None)

    async def test_api_returns_null_for_both_fields_when_no_results_doc(self, client: AsyncClient):
        """
        When results doc is None, detectedLanguage should be null.
        When summary doc is None, translatedTranscript should be null.
        """
        job_id = "test-lang-007"

        app.dependency_overrides[get_optional_user] = _override_get_optional_user_authenticated
        try:
            with patch("routers.result.firestore.get_job", return_value=make_job_doc(job_id)), \
                 patch("routers.result.firestore.get_result", return_value=None), \
                 patch("routers.result.firestore.get_summary", return_value=None):

                response = await client.get(f"/result/{job_id}")

            assert response.status_code == 200
            data = response.json()
            assert data["detectedLanguage"] is None
            assert data["translatedTranscript"] is None
        finally:
            app.dependency_overrides.pop(get_optional_user, None)
