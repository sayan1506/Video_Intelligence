# worker/tests/test_time_distribution_properties.py
# Feature: multi-language-support, Property 3: Time distribution preserves timing invariants
"""
Property-based test for time distribution in parse_translation_response().

**Validates: Requirements 2.2, 2.3**

Property 3: For any valid source transcript (list of word entries with non-decreasing
startTimes where each entry has startTime < endTime) and for any valid word-count
mapping (each source entry maps to 1 or more translated words), the time distribution
algorithm SHALL produce a translated transcript where:
- Each group of translated words for source entry i collectively spans exactly
  [source[i].startTime, source[i].endTime]
- Each translated word within a group has equal duration ((endTime - startTime) / N)
- All translated words carry the same speaker value as their source entry
- The startTime values across the entire translated transcript are monotonically
  non-decreasing
"""

import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Set required env vars before importing pipeline modules
os.environ.setdefault("GCP_PROJECT_ID", "test-project")
os.environ.setdefault("GCP_BUCKET_NAME", "test-bucket")
os.environ.setdefault("GCP_SERVICE_ACCOUNT_EMAIL", "test@test.iam.gserviceaccount.com")

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from pipeline.gemini import parse_translation_response


# --- Strategies ---

# Strategy for generating a valid source transcript entry
# We build the transcript as a whole to ensure non-decreasing startTimes
@st.composite
def valid_source_transcript(draw):
    """
    Generate a valid source transcript with non-decreasing startTimes
    and startTime < endTime for each entry.

    Each entry has: word, startTime, endTime, speaker.
    """
    num_entries = draw(st.integers(min_value=1, max_value=10))

    transcript = []
    current_time = draw(st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False))
    current_time = round(current_time, 3)

    for _ in range(num_entries):
        start_time = current_time
        # Duration must be positive (at least 0.001 to allow meaningful division)
        duration = draw(st.floats(min_value=0.01, max_value=10.0, allow_nan=False, allow_infinity=False))
        duration = round(duration, 3)
        end_time = round(start_time + duration, 3)

        speaker = draw(st.integers(min_value=0, max_value=5))
        word = draw(st.text(
            alphabet=st.characters(whitelist_categories=("L",)),
            min_size=1,
            max_size=10,
        ))

        transcript.append({
            "word": word,
            "startTime": start_time,
            "endTime": end_time,
            "speaker": speaker,
        })

        # Next entry starts at or after this entry's end time (non-decreasing)
        gap = draw(st.floats(min_value=0.0, max_value=2.0, allow_nan=False, allow_infinity=False))
        current_time = round(end_time + gap, 3)

    return transcript


@st.composite
def word_count_mapping(draw, num_entries):
    """
    Generate a word-count mapping: for each source entry, how many
    translated words it maps to (1 or more).
    """
    counts = []
    for _ in range(num_entries):
        count = draw(st.integers(min_value=1, max_value=5))
        counts.append(count)
    return counts


@st.composite
def valid_transcript_and_response(draw):
    """
    Generate a valid source transcript and a corresponding valid Gemini
    translation response JSON string.
    """
    transcript = draw(valid_source_transcript())
    num_entries = len(transcript)
    word_counts = draw(word_count_mapping(num_entries))

    # Build the Gemini response JSON
    response_data = []
    for i, count in enumerate(word_counts):
        words = []
        for j in range(count):
            word = draw(st.text(
                alphabet=st.characters(whitelist_categories=("L",)),
                min_size=1,
                max_size=10,
            ))
            words.append(word)
        response_data.append({
            "original_index": i,
            "translated_words": words,
        })

    raw_text = json.dumps(response_data)
    return transcript, raw_text, word_counts


# --- Property Tests ---


class TestTimeDistributionProperty:
    """Property 3: Time distribution preserves timing invariants."""

    @given(data=valid_transcript_and_response())
    @settings(max_examples=30)
    def test_each_group_spans_source_entry_time_range(self, data):
        """
        **Validates: Requirements 2.2, 2.3**

        Each group of translated words for source entry i collectively spans
        exactly [source[i].startTime, source[i].endTime].
        """
        transcript, raw_text, word_counts = data

        result = parse_translation_response(raw_text, transcript, job_id="test")
        assert result is not None, "parse_translation_response returned None for valid input"

        # Walk through the result, grouping by source entry
        idx = 0
        for i, source_entry in enumerate(transcript):
            n = word_counts[i]
            group = result[idx:idx + n]
            assert len(group) == n

            # First word in group starts at source entry's startTime
            expected_start = round(source_entry["startTime"], 3)
            assert group[0]["startTime"] == expected_start, (
                f"Group {i} first word startTime={group[0]['startTime']}, "
                f"expected {expected_start}"
            )

            # Last word in group ends at source entry's endTime
            expected_end = round(source_entry["endTime"], 3)
            assert group[-1]["endTime"] == expected_end, (
                f"Group {i} last word endTime={group[-1]['endTime']}, "
                f"expected {expected_end}"
            )

            idx += n

    @given(data=valid_transcript_and_response())
    @settings(max_examples=30)
    def test_equal_duration_per_word_within_group(self, data):
        """
        **Validates: Requirements 2.2, 2.3**

        Each translated word within a group has equal duration
        ((endTime - startTime) / N), rounded to 3 decimal places.
        """
        transcript, raw_text, word_counts = data

        result = parse_translation_response(raw_text, transcript, job_id="test")
        assert result is not None, "parse_translation_response returned None for valid input"

        idx = 0
        for i, source_entry in enumerate(transcript):
            n = word_counts[i]
            group = result[idx:idx + n]

            source_duration = source_entry["endTime"] - source_entry["startTime"]
            expected_word_duration = round(source_duration / n, 3)

            for j, word_entry in enumerate(group):
                actual_duration = round(word_entry["endTime"] - word_entry["startTime"], 3)
                # Allow tolerance for rounding at word boundaries.
                # The algorithm rounds each boundary independently to 3 decimal places,
                # and forces the last word's endTime to match the source endTime exactly.
                # This can cause up to 0.001 rounding difference per boundary, so
                # individual word durations may differ by up to 0.002 from the ideal.
                assert abs(actual_duration - expected_word_duration) <= 0.002, (
                    f"Group {i}, word {j}: duration={actual_duration}, "
                    f"expected={expected_word_duration}"
                )

            idx += n

    @given(data=valid_transcript_and_response())
    @settings(max_examples=30)
    def test_speaker_preserved_from_source_entry(self, data):
        """
        **Validates: Requirements 2.2, 2.3**

        All translated words carry the same speaker value as their source entry.
        """
        transcript, raw_text, word_counts = data

        result = parse_translation_response(raw_text, transcript, job_id="test")
        assert result is not None, "parse_translation_response returned None for valid input"

        idx = 0
        for i, source_entry in enumerate(transcript):
            n = word_counts[i]
            group = result[idx:idx + n]

            for j, word_entry in enumerate(group):
                assert word_entry["speaker"] == source_entry["speaker"], (
                    f"Group {i}, word {j}: speaker={word_entry['speaker']}, "
                    f"expected={source_entry['speaker']}"
                )

            idx += n

    @given(data=valid_transcript_and_response())
    @settings(max_examples=30)
    def test_monotonically_non_decreasing_start_times(self, data):
        """
        **Validates: Requirements 2.2, 2.3**

        The startTime values across the entire translated transcript are
        monotonically non-decreasing.
        """
        transcript, raw_text, word_counts = data

        result = parse_translation_response(raw_text, transcript, job_id="test")
        assert result is not None, "parse_translation_response returned None for valid input"

        for i in range(1, len(result)):
            assert result[i]["startTime"] >= result[i - 1]["startTime"], (
                f"startTime not non-decreasing at index {i}: "
                f"{result[i]['startTime']} < {result[i - 1]['startTime']}"
            )

    @given(data=valid_transcript_and_response())
    @settings(max_examples=30)
    def test_total_output_count_matches_word_counts(self, data):
        """
        **Validates: Requirements 2.2, 2.3**

        The total number of entries in the translated transcript equals
        the sum of all word counts from the mapping.
        """
        transcript, raw_text, word_counts = data

        result = parse_translation_response(raw_text, transcript, job_id="test")
        assert result is not None, "parse_translation_response returned None for valid input"

        expected_total = sum(word_counts)
        assert len(result) == expected_total, (
            f"Total output entries={len(result)}, expected={expected_total}"
        )
