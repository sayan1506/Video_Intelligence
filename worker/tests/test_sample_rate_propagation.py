# worker/tests/test_sample_rate_propagation.py
"""
Property-based test: sample_rate propagation through transcribe_chunked.

**Validates: Requirements 4.2**

Property 6: For any valid sample_rate value passed to transcribe_chunked,
that exact value is forwarded to split_audio_to_chunks.
"""

import os

# Set required env vars before importing pipeline modules
os.environ.setdefault("GCP_PROJECT_ID", "test-project")
os.environ.setdefault("GCP_BUCKET_NAME", "test-bucket")
os.environ.setdefault("GCP_SERVICE_ACCOUNT_EMAIL", "test@test.iam.gserviceaccount.com")

import asyncio
from unittest.mock import patch, MagicMock, AsyncMock

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from pipeline.speech_to_text import transcribe_chunked


@pytest.mark.asyncio
@given(sample_rate=st.integers(min_value=1, max_value=192000))
@settings(max_examples=100, deadline=None)
async def test_sample_rate_propagates_to_split_audio_to_chunks(sample_rate: int):
    """
    **Validates: Requirements 4.2**

    Property 6: sample_rate parameter propagates through transcribe_chunked
    to split_audio_to_chunks.

    For any valid sample_rate integer passed to transcribe_chunked, that exact
    value is forwarded as the third argument to split_audio_to_chunks.
    """
    with patch(
        "pipeline.speech_to_text.split_audio_to_chunks"
    ) as mock_split, patch(
        "pipeline.speech_to_text.upload_chunk_to_gcs",
        return_value="gs://bucket/chunk_0.flac",
    ), patch(
        "pipeline.speech_to_text.transcribe_chunk",
        new_callable=AsyncMock,
        return_value=[{"word": "hello", "startTime": 0.0, "endTime": 0.5}],
    ), patch(
        "pipeline.speech_to_text.delete_chunk_from_gcs",
    ):
        # split_audio_to_chunks returns a list of (chunk_path, start_offset) tuples
        mock_split.return_value = [("/tmp/chunk_0.flac", 0.0)]

        await transcribe_chunked(
            video_path="/tmp/test_video.mp4",
            job_id="test-job-123",
            sample_rate=sample_rate,
        )

        # Assert split_audio_to_chunks was called with the exact sample_rate
        mock_split.assert_called_once()
        call_args = mock_split.call_args
        # split_audio_to_chunks(video_path, chunk_dir, sample_rate)
        actual_sample_rate = call_args[0][2]  # Third positional argument
        assert actual_sample_rate == sample_rate, (
            f"Expected sample_rate={sample_rate} to propagate to "
            f"split_audio_to_chunks, but got {actual_sample_rate}"
        )
