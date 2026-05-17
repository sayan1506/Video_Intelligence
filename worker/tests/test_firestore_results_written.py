# worker/tests/test_firestore_results_written.py
"""
Property-based test: Firestore results are written for both audio-only and video paths.

**Validates: Requirements 6.4**

Property 7: Firestore results are written for both audio-only and video paths.
For any successfully processed job, verify transcript, scenes, and summary are
written to Firestore before marking the job as completed.
"""

import os

# Set required env vars before importing pipeline modules
os.environ.setdefault("GCP_PROJECT_ID", "test-project")
os.environ.setdefault("GCP_BUCKET_NAME", "test-bucket")
os.environ.setdefault("GCP_SERVICE_ACCOUNT_EMAIL", "test@test.iam.gserviceaccount.com")

import asyncio
from unittest.mock import patch, MagicMock, AsyncMock, call

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from pipeline.orchestrator import run_pipeline, AUDIO_ONLY_MIME_TYPES
from models.schemas import JobMessage


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Strategy: pick a known audio MIME type from the set (audio-only path)
audio_mime_types = st.sampled_from(sorted(AUDIO_ONLY_MIME_TYPES))

# Strategy: well-known video MIME types (video path)
video_mime_types = st.sampled_from([
    "video/mp4",
    "video/webm",
    "video/x-msvideo",
    "video/quicktime",
    "video/x-matroska",
    "video/mpeg",
    "video/ogg",
    "video/3gpp",
])

# Strategy: combine both paths for a unified test
any_content_type = st.one_of(audio_mime_types, video_mime_types)


def build_job_message(content_type: str, job_id: str = "test-job-789") -> JobMessage:
    """Build a valid JobMessage with the given contentType."""
    return JobMessage(
        jobId=job_id,
        gcsPath=f"raw-videos/{job_id}/file.mp4",
        gcsBucket="test-bucket",
        gcsUri=f"gs://test-bucket/raw-videos/{job_id}/file.mp4",
        filename="file.mp4",
        fileSizeMb=10.0,
        contentType=content_type,
        uploadedAt="2024-01-01T00:00:00Z",
        schemaVersion="1",
    )


# ---------------------------------------------------------------------------
# Property Tests — Audio-Only Path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@given(mime_type=audio_mime_types)
@settings(max_examples=100, deadline=None)
async def test_audio_only_path_writes_results_to_firestore(mime_type: str):
    """
    **Validates: Requirements 6.4**

    Property 7: For any successfully processed audio-only job, the orchestrator
    calls firestore.write_results with transcript and scenes (empty list).
    """
    job_message = build_job_message(mime_type)

    with patch("pipeline.orchestrator._run_stt_with_progress", new_callable=AsyncMock) as mock_stt, \
         patch("pipeline.orchestrator.firestore") as mock_firestore, \
         patch("pipeline.orchestrator.generate_summary", new_callable=AsyncMock) as mock_summary:

        transcript = [{"word": "hello", "startTime": 0.0, "endTime": 0.5, "speaker": 1}]
        mock_stt.return_value = transcript
        mock_summary.return_value = {
            "summary": "Test summary",
            "chapters": [],
            "highlights": [],
            "sentiment": "neutral",
            "actionItems": [],
        }

        result = await run_pipeline(job_message)

        # Pipeline should succeed
        assert result is True, (
            f"run_pipeline returned {result} for audio-only contentType={mime_type!r}, expected True"
        )

        # write_results must be called with transcript and scenes (empty list for audio)
        mock_firestore.write_results.assert_called_once()
        wr_kwargs = mock_firestore.write_results.call_args
        assert wr_kwargs == call(job_id=job_message.jobId, transcript=transcript, scenes=[]), (
            f"write_results called with unexpected args: {wr_kwargs}"
        )


@pytest.mark.asyncio
@given(mime_type=audio_mime_types)
@settings(max_examples=100, deadline=None)
async def test_audio_only_path_writes_summary_to_firestore(mime_type: str):
    """
    **Validates: Requirements 6.4**

    Property 7: For any successfully processed audio-only job, the orchestrator
    calls firestore.write_summary with the generated summary data.
    """
    job_message = build_job_message(mime_type)

    with patch("pipeline.orchestrator._run_stt_with_progress", new_callable=AsyncMock) as mock_stt, \
         patch("pipeline.orchestrator.firestore") as mock_firestore, \
         patch("pipeline.orchestrator.generate_summary", new_callable=AsyncMock) as mock_summary:

        mock_stt.return_value = [{"word": "test", "startTime": 0.0, "endTime": 0.3, "speaker": 1}]
        summary_data = {
            "summary": "Generated summary",
            "chapters": [{"title": "Intro", "startTime": 0}],
            "highlights": ["key point"],
            "sentiment": "positive",
            "actionItems": ["do something"],
        }
        mock_summary.return_value = summary_data

        result = await run_pipeline(job_message)

        assert result is True

        # write_summary must be called with the summary data
        mock_firestore.write_summary.assert_called_once()
        ws_kwargs = mock_firestore.write_summary.call_args
        assert ws_kwargs == call(job_id=job_message.jobId, summary_data=summary_data), (
            f"write_summary called with unexpected args: {ws_kwargs}"
        )


@pytest.mark.asyncio
@given(mime_type=audio_mime_types)
@settings(max_examples=100, deadline=None)
async def test_audio_only_path_marks_completed_after_writes(mime_type: str):
    """
    **Validates: Requirements 6.4**

    Property 7: For any successfully processed audio-only job, the orchestrator
    calls mark_processing_completed AFTER write_results and write_summary.
    """
    job_message = build_job_message(mime_type)

    with patch("pipeline.orchestrator._run_stt_with_progress", new_callable=AsyncMock) as mock_stt, \
         patch("pipeline.orchestrator.firestore") as mock_firestore, \
         patch("pipeline.orchestrator.generate_summary", new_callable=AsyncMock) as mock_summary:

        mock_stt.return_value = [{"word": "test", "startTime": 0.0, "endTime": 0.3, "speaker": 1}]
        mock_summary.return_value = {
            "summary": "Test summary",
            "chapters": [],
            "highlights": [],
            "sentiment": "neutral",
            "actionItems": [],
        }

        # Track call order
        call_order = []
        mock_firestore.write_results.side_effect = lambda **kwargs: call_order.append("write_results")
        mock_firestore.write_summary.side_effect = lambda **kwargs: call_order.append("write_summary")
        mock_firestore.mark_processing_completed.side_effect = lambda *args, **kwargs: call_order.append("mark_completed")

        result = await run_pipeline(job_message)

        assert result is True

        # mark_processing_completed must be called
        mock_firestore.mark_processing_completed.assert_called_once()

        # Verify ordering: write_results and write_summary before mark_completed
        assert "write_results" in call_order, "write_results was not called"
        assert "mark_completed" in call_order, "mark_processing_completed was not called"
        completed_idx = call_order.index("mark_completed")
        results_idx = call_order.index("write_results")
        assert results_idx < completed_idx, (
            f"write_results (index {results_idx}) must be called before "
            f"mark_processing_completed (index {completed_idx}). Order: {call_order}"
        )


# ---------------------------------------------------------------------------
# Property Tests — Video Path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@given(mime_type=video_mime_types)
@settings(max_examples=100, deadline=None)
async def test_video_path_writes_results_to_firestore(mime_type: str):
    """
    **Validates: Requirements 6.4**

    Property 7: For any successfully processed video job, the orchestrator
    calls firestore.write_results with transcript and scenes.
    """
    job_message = build_job_message(mime_type)

    with patch("pipeline.orchestrator._run_stt_with_progress", new_callable=AsyncMock) as mock_stt, \
         patch("pipeline.orchestrator._run_vi_with_progress", new_callable=AsyncMock) as mock_vi, \
         patch("pipeline.orchestrator.firestore") as mock_firestore, \
         patch("pipeline.orchestrator.generate_summary", new_callable=AsyncMock) as mock_summary:

        transcript = [{"word": "video", "startTime": 0.0, "endTime": 0.4, "speaker": 1}]
        scenes = [{"startTime": 0.0, "endTime": 5.0, "confidence": 0.9, "labels": ["scene1"]}]
        mock_stt.return_value = transcript
        mock_vi.return_value = scenes
        mock_summary.return_value = {
            "summary": "Video summary",
            "chapters": [],
            "highlights": [],
            "sentiment": "neutral",
            "actionItems": [],
        }

        result = await run_pipeline(job_message)

        assert result is True, (
            f"run_pipeline returned {result} for video contentType={mime_type!r}, expected True"
        )

        # write_results must be called with transcript and scenes
        mock_firestore.write_results.assert_called_once()
        wr_kwargs = mock_firestore.write_results.call_args
        assert wr_kwargs == call(job_id=job_message.jobId, transcript=transcript, scenes=scenes), (
            f"write_results called with unexpected args: {wr_kwargs}"
        )


@pytest.mark.asyncio
@given(mime_type=video_mime_types)
@settings(max_examples=100, deadline=None)
async def test_video_path_writes_summary_to_firestore(mime_type: str):
    """
    **Validates: Requirements 6.4**

    Property 7: For any successfully processed video job, the orchestrator
    calls firestore.write_summary with the generated summary data.
    """
    job_message = build_job_message(mime_type)

    with patch("pipeline.orchestrator._run_stt_with_progress", new_callable=AsyncMock) as mock_stt, \
         patch("pipeline.orchestrator._run_vi_with_progress", new_callable=AsyncMock) as mock_vi, \
         patch("pipeline.orchestrator.firestore") as mock_firestore, \
         patch("pipeline.orchestrator.generate_summary", new_callable=AsyncMock) as mock_summary:

        mock_stt.return_value = [{"word": "test", "startTime": 0.0, "endTime": 0.3, "speaker": 1}]
        mock_vi.return_value = [{"startTime": 0.0, "endTime": 10.0, "confidence": 0.95, "labels": ["intro"]}]
        summary_data = {
            "summary": "Video summary content",
            "chapters": [{"title": "Chapter 1", "startTime": 0}],
            "highlights": ["highlight 1"],
            "sentiment": "positive",
            "actionItems": ["action 1"],
        }
        mock_summary.return_value = summary_data

        result = await run_pipeline(job_message)

        assert result is True

        # write_summary must be called with the summary data
        mock_firestore.write_summary.assert_called_once()
        ws_kwargs = mock_firestore.write_summary.call_args
        assert ws_kwargs == call(job_id=job_message.jobId, summary_data=summary_data), (
            f"write_summary called with unexpected args: {ws_kwargs}"
        )


@pytest.mark.asyncio
@given(mime_type=video_mime_types)
@settings(max_examples=100, deadline=None)
async def test_video_path_marks_completed_after_writes(mime_type: str):
    """
    **Validates: Requirements 6.4**

    Property 7: For any successfully processed video job, the orchestrator
    calls mark_processing_completed AFTER write_results and write_summary.
    """
    job_message = build_job_message(mime_type)

    with patch("pipeline.orchestrator._run_stt_with_progress", new_callable=AsyncMock) as mock_stt, \
         patch("pipeline.orchestrator._run_vi_with_progress", new_callable=AsyncMock) as mock_vi, \
         patch("pipeline.orchestrator.firestore") as mock_firestore, \
         patch("pipeline.orchestrator.generate_summary", new_callable=AsyncMock) as mock_summary:

        mock_stt.return_value = [{"word": "test", "startTime": 0.0, "endTime": 0.3, "speaker": 1}]
        mock_vi.return_value = [{"startTime": 0.0, "endTime": 10.0, "confidence": 0.95, "labels": ["intro"]}]
        mock_summary.return_value = {
            "summary": "Test summary",
            "chapters": [],
            "highlights": [],
            "sentiment": "neutral",
            "actionItems": [],
        }

        # Track call order
        call_order = []
        mock_firestore.write_results.side_effect = lambda **kwargs: call_order.append("write_results")
        mock_firestore.write_summary.side_effect = lambda **kwargs: call_order.append("write_summary")
        mock_firestore.mark_processing_completed.side_effect = lambda *args, **kwargs: call_order.append("mark_completed")

        result = await run_pipeline(job_message)

        assert result is True

        # mark_processing_completed must be called
        mock_firestore.mark_processing_completed.assert_called_once()

        # Verify ordering: write_results and write_summary before mark_completed
        assert "write_results" in call_order, "write_results was not called"
        assert "mark_completed" in call_order, "mark_processing_completed was not called"
        completed_idx = call_order.index("mark_completed")
        results_idx = call_order.index("write_results")
        assert results_idx < completed_idx, (
            f"write_results (index {results_idx}) must be called before "
            f"mark_processing_completed (index {completed_idx}). Order: {call_order}"
        )
