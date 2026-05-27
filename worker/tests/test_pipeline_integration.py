"""
Integration regression: run_pipeline() full output shape after all V1.1 changes.

All GCP calls are mocked. Verifies:
- Firestore write_results() and write_summary() are called with correct shapes
- mark_processing_completed() is called on success
- Audio-only path skips VI (scenes=[])
- Video path produces both transcript and scenes
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from models.schemas import JobMessage
from pipeline.orchestrator import run_pipeline


def make_job_message(content_type: str = "video/mp4") -> JobMessage:
    return JobMessage(
        jobId="test-job-001",
        gcsPath="raw-videos/test-job-001/video.mp4",
        gcsBucket="video-intelligence-raw",
        gcsUri="gs://video-intelligence-raw/raw-videos/test-job-001/video.mp4",
        filename="video.mp4",
        fileSizeMb=10.0,
        contentType=content_type,
        uploadedAt="2026-05-16T00:00:00Z",
        schemaVersion="1",
    )


MOCK_TRANSCRIPT = [
    {"word": "hello", "startTime": 0.0, "endTime": 0.5, "speaker": 1},
    {"word": "world", "startTime": 0.5, "endTime": 1.0, "speaker": 1},
]

MOCK_STT_RESULT = (MOCK_TRANSCRIPT, "en-IN")

MOCK_SCENES = [
    {"startTime": 0.0, "endTime": 5.0, "confidence": 0.9, "labels": ["outdoor"]},
]

MOCK_SUMMARY = {
    "summary": "Test summary.",
    "chapters": [],
    "highlights": [],
    "sentiment": "neutral",
    "actionItems": [],
}


class TestRunPipelineVideoPath:
    def test_write_results_called_on_success(self):
        msg = make_job_message("video/mp4")

        with (
            patch("pipeline.orchestrator._run_stt_with_progress",
                  new=AsyncMock(return_value=MOCK_STT_RESULT)),
            patch("pipeline.orchestrator._run_vi_with_progress",
                  new=AsyncMock(return_value=MOCK_SCENES)),
            patch("pipeline.orchestrator.generate_summary",
                  new=AsyncMock(return_value=MOCK_SUMMARY)),
            patch("pipeline.orchestrator.firestore") as mock_fs,
        ):
            mock_fs.update_job_status = MagicMock()
            mock_fs.mark_processing_failed = MagicMock()
            mock_fs.mark_processing_completed = MagicMock()
            mock_fs.write_results = MagicMock()
            mock_fs.write_summary = MagicMock()

            result = asyncio.run(run_pipeline(msg))

            assert result is True
            mock_fs.write_results.assert_called_once()
            mock_fs.write_summary.assert_called_once()
            mock_fs.mark_processing_completed.assert_called_once()

    def test_write_results_receives_transcript_and_scenes(self):
        msg = make_job_message("video/mp4")

        with (
            patch("pipeline.orchestrator._run_stt_with_progress",
                  new=AsyncMock(return_value=MOCK_STT_RESULT)),
            patch("pipeline.orchestrator._run_vi_with_progress",
                  new=AsyncMock(return_value=MOCK_SCENES)),
            patch("pipeline.orchestrator.generate_summary",
                  new=AsyncMock(return_value=MOCK_SUMMARY)),
            patch("pipeline.orchestrator.firestore") as mock_fs,
        ):
            mock_fs.update_job_status = MagicMock()
            mock_fs.mark_processing_failed = MagicMock()
            mock_fs.mark_processing_completed = MagicMock()
            mock_fs.write_results = MagicMock()
            mock_fs.write_summary = MagicMock()

            asyncio.run(run_pipeline(msg))

            call_kwargs = mock_fs.write_results.call_args.kwargs
            assert call_kwargs["transcript"] == MOCK_TRANSCRIPT
            assert call_kwargs["scenes"] == MOCK_SCENES


class TestRunPipelineAudioOnlyPath:
    def test_audio_only_scenes_is_empty_list(self):
        msg = make_job_message("audio/mpeg")

        with (
            patch("pipeline.orchestrator._run_stt_with_progress",
                  new=AsyncMock(return_value=MOCK_STT_RESULT)),
            patch("pipeline.orchestrator.generate_summary",
                  new=AsyncMock(return_value=MOCK_SUMMARY)),
            patch("pipeline.orchestrator.firestore") as mock_fs,
        ):
            mock_fs.update_job_status = MagicMock()
            mock_fs.mark_processing_failed = MagicMock()
            mock_fs.mark_processing_completed = MagicMock()
            mock_fs.write_results = MagicMock()
            mock_fs.write_summary = MagicMock()

            result = asyncio.run(run_pipeline(msg))

            assert result is True
            call_kwargs = mock_fs.write_results.call_args.kwargs
            assert call_kwargs["scenes"] == []
