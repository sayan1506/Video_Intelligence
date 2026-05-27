# worker/tests/test_language_extraction_properties.py
# Feature: multi-language-support, Property 1: Language extraction returns first valid code
"""
Property-based test for extract_language_from_response().

**Validates: Requirements 1.1, 1.3**

Property 1: For any STT response containing a list of recognition results with
alternatives, where each alternative may have a language_code that is null, empty,
or a valid BCP-47 string, extract_language_from_response() SHALL return the
language_code from the first alternative (in response order) whose language_code
is neither null nor empty. If no such alternative exists, it SHALL return an
empty string.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Set required env vars before importing pipeline modules
os.environ.setdefault("GCP_PROJECT_ID", "test-project")
os.environ.setdefault("GCP_BUCKET_NAME", "test-bucket")
os.environ.setdefault("GCP_SERVICE_ACCOUNT_EMAIL", "test@test.iam.gserviceaccount.com")

from unittest.mock import MagicMock
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from pipeline.speech_to_text import extract_language_from_response


# --- Strategies ---

# Valid BCP-47 language codes (subset representative of real codes)
VALID_BCP47_CODES = [
    "hi-IN", "en-IN", "en-US", "fr-FR", "de-DE", "es-ES",
    "ja-JP", "ko-KR", "zh-CN", "pt-BR", "ar-SA", "ru-RU",
    "it-IT", "nl-NL", "sv-SE", "pl-PL", "ta-IN", "te-IN",
]

valid_language_code = st.sampled_from(VALID_BCP47_CODES)

# A language_code value that is "invalid" (null or empty) — should be skipped
invalid_language_code = st.sampled_from([None, ""])

# Any language_code value: either valid or invalid
any_language_code = st.one_of(valid_language_code, invalid_language_code)


def _build_mock_alternative(language_code):
    """Build a mock SpeechRecognitionAlternative with a given language_code."""
    alt = MagicMock()
    alt.language_code = language_code
    return alt


def _build_mock_result(alternatives):
    """Build a mock SpeechRecognitionResult with a list of alternatives."""
    result = MagicMock()
    result.alternatives = alternatives
    return result


def _build_mock_batch_results(results_list):
    """Build a mock BatchRecognizeResults with a list of results."""
    batch = MagicMock()
    batch.results = results_list
    return batch


# --- Property Tests ---


class TestLanguageExtractionProperty:
    """Property 1: Language extraction returns first valid code."""

    @given(
        language_codes=st.lists(any_language_code, min_size=1, max_size=10),
    )
    @settings(max_examples=30)
    def test_returns_first_valid_code_single_alternative_per_result(self, language_codes):
        """
        **Validates: Requirements 1.1, 1.3**

        Given a list of results each with one alternative, the function returns
        the first non-null, non-empty language_code. If none exist, returns "".
        """
        # Build mock: each result has one alternative with the given language_code
        results = [
            _build_mock_result([_build_mock_alternative(code)])
            for code in language_codes
        ]
        batch = _build_mock_batch_results(results)

        actual = extract_language_from_response(batch)

        # Compute expected: first valid code in order
        expected = ""
        for code in language_codes:
            if code is not None and code != "":
                expected = code
                break

        assert actual == expected

    @given(
        codes_per_result=st.lists(
            st.lists(any_language_code, min_size=1, max_size=4),
            min_size=1,
            max_size=5,
        ),
    )
    @settings(max_examples=30)
    def test_returns_first_valid_code_multiple_alternatives_per_result(self, codes_per_result):
        """
        **Validates: Requirements 1.1, 1.3**

        Given results with multiple alternatives each, the function iterates
        through all alternatives in order and returns the first valid code.
        """
        # Build mock: each result has multiple alternatives
        results = []
        for alt_codes in codes_per_result:
            alternatives = [_build_mock_alternative(code) for code in alt_codes]
            results.append(_build_mock_result(alternatives))

        batch = _build_mock_batch_results(results)

        actual = extract_language_from_response(batch)

        # Compute expected: flatten all codes in order, find first valid
        expected = ""
        for alt_codes in codes_per_result:
            for code in alt_codes:
                if code is not None and code != "":
                    expected = code
                    break
            if expected:
                break

        assert actual == expected

    @given(
        num_results=st.integers(min_value=0, max_value=5),
    )
    @settings(max_examples=30)
    def test_all_invalid_codes_returns_empty_string(self, num_results):
        """
        **Validates: Requirements 1.3**

        When all language_codes are null or empty, returns empty string.
        """
        # Build results where every alternative has None or "" as language_code
        results = []
        for _ in range(num_results):
            # Mix of None and "" alternatives
            alternatives = [
                _build_mock_alternative(None),
                _build_mock_alternative(""),
            ]
            results.append(_build_mock_result(alternatives))

        batch = _build_mock_batch_results(results)

        actual = extract_language_from_response(batch)
        assert actual == ""

    @settings(max_examples=30)
    @given(
        prefix_codes=st.lists(invalid_language_code, min_size=0, max_size=5),
        first_valid=valid_language_code,
        suffix_codes=st.lists(any_language_code, min_size=0, max_size=5),
    )
    def test_skips_invalid_returns_first_valid(self, prefix_codes, first_valid, suffix_codes):
        """
        **Validates: Requirements 1.1, 1.3**

        The function skips over invalid codes and returns the first valid one,
        regardless of what follows.
        """
        all_codes = prefix_codes + [first_valid] + suffix_codes

        results = [
            _build_mock_result([_build_mock_alternative(code)])
            for code in all_codes
        ]
        batch = _build_mock_batch_results(results)

        actual = extract_language_from_response(batch)
        assert actual == first_valid

    def test_empty_results_returns_empty_string(self):
        """
        **Validates: Requirements 1.3**

        When the response has no results at all, returns empty string.
        """
        batch = _build_mock_batch_results([])
        actual = extract_language_from_response(batch)
        assert actual == ""

    @given(
        num_empty_results=st.integers(min_value=1, max_value=5),
    )
    @settings(max_examples=30)
    def test_results_with_no_alternatives_returns_empty_string(self, num_empty_results):
        """
        **Validates: Requirements 1.3**

        When results exist but have no alternatives, returns empty string.
        """
        results = [_build_mock_result([]) for _ in range(num_empty_results)]
        batch = _build_mock_batch_results(results)

        actual = extract_language_from_response(batch)
        assert actual == ""
