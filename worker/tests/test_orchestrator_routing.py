# worker/tests/test_orchestrator_routing.py
"""
Unit tests for audio-only orchestrator routing in run_pipeline().

Validates:
- Req 1.1: Audio MIME types (case-insensitive, params stripped) → audio-only path
- Req 1.2: Non-audio MIME types → video path
- Req 1.4: Empty/null contentType → video path
- Req 2.1: Audio-only → only STT, no VI
- Req 2.2: Audio-only → scenes = []
- Req 2.3: Audio-only → progress=75 after STT
- Req 2.4: Video → both STT and VI concurrently
- Req 3.1: Audio-only STT failure → mark job failed with error message
- Req 3.2: Audio-only STT failure → return False, no partial results
"""

import os

# Set required env vars before importing pipeline modules
os.environ.setdefault("GCP_PROJECT_ID", "test-project")
os.environ.setdefault("GCP_BUCKET_NAME", "test-bucket")
os.environ.setdefault("GCP_SERVICE_ACCOUNT_EMAIL", "test@test.iam.gserviceaccount.com")

import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock, call

from models.schemas import JobMessage
from pipeline.orchestrator import run_pipeline, _is_audio_only


def _make_job_message(content_type: str = "video/mp4") -> JobMessage:
    """Create a test JobMessage with the given contentType."""
    return JobMessage(
        jobId="test-job-001",
        gcsPath="raw-videos/test-job-001/test.mp4",
        gcsBucket="test-bucket",
        gcsUri="gs://test-bucket/raw-videos/test-job-001/test.mp4",
        filename="test.mp4",
        fileSizeMb=10.5,
        contentType=content_type,
        uploadedAt="2024-01-01T00:00:00Z",
        schemaVersion="1",
    )


@pytest.fixture
def mock_firestore():
    """Mock the firestore service module."""
    with patch("pipeline.orchestrator.firestore") as mock_fs:
        mock_fs.update_job_status = MagicMock()
        mock_fs.mark_processing_failed = MagicMock()
        mock_fs.mark_processing_completed = MagicMock()
        mock_fs.write_results = MagicMock()
        mock_fs.write_summary = MagicMock()
        yield mock_fs


@pytest.fixture
def mock_stt():
    """Mock _run_stt_with_progress to return a fake (transcript, detected_language) tuple."""
    with patch("pipeline.orchestrator._run_stt_with_progress", new_callable=AsyncMock) as mock:
        mock.return_value = (
            [
                {"word": "hello", "startTime": 0.0, "endTime": 0.5, "speaker": 1},
                {"word": "world", "startTime": 0.5, "endTime": 1.0, "speaker": 1},
            ],
            "en-IN",
        )
        yield mock


@pytest.fixture
def mock_vi():
    """Mock _run_vi_with_progress to return fake scenes."""
    with patch("pipeline.orchestrator._run_vi_with_progress", new_callable=AsyncMock) as mock:
        mock.return_value = [
            {"startTime": 0.0, "endTime": 5.0, "confidence": 0.9, "labels": ["intro"]},
        ]
        yield mock


@pytest.fixture
def mock_generate_summary():
    """Mock generate_summary to return a fake summary."""
    with patch("pipeline.orchestrator.generate_summary", new_callable=AsyncMock) as mock:
        mock.return_value = {
            "summary": "Test summary",
            "chapters": [],
            "highlights": [],
            "sentiment": "neutral",
            "actionItems": [],
        }
        yield mock


class TestAudioOnlyPath:
    """Tests for audio-only routing (contentType in AUDIO_ONLY_MIME_TYPES)."""

    @pytest.mark.asyncio
    async def test_audio_only_skips_vi(
        self, mock_firestore, mock_stt, mock_vi, mock_generate_summary
    ):
        """
        Req 1.1, 2.1: Audio MIME type routes to audio-only path; VI is NOT called.
        """
        job = _make_job_message(content_type="audio/mpeg")

        result = await run_pipeline(job)

        assert result is True
        mock_stt.assert_called_once()
        mock_vi.assert_not_called()

    @pytest.mark.asyncio
    async def test_audio_only_scenes_empty(
        self, mock_firestore, mock_stt, mock_vi, mock_generate_summary
    ):
        """
        Req 2.2: Audio-only path sets scenes to an empty list.
        """
        job = _make_job_message(content_type="audio/mpeg")

        await run_pipeline(job)

        # Verify write_results is called with scenes=[]
        mock_firestore.write_results.assert_called_once()
        call_kwargs = mock_firestore.write_results.call_args
        assert call_kwargs.kwargs.get("scenes") == [] or (
            len(call_kwargs.args) >= 3 and call_kwargs.args[2] == []
        )

    @pytest.mark.asyncio
    async def test_audio_only_progress_75_after_stt(
        self, mock_firestore, mock_stt, mock_vi, mock_generate_summary
    ):
        """
        Req 2.3: Audio-only path sets progress=75 after STT completes.
        """
        job = _make_job_message(content_type="audio/mpeg")

        await run_pipeline(job)

        # Check that update_job_status was called with progress=75
        progress_calls = [
            c for c in mock_firestore.update_job_status.call_args_list
            if c.kwargs.get("progress") == 75
            or (len(c.args) >= 3 and c.args[2] == 75)
        ]
        assert len(progress_calls) >= 1, (
            f"Expected at least one update_job_status call with progress=75. "
            f"Actual calls: {mock_firestore.update_job_status.call_args_list}"
        )


class TestVideoPath:
    """Tests for video routing (contentType NOT in AUDIO_ONLY_MIME_TYPES)."""

    @pytest.mark.asyncio
    async def test_video_calls_both_stt_and_vi(
        self, mock_firestore, mock_stt, mock_vi, mock_generate_summary
    ):
        """
        Req 1.2, 2.4: Non-audio MIME type routes to video path; both STT and VI called.
        """
        job = _make_job_message(content_type="video/mp4")

        result = await run_pipeline(job)

        assert result is True
        mock_stt.assert_called_once()
        mock_vi.assert_called_once()


class TestEdgeCases:
    """Tests for edge cases in contentType routing."""

    @pytest.mark.asyncio
    async def test_empty_content_type_routes_to_video(
        self, mock_firestore, mock_stt, mock_vi, mock_generate_summary
    ):
        """
        Req 1.4: Empty contentType routes to video path (both STT and VI called).
        """
        job = _make_job_message(content_type="")

        result = await run_pipeline(job)

        assert result is True
        mock_stt.assert_called_once()
        mock_vi.assert_called_once()

    @pytest.mark.asyncio
    async def test_mime_params_stripped_routes_audio_only(
        self, mock_firestore, mock_stt, mock_vi, mock_generate_summary
    ):
        """
        Req 1.1: MIME parameters after semicolon are stripped.
        "audio/mpeg; codecs=mp3" normalizes to "audio/mpeg" → audio-only path.
        """
        job = _make_job_message(content_type="audio/mpeg; codecs=mp3")

        result = await run_pipeline(job)

        assert result is True
        mock_stt.assert_called_once()
        mock_vi.assert_not_called()


class TestAudioOnlySTTFailure:
    """Tests for STT failure handling on audio-only files."""

    @pytest.mark.asyncio
    async def test_stt_failure_marks_job_failed(
        self, mock_firestore, mock_vi, mock_generate_summary
    ):
        """
        Req 3.1: Audio-only STT failure marks job as failed with error message.
        """
        with patch(
            "pipeline.orchestrator._run_stt_with_progress",
            new_callable=AsyncMock,
        ) as mock_stt_fail:
            mock_stt_fail.side_effect = RuntimeError("Corrupt audio file")

            job = _make_job_message(content_type="audio/mpeg")
            result = await run_pipeline(job)

            assert result is False
            mock_firestore.mark_processing_failed.assert_called_once()
            error_msg = mock_firestore.mark_processing_failed.call_args[0][1]
            assert "Corrupt audio file" in error_msg

    @pytest.mark.asyncio
    async def test_stt_failure_returns_false_no_partial_results(
        self, mock_firestore, mock_vi, mock_generate_summary
    ):
        """
        Req 3.2: Audio-only STT failure returns False and does NOT write partial results.
        """
        with patch(
            "pipeline.orchestrator._run_stt_with_progress",
            new_callable=AsyncMock,
        ) as mock_stt_fail:
            mock_stt_fail.side_effect = RuntimeError("Unsupported codec")

            job = _make_job_message(content_type="audio/mpeg")
            result = await run_pipeline(job)

            assert result is False
            # No results should be written to Firestore
            mock_firestore.write_results.assert_not_called()
            mock_firestore.write_summary.assert_not_called()
            mock_firestore.mark_processing_completed.assert_not_called()
            # VI should not be called for audio-only path
            mock_vi.assert_not_called()
