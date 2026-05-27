# worker/tests/test_audio_only_skips_vi.py
"""
Property-based test: audio-only pipeline skips Video Intelligence.

**Validates: Requirements 2.1, 2.2**

Property 2: Audio-only pipeline skips Video Intelligence and produces empty scenes.
For any job message with contentType in AUDIO_ONLY_MIME_TYPES, verify VI is never
called and scenes == [].
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

# Strategy: generate optional MIME parameters (e.g., "; charset=utf-8", "; codecs=mp3")
mime_params = st.one_of(
    st.just(""),
    st.text(
        alphabet=st.characters(whitelist_categories=("L", "N", "P", "Z")),
        min_size=1,
        max_size=30,
    ).map(lambda s: f"; {s}"),
)

# Strategy: generate case variations of a string
case_booleans = st.lists(st.booleans(), min_size=1, max_size=50)

# Strategy: generate valid job IDs
job_ids = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N")),
    min_size=5,
    max_size=20,
).filter(lambda s: len(s) > 0)

# Strategy: generate valid filenames
filenames = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N")),
    min_size=3,
    max_size=20,
).map(lambda s: f"{s}.mp3")

# Strategy: generate file sizes
file_sizes = st.floats(min_value=0.01, max_value=500.0, allow_nan=False, allow_infinity=False)


def build_job_message(content_type: str, job_id: str = "test-job-123", filename: str = "audio.mp3", file_size: float = 5.0) -> JobMessage:
    """Build a valid JobMessage with the given contentType."""
    return JobMessage(
        jobId=job_id,
        gcsPath=f"raw-videos/{job_id}/{filename}",
        gcsBucket="test-bucket",
        gcsUri=f"gs://test-bucket/raw-videos/{job_id}/{filename}",
        filename=filename,
        fileSizeMb=round(file_size, 2),
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
    params=mime_params,
)
@settings(max_examples=200, deadline=None)
async def test_audio_only_never_calls_vi(mime_type: str, params: str):
    """
    **Validates: Requirements 2.1**

    Property 2: For any job message with contentType in AUDIO_ONLY_MIME_TYPES
    (with or without MIME parameters), the Video Intelligence pipeline is never invoked.
    """
    content_type = mime_type + params
    job_message = build_job_message(content_type)

    with patch("pipeline.orchestrator._run_stt_with_progress", new_callable=AsyncMock) as mock_stt, \
         patch("pipeline.orchestrator._run_vi_with_progress", new_callable=AsyncMock) as mock_vi, \
         patch("pipeline.orchestrator.firestore") as mock_firestore, \
         patch("pipeline.orchestrator.generate_summary", new_callable=AsyncMock) as mock_summary:

        # STT returns a valid transcript tuple (transcript, detected_language)
        mock_stt.return_value = ([{"word": "hello", "startTime": 0.0, "endTime": 0.5, "speaker": 1}], "en-IN")
        # Summary returns valid data
        mock_summary.return_value = {
            "summary": "Test summary",
            "chapters": [],
            "highlights": [],
            "sentiment": "neutral",
            "actionItems": [],
        }

        result = await run_pipeline(job_message)

        # VI must never be called for audio-only files
        mock_vi.assert_not_called(), (
            f"_run_vi_with_progress was called for audio-only contentType={content_type!r}"
        )


@pytest.mark.asyncio
@given(
    mime_type=audio_mime_types,
    params=mime_params,
)
@settings(max_examples=200, deadline=None)
async def test_audio_only_produces_empty_scenes(mime_type: str, params: str):
    """
    **Validates: Requirements 2.2**

    Property 2: For any job message with contentType in AUDIO_ONLY_MIME_TYPES,
    the scenes result written to Firestore is an empty list.
    """
    content_type = mime_type + params
    job_message = build_job_message(content_type)

    with patch("pipeline.orchestrator._run_stt_with_progress", new_callable=AsyncMock) as mock_stt, \
         patch("pipeline.orchestrator._run_vi_with_progress", new_callable=AsyncMock) as mock_vi, \
         patch("pipeline.orchestrator.firestore") as mock_firestore, \
         patch("pipeline.orchestrator.generate_summary", new_callable=AsyncMock) as mock_summary:

        # STT returns a valid transcript tuple (transcript, detected_language)
        mock_stt.return_value = ([{"word": "hello", "startTime": 0.0, "endTime": 0.5, "speaker": 1}], "en-IN")
        # Summary returns valid data
        mock_summary.return_value = {
            "summary": "Test summary",
            "chapters": [],
            "highlights": [],
            "sentiment": "neutral",
            "actionItems": [],
        }

        result = await run_pipeline(job_message)

        # Verify write_results was called with scenes=[]
        mock_firestore.write_results.assert_called_once()
        call_kwargs = mock_firestore.write_results.call_args
        # write_results(job_id=job_id, transcript=transcript, scenes=scenes)
        actual_scenes = call_kwargs.kwargs.get("scenes", call_kwargs[1].get("scenes") if len(call_kwargs) > 1 else None)
        assert actual_scenes == [], (
            f"Expected scenes=[] for audio-only contentType={content_type!r}, "
            f"but got scenes={actual_scenes}"
        )


@pytest.mark.asyncio
@given(
    mime_type=audio_mime_types,
    case_choices=case_booleans,
    params=mime_params,
)
@settings(max_examples=200, deadline=None)
async def test_audio_only_case_insensitive_skips_vi(
    mime_type: str, case_choices: list, params: str
):
    """
    **Validates: Requirements 2.1, 2.2**

    Property 2 (case-insensitive variant): For any audio MIME type with arbitrary
    case variations, VI is still never called and scenes are still empty.
    """
    # Apply random case to the MIME type portion
    case_varied = "".join(
        c.upper() if case_choices[i % len(case_choices)] else c.lower()
        for i, c in enumerate(mime_type)
    )
    content_type = case_varied + params
    job_message = build_job_message(content_type)

    with patch("pipeline.orchestrator._run_stt_with_progress", new_callable=AsyncMock) as mock_stt, \
         patch("pipeline.orchestrator._run_vi_with_progress", new_callable=AsyncMock) as mock_vi, \
         patch("pipeline.orchestrator.firestore") as mock_firestore, \
         patch("pipeline.orchestrator.generate_summary", new_callable=AsyncMock) as mock_summary:

        mock_stt.return_value = ([{"word": "test", "startTime": 0.0, "endTime": 0.3, "speaker": 1}], "en-IN")
        mock_summary.return_value = {
            "summary": "Test summary",
            "chapters": [],
            "highlights": [],
            "sentiment": "neutral",
            "actionItems": [],
        }

        result = await run_pipeline(job_message)

        # VI must never be called
        mock_vi.assert_not_called(), (
            f"_run_vi_with_progress was called for case-varied audio contentType={content_type!r}"
        )

        # Scenes must be empty
        mock_firestore.write_results.assert_called_once()
        call_kwargs = mock_firestore.write_results.call_args
        actual_scenes = call_kwargs.kwargs.get("scenes", call_kwargs[1].get("scenes") if len(call_kwargs) > 1 else None)
        assert actual_scenes == [], (
            f"Expected scenes=[] for case-varied audio contentType={content_type!r}, "
            f"but got scenes={actual_scenes}"
        )
