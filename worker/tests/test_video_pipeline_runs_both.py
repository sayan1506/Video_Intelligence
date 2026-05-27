# worker/tests/test_video_pipeline_runs_both.py
"""
Property-based test: video pipeline runs both STT and VI concurrently.

**Validates: Requirements 2.4, 6.1**

Property 3: Video pipeline runs both STT and VI concurrently.
For any job message with contentType NOT in AUDIO_ONLY_MIME_TYPES, verify both
STT and VI are invoked.
"""

import os

# Set required env vars before importing pipeline modules
os.environ.setdefault("GCP_PROJECT_ID", "test-project")
os.environ.setdefault("GCP_BUCKET_NAME", "test-bucket")
os.environ.setdefault("GCP_SERVICE_ACCOUNT_EMAIL", "test@test.iam.gserviceaccount.com")

import asyncio
from unittest.mock import patch, MagicMock, AsyncMock

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from pipeline.orchestrator import run_pipeline, AUDIO_ONLY_MIME_TYPES
from models.schemas import JobMessage


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Strategy: well-known video MIME types that are definitely NOT audio-only
known_video_mime_types = st.sampled_from([
    "video/mp4",
    "video/webm",
    "video/x-msvideo",
    "video/quicktime",
    "video/x-matroska",
    "video/mpeg",
    "video/ogg",
    "video/3gpp",
    "application/octet-stream",
])

# Strategy: arbitrary non-empty strings that are NOT in AUDIO_ONLY_MIME_TYPES when normalized
non_audio_content_types = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P", "Z"), whitelist_characters="/-.+"),
    min_size=1,
    max_size=60,
).filter(
    lambda s: s.split(";")[0].strip().lower() not in AUDIO_ONLY_MIME_TYPES
)

# Strategy: empty string (also routes to video path)
empty_content_type = st.just("")

# Strategy: combine all non-audio content type strategies
video_content_types = st.one_of(
    known_video_mime_types,
    non_audio_content_types,
    empty_content_type,
)


def build_job_message(content_type: str, job_id: str = "test-job-456") -> JobMessage:
    """Build a valid JobMessage with the given contentType."""
    return JobMessage(
        jobId=job_id,
        gcsPath=f"raw-videos/{job_id}/video.mp4",
        gcsBucket="test-bucket",
        gcsUri=f"gs://test-bucket/raw-videos/{job_id}/video.mp4",
        filename="video.mp4",
        fileSizeMb=25.0,
        contentType=content_type,
        uploadedAt="2024-01-01T00:00:00Z",
        schemaVersion="1",
    )


# ---------------------------------------------------------------------------
# Property Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@given(content_type=video_content_types)
@settings(max_examples=200, deadline=None)
async def test_video_pipeline_invokes_both_stt_and_vi(content_type: str):
    """
    **Validates: Requirements 2.4, 6.1**

    Property 3: For any job message with contentType NOT in AUDIO_ONLY_MIME_TYPES,
    both _run_stt_with_progress and _run_vi_with_progress are invoked.
    """
    job_message = build_job_message(content_type)

    with patch("pipeline.orchestrator._run_stt_with_progress", new_callable=AsyncMock) as mock_stt, \
         patch("pipeline.orchestrator._run_vi_with_progress", new_callable=AsyncMock) as mock_vi, \
         patch("pipeline.orchestrator.firestore") as mock_firestore, \
         patch("pipeline.orchestrator.generate_summary", new_callable=AsyncMock) as mock_summary:

        # STT returns a valid transcript tuple (transcript, detected_language)
        mock_stt.return_value = ([{"word": "hello", "startTime": 0.0, "endTime": 0.5, "speaker": 1}], "en-IN")
        # VI returns valid scenes
        mock_vi.return_value = [{"startTime": 0.0, "endTime": 5.0, "confidence": 0.9, "labels": ["scene1"]}]
        # Summary returns valid data
        mock_summary.return_value = {
            "summary": "Test summary",
            "chapters": [],
            "highlights": [],
            "sentiment": "neutral",
            "actionItems": [],
        }

        result = await run_pipeline(job_message)

        # Both STT and VI must be called for non-audio content types
        mock_stt.assert_called_once(), (
            f"_run_stt_with_progress was NOT called for video contentType={content_type!r}"
        )
        mock_vi.assert_called_once(), (
            f"_run_vi_with_progress was NOT called for video contentType={content_type!r}"
        )


@pytest.mark.asyncio
@given(content_type=known_video_mime_types)
@settings(max_examples=200, deadline=None)
async def test_known_video_types_invoke_both_pipelines(content_type: str):
    """
    **Validates: Requirements 2.4, 6.1**

    Property 3: For well-known video MIME types, both STT and VI are invoked
    concurrently and the pipeline returns True on success.
    """
    job_message = build_job_message(content_type)

    with patch("pipeline.orchestrator._run_stt_with_progress", new_callable=AsyncMock) as mock_stt, \
         patch("pipeline.orchestrator._run_vi_with_progress", new_callable=AsyncMock) as mock_vi, \
         patch("pipeline.orchestrator.firestore") as mock_firestore, \
         patch("pipeline.orchestrator.generate_summary", new_callable=AsyncMock) as mock_summary:

        mock_stt.return_value = ([{"word": "test", "startTime": 0.0, "endTime": 0.3, "speaker": 1}], "en-IN")
        mock_vi.return_value = [{"startTime": 0.0, "endTime": 10.0, "confidence": 0.95, "labels": ["intro"]}]
        mock_summary.return_value = {
            "summary": "Test summary",
            "chapters": [],
            "highlights": [],
            "sentiment": "neutral",
            "actionItems": [],
        }

        result = await run_pipeline(job_message)

        # Both must be called
        mock_stt.assert_called_once()
        mock_vi.assert_called_once()

        # Pipeline should succeed
        assert result is True, (
            f"run_pipeline returned {result} for video contentType={content_type!r}, expected True"
        )


@pytest.mark.asyncio
@given(content_type=non_audio_content_types)
@settings(max_examples=200, deadline=None)
async def test_arbitrary_non_audio_types_invoke_both_pipelines(content_type: str):
    """
    **Validates: Requirements 2.4, 6.1**

    Property 3: For any arbitrary contentType string that is NOT in AUDIO_ONLY_MIME_TYPES
    (when normalized), both STT and VI are invoked. This includes unknown MIME types,
    empty strings, and any non-audio content type.
    """
    job_message = build_job_message(content_type)

    with patch("pipeline.orchestrator._run_stt_with_progress", new_callable=AsyncMock) as mock_stt, \
         patch("pipeline.orchestrator._run_vi_with_progress", new_callable=AsyncMock) as mock_vi, \
         patch("pipeline.orchestrator.firestore") as mock_firestore, \
         patch("pipeline.orchestrator.generate_summary", new_callable=AsyncMock) as mock_summary:

        mock_stt.return_value = ([{"word": "arbitrary", "startTime": 0.0, "endTime": 0.4, "speaker": 1}], "en-IN")
        mock_vi.return_value = [{"startTime": 0.0, "endTime": 3.0, "confidence": 0.8, "labels": ["test"]}]
        mock_summary.return_value = {
            "summary": "Test summary",
            "chapters": [],
            "highlights": [],
            "sentiment": "neutral",
            "actionItems": [],
        }

        result = await run_pipeline(job_message)

        # Both STT and VI must be invoked
        mock_stt.assert_called_once(), (
            f"_run_stt_with_progress was NOT called for contentType={content_type!r}"
        )
        mock_vi.assert_called_once(), (
            f"_run_vi_with_progress was NOT called for contentType={content_type!r}"
        )
