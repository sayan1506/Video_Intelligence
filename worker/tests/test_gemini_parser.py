# worker/tests/test_gemini_parser.py

import json
import pytest
from pipeline.gemini import parse_gemini_response, _FALLBACK_SUMMARY


# --- Helpers ---

def valid_response(**overrides) -> str:
    """Build a valid Gemini response JSON string with optional field overrides."""
    base = {
        "summary": "This video demonstrates how to build a FastAPI backend on Google Cloud Run, covering deployment configuration and environment variable setup. It is aimed at Python developers new to GCP. The presenter walks through each step methodically, making it suitable for beginners.",
        "chapters": [
            {"title": "Setting up the local environment", "startTime": 0, "endTime": 45},
            {"title": "Configuring Cloud Run", "startTime": 45, "endTime": 120},
        ],
        "highlights": [
            {"timestamp": 23.5, "description": "Shows the correct gcloud deploy command with all required flags"},
        ],
        "sentiment": "positive",
        "actionItems": ["Install the gcloud CLI before following along"],
    }
    base.update(overrides)
    return json.dumps(base)


# --- JSON parse failures ---

class TestJsonParsing:

    def test_valid_json_parses_successfully(self):
        result = parse_gemini_response(valid_response(), job_id="test")
        assert isinstance(result, dict)
        assert "summary" in result

    def test_invalid_json_returns_fallback(self):
        result = parse_gemini_response("This is not JSON at all.", job_id="test")
        assert result["summary"] == _FALLBACK_SUMMARY["summary"]
        assert result["chapters"] == []

    def test_empty_string_returns_fallback(self):
        result = parse_gemini_response("", job_id="test")
        assert result["sentiment"] == "neutral"

    def test_json_array_returns_fallback(self):
        result = parse_gemini_response("[1, 2, 3]", job_id="test")
        assert result == _FALLBACK_SUMMARY

    def test_truncated_json_returns_fallback(self):
        truncated = '{"summary": "This is cut off mid'
        result = parse_gemini_response(truncated, job_id="test")
        assert result["chapters"] == []


# --- Summary field ---

class TestSummaryParsing:

    def test_valid_summary_returned_as_is(self):
        result = parse_gemini_response(valid_response(), job_id="test")
        assert "FastAPI" in result["summary"]

    def test_missing_summary_uses_fallback(self):
        data = json.loads(valid_response())
        del data["summary"]
        result = parse_gemini_response(json.dumps(data), job_id="test")
        assert result["summary"] == _FALLBACK_SUMMARY["summary"]

    def test_none_summary_uses_fallback(self):
        result = parse_gemini_response(valid_response(summary=None), job_id="test")
        assert result["summary"] == _FALLBACK_SUMMARY["summary"]

    def test_too_short_summary_uses_fallback(self):
        result = parse_gemini_response(valid_response(summary="Short."), job_id="test")
        assert result["summary"] == _FALLBACK_SUMMARY["summary"]

    def test_integer_summary_coerced_to_string(self):
        result = parse_gemini_response(valid_response(summary=42), job_id="test")
        # Coerced to "42" — too short, falls back
        assert result["summary"] == _FALLBACK_SUMMARY["summary"]


# --- Chapters field ---

class TestChapterParsing:

    def test_valid_chapters_parsed(self):
        result = parse_gemini_response(valid_response(), job_id="test")
        assert len(result["chapters"]) == 2
        assert result["chapters"][0]["title"] == "Setting up the local environment"
        assert result["chapters"][0]["startTime"] == 0
        assert result["chapters"][0]["endTime"] == 45

    def test_missing_chapters_returns_empty_list(self):
        data = json.loads(valid_response())
        del data["chapters"]
        result = parse_gemini_response(json.dumps(data), job_id="test")
        assert result["chapters"] == []

    def test_string_timestamps_coerced_to_int(self):
        chapters = [{"title": "Chapter one", "startTime": "10", "endTime": "45.5"}]
        result = parse_gemini_response(valid_response(chapters=chapters), job_id="test")
        assert isinstance(result["chapters"][0]["startTime"], int)
        assert result["chapters"][0]["startTime"] == 10
        assert isinstance(result["chapters"][0]["endTime"], int)
        assert result["chapters"][0]["endTime"] == 45

    def test_degenerate_chapter_start_equals_end_filtered(self):
        chapters = [
            {"title": "Valid chapter", "startTime": 0, "endTime": 30},
            {"title": "Bad chapter", "startTime": 50, "endTime": 50},
        ]
        result = parse_gemini_response(valid_response(chapters=chapters), job_id="test")
        assert len(result["chapters"]) == 1
        assert result["chapters"][0]["title"] == "Valid chapter"

    def test_reversed_chapter_timestamps_filtered(self):
        chapters = [{"title": "Backwards", "startTime": 100, "endTime": 30}]
        result = parse_gemini_response(valid_response(chapters=chapters), job_id="test")
        assert result["chapters"] == []

    def test_non_dict_chapter_skipped(self):
        chapters = [
            {"title": "Real chapter", "startTime": 0, "endTime": 45},
            "not a dict",
            None,
        ]
        result = parse_gemini_response(valid_response(chapters=chapters), job_id="test")
        assert len(result["chapters"]) == 1


# --- Highlights field ---

class TestHighlightParsing:

    def test_valid_highlights_parsed(self):
        result = parse_gemini_response(valid_response(), job_id="test")
        assert len(result["highlights"]) == 1
        assert result["highlights"][0]["timestamp"] == 23.5

    def test_missing_highlights_returns_empty_list(self):
        data = json.loads(valid_response())
        del data["highlights"]
        result = parse_gemini_response(json.dumps(data), job_id="test")
        assert result["highlights"] == []

    def test_string_timestamp_coerced_to_float(self):
        highlights = [{"timestamp": "30", "description": "Some moment"}]
        result = parse_gemini_response(valid_response(highlights=highlights), job_id="test")
        assert isinstance(result["highlights"][0]["timestamp"], float)
        assert result["highlights"][0]["timestamp"] == 30.0

    def test_highlight_without_description_skipped(self):
        highlights = [
            {"timestamp": 10.0, "description": "Good highlight"},
            {"timestamp": 20.0, "description": ""},
            {"timestamp": 30.0},
        ]
        result = parse_gemini_response(valid_response(highlights=highlights), job_id="test")
        assert len(result["highlights"]) == 1
        assert result["highlights"][0]["timestamp"] == 10.0


# --- Sentiment field ---

class TestSentimentParsing:

    def test_positive_sentiment_valid(self):
        result = parse_gemini_response(valid_response(sentiment="positive"), job_id="test")
        assert result["sentiment"] == "positive"

    def test_neutral_sentiment_valid(self):
        result = parse_gemini_response(valid_response(sentiment="neutral"), job_id="test")
        assert result["sentiment"] == "neutral"

    def test_negative_sentiment_valid(self):
        result = parse_gemini_response(valid_response(sentiment="negative"), job_id="test")
        assert result["sentiment"] == "negative"

    def test_capitalised_positive_normalised(self):
        result = parse_gemini_response(valid_response(sentiment="Positive"), job_id="test")
        assert result["sentiment"] == "positive"

    def test_all_caps_normalised(self):
        result = parse_gemini_response(valid_response(sentiment="NEUTRAL"), job_id="test")
        assert result["sentiment"] == "neutral"

    def test_near_match_mapped(self):
        result = parse_gemini_response(valid_response(sentiment="optimistic"), job_id="test")
        assert result["sentiment"] == "positive"

    def test_unrecognised_sentiment_defaults_to_neutral(self):
        result = parse_gemini_response(valid_response(sentiment="mixed"), job_id="test")
        assert result["sentiment"] == "neutral"

    def test_missing_sentiment_defaults_to_neutral(self):
        data = json.loads(valid_response())
        del data["sentiment"]
        result = parse_gemini_response(json.dumps(data), job_id="test")
        assert result["sentiment"] == "neutral"


# --- Action items field ---

class TestActionItemsParsing:

    def test_valid_action_items_returned(self):
        result = parse_gemini_response(valid_response(), job_id="test")
        assert len(result["actionItems"]) == 1
        assert "gcloud CLI" in result["actionItems"][0]

    def test_missing_action_items_returns_empty_list(self):
        data = json.loads(valid_response())
        del data["actionItems"]
        result = parse_gemini_response(json.dumps(data), job_id="test")
        assert result["actionItems"] == []

    def test_null_action_items_returns_empty_list(self):
        result = parse_gemini_response(valid_response(actionItems=None), job_id="test")
        assert result["actionItems"] == []

    def test_non_string_items_filtered(self):
        items = ["Valid item", 42, None, "", "Another valid item"]
        result = parse_gemini_response(valid_response(actionItems=items), job_id="test")
        assert len(result["actionItems"]) == 2
        assert "Valid item" in result["actionItems"]
        assert "Another valid item" in result["actionItems"]

    def test_whitespace_stripped_from_items(self):
        items = ["  Install ffmpeg  ", "Configure .env file  "]
        result = parse_gemini_response(valid_response(actionItems=items), job_id="test")
        assert result["actionItems"][0] == "Install ffmpeg"
        assert result["actionItems"][1] == "Configure .env file"