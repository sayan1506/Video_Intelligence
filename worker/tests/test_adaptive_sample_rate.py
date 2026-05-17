# worker/tests/test_adaptive_sample_rate.py
"""
Property-based test: adaptive sample rate by duration threshold.

**Validates: Requirements 4.3, 4.4, 6.2, 6.3**

Property 5: Adaptive sample rate is determined by duration threshold.
For any duration value, verify sample_rate=8000 when duration > 1800, else 16000.
Verify this holds for both whole-file and chunked paths.
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

from pipeline.speech_to_text import (
    transcribe,
    ADAPTIVE_FFMPEG_THRESHOLD_SECONDS,
    CHUNK_THRESHOLD_SECONDS,
)


# Strategy: positive floats representing video duration in seconds.
# We use a range from just above 0 to a large value covering both paths.
duration_strategy = st.floats(min_value=0.1, max_value=7200.0, allow_nan=False, allow_infinity=False)


@pytest.mark.asyncio
@given(duration=st.floats(
    min_value=CHUNK_THRESHOLD_SECONDS + 0.1,
    max_value=7200.0,
    allow_nan=False,
    allow_infinity=False,
))
@settings(max_examples=100, deadline=None)
async def test_chunked_path_uses_8000_when_duration_exceeds_1800(duration: float):
    """
    **Validates: Requirements 4.3, 6.3**

    Property 5 (chunked path, long duration):
    For any duration > CHUNK_THRESHOLD_SECONDS (300s) AND > ADAPTIVE_FFMPEG_THRESHOLD_SECONDS (1800s),
    transcribe SHALL pass sample_rate=8000 to transcribe_chunked.
    """
    assume(duration > ADAPTIVE_FFMPEG_THRESHOLD_SECONDS)

    with patch("pipeline.speech_to_text.download_from_gcs") as mock_download, \
         patch("pipeline.speech_to_text.get_video_duration_seconds", return_value=duration), \
         patch("pipeline.speech_to_text.transcribe_chunked", new_callable=AsyncMock) as mock_chunked:

        mock_chunked.return_value = [{"word": "test", "startTime": 0.0, "endTime": 0.5, "speaker": 1}]

        await transcribe("gs://bucket/video.mp4", job_id="test-job")

        mock_chunked.assert_called_once()
        call_kwargs = mock_chunked.call_args
        # transcribe_chunked(video_path, job_id, sample_rate=sample_rate)
        actual_sample_rate = call_kwargs.kwargs.get("sample_rate", call_kwargs[0][2] if len(call_kwargs[0]) > 2 else None)
        assert actual_sample_rate == 8000, (
            f"For duration={duration:.1f}s (> 1800s), expected sample_rate=8000 "
            f"passed to transcribe_chunked, but got {actual_sample_rate}"
        )


@pytest.mark.asyncio
@given(duration=st.floats(
    min_value=CHUNK_THRESHOLD_SECONDS + 0.1,
    max_value=ADAPTIVE_FFMPEG_THRESHOLD_SECONDS,
    allow_nan=False,
    allow_infinity=False,
))
@settings(max_examples=100, deadline=None)
async def test_chunked_path_uses_16000_when_duration_at_or_below_1800(duration: float):
    """
    **Validates: Requirements 4.4, 6.3**

    Property 5 (chunked path, medium duration):
    For any duration > CHUNK_THRESHOLD_SECONDS (300s) AND <= ADAPTIVE_FFMPEG_THRESHOLD_SECONDS (1800s),
    transcribe SHALL pass sample_rate=16000 to transcribe_chunked.
    """
    assume(duration <= ADAPTIVE_FFMPEG_THRESHOLD_SECONDS)

    with patch("pipeline.speech_to_text.download_from_gcs") as mock_download, \
         patch("pipeline.speech_to_text.get_video_duration_seconds", return_value=duration), \
         patch("pipeline.speech_to_text.transcribe_chunked", new_callable=AsyncMock) as mock_chunked:

        mock_chunked.return_value = [{"word": "test", "startTime": 0.0, "endTime": 0.5, "speaker": 1}]

        await transcribe("gs://bucket/video.mp4", job_id="test-job")

        mock_chunked.assert_called_once()
        call_kwargs = mock_chunked.call_args
        actual_sample_rate = call_kwargs.kwargs.get("sample_rate", call_kwargs[0][2] if len(call_kwargs[0]) > 2 else None)
        assert actual_sample_rate == 16000, (
            f"For duration={duration:.1f}s (<= 1800s), expected sample_rate=16000 "
            f"passed to transcribe_chunked, but got {actual_sample_rate}"
        )


@pytest.mark.asyncio
@given(duration=st.floats(
    min_value=0.1,
    max_value=CHUNK_THRESHOLD_SECONDS,
    allow_nan=False,
    allow_infinity=False,
))
@settings(max_examples=100, deadline=None)
async def test_whole_file_path_uses_16000_when_duration_at_or_below_1800(duration: float):
    """
    **Validates: Requirements 6.2**

    Property 5 (whole-file path, short duration):
    For any duration <= CHUNK_THRESHOLD_SECONDS (300s) — which is always <= 1800s —
    transcribe SHALL use whole-file extraction with sample_rate=16000.
    """
    with patch("pipeline.speech_to_text.download_from_gcs") as mock_download, \
         patch("pipeline.speech_to_text.get_video_duration_seconds", return_value=duration), \
         patch("pipeline.speech_to_text.extract_audio_to_flac") as mock_extract, \
         patch("pipeline.speech_to_text.upload_flac_to_gcs", return_value="gs://bucket/audio.flac"), \
         patch("pipeline.speech_to_text.get_speech_client") as mock_client, \
         patch("pipeline.speech_to_text._poll_operation_with_retry") as mock_poll:

        # Set up mock for the STT call that happens after extraction
        mock_speech_client = MagicMock()
        mock_client.return_value = mock_speech_client
        mock_operation = MagicMock()
        mock_speech_client.batch_recognize.return_value = mock_operation

        # Mock poll to return a response with no results
        mock_response = MagicMock()
        mock_response.results = {}
        mock_poll.return_value = mock_response

        await transcribe("gs://bucket/video.mp4", job_id="test-job")

        mock_extract.assert_called_once()
        call_args = mock_extract.call_args[0]
        # extract_audio_to_flac(video_path, flac_path, sample_rate)
        actual_sample_rate = call_args[2]
        assert actual_sample_rate == 16000, (
            f"For duration={duration:.1f}s (<= 300s, thus <= 1800s), expected "
            f"sample_rate=16000 for whole-file extraction, but got {actual_sample_rate}"
        )


@pytest.mark.asyncio
@given(duration=duration_strategy)
@settings(max_examples=200, deadline=None)
async def test_adaptive_sample_rate_threshold_property(duration: float):
    """
    **Validates: Requirements 4.3, 4.4, 6.2, 6.3**

    Property 5 (unified): For any positive duration, the sample_rate selected by
    transcribe is 8000 if duration > 1800, else 16000. This holds regardless of
    whether the whole-file or chunked path is taken.
    """
    expected_sample_rate = 8000 if duration > ADAPTIVE_FFMPEG_THRESHOLD_SECONDS else 16000
    uses_chunked_path = duration > CHUNK_THRESHOLD_SECONDS

    with patch("pipeline.speech_to_text.download_from_gcs") as mock_download, \
         patch("pipeline.speech_to_text.get_video_duration_seconds", return_value=duration), \
         patch("pipeline.speech_to_text.transcribe_chunked", new_callable=AsyncMock) as mock_chunked, \
         patch("pipeline.speech_to_text.extract_audio_to_flac") as mock_extract, \
         patch("pipeline.speech_to_text.upload_flac_to_gcs", return_value="gs://bucket/audio.flac"), \
         patch("pipeline.speech_to_text.get_speech_client") as mock_client, \
         patch("pipeline.speech_to_text._poll_operation_with_retry") as mock_poll:

        mock_chunked.return_value = [{"word": "test", "startTime": 0.0, "endTime": 0.5, "speaker": 1}]

        # Set up mock for whole-file STT path
        mock_speech_client = MagicMock()
        mock_client.return_value = mock_speech_client
        mock_operation = MagicMock()
        mock_speech_client.batch_recognize.return_value = mock_operation
        mock_response = MagicMock()
        mock_response.results = {}
        mock_poll.return_value = mock_response

        await transcribe("gs://bucket/video.mp4", job_id="test-job")

        if uses_chunked_path:
            mock_chunked.assert_called_once()
            call_kwargs = mock_chunked.call_args
            actual_sample_rate = call_kwargs.kwargs.get("sample_rate", call_kwargs[0][2] if len(call_kwargs[0]) > 2 else None)
            assert actual_sample_rate == expected_sample_rate, (
                f"Chunked path: duration={duration:.1f}s, expected sample_rate="
                f"{expected_sample_rate}, got {actual_sample_rate}"
            )
        else:
            mock_extract.assert_called_once()
            call_args = mock_extract.call_args[0]
            actual_sample_rate = call_args[2]
            assert actual_sample_rate == expected_sample_rate, (
                f"Whole-file path: duration={duration:.1f}s, expected sample_rate="
                f"{expected_sample_rate}, got {actual_sample_rate}"
            )
