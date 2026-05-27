# worker/tests/test_translation_parser_properties.py
# Feature: multi-language-support, Property 4: Invalid translation responses produce None
"""
Property-based test for invalid translation response handling.

**Validates: Requirements 2.7**

Property 4: For any string that is not valid JSON, or is valid JSON but does not
conform to the expected translation response schema (array of objects each containing
original_index as integer and translated_words as non-empty array of strings), the
parse_translation_response() function SHALL return None.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Set required env vars before importing pipeline modules
os.environ.setdefault("GCP_PROJECT_ID", "test-project")
os.environ.setdefault("GCP_BUCKET_NAME", "test-bucket")
os.environ.setdefault("GCP_SERVICE_ACCOUNT_EMAIL", "test@test.iam.gserviceaccount.com")

import json
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from pipeline.gemini import parse_translation_response


# --- Helpers ---

def make_original_transcript(n: int) -> list[dict]:
    """Create a simple valid original transcript with n entries."""
    return [
        {
            "word": f"word{i}",
            "startTime": float(i),
            "endTime": float(i) + 0.5,
            "speaker": 1,
        }
        for i in range(n)
    ]


# --- Strategies ---

# Strategy for strings that are NOT valid JSON
invalid_json_strategy = st.text(min_size=1, max_size=200).filter(
    lambda s: _is_invalid_json(s)
)


def _is_invalid_json(s: str) -> bool:
    """Return True if s is not valid JSON."""
    try:
        json.loads(s)
        return False
    except (json.JSONDecodeError, ValueError):
        return True


# Strategy for valid JSON that is not a list (objects, strings, numbers, booleans, null)
json_non_list_strategy = st.one_of(
    st.dictionaries(st.text(min_size=1, max_size=10), st.integers(), min_size=0, max_size=5),
    st.integers(),
    st.floats(allow_nan=False, allow_infinity=False),
    st.booleans(),
    st.none(),
    st.text(min_size=0, max_size=50),
)

# Strategy for entries missing "original_index" field
entry_missing_original_index = st.fixed_dictionaries({
    "translated_words": st.lists(st.text(min_size=1, max_size=20), min_size=1, max_size=5),
})

# Strategy for entries missing "translated_words" field
entry_missing_translated_words = st.fixed_dictionaries({
    "original_index": st.integers(min_value=0, max_value=100),
})

# Strategy for entries with non-integer original_index
# Note: In Python, bool is a subclass of int, so isinstance(True, int) == True.
# JSON booleans deserialize to Python bools which pass isinstance(x, int).
# We exclude booleans here since they are technically ints in Python's type system.
entry_non_integer_index = st.fixed_dictionaries({
    "original_index": st.one_of(
        st.text(min_size=1, max_size=10),
        st.floats(allow_nan=False, allow_infinity=False).filter(lambda x: x != int(x) if x == x else True),
        st.lists(st.integers(), min_size=0, max_size=3),
        st.none(),
    ),
    "translated_words": st.lists(st.text(min_size=1, max_size=20), min_size=1, max_size=5),
})

# Strategy for entries with non-list translated_words
entry_non_list_translated_words = st.fixed_dictionaries({
    "original_index": st.integers(min_value=0, max_value=100),
    "translated_words": st.one_of(
        st.text(min_size=0, max_size=20),
        st.integers(),
        st.none(),
        st.booleans(),
        st.dictionaries(st.text(min_size=1, max_size=5), st.integers(), min_size=0, max_size=3),
    ),
})

# Strategy for entries with empty translated_words array
entry_empty_translated_words = st.fixed_dictionaries({
    "original_index": st.integers(min_value=0, max_value=100),
    "translated_words": st.just([]),
})

# Strategy for entries with non-string words in translated_words
non_string_word = st.one_of(
    st.integers(),
    st.floats(allow_nan=False, allow_infinity=False),
    st.none(),
    st.booleans(),
    st.lists(st.integers(), min_size=0, max_size=2),
)

entry_non_string_words = st.fixed_dictionaries({
    "original_index": st.integers(min_value=0, max_value=100),
    "translated_words": st.lists(non_string_word, min_size=1, max_size=5),
})


# --- Property Tests ---


class TestInvalidTranslationResponseProperty:
    """Property 4: Invalid translation responses produce None."""

    @given(raw_text=invalid_json_strategy)
    @settings(max_examples=30)
    def test_invalid_json_returns_none(self, raw_text):
        """
        **Validates: Requirements 2.7**

        Any string that is not valid JSON must cause parse_translation_response
        to return None.
        """
        original_transcript = make_original_transcript(3)
        result = parse_translation_response(raw_text, original_transcript, job_id="test")
        assert result is None, (
            f"Expected None for invalid JSON input: {raw_text!r}, got {result}"
        )

    @given(data=json_non_list_strategy)
    @settings(max_examples=30)
    def test_valid_json_non_list_returns_none(self, data):
        """
        **Validates: Requirements 2.7**

        Valid JSON that is not a list (objects, strings, numbers, booleans, null)
        must cause parse_translation_response to return None.
        """
        raw_text = json.dumps(data)
        original_transcript = make_original_transcript(3)
        result = parse_translation_response(raw_text, original_transcript, job_id="test")
        assert result is None, (
            f"Expected None for non-list JSON: {raw_text!r}, got {result}"
        )

    @given(entry=entry_missing_original_index)
    @settings(max_examples=30)
    def test_entry_missing_original_index_returns_none(self, entry):
        """
        **Validates: Requirements 2.7**

        A JSON array where entries are missing the "original_index" field
        must cause parse_translation_response to return None.
        """
        original_transcript = make_original_transcript(1)
        raw_text = json.dumps([entry])
        result = parse_translation_response(raw_text, original_transcript, job_id="test")
        assert result is None, (
            f"Expected None for entry missing original_index: {raw_text!r}, got {result}"
        )

    @given(entry=entry_missing_translated_words)
    @settings(max_examples=30)
    def test_entry_missing_translated_words_returns_none(self, entry):
        """
        **Validates: Requirements 2.7**

        A JSON array where entries are missing the "translated_words" field
        must cause parse_translation_response to return None.
        """
        original_transcript = make_original_transcript(1)
        raw_text = json.dumps([entry])
        result = parse_translation_response(raw_text, original_transcript, job_id="test")
        assert result is None, (
            f"Expected None for entry missing translated_words: {raw_text!r}, got {result}"
        )

    @given(entry=entry_non_integer_index)
    @settings(max_examples=30)
    def test_non_integer_original_index_returns_none(self, entry):
        """
        **Validates: Requirements 2.7**

        Entries where original_index is not an integer (string, float, list,
        null, boolean) must cause parse_translation_response to return None.
        """
        original_transcript = make_original_transcript(1)
        raw_text = json.dumps([entry])
        result = parse_translation_response(raw_text, original_transcript, job_id="test")
        assert result is None, (
            f"Expected None for non-integer original_index: {raw_text!r}, got {result}"
        )

    @given(entry=entry_non_list_translated_words)
    @settings(max_examples=30)
    def test_non_list_translated_words_returns_none(self, entry):
        """
        **Validates: Requirements 2.7**

        Entries where translated_words is not a list (string, integer, null,
        boolean, dict) must cause parse_translation_response to return None.
        """
        original_transcript = make_original_transcript(1)
        raw_text = json.dumps([entry])
        result = parse_translation_response(raw_text, original_transcript, job_id="test")
        assert result is None, (
            f"Expected None for non-list translated_words: {raw_text!r}, got {result}"
        )

    @given(entry=entry_empty_translated_words)
    @settings(max_examples=30)
    def test_empty_translated_words_returns_none(self, entry):
        """
        **Validates: Requirements 2.7**

        Entries where translated_words is an empty array must cause
        parse_translation_response to return None.
        """
        original_transcript = make_original_transcript(1)
        raw_text = json.dumps([entry])
        result = parse_translation_response(raw_text, original_transcript, job_id="test")
        assert result is None, (
            f"Expected None for empty translated_words: {raw_text!r}, got {result}"
        )

    @given(entry=entry_non_string_words)
    @settings(max_examples=30)
    def test_non_string_words_in_translated_words_returns_none(self, entry):
        """
        **Validates: Requirements 2.7**

        Entries where translated_words contains non-string elements (integers,
        floats, null, booleans, lists) must cause parse_translation_response
        to return None.
        """
        original_transcript = make_original_transcript(1)
        raw_text = json.dumps([entry])
        result = parse_translation_response(raw_text, original_transcript, job_id="test")
        assert result is None, (
            f"Expected None for non-string words: {raw_text!r}, got {result}"
        )

    @given(
        n=st.integers(min_value=1, max_value=10),
        mismatch_delta=st.integers(min_value=1, max_value=5),
    )
    @settings(max_examples=30)
    def test_length_mismatch_returns_none(self, n, mismatch_delta):
        """
        **Validates: Requirements 2.7**

        When the response array length does not match the original transcript
        length, parse_translation_response must return None.
        """
        original_transcript = make_original_transcript(n)
        # Create a response with wrong length (n + delta entries)
        response_data = [
            {"original_index": i, "translated_words": ["word"]}
            for i in range(n + mismatch_delta)
        ]
        raw_text = json.dumps(response_data)
        result = parse_translation_response(raw_text, original_transcript, job_id="test")
        assert result is None, (
            f"Expected None for length mismatch (transcript={n}, response={n + mismatch_delta}): "
            f"got {result}"
        )
