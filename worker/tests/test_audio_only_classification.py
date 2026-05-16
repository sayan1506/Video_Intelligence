# worker/tests/test_audio_only_classification.py
"""
Property-based test: audio-only classification by MIME type.

**Validates: Requirements 1.1, 1.2, 3.2**

Property 1: Audio-only classification is determined solely by MIME type membership.
For any contentType string, the orchestrator classifies as audio-only if and only if
the contentType (normalized: lowercased, MIME params stripped) is in AUDIO_ONLY_MIME_TYPES.
"""

import os

# Set required env vars before importing pipeline modules
os.environ.setdefault("GCP_PROJECT_ID", "test-project")
os.environ.setdefault("GCP_BUCKET_NAME", "test-bucket")
os.environ.setdefault("GCP_SERVICE_ACCOUNT_EMAIL", "test@test.iam.gserviceaccount.com")

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from pipeline.orchestrator import _is_audio_only, AUDIO_ONLY_MIME_TYPES


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Strategy: pick a known audio MIME type from the set
known_audio_mime_types = st.sampled_from(sorted(AUDIO_ONLY_MIME_TYPES))

# Strategy: generate arbitrary MIME parameters (e.g., "; charset=utf-8")
mime_params = st.one_of(
    st.just(""),
    st.text(
        alphabet=st.characters(whitelist_categories=("L", "N", "P", "Z")),
        min_size=1,
        max_size=30,
    ).map(lambda s: f"; {s}"),
)

# Strategy: generate case variations of a string
def random_case(s: str) -> st.SearchStrategy[str]:
    """Generate random case variations of a given string."""
    return st.builds(
        lambda choices: "".join(
            c.upper() if choice else c.lower()
            for c, choice in zip(s, choices)
        ),
        st.lists(st.booleans(), min_size=len(s), max_size=len(s)),
    )


# Strategy: arbitrary strings that are NOT audio MIME types when normalized
arbitrary_strings = st.text(min_size=0, max_size=100)


# ---------------------------------------------------------------------------
# Property Tests
# ---------------------------------------------------------------------------


@given(mime_type=known_audio_mime_types, params=mime_params)
@settings(max_examples=200, deadline=None)
def test_known_audio_mime_types_classify_as_audio_only(mime_type: str, params: str):
    """
    **Validates: Requirements 1.1**

    For any known audio MIME type (with or without MIME parameters appended),
    _is_audio_only must return True.
    """
    content_type = mime_type + params
    assert _is_audio_only(content_type) is True, (
        f"Expected _is_audio_only({content_type!r}) to be True "
        f"(base MIME type: {mime_type!r})"
    )


@given(
    mime_type=known_audio_mime_types,
    params=mime_params,
    case_choices=st.lists(st.booleans(), min_size=1, max_size=100),
)
@settings(max_examples=200, deadline=None)
def test_case_insensitive_matching(
    mime_type: str, params: str, case_choices: list
):
    """
    **Validates: Requirements 1.1**

    For any known audio MIME type with arbitrary case variations,
    _is_audio_only must return True (case-insensitive matching).
    """
    # Apply random case to the MIME type portion
    case_varied = "".join(
        c.upper() if case_choices[i % len(case_choices)] else c.lower()
        for i, c in enumerate(mime_type)
    )
    content_type = case_varied + params
    assert _is_audio_only(content_type) is True, (
        f"Expected _is_audio_only({content_type!r}) to be True "
        f"(case variation of {mime_type!r})"
    )


@given(content_type=arbitrary_strings)
@settings(max_examples=200, deadline=None)
def test_arbitrary_strings_classify_correctly(content_type: str):
    """
    **Validates: Requirements 1.1, 1.2, 3.2**

    For any arbitrary contentType string, _is_audio_only returns True
    if and only if the normalized form (lowercased, params stripped)
    is in AUDIO_ONLY_MIME_TYPES.
    """
    # Compute expected result using the same normalization logic
    if not content_type:
        expected = False
    else:
        normalized = content_type.split(";")[0].strip().lower()
        expected = normalized in AUDIO_ONLY_MIME_TYPES

    result = _is_audio_only(content_type)
    assert result == expected, (
        f"_is_audio_only({content_type!r}) returned {result}, expected {expected}"
    )


@given(content_type=st.just(""))
@settings(max_examples=1, deadline=None)
def test_empty_string_returns_false(content_type: str):
    """
    **Validates: Requirements 1.2, 3.2**

    Empty contentType values must return False (treated as video).
    """
    assert _is_audio_only(content_type) is False


def test_none_returns_false():
    """
    **Validates: Requirements 1.2, 3.2**

    None/null contentType values must return False (treated as video).
    """
    assert _is_audio_only(None) is False
    assert _is_audio_only("") is False


@given(
    content_type=st.text(min_size=1, max_size=100).filter(
        lambda s: s.split(";")[0].strip().lower() not in AUDIO_ONLY_MIME_TYPES
    )
)
@settings(max_examples=200, deadline=None)
def test_non_audio_mime_types_classify_as_video(content_type: str):
    """
    **Validates: Requirements 1.2, 3.2**

    For any contentType whose normalized form is NOT in AUDIO_ONLY_MIME_TYPES,
    _is_audio_only must return False (treated as video).
    """
    assert _is_audio_only(content_type) is False, (
        f"Expected _is_audio_only({content_type!r}) to be False "
        f"(not in AUDIO_ONLY_MIME_TYPES)"
    )
