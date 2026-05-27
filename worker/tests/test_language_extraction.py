# worker/tests/test_language_extraction.py
"""
Unit tests for language extraction from STT responses.

Tests cover:
- Whole-file path extracts language correctly (Req 1.1)
- Chunked path returns empty language (Req 1.2)
- Response with no valid language codes returns empty string (Req 1.3)
- transcribe_with_language() returns correct tuple structure (Req 1.4)
"""

import os

# Set required env vars before importing pipeline modules
os.environ.setdefault("GCP_PROJECT_ID", "test-project")
os.environ.setdefault("GCP_BUCKET_NAME", "test-bucket")
os.environ.setdefault("GCP_SERVICE_ACCOUNT_EMAIL", "test@test.iam.gserviceaccount.com")

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest
from google.cloud.speech_v2.types import cloud_speech

from pipeline.speech_to_text import (
    extract_language_from_response,
    transcribe_with_language,
    CHUNK_THRESHOLD_SECONDS,
)


# ---------------------------------------------------------------------------
# Helpers to build mock STT response objects
# ---------------------------------------------------------------------------


def make_alternative(language_code=None, words=None):
    """Create a mock SpeechRecognitionAlternative with a language_code."""
    alt = MagicMock()
    alt.language_code = language_code
    alt.words = words or []
    return alt


def make_result(alternatives):
    """Create a mock SpeechRecognitionResult with a list of alternatives."""
    result = MagicMock()
    result.alternatives = alternatives
    return result


def make_batch_recognize_results(results_list):
    """Create a mock BatchRecognizeResults with a list of results."""
    batch_results = MagicMock(spec=cloud_speech.BatchRecognizeResults)
    batch_results.results = results_list
    return batch_results


# ---------------------------------------------------------------------------
# Tests for extract_language_from_response() — Req 1.1, 1.3
# ---------------------------------------------------------------------------


class TestExtractLanguageFromResponse:
    """Tests for the extract_language_from_response() helper."""

    def test_returns_first_valid_language_code(self):
        """
        Req 1.1: Whole-file path extracts language correctly.
        When multiple alternatives have language codes, returns the first valid one.
        """
        alt1 = make_alternative(language_code="hi-IN")
        alt2 = make_alternative(language_code="en-IN")
        result = make_result([alt1, alt2])
        batch = make_batch_recognize_results([result])

        assert extract_language_from_response(batch) == "hi-IN"

    def test_skips_empty_language_codes(self):
        """
        Req 1.1: Skips alternatives with empty language_code and returns
        the first non-empty one.
        """
        alt1 = make_alternative(language_code="")
        alt2 = make_alternative(language_code="en-IN")
        result = make_result([alt1, alt2])
        batch = make_batch_recognize_results([result])

        assert extract_language_from_response(batch) == "en-IN"

    def test_skips_none_language_codes(self):
        """
        Req 1.1: Skips alternatives with None language_code and returns
        the first valid one.
        """
        alt1 = make_alternative(language_code=None)
        alt2 = make_alternative(language_code="hi-IN")
        result = make_result([alt1, alt2])
        batch = make_batch_recognize_results([result])

        assert extract_language_from_response(batch) == "hi-IN"

    def test_searches_across_multiple_results(self):
        """
        Req 1.1: Iterates through multiple results to find the first valid code.
        """
        alt1 = make_alternative(language_code="")
        result1 = make_result([alt1])

        alt2 = make_alternative(language_code="hi-IN")
        result2 = make_result([alt2])

        batch = make_batch_recognize_results([result1, result2])

        assert extract_language_from_response(batch) == "hi-IN"

    def test_empty_results_returns_empty_string(self):
        """
        Req 1.3: When the STT response has no results, returns empty string.
        """
        batch = make_batch_recognize_results([])

        assert extract_language_from_response(batch) == ""

    def test_all_null_language_codes_returns_empty_string(self):
        """
        Req 1.3: When all alternatives have None language_code, returns empty string.
        """
        alt1 = make_alternative(language_code=None)
        alt2 = make_alternative(language_code=None)
        result = make_result([alt1, alt2])
        batch = make_batch_recognize_results([result])

        assert extract_language_from_response(batch) == ""

    def test_all_empty_language_codes_returns_empty_string(self):
        """
        Req 1.3: When all alternatives have empty string language_code,
        returns empty string.
        """
        alt1 = make_alternative(language_code="")
        alt2 = make_alternative(language_code="")
        result = make_result([alt1, alt2])
        batch = make_batch_recognize_results([result])

        assert extract_language_from_response(batch) == ""

    def test_no_alternatives_returns_empty_string(self):
        """
        Req 1.3: When results have no alternatives, returns empty string.
        """
        result = make_result([])
        batch = make_batch_recognize_results([result])

        assert extract_language_from_response(batch) == ""

    def test_result_with_no_alternatives_attribute(self):
        """
        Req 1.3: When a result has empty alternatives list, it is skipped.
        """
        result1 = MagicMock()
        result1.alternatives = []

        alt = make_alternative(language_code="en-IN")
        result2 = make_result([alt])

        batch = make_batch_recognize_results([result1, result2])

        assert extract_language_from_response(batch) == "en-IN"


# ---------------------------------------------------------------------------
# Tests for transcribe_with_language() — Req 1.2, 1.4
# ---------------------------------------------------------------------------


class TestTranscribeWithLanguageChunkedPath:
    """Tests for the chunked path returning empty language (Req 1.2)."""

    def test_chunked_path_returns_empty_language(self):
        """
        Req 1.2: When video duration exceeds CHUNK_THRESHOLD_SECONDS,
        the chunked path is used and detected_language is empty string.
        """
        # Duration > CHUNK_THRESHOLD_SECONDS triggers chunked path
        long_duration = CHUNK_THRESHOLD_SECONDS + 100

        mock_transcript = [
            {"word": "hello", "startTime": 0.0, "endTime": 0.5, "speaker": 0},
        ]

        with (
            patch(
                "pipeline.speech_to_text.download_from_gcs"
            ) as mock_download,
            patch(
                "pipeline.speech_to_text.get_video_duration_seconds",
                return_value=long_duration,
            ),
            patch(
                "pipeline.speech_to_text.transcribe_chunked",
                new=AsyncMock(return_value=mock_transcript),
            ),
        ):
            result = asyncio.run(
                transcribe_with_language("gs://bucket/video.mp4", "test-job")
            )

        # Should return tuple of (transcript, "")
        assert isinstance(result, tuple)
        assert len(result) == 2
        transcript, detected_language = result
        assert transcript == mock_transcript
        assert detected_language == ""


class TestTranscribeWithLanguageWholeFilePath:
    """Tests for the whole-file path extracting language (Req 1.1, 1.4)."""

    def test_whole_file_path_extracts_language(self):
        """
        Req 1.1: When video duration <= CHUNK_THRESHOLD_SECONDS,
        the whole-file path extracts language from the STT response.
        """
        short_duration = CHUNK_THRESHOLD_SECONDS - 10

        # Build a mock STT response with language_code
        mock_word = MagicMock()
        mock_word.word = "namaste"
        mock_word.start_offset.total_seconds.return_value = 0.0
        mock_word.end_offset.total_seconds.return_value = 0.5
        mock_word.speaker_label = "1"

        mock_alternative = MagicMock()
        mock_alternative.language_code = "hi-IN"
        mock_alternative.words = [mock_word]

        mock_result = MagicMock()
        mock_result.alternatives = [mock_alternative]

        mock_transcript_obj = MagicMock(spec=cloud_speech.BatchRecognizeResults)
        mock_transcript_obj.results = [mock_result]

        mock_file_result = MagicMock()
        mock_file_result.transcript = mock_transcript_obj

        mock_response = MagicMock()
        mock_response.results = MagicMock()
        mock_response.results.get = MagicMock(return_value=mock_file_result)

        mock_operation = MagicMock()

        with (
            patch("pipeline.speech_to_text.download_from_gcs"),
            patch(
                "pipeline.speech_to_text.get_video_duration_seconds",
                return_value=short_duration,
            ),
            patch("pipeline.speech_to_text.extract_audio_to_flac"),
            patch(
                "pipeline.speech_to_text.upload_flac_to_gcs",
                return_value="gs://bucket/processed/test-job/audio.flac",
            ),
            patch(
                "pipeline.speech_to_text.get_speech_client"
            ) as mock_client_fn,
            patch(
                "pipeline.speech_to_text._poll_operation_with_retry",
                return_value=mock_response,
            ),
            patch("pipeline.speech_to_text.write_processed_json"),
        ):
            mock_client = MagicMock()
            mock_client.batch_recognize.return_value = mock_operation
            mock_client_fn.return_value = mock_client

            result = asyncio.run(
                transcribe_with_language("gs://bucket/video.mp4", "test-job")
            )

        assert isinstance(result, tuple)
        assert len(result) == 2
        transcript, detected_language = result
        assert detected_language == "hi-IN"
        assert isinstance(transcript, list)
        assert len(transcript) == 1
        assert transcript[0]["word"] == "namaste"

    def test_whole_file_path_no_language_returns_empty(self):
        """
        Req 1.3: When the STT response has no valid language codes,
        the whole-file path returns empty string for detected_language.
        """
        short_duration = CHUNK_THRESHOLD_SECONDS - 10

        # Build a mock STT response without language_code
        mock_word = MagicMock()
        mock_word.word = "hello"
        mock_word.start_offset.total_seconds.return_value = 0.0
        mock_word.end_offset.total_seconds.return_value = 0.5
        mock_word.speaker_label = "1"

        mock_alternative = MagicMock()
        mock_alternative.language_code = ""
        mock_alternative.words = [mock_word]

        mock_result = MagicMock()
        mock_result.alternatives = [mock_alternative]

        mock_transcript_obj = MagicMock(spec=cloud_speech.BatchRecognizeResults)
        mock_transcript_obj.results = [mock_result]

        mock_file_result = MagicMock()
        mock_file_result.transcript = mock_transcript_obj

        mock_response = MagicMock()
        mock_response.results = MagicMock()
        mock_response.results.get = MagicMock(return_value=mock_file_result)

        mock_operation = MagicMock()

        with (
            patch("pipeline.speech_to_text.download_from_gcs"),
            patch(
                "pipeline.speech_to_text.get_video_duration_seconds",
                return_value=short_duration,
            ),
            patch("pipeline.speech_to_text.extract_audio_to_flac"),
            patch(
                "pipeline.speech_to_text.upload_flac_to_gcs",
                return_value="gs://bucket/processed/test-job/audio.flac",
            ),
            patch(
                "pipeline.speech_to_text.get_speech_client"
            ) as mock_client_fn,
            patch(
                "pipeline.speech_to_text._poll_operation_with_retry",
                return_value=mock_response,
            ),
            patch("pipeline.speech_to_text.write_processed_json"),
        ):
            mock_client = MagicMock()
            mock_client.batch_recognize.return_value = mock_operation
            mock_client_fn.return_value = mock_client

            result = asyncio.run(
                transcribe_with_language("gs://bucket/video.mp4", "test-job")
            )

        assert isinstance(result, tuple)
        assert len(result) == 2
        transcript, detected_language = result
        assert detected_language == ""


class TestTranscribeWithLanguageTupleStructure:
    """Tests for transcribe_with_language() return type (Req 1.4)."""

    def test_returns_tuple_with_list_and_string(self):
        """
        Req 1.4: transcribe_with_language() returns a tuple of
        (list[dict], str) where the list has the same element structure
        as the existing transcribe() return value.
        """
        short_duration = CHUNK_THRESHOLD_SECONDS - 10

        mock_word = MagicMock()
        mock_word.word = "test"
        mock_word.start_offset.total_seconds.return_value = 0.0
        mock_word.end_offset.total_seconds.return_value = 0.3
        mock_word.speaker_label = "2"

        mock_alternative = MagicMock()
        mock_alternative.language_code = "en-IN"
        mock_alternative.words = [mock_word]

        mock_result = MagicMock()
        mock_result.alternatives = [mock_alternative]

        mock_transcript_obj = MagicMock(spec=cloud_speech.BatchRecognizeResults)
        mock_transcript_obj.results = [mock_result]

        mock_file_result = MagicMock()
        mock_file_result.transcript = mock_transcript_obj

        mock_response = MagicMock()
        mock_response.results = MagicMock()
        mock_response.results.get = MagicMock(return_value=mock_file_result)

        mock_operation = MagicMock()

        with (
            patch("pipeline.speech_to_text.download_from_gcs"),
            patch(
                "pipeline.speech_to_text.get_video_duration_seconds",
                return_value=short_duration,
            ),
            patch("pipeline.speech_to_text.extract_audio_to_flac"),
            patch(
                "pipeline.speech_to_text.upload_flac_to_gcs",
                return_value="gs://bucket/processed/test-job/audio.flac",
            ),
            patch(
                "pipeline.speech_to_text.get_speech_client"
            ) as mock_client_fn,
            patch(
                "pipeline.speech_to_text._poll_operation_with_retry",
                return_value=mock_response,
            ),
            patch("pipeline.speech_to_text.write_processed_json"),
        ):
            mock_client = MagicMock()
            mock_client.batch_recognize.return_value = mock_operation
            mock_client_fn.return_value = mock_client

            result = asyncio.run(
                transcribe_with_language("gs://bucket/video.mp4", "test-job")
            )

        # Verify tuple structure
        assert isinstance(result, tuple)
        assert len(result) == 2

        transcript, detected_language = result

        # Verify transcript is a list of dicts with expected keys
        assert isinstance(transcript, list)
        assert len(transcript) == 1
        word_entry = transcript[0]
        assert isinstance(word_entry, dict)
        assert "word" in word_entry
        assert "startTime" in word_entry
        assert "endTime" in word_entry
        assert "speaker" in word_entry
        assert word_entry["word"] == "test"
        assert isinstance(word_entry["startTime"], float)
        assert isinstance(word_entry["endTime"], float)
        assert isinstance(word_entry["speaker"], int)

        # Verify detected_language is a string
        assert isinstance(detected_language, str)
        assert detected_language == "en-IN"

    def test_empty_response_returns_empty_list_and_empty_string(self):
        """
        Req 1.4: When STT returns no transcript, the function returns
        ([], "") — maintaining the tuple structure.
        """
        short_duration = CHUNK_THRESHOLD_SECONDS - 10

        mock_file_result = MagicMock()
        mock_file_result.transcript = None

        mock_response = MagicMock()
        mock_response.results = MagicMock()
        mock_response.results.get = MagicMock(return_value=mock_file_result)

        mock_operation = MagicMock()

        with (
            patch("pipeline.speech_to_text.download_from_gcs"),
            patch(
                "pipeline.speech_to_text.get_video_duration_seconds",
                return_value=short_duration,
            ),
            patch("pipeline.speech_to_text.extract_audio_to_flac"),
            patch(
                "pipeline.speech_to_text.upload_flac_to_gcs",
                return_value="gs://bucket/processed/test-job/audio.flac",
            ),
            patch(
                "pipeline.speech_to_text.get_speech_client"
            ) as mock_client_fn,
            patch(
                "pipeline.speech_to_text._poll_operation_with_retry",
                return_value=mock_response,
            ),
            patch("pipeline.speech_to_text.write_processed_json"),
        ):
            mock_client = MagicMock()
            mock_client.batch_recognize.return_value = mock_operation
            mock_client_fn.return_value = mock_client

            result = asyncio.run(
                transcribe_with_language("gs://bucket/video.mp4", "test-job")
            )

        assert isinstance(result, tuple)
        assert len(result) == 2
        transcript, detected_language = result
        assert transcript == []
        assert detected_language == ""
