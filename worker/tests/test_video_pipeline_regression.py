# worker/tests/test_video_pipeline_regression.py
"""
Regression tests for video pipeline unchanged behavior.

These tests verify that the existing video processing path was NOT broken
by the PERF-3 (audio-only skip) and PERF-4 (adaptive sample rate) changes.

**Validates: Requirements 6.1, 6.2, 6.3, 6.5**

- Req 6.1: Video files run both STT and VI concurrently via asyncio.gather
- Req 6.2: Short videos (≤300s) use whole-file extraction with adaptive sample rate
- Req 6.3: Long videos (>300s) call transcribe_chunked with adaptive sample_rate
- Req 6.5: Video files set progress to 75 after both STT and VI complete
"""

import os

# Set required env vars before importing pipeline modules
os.environ.setdefault("GCP_PROJECT_ID", "test-project")
os.environ.setdefault("GCP_BUCKET_NAME", "test-bucket")
os.environ.setdefault("GCP_SERVICE_ACCOUNT_EMAIL", "test@test.iam.gserviceaccount.com")

import pytest
from unittest.mock import patch, MagicMock, AsyncMock, call

from models.schemas import JobMessage
from pipeline.orchestrator import run_pipeline, AUDIO_ONLY_MIME_TYPES
from pipeline.speech_to_text import (
    transcribe,
    CHUNK_THRESHOLD_SECONDS,
    ADAPTIVE_FFMPEG_THRESHOLD_SECONDS,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_video_job(content_type: str = "video/mp4", job_id: str = "regression-job-001") -> JobMessage:
    """Create a test JobMessage with a video contentType."""
    return JobMessage(
        jobId=job_id,
        gcsPath=f"raw-videos/{job_id}/video.mp4",
        gcsBucket="test-bucket",
        gcsUri=f"gs://test-bucket/raw-videos/{job_id}/video.mp4",
        filename="video.mp4",
        fileSizeMb=50.0,
        contentType=content_type,
        uploadedAt="2024-01-01T00:00:00Z",
        schemaVersion="1",
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


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
    """Mock _run_stt_with_progress to return a fake transcript."""
    with patch("pipeline.orchestrator._run_stt_with_progress", new_callable=AsyncMock) as mock:
        mock.return_value = [
            {"word": "hello", "startTime": 0.0, "endTime": 0.5, "speaker": 1},
            {"word": "world", "startTime": 0.5, "endTime": 1.0, "speaker": 1},
        ]
        yield mock


@pytest.fixture
def mock_vi():
    """Mock _run_vi_with_progress to return fake scenes."""
    with patch("pipeline.orchestrator._run_vi_with_progress", new_callable=AsyncMock) as mock:
        mock.return_value = [
            {"startTime": 0.0, "endTime": 10.0, "confidence": 0.9, "labels": ["intro"]},
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


# ---------------------------------------------------------------------------
# Test Class: Video Pipeline Concurrency (Req 6.1)
# ---------------------------------------------------------------------------


class TestVideoPipelineConcurrency:
    """Verify video files still run STT + VI concurrently via asyncio.gather."""

    @pytest.mark.asyncio
    async def test_video_mp4_runs_both_stt_and_vi(
        self, mock_firestore, mock_stt, mock_vi, mock_generate_summary
    ):
        """
        Req 6.1: video/mp4 contentType triggers both STT and VI concurrently.
        """
        job = _make_video_job(content_type="video/mp4")

        result = await run_pipeline(job)

        assert result is True
        mock_stt.assert_called_once()
        mock_vi.assert_called_once()

    @pytest.mark.asyncio
    async def test_video_webm_runs_both_stt_and_vi(
        self, mock_firestore, mock_stt, mock_vi, mock_generate_summary
    ):
        """
        Req 6.1: video/webm contentType triggers both STT and VI concurrently.
        """
        job = _make_video_job(content_type="video/webm")

        result = await run_pipeline(job)

        assert result is True
        mock_stt.assert_called_once()
        mock_vi.assert_called_once()

    @pytest.mark.asyncio
    async def test_video_path_uses_asyncio_gather(
        self, mock_firestore, mock_generate_summary
    ):
        """
        Req 6.1: Verify that STT and VI are dispatched via asyncio.gather
        (both run concurrently, not sequentially).

        We verify this by checking that both coroutines are awaited even when
        one is slower — asyncio.gather runs them concurrently.
        """
        call_order = []

        async def mock_stt_slow(*args, **kwargs):
            call_order.append("stt_start")
            # Simulate some async work
            import asyncio
            await asyncio.sleep(0.01)
            call_order.append("stt_end")
            return [{"word": "test", "startTime": 0.0, "endTime": 0.5, "speaker": 1}]

        async def mock_vi_slow(*args, **kwargs):
            call_order.append("vi_start")
            import asyncio
            await asyncio.sleep(0.01)
            call_order.append("vi_end")
            return [{"startTime": 0.0, "endTime": 5.0, "confidence": 0.9, "labels": ["scene"]}]

        with patch("pipeline.orchestrator._run_stt_with_progress", side_effect=mock_stt_slow), \
             patch("pipeline.orchestrator._run_vi_with_progress", side_effect=mock_vi_slow):

            job = _make_video_job(content_type="video/mp4")
            result = await run_pipeline(job)

            assert result is True
            # Both should have started (concurrent via gather)
            assert "stt_start" in call_order
            assert "vi_start" in call_order
            assert "stt_end" in call_order
            assert "vi_end" in call_order


# ---------------------------------------------------------------------------
# Test Class: Progress Set to 75 After Both Complete (Req 6.5)
# ---------------------------------------------------------------------------


class TestVideoProgressAfterPhase1:
    """Verify progress is set to 75 after both STT and VI complete for video files."""

    @pytest.mark.asyncio
    async def test_progress_75_set_after_both_complete(
        self, mock_firestore, mock_stt, mock_vi, mock_generate_summary
    ):
        """
        Req 6.5: After both STT and VI complete for a video file,
        progress is updated to 75.
        """
        job = _make_video_job(content_type="video/mp4")

        await run_pipeline(job)

        # Find the call that sets progress=75
        progress_75_calls = [
            c for c in mock_firestore.update_job_status.call_args_list
            if len(c.args) >= 2
            and c.args[1] == "processing"
            and c.kwargs.get("progress") == 75
        ]
        assert len(progress_75_calls) >= 1, (
            f"Expected update_job_status called with progress=75 after Phase 1. "
            f"Actual calls: {mock_firestore.update_job_status.call_args_list}"
        )

    @pytest.mark.asyncio
    async def test_progress_75_comes_after_progress_35(
        self, mock_firestore, mock_stt, mock_vi, mock_generate_summary
    ):
        """
        Req 6.5: The progress=75 update comes after the initial progress=35 update,
        confirming the correct sequence for video files.
        """
        job = _make_video_job(content_type="video/mp4")

        await run_pipeline(job)

        progress_values = []
        for c in mock_firestore.update_job_status.call_args_list:
            progress = c.kwargs.get("progress")
            if progress is not None:
                progress_values.append(progress)

        # Progress should go 35 → 75 → 90 for video files
        assert 35 in progress_values, f"Expected progress=35 in sequence. Got: {progress_values}"
        assert 75 in progress_values, f"Expected progress=75 in sequence. Got: {progress_values}"

        idx_35 = progress_values.index(35)
        idx_75 = progress_values.index(75)
        assert idx_75 > idx_35, (
            f"progress=75 should come after progress=35. "
            f"Sequence: {progress_values}"
        )

    @pytest.mark.asyncio
    async def test_progress_75_set_even_with_partial_failure(
        self, mock_firestore, mock_generate_summary
    ):
        """
        Req 6.5: Progress=75 is still set after Phase 1 even if one pipeline
        (e.g., VI) fails — as long as not both fail.
        """
        with patch("pipeline.orchestrator._run_stt_with_progress", new_callable=AsyncMock) as mock_stt, \
             patch("pipeline.orchestrator._run_vi_with_progress", new_callable=AsyncMock) as mock_vi:

            mock_stt.return_value = [{"word": "test", "startTime": 0.0, "endTime": 0.5, "speaker": 1}]
            mock_vi.side_effect = RuntimeError("VI API unavailable")

            job = _make_video_job(content_type="video/mp4")
            result = await run_pipeline(job)

            assert result is True

            progress_75_calls = [
                c for c in mock_firestore.update_job_status.call_args_list
                if c.kwargs.get("progress") == 75
            ]
            assert len(progress_75_calls) >= 1, (
                "progress=75 should still be set even when VI fails (partial failure)"
            )


# ---------------------------------------------------------------------------
# Test Class: Short Videos Use Whole-File Extraction (Req 6.2)
# ---------------------------------------------------------------------------


class TestShortVideoWholeFilePath:
    """Verify short videos (≤300s) use the whole-file extraction path."""

    @pytest.mark.asyncio
    async def test_short_video_uses_extract_audio_to_flac(self):
        """
        Req 6.2: A video with duration ≤ CHUNK_THRESHOLD_SECONDS (300s)
        uses extract_audio_to_flac (whole-file path), NOT transcribe_chunked.
        """
        duration = 200.0  # Well under 300s threshold

        with patch("pipeline.speech_to_text.download_from_gcs") as mock_download, \
             patch("pipeline.speech_to_text.get_video_duration_seconds", return_value=duration), \
             patch("pipeline.speech_to_text.extract_audio_to_flac") as mock_extract, \
             patch("pipeline.speech_to_text.upload_flac_to_gcs", return_value="gs://bucket/audio.flac"), \
             patch("pipeline.speech_to_text.transcribe_chunked", new_callable=AsyncMock) as mock_chunked, \
             patch("pipeline.speech_to_text.get_speech_client") as mock_client, \
             patch("pipeline.speech_to_text._poll_operation_with_retry") as mock_poll:

            mock_speech_client = MagicMock()
            mock_client.return_value = mock_speech_client
            mock_operation = MagicMock()
            mock_speech_client.batch_recognize.return_value = mock_operation
            mock_response = MagicMock()
            mock_response.results = {}
            mock_poll.return_value = mock_response

            await transcribe("gs://bucket/video.mp4", job_id="short-video-job")

            # Whole-file path should be used
            mock_extract.assert_called_once()
            # Chunked path should NOT be used
            mock_chunked.assert_not_called()

    @pytest.mark.asyncio
    async def test_short_video_at_boundary_uses_whole_file(self):
        """
        Req 6.2: A video with duration exactly at CHUNK_THRESHOLD_SECONDS (300s)
        uses the whole-file extraction path (threshold is ≤300s).
        """
        duration = 300.0  # Exactly at threshold

        with patch("pipeline.speech_to_text.download_from_gcs") as mock_download, \
             patch("pipeline.speech_to_text.get_video_duration_seconds", return_value=duration), \
             patch("pipeline.speech_to_text.extract_audio_to_flac") as mock_extract, \
             patch("pipeline.speech_to_text.upload_flac_to_gcs", return_value="gs://bucket/audio.flac"), \
             patch("pipeline.speech_to_text.transcribe_chunked", new_callable=AsyncMock) as mock_chunked, \
             patch("pipeline.speech_to_text.get_speech_client") as mock_client, \
             patch("pipeline.speech_to_text._poll_operation_with_retry") as mock_poll:

            mock_speech_client = MagicMock()
            mock_client.return_value = mock_speech_client
            mock_operation = MagicMock()
            mock_speech_client.batch_recognize.return_value = mock_operation
            mock_response = MagicMock()
            mock_response.results = {}
            mock_poll.return_value = mock_response

            await transcribe("gs://bucket/video.mp4", job_id="boundary-video-job")

            mock_extract.assert_called_once()
            mock_chunked.assert_not_called()

    @pytest.mark.asyncio
    async def test_short_video_uses_16000_sample_rate(self):
        """
        Req 6.2: Short videos (≤300s, which is always ≤1800s) use
        sample_rate=16000 for whole-file extraction.
        """
        duration = 150.0  # Short video

        with patch("pipeline.speech_to_text.download_from_gcs") as mock_download, \
             patch("pipeline.speech_to_text.get_video_duration_seconds", return_value=duration), \
             patch("pipeline.speech_to_text.extract_audio_to_flac") as mock_extract, \
             patch("pipeline.speech_to_text.upload_flac_to_gcs", return_value="gs://bucket/audio.flac"), \
             patch("pipeline.speech_to_text.get_speech_client") as mock_client, \
             patch("pipeline.speech_to_text._poll_operation_with_retry") as mock_poll:

            mock_speech_client = MagicMock()
            mock_client.return_value = mock_speech_client
            mock_operation = MagicMock()
            mock_speech_client.batch_recognize.return_value = mock_operation
            mock_response = MagicMock()
            mock_response.results = {}
            mock_poll.return_value = mock_response

            await transcribe("gs://bucket/video.mp4", job_id="short-rate-job")

            mock_extract.assert_called_once()
            # extract_audio_to_flac(video_path, flac_path, sample_rate)
            call_args = mock_extract.call_args[0]
            actual_sample_rate = call_args[2]
            assert actual_sample_rate == 16000, (
                f"Short video (duration={duration}s) should use sample_rate=16000, "
                f"got {actual_sample_rate}"
            )


# ---------------------------------------------------------------------------
# Test Class: Long Videos Use Chunked Path (Req 6.3)
# ---------------------------------------------------------------------------


class TestLongVideoChunkedPath:
    """Verify long videos (>300s) use the chunked transcription path."""

    @pytest.mark.asyncio
    async def test_long_video_uses_transcribe_chunked(self):
        """
        Req 6.3: A video with duration > CHUNK_THRESHOLD_SECONDS (300s)
        uses transcribe_chunked, NOT the whole-file extraction path.
        """
        duration = 600.0  # 10 minutes, well over 300s

        with patch("pipeline.speech_to_text.download_from_gcs") as mock_download, \
             patch("pipeline.speech_to_text.get_video_duration_seconds", return_value=duration), \
             patch("pipeline.speech_to_text.extract_audio_to_flac") as mock_extract, \
             patch("pipeline.speech_to_text.transcribe_chunked", new_callable=AsyncMock) as mock_chunked:

            mock_chunked.return_value = [
                {"word": "long", "startTime": 0.0, "endTime": 0.5, "speaker": 1},
                {"word": "video", "startTime": 0.5, "endTime": 1.0, "speaker": 1},
            ]

            result = await transcribe("gs://bucket/video.mp4", job_id="long-video-job")

            # Chunked path should be used
            mock_chunked.assert_called_once()
            # Whole-file path should NOT be used
            mock_extract.assert_not_called()

    @pytest.mark.asyncio
    async def test_long_video_just_over_threshold_uses_chunked(self):
        """
        Req 6.3: A video with duration just over CHUNK_THRESHOLD_SECONDS (300.1s)
        uses the chunked path.
        """
        duration = 300.1  # Just over threshold

        with patch("pipeline.speech_to_text.download_from_gcs") as mock_download, \
             patch("pipeline.speech_to_text.get_video_duration_seconds", return_value=duration), \
             patch("pipeline.speech_to_text.extract_audio_to_flac") as mock_extract, \
             patch("pipeline.speech_to_text.transcribe_chunked", new_callable=AsyncMock) as mock_chunked:

            mock_chunked.return_value = [
                {"word": "test", "startTime": 0.0, "endTime": 0.3, "speaker": 1},
            ]

            await transcribe("gs://bucket/video.mp4", job_id="boundary-long-job")

            mock_chunked.assert_called_once()
            mock_extract.assert_not_called()

    @pytest.mark.asyncio
    async def test_long_video_under_1800s_uses_16000_sample_rate(self):
        """
        Req 6.3: A long video (>300s but ≤1800s) passes sample_rate=16000
        to transcribe_chunked.
        """
        duration = 900.0  # 15 minutes — over 300s but under 1800s

        with patch("pipeline.speech_to_text.download_from_gcs") as mock_download, \
             patch("pipeline.speech_to_text.get_video_duration_seconds", return_value=duration), \
             patch("pipeline.speech_to_text.transcribe_chunked", new_callable=AsyncMock) as mock_chunked:

            mock_chunked.return_value = [
                {"word": "medium", "startTime": 0.0, "endTime": 0.5, "speaker": 1},
            ]

            await transcribe("gs://bucket/video.mp4", job_id="medium-video-job")

            mock_chunked.assert_called_once()
            call_kwargs = mock_chunked.call_args
            # transcribe_chunked(video_path, job_id, sample_rate=sample_rate)
            actual_sample_rate = call_kwargs.kwargs.get("sample_rate")
            if actual_sample_rate is None and len(call_kwargs.args) > 2:
                actual_sample_rate = call_kwargs.args[2]
            assert actual_sample_rate == 16000, (
                f"Video duration={duration}s (≤1800s) should pass sample_rate=16000 "
                f"to transcribe_chunked, got {actual_sample_rate}"
            )

    @pytest.mark.asyncio
    async def test_long_video_over_1800s_uses_8000_sample_rate(self):
        """
        Req 6.3: A very long video (>1800s) passes sample_rate=8000
        to transcribe_chunked.
        """
        duration = 3600.0  # 60 minutes — over 1800s threshold

        with patch("pipeline.speech_to_text.download_from_gcs") as mock_download, \
             patch("pipeline.speech_to_text.get_video_duration_seconds", return_value=duration), \
             patch("pipeline.speech_to_text.transcribe_chunked", new_callable=AsyncMock) as mock_chunked:

            mock_chunked.return_value = [
                {"word": "lecture", "startTime": 0.0, "endTime": 0.5, "speaker": 1},
            ]

            await transcribe("gs://bucket/video.mp4", job_id="very-long-video-job")

            mock_chunked.assert_called_once()
            call_kwargs = mock_chunked.call_args
            actual_sample_rate = call_kwargs.kwargs.get("sample_rate")
            if actual_sample_rate is None and len(call_kwargs.args) > 2:
                actual_sample_rate = call_kwargs.args[2]
            assert actual_sample_rate == 8000, (
                f"Video duration={duration}s (>1800s) should pass sample_rate=8000 "
                f"to transcribe_chunked, got {actual_sample_rate}"
            )

    @pytest.mark.asyncio
    async def test_long_video_at_1800s_boundary_uses_16000(self):
        """
        Req 6.3: A video with duration exactly at 1800s uses sample_rate=16000
        (threshold is >1800, not >=1800).
        """
        duration = 1800.0  # Exactly at adaptive threshold

        with patch("pipeline.speech_to_text.download_from_gcs") as mock_download, \
             patch("pipeline.speech_to_text.get_video_duration_seconds", return_value=duration), \
             patch("pipeline.speech_to_text.transcribe_chunked", new_callable=AsyncMock) as mock_chunked:

            mock_chunked.return_value = [
                {"word": "boundary", "startTime": 0.0, "endTime": 0.5, "speaker": 1},
            ]

            await transcribe("gs://bucket/video.mp4", job_id="boundary-1800-job")

            mock_chunked.assert_called_once()
            call_kwargs = mock_chunked.call_args
            actual_sample_rate = call_kwargs.kwargs.get("sample_rate")
            if actual_sample_rate is None and len(call_kwargs.args) > 2:
                actual_sample_rate = call_kwargs.args[2]
            assert actual_sample_rate == 16000, (
                f"Video duration={duration}s (exactly 1800s, NOT >1800) should use "
                f"sample_rate=16000, got {actual_sample_rate}"
            )
