# worker/tests/test_translation_prompt.py
"""Unit tests for build_translation_prompt(), parse_translation_response(),
and translate_transcript() retry exhaustion.

Validates: Requirements 2.5, 2.6, 2.7
"""

import json
import sys
import os
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pipeline.gemini import (
    build_translation_prompt,
    parse_translation_response,
    translate_transcript,
)
from google.api_core.exceptions import ServiceUnavailable, ResourceExhausted


class TestBuildTranslationPrompt:
    """Tests for the build_translation_prompt helper."""

    def test_returns_string(self):
        """Prompt should be a non-empty string."""
        transcript = [
            {"word": "नमस्ते", "startTime": 0.5, "endTime": 1.0, "speaker": 1},
        ]
        result = build_translation_prompt(transcript, "hi-IN")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_contains_source_language(self):
        """Prompt should reference the source language."""
        transcript = [
            {"word": "bonjour", "startTime": 0.0, "endTime": 0.5, "speaker": 1},
        ]
        result = build_translation_prompt(transcript, "fr-FR")
        assert "fr-FR" in result

    def test_contains_english_target(self):
        """Prompt should specify English as the target language."""
        transcript = [
            {"word": "hola", "startTime": 0.0, "endTime": 0.5, "speaker": 1},
        ]
        result = build_translation_prompt(transcript, "es-ES")
        assert "English" in result

    def test_contains_all_words(self):
        """Prompt should include every word from the transcript."""
        transcript = [
            {"word": "नमस्ते", "startTime": 0.5, "endTime": 1.0, "speaker": 1},
            {"word": "मेरा", "startTime": 1.0, "endTime": 1.5, "speaker": 1},
            {"word": "नाम", "startTime": 1.5, "endTime": 2.0, "speaker": 1},
        ]
        result = build_translation_prompt(transcript, "hi-IN")
        for entry in transcript:
            assert entry["word"] in result

    def test_instructs_json_array_output(self):
        """Prompt should instruct Gemini to return a JSON array."""
        transcript = [
            {"word": "test", "startTime": 0.0, "endTime": 0.5, "speaker": 1},
        ]
        result = build_translation_prompt(transcript, "hi-IN")
        assert "JSON" in result
        assert "original_index" in result
        assert "translated_words" in result

    def test_specifies_correct_entry_count(self):
        """Prompt should tell Gemini the exact number of entries expected."""
        transcript = [
            {"word": "a", "startTime": 0.0, "endTime": 0.5, "speaker": 1},
            {"word": "b", "startTime": 0.5, "endTime": 1.0, "speaker": 1},
            {"word": "c", "startTime": 1.0, "endTime": 1.5, "speaker": 1},
        ]
        result = build_translation_prompt(transcript, "hi-IN")
        assert str(len(transcript)) in result

    def test_empty_transcript(self):
        """Prompt should handle empty transcript without error."""
        result = build_translation_prompt([], "hi-IN")
        assert isinstance(result, str)
        assert "hi-IN" in result
        assert "0" in result  # 0 entries expected


class TestParseTranslationResponse:
    """Tests for parse_translation_response() — validates Req 2.7."""

    def test_valid_single_word_per_entry(self):
        """Valid response with one translated word per entry produces correct structure."""
        original_transcript = [
            {"word": "नमस्ते", "startTime": 0.5, "endTime": 1.0, "speaker": 1},
            {"word": "दुनिया", "startTime": 1.0, "endTime": 1.5, "speaker": 2},
        ]
        raw_text = json.dumps([
            {"original_index": 0, "translated_words": ["Hello"]},
            {"original_index": 1, "translated_words": ["World"]},
        ])

        result = parse_translation_response(raw_text, original_transcript)

        assert result is not None
        assert len(result) == 2
        assert result[0] == {
            "word": "Hello",
            "startTime": 0.5,
            "endTime": 1.0,
            "speaker": 1,
        }
        assert result[1] == {
            "word": "World",
            "startTime": 1.0,
            "endTime": 1.5,
            "speaker": 2,
        }

    def test_valid_multiple_words_per_entry(self):
        """Valid response with multiple translated words distributes time equally."""
        original_transcript = [
            {"word": "मेरा", "startTime": 1.0, "endTime": 2.0, "speaker": 1},
        ]
        raw_text = json.dumps([
            {"original_index": 0, "translated_words": ["my", "name"]},
        ])

        result = parse_translation_response(raw_text, original_transcript)

        assert result is not None
        assert len(result) == 2
        # First word: 1.0 to 1.5
        assert result[0]["word"] == "my"
        assert result[0]["startTime"] == 1.0
        assert result[0]["endTime"] == 1.5
        assert result[0]["speaker"] == 1
        # Second word: 1.5 to 2.0
        assert result[1]["word"] == "name"
        assert result[1]["startTime"] == 1.5
        assert result[1]["endTime"] == 2.0
        assert result[1]["speaker"] == 1

    def test_valid_preserves_speaker(self):
        """Translated words inherit the speaker from the source entry."""
        original_transcript = [
            {"word": "hola", "startTime": 0.0, "endTime": 1.0, "speaker": 3},
        ]
        raw_text = json.dumps([
            {"original_index": 0, "translated_words": ["hello", "there"]},
        ])

        result = parse_translation_response(raw_text, original_transcript)

        assert result is not None
        for entry in result:
            assert entry["speaker"] == 3

    def test_valid_rounds_to_three_decimals(self):
        """Time values are rounded to 3 decimal places."""
        original_transcript = [
            {"word": "test", "startTime": 0.0, "endTime": 1.0, "speaker": 1},
        ]
        raw_text = json.dumps([
            {"original_index": 0, "translated_words": ["a", "b", "c"]},
        ])

        result = parse_translation_response(raw_text, original_transcript)

        assert result is not None
        assert len(result) == 3
        # 1.0 / 3 = 0.333...
        assert result[0]["startTime"] == 0.0
        assert result[0]["endTime"] == 0.333
        assert result[1]["startTime"] == 0.333
        assert result[1]["endTime"] == 0.667
        assert result[2]["startTime"] == 0.667
        assert result[2]["endTime"] == 1.0

    def test_invalid_json_returns_none(self):
        """Non-JSON response returns None."""
        original_transcript = [
            {"word": "test", "startTime": 0.0, "endTime": 1.0, "speaker": 1},
        ]
        result = parse_translation_response("not valid json {{{", original_transcript)
        assert result is None

    def test_wrong_schema_returns_none(self):
        """Valid JSON but wrong schema returns None."""
        original_transcript = [
            {"word": "test", "startTime": 0.0, "endTime": 1.0, "speaker": 1},
        ]
        # Missing translated_words field
        raw_text = json.dumps([{"original_index": 0, "wrong_field": ["hello"]}])
        result = parse_translation_response(raw_text, original_transcript)
        assert result is None

    def test_length_mismatch_returns_none(self):
        """Response with wrong number of entries returns None."""
        original_transcript = [
            {"word": "a", "startTime": 0.0, "endTime": 0.5, "speaker": 1},
            {"word": "b", "startTime": 0.5, "endTime": 1.0, "speaker": 1},
        ]
        raw_text = json.dumps([
            {"original_index": 0, "translated_words": ["hello"]},
        ])
        result = parse_translation_response(raw_text, original_transcript)
        assert result is None

    def test_empty_translated_words_returns_none(self):
        """Entry with empty translated_words array returns None."""
        original_transcript = [
            {"word": "test", "startTime": 0.0, "endTime": 1.0, "speaker": 1},
        ]
        raw_text = json.dumps([
            {"original_index": 0, "translated_words": []},
        ])
        result = parse_translation_response(raw_text, original_transcript)
        assert result is None


class TestTranslateTranscriptRetryExhaustion:
    """Tests for translate_transcript() retry exhaustion — validates Req 2.5."""

    @pytest.mark.asyncio
    async def test_returns_none_after_service_unavailable_retries(self):
        """translate_transcript returns None after exhausting retries on ServiceUnavailable."""
        transcript = [
            {"word": "test", "startTime": 0.0, "endTime": 1.0, "speaker": 1},
        ]

        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = ServiceUnavailable(
            "Service unavailable"
        )

        with patch("pipeline.gemini.get_gemini_client", return_value=mock_client), \
             patch("pipeline.gemini.time_module.sleep"):
            result = await translate_transcript(transcript, "hi-IN", job_id="test-job")

        assert result is None
        # Initial attempt + 2 retries = 3 calls total
        assert mock_client.models.generate_content.call_count == 3

    @pytest.mark.asyncio
    async def test_returns_none_after_resource_exhausted_retries(self):
        """translate_transcript returns None after exhausting retries on ResourceExhausted."""
        transcript = [
            {"word": "test", "startTime": 0.0, "endTime": 1.0, "speaker": 1},
        ]

        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = ResourceExhausted(
            "Quota exceeded"
        )

        with patch("pipeline.gemini.get_gemini_client", return_value=mock_client), \
             patch("pipeline.gemini.time_module.sleep"):
            result = await translate_transcript(transcript, "hi-IN", job_id="test-job")

        assert result is None
        assert mock_client.models.generate_content.call_count == 3

    @pytest.mark.asyncio
    async def test_returns_none_immediately_on_safety_block(self):
        """translate_transcript returns None immediately on safety block without retrying."""
        transcript = [
            {"word": "test", "startTime": 0.0, "endTime": 1.0, "speaker": 1},
        ]

        mock_candidate = MagicMock()
        mock_candidate.finish_reason.name = "SAFETY"

        mock_response = MagicMock()
        mock_response.candidates = [mock_candidate]

        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response

        with patch("pipeline.gemini.get_gemini_client", return_value=mock_client), \
             patch("pipeline.gemini.time_module.sleep"):
            result = await translate_transcript(transcript, "hi-IN", job_id="test-job")

        assert result is None
        # Only 1 call — no retries on safety block
        assert mock_client.models.generate_content.call_count == 1
