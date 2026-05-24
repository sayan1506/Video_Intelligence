"""
Bug Condition Exploration Tests — Pipeline Speed Refactor
=========================================================

These tests MUST FAIL on unfixed code. Failure confirms the bugs exist.
DO NOT attempt to fix the tests or the code when they fail.

These tests encode the expected (fixed) behavior. They will pass after
the fixes in tasks 3.1–3.3 are implemented.

Bugs documented:
  Bug 1 — VI Bottleneck (isBugCondition_VI):
    run_pipeline() calls _run_vi_with_progress instead of _run_gemini_scenes
    for video/mp4 jobs. _run_gemini_scenes does not exist on unfixed code.

  Bug 2 — Thumbnail Re-download (isBugCondition_Thumb):
    download_from_gcs is called twice for video jobs — once in transcribe()
    and once in _extract_and_upload_thumbnail(). Expected: called exactly once.

  Bug 3 — Chunk Count (isBugCondition_Chunk):
    CHUNK_DURATION_SECONDS == 300 produces 24 chunks for a 2-hour video.
    Expected: CHUNK_DURATION_SECONDS == 600 (12 chunks for a 2-hour video).

Validates: Requirements 1.1, 1.3, 1.4
"""

import asyncio
import os

# Set required env vars before importing pipeline modules
os.environ.setdefault("GCP_PROJECT_ID", "test-project")
os.environ.setdefault("GCP_BUCKET_NAME", "test-bucket")
os.environ.setdefault("GCP_SERVICE_ACCOUNT_EMAIL", "test@test.iam.gserviceaccount.com")

import math
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from models.schemas import JobMessage
from pipeline.orchestrator import run_pipeline
import pipeline.speech_to_text as stt_module


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_video_job(content_type: str = "video/mp4") -> JobMessage:
    return JobMessage(
        jobId="bug-test-job-001",
        gcsPath="raw-videos/bug-test-job-001/video.mp4",
        gcsBucket="test-bucket",
        gcsUri="gs://test-bucket/raw-videos/bug-test-job-001/video.mp4",
        filename="video.mp4",
        fileSizeMb=500.0,
        contentType=content_type,
        uploadedAt="2024-01-01T00:00:00Z",
        schemaVersion="1",
    )


MOCK_TRANSCRIPT = [{"word": "hello", "startTime": 0.0, "endTime": 0.5, "speaker": 1}]
MOCK_SCENES = [{"startTime": 0.0, "endTime": 5.0, "labels": ["outdoor"]}]
MOCK_SUMMARY = {
    "summary": "Test summary.",
    "chapters": [],
    "highlights": [],
    "sentiment": "neutral",
    "actionItems": [],
}

def _mock_firestore(mock_fs):
    mock_fs.update_job_status = MagicMock()
    mock_fs.mark_processing_failed = MagicMock()
    mock_fs.mark_processing_completed = MagicMock()
    mock_fs.write_results = MagicMock()
    mock_fs.write_summary = MagicMock()
    mock_fs.write_thumbnail_gcs_path = MagicMock()


# ---------------------------------------------------------------------------
# Bug 1 — VI Bottleneck (isBugCondition_VI)
# ---------------------------------------------------------------------------

class TestBugConditionVI:
    """
    isBugCondition_VI: job.contentType NOT IN AUDIO_ONLY_MIME_TYPES
                       AND _run_vi_with_progress IS called instead of _run_gemini_scenes

    Validates: Requirements 1.1, 2.1
    """

    @pytest.mark.asyncio
    async def test_video_job_calls_gemini_scenes_not_vi(self):
        """
        For a video/mp4 job, run_pipeline() MUST call _run_gemini_scenes
        and MUST NOT call _run_vi_with_progress.

        EXPECTED TO FAIL on unfixed code:
          - _run_gemini_scenes does not exist → AttributeError
          - OR _run_vi_with_progress is called instead → assertion fails

        Counterexample: "run_pipeline() calls _run_vi_with_progress instead of
        _run_gemini_scenes for video/mp4 job"
        """
        job = _make_video_job("video/mp4")

        with (
            patch("pipeline.orchestrator._run_stt_with_progress",
                  new=AsyncMock(return_value=MOCK_TRANSCRIPT)),
            patch("pipeline.orchestrator._run_gemini_scenes",
                  new=AsyncMock(return_value=MOCK_SCENES)) as mock_gemini_scenes,
            patch("pipeline.orchestrator._run_vi_with_progress",
                  new=AsyncMock(return_value=MOCK_SCENES)) as mock_vi,
            patch("pipeline.orchestrator.generate_summary",
                  new=AsyncMock(return_value=MOCK_SUMMARY)),
            patch("pipeline.orchestrator.firestore") as mock_fs,
        ):
            _mock_firestore(mock_fs)
            result = await run_pipeline(job)

            assert result is True, "run_pipeline() should succeed for a video job"

            mock_gemini_scenes.assert_called_once(), (
                "COUNTEREXAMPLE: _run_gemini_scenes was NOT called for video/mp4 job. "
                "run_pipeline() calls _run_vi_with_progress instead of _run_gemini_scenes."
            )
            mock_vi.assert_not_called(), (
                "COUNTEREXAMPLE: _run_vi_with_progress WAS called for video/mp4 job. "
                "Expected: _run_gemini_scenes to be called instead."
            )


# ---------------------------------------------------------------------------
# Bug 2 — Thumbnail Re-download (isBugCondition_Thumb)
# ---------------------------------------------------------------------------

class TestBugConditionThumb:
    """
    isBugCondition_Thumb: job.contentType NOT IN AUDIO_ONLY_MIME_TYPES
                          AND download_from_gcs() called inside _extract_and_upload_thumbnail()
                          AND already called inside transcribe()

    Validates: Requirements 1.3, 2.3
    """

    @pytest.mark.asyncio
    async def test_download_from_gcs_called_exactly_once_for_video_job(self):
        """
        For a video/mp4 job, download_from_gcs from orchestrator.py MUST NOT be
        called — thumbnail bytes should come from transcribe() via _run_stt_with_progress.

        EXPECTED TO FAIL on unfixed code:
          _extract_and_upload_thumbnail() calls download_from_gcs unconditionally
          → mock_download.call_count == 1, assertion fails.

        Counterexample: "download_from_gcs called 2 times for video/mp4 job —
        once in transcribe(), once in _extract_and_upload_thumbnail()"
        """
        job = _make_video_job("video/mp4")

        with (
            patch("pipeline.orchestrator._run_stt_with_progress",
                  new=AsyncMock(return_value=MOCK_TRANSCRIPT)),
            patch("pipeline.orchestrator._run_vi_with_progress",
                  new=AsyncMock(return_value=MOCK_SCENES)),
            patch("pipeline.orchestrator.generate_summary",
                  new=AsyncMock(return_value=MOCK_SUMMARY)),
            patch("pipeline.orchestrator.download_from_gcs") as mock_download,
            patch("pipeline.orchestrator.BUCKET_NAME", "test-bucket"),
            patch("pipeline.orchestrator.subprocess.run") as mock_subprocess,
            patch("pipeline.orchestrator.gcs_storage.Client") as mock_gcs_client,
            patch("pipeline.orchestrator.firestore") as mock_fs,
        ):
            mock_subprocess.return_value = MagicMock(returncode=0, stdout="7200.0\n", stderr="")
            mock_gcs_client.return_value.bucket.return_value.blob.return_value = MagicMock()
            _mock_firestore(mock_fs)

            await run_pipeline(job)

            assert mock_download.call_count == 0, (
                f"COUNTEREXAMPLE: download_from_gcs called {mock_download.call_count} time(s) "
                f"from orchestrator.py for video/mp4 job. "
                f"Expected 0 — thumbnail bytes should come from transcribe(), not a second download. "
                f"Bug: _extract_and_upload_thumbnail() calls download_from_gcs unconditionally."
            )


# ---------------------------------------------------------------------------
# Bug 3 — Chunk Count (isBugCondition_Chunk)
# ---------------------------------------------------------------------------

class TestBugConditionChunk:
    """
    isBugCondition_Chunk: CHUNK_DURATION_SECONDS == 300
                          produces 24 chunks for a 2-hour video instead of 12

    Validates: Requirements 1.4, 2.4
    """

    def test_chunk_duration_seconds_is_600(self):
        """
        CHUNK_DURATION_SECONDS MUST be 600.

        EXPECTED TO FAIL on unfixed code: value is 300 → assertion fails.

        Counterexample: "CHUNK_DURATION_SECONDS is 300, produces 24 chunks
        for a 2-hour video instead of 12"
        """
        actual = stt_module.CHUNK_DURATION_SECONDS
        assert actual == 600, (
            f"COUNTEREXAMPLE: CHUNK_DURATION_SECONDS is {actual}, not 600. "
            f"A 2-hour video (7200s) produces {7200 // actual} chunks instead of 12."
        )

    def test_two_hour_video_produces_12_chunks(self):
        """
        A 2-hour video (7200s) must produce 12 chunks with CHUNK_DURATION_SECONDS=600.

        EXPECTED TO FAIL on unfixed code (produces 24 chunks at 300s).
        """
        expected_chunks = math.ceil(7200 / stt_module.CHUNK_DURATION_SECONDS)
        assert expected_chunks == 12, (
            f"COUNTEREXAMPLE: 7200s video produces {expected_chunks} chunks "
            f"with CHUNK_DURATION_SECONDS={stt_module.CHUNK_DURATION_SECONDS}. "
            f"Expected 12 (CHUNK_DURATION_SECONDS=600)."
        )
