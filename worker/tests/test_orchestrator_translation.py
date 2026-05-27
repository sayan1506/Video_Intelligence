# worker/tests/test_orchestrator_translation.py
"""
Integration tests for orchestrator translation flow.

Validates:
- Req 6.3: Orchestrator calls transcribe_with_language()
- Req 6.4: Orchestrator passes detected_language to write_results()
- Req 6.1: Translation executes between write_results() and write_summary()
- Req 6.5: Translation failure results in None passed to write_summary()
- Req 2.5: Retry exhaustion allows pipeline to continue
"""

import os

# Set required env vars before importing pipeline modules
os.environ.setdefault("GCP_PROJECT_ID", "test-project")
os.environ.setdefault("GCP_BUCKET_NAME", "test-bucket")
os.environ.setdefault("GCP_SERVICE_ACCOUNT_EMAIL", "test@test.iam.gserviceaccount.com")

import pytest
from unittest.mock import patch, MagicMock, AsyncMock, call

from models.schemas import JobMessage
from pipeline.orchestrator import run_pipeline


def _make_job_message(content_type: str = "audio/mpeg") -> JobMessage:
    """Create a test JobMessage with the given contentType."""
    return JobMessage(
        jobId="test-job-translation",
        gcsPath="raw-videos/test-job-translation/test.mp3",
        gcsBucket="test-bucket",
        gcsUri="gs://test-bucket/raw-videos/test-job-translation/test.mp3",
        filename="test.mp3",
        fileSizeMb=5.0,
        contentType=content_type,
        uploadedAt="2024-01-01T00:00:00Z",
        schemaVersion="1",
    )


FAKE_TRANSCRIPT = [
    {"word": "namaste", "startTime": 0.0, "endTime": 0.5, "speaker": 1},
    {"word": "duniya", "startTime": 0.5, "endTime": 1.0, "speaker": 1},
]

FAKE_TRANSLATED_TRANSCRIPT = [
    {"word": "hello", "startTime": 0.0, "endTime": 0.5, "speaker": 1},
    {"word": "world", "startTime": 0.5, "endTime": 1.0, "speaker": 1},
]


@pytest.fixture
def mock_firestore():
    """Mock the firestore service module."""
    with patch("pipeline.orchestrator.firestore") as mock_fs:
        mock_fs.update_job_status = MagicMock()
        mock_fs.mark_processing_failed = MagicMock()
        mock_fs.mark_processing_completed = MagicMock()
        mock_fs.write_results = MagicMock()
        mock_fs.write_summary = MagicMock()
        mock_fs.write_job_fields = MagicMock()
        mock_fs.get_job = MagicMock(return_value={"geminiEstimatedCostUsd": 0.01})
        mock_fs.get_transcript_chunk_count = MagicMock(return_value=0)
        yield mock_fs


@pytest.fixture
def mock_stt_hindi():
    """Mock _run_stt_with_progress to return Hindi transcript."""
    with patch("pipeline.orchestrator._run_stt_with_progress", new_callable=AsyncMock) as mock:
        mock.return_value = (FAKE_TRANSCRIPT, "hi-IN")
        yield mock


@pytest.fixture
def mock_stt_english():
    """Mock _run_stt_with_progress to return English transcript."""
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


@pytest.fixture
def mock_translate_success():
    """Mock translate_transcript to return a successful translation."""
    with patch("pipeline.orchestrator.translate_transcript", new_callable=AsyncMock) as mock:
        mock.return_value = FAKE_TRANSLATED_TRANSCRIPT
        yield mock


@pytest.fixture
def mock_translate_failure():
    """Mock translate_transcript to raise an exception (simulating failure after retries)."""
    with patch("pipeline.orchestrator.translate_transcript", new_callable=AsyncMock) as mock:
        mock.side_effect = Exception("Translation failed after 2 retries")
        yield mock


@pytest.fixture
def mock_embed():
    """Mock embed_transcript_chunks to do nothing."""
    with patch("pipeline.orchestrator.embed_transcript_chunks", new_callable=AsyncMock) as mock:
        yield mock


class TestOrchestratorCallsTranscribeWithLanguage:
    """Req 6.3: Orchestrator calls transcribe_with_language()."""

    @pytest.mark.asyncio
    async def test_audio_path_calls_transcribe_with_language(
        self, mock_firestore, mock_stt_hindi, mock_generate_summary, mock_translate_success, mock_embed
    ):
        """
        Req 6.3: Audio-only path uses _run_stt_with_progress which wraps
        transcribe_with_language(), returning (transcript, detected_language) tuple.
        """
        job = _make_job_message(content_type="audio/mpeg")

        result = await run_pipeline(job)

        assert result is True
        mock_stt_hindi.assert_called_once()
        # Verify it was called with the correct GCS URI and job_id
        mock_stt_hindi.assert_called_once_with(
            "gs://test-bucket/raw-videos/test-job-translation/test.mp3",
            "test-job-translation",
        )

    @pytest.mark.asyncio
    async def test_video_path_calls_transcribe_with_language(
        self, mock_firestore, mock_stt_hindi, mock_vi, mock_generate_summary, mock_translate_success, mock_embed
    ):
        """
        Req 6.3: Video path also uses _run_stt_with_progress which wraps
        transcribe_with_language(), returning (transcript, detected_language) tuple.
        """
        job = _make_job_message(content_type="video/mp4")

        result = await run_pipeline(job)

        assert result is True
        mock_stt_hindi.assert_called_once()


class TestOrchestratorPassesDetectedLanguageToWriteResults:
    """Req 6.4: Orchestrator passes detected_language to write_results()."""

    @pytest.mark.asyncio
    async def test_detected_language_passed_to_write_results_hindi(
        self, mock_firestore, mock_stt_hindi, mock_generate_summary, mock_translate_success, mock_embed
    ):
        """
        Req 6.4: When STT detects Hindi, write_results() receives detected_language='hi-IN'.
        """
        job = _make_job_message(content_type="audio/mpeg")

        await run_pipeline(job)

        mock_firestore.write_results.assert_called_once()
        call_kwargs = mock_firestore.write_results.call_args.kwargs
        assert call_kwargs["detected_language"] == "hi-IN"

    @pytest.mark.asyncio
    async def test_detected_language_passed_to_write_results_english(
        self, mock_firestore, mock_stt_english, mock_generate_summary, mock_embed
    ):
        """
        Req 6.4: When STT detects English, write_results() receives detected_language='en-IN'.
        """
        job = _make_job_message(content_type="audio/mpeg")

        await run_pipeline(job)

        mock_firestore.write_results.assert_called_once()
        call_kwargs = mock_firestore.write_results.call_args.kwargs
        assert call_kwargs["detected_language"] == "en-IN"


class TestTranslationExecutesBetweenWriteResultsAndWriteSummary:
    """Req 6.1: Translation executes between write_results() and write_summary()."""

    @pytest.mark.asyncio
    async def test_translation_called_after_write_results_before_write_summary(
        self, mock_firestore, mock_stt_hindi, mock_generate_summary, mock_embed
    ):
        """
        Req 6.1: The call order must be write_results() → translate_transcript() → write_summary().
        Uses a call ordering tracker to verify the sequence.
        """
        call_order = []

        mock_firestore.write_results.side_effect = lambda **kwargs: call_order.append("write_results")
        mock_firestore.write_summary.side_effect = lambda **kwargs: call_order.append("write_summary")

        with patch("pipeline.orchestrator.translate_transcript", new_callable=AsyncMock) as mock_translate:
            async def translate_side_effect(**kwargs):
                call_order.append("translate_transcript")
                return FAKE_TRANSLATED_TRANSCRIPT

            mock_translate.side_effect = translate_side_effect

            job = _make_job_message(content_type="audio/mpeg")
            result = await run_pipeline(job)

            assert result is True
            # Verify ordering: write_results before translate_transcript before write_summary
            assert "write_results" in call_order
            assert "translate_transcript" in call_order
            assert "write_summary" in call_order

            wr_idx = call_order.index("write_results")
            tt_idx = call_order.index("translate_transcript")
            ws_idx = call_order.index("write_summary")

            assert wr_idx < tt_idx, (
                f"write_results (idx={wr_idx}) should come before translate_transcript (idx={tt_idx})"
            )
            assert tt_idx < ws_idx, (
                f"translate_transcript (idx={tt_idx}) should come before write_summary (idx={ws_idx})"
            )

    @pytest.mark.asyncio
    async def test_translated_transcript_passed_to_write_summary(
        self, mock_firestore, mock_stt_hindi, mock_generate_summary, mock_translate_success, mock_embed
    ):
        """
        Req 6.1: The translated transcript is passed to write_summary() when translation succeeds.
        """
        job = _make_job_message(content_type="audio/mpeg")

        await run_pipeline(job)

        mock_firestore.write_summary.assert_called_once()
        call_kwargs = mock_firestore.write_summary.call_args.kwargs
        assert call_kwargs["translated_transcript"] == FAKE_TRANSLATED_TRANSCRIPT


class TestTranslationFailurePassesNoneToWriteSummary:
    """Req 6.5: Translation failure results in None passed to write_summary()."""

    @pytest.mark.asyncio
    async def test_translation_exception_passes_none_to_write_summary(
        self, mock_firestore, mock_stt_hindi, mock_generate_summary, mock_translate_failure, mock_embed
    ):
        """
        Req 6.5: When translate_transcript() raises an exception, write_summary()
        receives translated_transcript=None and the pipeline continues.
        """
        job = _make_job_message(content_type="audio/mpeg")

        result = await run_pipeline(job)

        # Pipeline should still succeed
        assert result is True
        # write_summary should be called with translated_transcript=None
        mock_firestore.write_summary.assert_called_once()
        call_kwargs = mock_firestore.write_summary.call_args.kwargs
        assert call_kwargs["translated_transcript"] is None

    @pytest.mark.asyncio
    async def test_translation_returns_none_passes_none_to_write_summary(
        self, mock_firestore, mock_stt_hindi, mock_generate_summary, mock_embed
    ):
        """
        Req 6.5: When translate_transcript() returns None (e.g., parse failure),
        write_summary() receives translated_transcript=None.
        """
        with patch("pipeline.orchestrator.translate_transcript", new_callable=AsyncMock) as mock_translate:
            mock_translate.return_value = None

            job = _make_job_message(content_type="audio/mpeg")
            result = await run_pipeline(job)

            assert result is True
            mock_firestore.write_summary.assert_called_once()
            call_kwargs = mock_firestore.write_summary.call_args.kwargs
            assert call_kwargs["translated_transcript"] is None

    @pytest.mark.asyncio
    async def test_english_detected_skips_translation_passes_none(
        self, mock_firestore, mock_stt_english, mock_generate_summary, mock_embed
    ):
        """
        Req 6.5 / 2.4: When detected language is English, translation is skipped
        and write_summary() receives translated_transcript=None.
        """
        with patch("pipeline.orchestrator.translate_transcript", new_callable=AsyncMock) as mock_translate:
            job = _make_job_message(content_type="audio/mpeg")
            result = await run_pipeline(job)

            assert result is True
            # translate_transcript should NOT be called for English
            mock_translate.assert_not_called()
            # write_summary should still be called with translated_transcript=None
            mock_firestore.write_summary.assert_called_once()
            call_kwargs = mock_firestore.write_summary.call_args.kwargs
            assert call_kwargs["translated_transcript"] is None


class TestRetryExhaustionAllowsPipelineToContinue:
    """Req 2.5: Retry exhaustion allows pipeline to continue."""

    @pytest.mark.asyncio
    async def test_pipeline_completes_after_translation_retries_exhausted(
        self, mock_firestore, mock_stt_hindi, mock_generate_summary, mock_translate_failure, mock_embed
    ):
        """
        Req 2.5: When translate_transcript() fails after exhausting retries
        (raises exception), the pipeline still completes successfully.
        """
        job = _make_job_message(content_type="audio/mpeg")

        result = await run_pipeline(job)

        # Pipeline should complete successfully
        assert result is True
        # Job should be marked as completed
        mock_firestore.mark_processing_completed.assert_called_once()
        # mark_processing_failed should NOT be called
        mock_firestore.mark_processing_failed.assert_not_called()

    @pytest.mark.asyncio
    async def test_write_summary_still_called_after_translation_failure(
        self, mock_firestore, mock_stt_hindi, mock_generate_summary, mock_translate_failure, mock_embed
    ):
        """
        Req 2.5: After translation failure, write_summary() is still called
        (with translated_transcript=None) so the summary is persisted.
        """
        job = _make_job_message(content_type="audio/mpeg")

        result = await run_pipeline(job)

        assert result is True
        mock_firestore.write_summary.assert_called_once()
        call_kwargs = mock_firestore.write_summary.call_args.kwargs
        # Summary data should still be present
        assert "summary_data" in call_kwargs
        assert call_kwargs["summary_data"]["summary"] == "Test summary"
        # Translated transcript should be None due to failure
        assert call_kwargs["translated_transcript"] is None

    @pytest.mark.asyncio
    async def test_embeddings_still_run_after_translation_failure(
        self, mock_firestore, mock_stt_hindi, mock_generate_summary, mock_translate_failure, mock_embed
    ):
        """
        Req 2.5: After translation failure, the rest of the pipeline
        (embeddings, completion) still executes.
        """
        mock_firestore.get_transcript_chunk_count.return_value = 3

        job = _make_job_message(content_type="audio/mpeg")

        result = await run_pipeline(job)

        assert result is True
        # Embeddings should still be attempted
        mock_embed.assert_called_once_with("test-job-translation", 3)
