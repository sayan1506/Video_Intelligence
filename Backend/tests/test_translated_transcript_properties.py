# Feature: multi-language-support, Property 5: Valid translated transcript round-trip parsing

import pytest
from hypothesis import given, settings, strategies as st

from models.schemas import WordTimestamp


# ---------------------------------------------------------------------------
# Strategies for valid WordTimestamp data
# ---------------------------------------------------------------------------

# Non-empty word strings (printable characters, at least 1 char)
word_strategy = st.text(
    min_size=1,
    max_size=50,
    alphabet=st.characters(whitelist_categories=("L", "N", "P", "Z")),
).filter(lambda s: s.strip() != "")

# Non-negative floats for startTime (avoid infinity/nan)
start_time_strategy = st.floats(min_value=0.0, max_value=100000.0, allow_nan=False, allow_infinity=False)

# Non-negative integers for speaker
speaker_strategy = st.integers(min_value=0, max_value=100)


@st.composite
def word_timestamp_strategy(draw):
    """Generate a valid WordTimestamp dict with endTime >= startTime."""
    word = draw(word_strategy)
    start_time = draw(start_time_strategy)
    # endTime must be >= startTime
    end_time = draw(
        st.floats(min_value=start_time, max_value=start_time + 10000.0, allow_nan=False, allow_infinity=False)
    )
    speaker = draw(speaker_strategy)
    return {
        "word": word,
        "startTime": start_time,
        "endTime": end_time,
        "speaker": speaker,
    }


# Strategy for a list of valid WordTimestamp dicts
word_timestamp_list_strategy = st.lists(word_timestamp_strategy(), min_size=1, max_size=20)


# ---------------------------------------------------------------------------
# Property 5: Valid translated transcript round-trip parsing
# Validates: Requirements 4.5
# ---------------------------------------------------------------------------

@settings(max_examples=100, deadline=None)
@given(transcript_data=word_timestamp_list_strategy)
def test_property5_valid_translated_transcript_round_trip_parsing(transcript_data):
    """
    Property 5: Valid translated transcript round-trip parsing

    For any valid list of WordTimestamp objects (each with word as non-empty
    string, startTime as non-negative float, endTime as float >= startTime,
    and speaker as non-negative integer), serializing to the Firestore array
    format and parsing back via the Backend API's WordTimestamp model SHALL
    produce an equivalent list of objects with all fields preserved.

    **Validates: Requirements 4.5**
    """
    # Step 1: Serialize to Firestore format (list of dicts)
    firestore_format = []
    for entry in transcript_data:
        firestore_format.append({
            "word": entry["word"],
            "startTime": entry["startTime"],
            "endTime": entry["endTime"],
            "speaker": entry["speaker"],
        })

    # Step 2: Parse back via WordTimestamp model
    parsed_transcript = [WordTimestamp(**item) for item in firestore_format]

    # Step 3: Assert all fields are preserved
    assert len(parsed_transcript) == len(transcript_data)

    for original, parsed in zip(transcript_data, parsed_transcript):
        assert parsed.word == original["word"], (
            f"Word mismatch: expected {original['word']!r}, got {parsed.word!r}"
        )
        assert parsed.startTime == original["startTime"], (
            f"startTime mismatch: expected {original['startTime']}, got {parsed.startTime}"
        )
        assert parsed.endTime == original["endTime"], (
            f"endTime mismatch: expected {original['endTime']}, got {parsed.endTime}"
        )
        assert parsed.speaker == original["speaker"], (
            f"speaker mismatch: expected {original['speaker']}, got {parsed.speaker}"
        )
