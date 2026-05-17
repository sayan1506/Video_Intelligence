# worker/tests/test_audio_only_stt_failure.py
"""
Property-based test: audio-only STT failure marks job as failed.

**Validates: Requirements 3.1**

Property 4: Audio-only STT failure marks job as failed.
For any audio-only file where STT raises an exception, verify job is marked
failed with error message and returns False.
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

# Strategy: pick a known audio MIME type from the set
audio_mime_types = st.sampled_from(sorted(AUDIO_ONLY_MIME_TYPES))

# Strategy: generate arbitrary exception messages (non-empty)
exception_messages = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P", "Z", "S")),
    min_size=1,
    max_size=100,
)


def make_job_message(content_type: str) -> JobMessage:
    """Create a valid JobMessage with the given contentType."""
    return JobMessage(
        jobId="test-job-123",
        gcsPath="raw-videos/test-job-123/audio.mp3",
        gcsBucket="test-bucket",
        gcsUri="gs://test-bucket/raw-videos/test-job-123/audio.mp3",
        filename="audio.mp3",
        fileSizeMb=5.0,
        contentType=content_type,
        uploadedAt="2024-01-01T00:00:00Z",
        schemaVersion="1",
    )


# ---------------------------------------------------------------------------
# Property Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@given(
    mime_type=audio_mime_types,
    error_msg=exception_messages,
)
@settings(max_examples=100, deadline=None)
async def test_audio_only_stt_failure_marks_job_failed(
    mime_type: str, error_msg: str
):
    """
    **Validates: Requirements 3.1**

    Property 4: For any audio-only file where STT raises an exception,
    the orchestrator marks the job as failed in Firestore with a descriptive
    error message that includes the failure reason, and returns False.
    """
    job_message = make_job_message(mime_type)

    with patch("pipeline.orchestrator.firestore") as mock_firestore, \
         patch("pipeline.orchestrator._run_stt_with_progress", new_callable=AsyncMock) as mock_stt:

        # STT raises an exception with the generated error message
        mock_stt.side_effect = Exception(error_msg)

        result = await run_pipeline(job_message)

        # Verify run_pipeline returns False
        assert result is False, (
            f"Expected run_pipeline to return False when STT fails for "
            f"audio-only file (contentType={mime_type!r}), but got {result}"
        )

        # Verify mark_processing_failed was called with error message
        mock_firestore.mark_processing_failed.assert_called_once()
        call_args = mock_firestore.mark_processing_failed.call_args[0]
        assert call_args[0] == job_message.jobId, (
            f"Expected mark_processing_failed to be called with job_id="
            f"{job_message.jobId!r}, but got {call_args[0]!r}"
        )
        # The error message should include the STT failure reason
        assert error_msg in call_args[1], (
            f"Expected error message to contain the STT exception message "
            f"{error_msg!r}, but got {call_args[1]!r}"
        )


@pytest.mark.asyncio
@given(
    mime_type=audio_mime_types,
    error_msg=exception_messages,
)
@settings(max_examples=100, deadline=None)
async def test_audio_only_stt_failure_does_not_write_results(
    mime_type: str, error_msg: str
):
    """
    **Validates: Requirements 3.1**

    Property 4 (no partial results): For any audio-only file where STT raises
    an exception, the orchestrator does NOT call write_results or write_summary.
    """
    job_message = make_job_message(mime_type)

    with patch("pipeline.orchestrator.firestore") as mock_firestore, \
         patch("pipeline.orchestrator._run_stt_with_progress", new_callable=AsyncMock) as mock_stt:

        # STT raises an exception
        mock_stt.side_effect = Exception(error_msg)

        await run_pipeline(job_message)

        # Verify write_results was NOT called
        mock_firestore.write_results.assert_not_called(), (
            f"Expected write_results to NOT be called when STT fails for "
            f"audio-only file (contentType={mime_type!r})"
        )

        # Verify write_summary was NOT called
        mock_firestore.write_summary.assert_not_called(), (
            f"Expected write_summary to NOT be called when STT fails for "
            f"audio-only file (contentType={mime_type!r})"
        )
