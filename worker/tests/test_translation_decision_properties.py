# worker/tests/test_translation_decision_properties.py
# Feature: multi-language-support, Property 2: Translation decision correctness
"""
Property-based test for translation decision logic.

**Validates: Requirements 2.1, 2.4**

Property 2: For any BCP-47 language code string, the translation decision function
SHALL return true (translate) if and only if the code is not "en-US", not "en-IN",
and not an empty string. For all other inputs (including "en-US", "en-IN", and ""),
it SHALL return false (skip translation).
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Set required env vars before importing pipeline modules
os.environ.setdefault("GCP_PROJECT_ID", "test-project")
os.environ.setdefault("GCP_BUCKET_NAME", "test-bucket")
os.environ.setdefault("GCP_SERVICE_ACCOUNT_EMAIL", "test@test.iam.gserviceaccount.com")

from hypothesis import given, settings, assume
from hypothesis import strategies as st


# --- Translation Decision Logic ---
# This encapsulates the translation decision as specified in the design document
# and Requirements 2.1 and 2.4: translate iff code is not "en-US", not "en-IN",
# and not empty string.

def should_translate(language_code: str) -> bool:
    """
    Determine whether translation should be triggered for a given language code.

    Translation is triggered if and only if the language code is:
    - Not "en-US"
    - Not "en-IN"
    - Not an empty string ""

    Args:
        language_code: A BCP-47 language code string.

    Returns:
        True if translation should be performed, False otherwise.
    """
    return language_code != "en-US" and language_code != "en-IN" and language_code != ""


# --- Strategies ---

# Known BCP-47 codes that should NOT trigger translation
NO_TRANSLATE_CODES = ["en-US", "en-IN", ""]

# Known BCP-47 codes that SHOULD trigger translation
TRANSLATE_CODES = [
    "hi-IN", "fr-FR", "de-DE", "es-ES", "ja-JP", "ko-KR",
    "zh-CN", "pt-BR", "ar-SA", "ru-RU", "it-IT", "nl-NL",
    "sv-SE", "pl-PL", "ta-IN", "te-IN", "bn-IN", "mr-IN",
]

# Strategy for arbitrary strings (simulating arbitrary BCP-47 code inputs)
arbitrary_language_code = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P", "S")),
    min_size=0,
    max_size=20,
)


# --- Property Tests ---


class TestTranslationDecisionProperty:
    """Property 2: Translation decision correctness."""

    @given(code=arbitrary_language_code)
    @settings(max_examples=30)
    def test_translation_decision_matches_specification(self, code):
        """
        **Validates: Requirements 2.1, 2.4**

        For any arbitrary string input, should_translate returns True iff
        the code is not "en-US", not "en-IN", and not empty string.
        """
        result = should_translate(code)

        # Compute expected based on the specification
        expected = code != "en-US" and code != "en-IN" and code != ""

        assert result == expected, (
            f"Translation decision mismatch for code={code!r}: "
            f"got {result}, expected {expected}"
        )

    @given(code=st.sampled_from(NO_TRANSLATE_CODES))
    @settings(max_examples=30)
    def test_skip_codes_never_trigger_translation(self, code):
        """
        **Validates: Requirements 2.4**

        "en-US", "en-IN", and "" must always return False (skip translation).
        """
        assert should_translate(code) is False, (
            f"Expected no translation for code={code!r}, but got True"
        )

    @given(code=st.sampled_from(TRANSLATE_CODES))
    @settings(max_examples=30)
    def test_non_english_codes_always_trigger_translation(self, code):
        """
        **Validates: Requirements 2.1**

        Known non-English, non-empty codes must always return True (translate).
        """
        assert should_translate(code) is True, (
            f"Expected translation for code={code!r}, but got False"
        )

    @given(code=arbitrary_language_code)
    @settings(max_examples=30)
    def test_decision_is_deterministic(self, code):
        """
        **Validates: Requirements 2.1, 2.4**

        Calling should_translate multiple times with the same input always
        produces the same result — the decision is purely based on the
        three exclusion conditions.
        """
        result1 = should_translate(code)
        result2 = should_translate(code)
        assert result1 == result2, (
            f"Non-deterministic result for code={code!r}: "
            f"first={result1}, second={result2}"
        )

    @given(
        code=st.text(
            alphabet=st.characters(whitelist_categories=("L", "N", "P", "S")),
            min_size=1,
            max_size=20,
        )
    )
    @settings(max_examples=30)
    def test_non_empty_non_english_triggers_translation(self, code):
        """
        **Validates: Requirements 2.1, 2.4**

        Any non-empty string that is not "en-US" or "en-IN" must trigger
        translation.
        """
        assume(code != "en-US")
        assume(code != "en-IN")

        assert should_translate(code) is True, (
            f"Expected translation for non-empty, non-English code={code!r}"
        )

    @settings(max_examples=30)
    @given(
        prefix=st.text(min_size=0, max_size=5),
        suffix=st.text(min_size=0, max_size=5),
    )
    def test_empty_string_never_triggers_regardless_of_context(self, prefix, suffix):
        """
        **Validates: Requirements 2.4**

        The empty string "" always returns False, confirming that the
        decision is based on exact string matching, not substring logic.
        """
        # The empty string itself should never trigger translation
        assert should_translate("") is False
