# worker/tests/test_firestore_language.py
"""
Integration tests for Firestore persistence of language and translation data.

Tests verify that:
- write_results() includes detectedLanguage in a single write (Req 3.1, 3.4)
- write_summary() includes translatedTranscript when available (Req 3.2)
- write_summary() omits translatedTranscript when None/empty (Req 3.3)
- Firestore write failure propagates exception (Req 3.5)
"""

import os

# Set required env vars before importing pipeline modules
os.environ.setdefault("GCP_PROJECT_ID", "test-project")
os.environ.setdefault("GCP_BUCKET_NAME", "test-bucket")

from unittest.mock import patch, MagicMock

import pytest

from services.firestore import write_results, write_summary


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_firestore_db():
    """Create a mock Firestore client with collection/document/set chain."""
    mock_db = MagicMock()
    mock_collection = MagicMock()
    mock_document = MagicMock()
    mock_subcollection = MagicMock()
    mock_subdocument = MagicMock()

    mock_db.collection.return_value = mock_collection
    mock_collection.document.return_value = mock_document
    mock_document.set.return_value = None
    # For transcript_chunks subcollection
    mock_document.collection.return_value = mock_subcollection
    mock_subcollection.document.return_value = mock_subdocument
    mock_subdocument.set.return_value = None

    return mock_db, mock_document


# ---------------------------------------------------------------------------
# Tests: write_results() includes detectedLanguage (Req 3.1, 3.4)
# ---------------------------------------------------------------------------


class TestWriteResultsDetectedLanguage:
    """Test that write_results() persists detectedLanguage in a single write."""

    @patch("services.firestore.get_db")
    def test_write_results_includes_detected_language_hindi(self, mock_get_db):
        """
        Req 3.1, 3.4: write_results() writes detectedLanguage as a string field
        in the results/{jobId} document alongside existing fields in a single write.
        """
        mock_db, mock_document = _mock_firestore_db()
        mock_get_db.return_value = mock_db

        transcript = [
            {"word": "namaste", "startTime": 0.0, "endTime": 0.5, "speaker": 1},
        ]
        scenes = [
            {"startTime": 0.0, "endTime": 5.0, "confidence": 0.9, "labels": ["greeting"]},
        ]

        write_results(
            job_id="job-123",
            transcript=transcript,
            scenes=scenes,
            detected_language="hi-IN",
        )

        # The parent document .set() should be called once (single write)
        mock_document.set.assert_called_once()
        written_data = mock_document.set.call_args[0][0]

        # Verify detectedLanguage is present and correct
        assert "detectedLanguage" in written_data
        assert written_data["detectedLanguage"] == "hi-IN"

        # Verify other fields are also present in the same write
        assert written_data["jobId"] == "job-123"
        assert written_data["scenes"] == scenes
        assert "transcriptChunkCount" in written_data
        assert "writtenAt" in written_data

    @patch("services.firestore.get_db")
    def test_write_results_includes_empty_detected_language(self, mock_get_db):
        """
        Req 3.1, 3.4: write_results() writes empty string as detectedLanguage
        when no language was detected (e.g., chunked path).
        """
        mock_db, mock_document = _mock_firestore_db()
        mock_get_db.return_value = mock_db

        transcript = [
            {"word": "hello", "startTime": 0.0, "endTime": 0.3, "speaker": 1},
        ]
        scenes = []

        write_results(
            job_id="job-456",
            transcript=transcript,
            scenes=scenes,
            detected_language="",
        )

        mock_document.set.assert_called_once()
        written_data = mock_document.set.call_args[0][0]

        assert "detectedLanguage" in written_data
        assert written_data["detectedLanguage"] == ""

    @patch("services.firestore.get_db")
    def test_write_results_default_detected_language_is_empty(self, mock_get_db):
        """
        Req 3.4: detected_language defaults to empty string when not provided,
        and is still written in the same Firestore operation.
        """
        mock_db, mock_document = _mock_firestore_db()
        mock_get_db.return_value = mock_db

        transcript = [
            {"word": "test", "startTime": 0.0, "endTime": 0.2, "speaker": 1},
        ]
        scenes = []

        write_results(
            job_id="job-789",
            transcript=transcript,
            scenes=scenes,
        )

        mock_document.set.assert_called_once()
        written_data = mock_document.set.call_args[0][0]

        assert "detectedLanguage" in written_data
        assert written_data["detectedLanguage"] == ""


# ---------------------------------------------------------------------------
# Tests: write_summary() includes translatedTranscript when available (Req 3.2)
# ---------------------------------------------------------------------------


class TestWriteSummaryTranslatedTranscript:
    """Test that write_summary() correctly handles translatedTranscript."""

    @patch("services.firestore.get_db")
    def test_write_summary_includes_translated_transcript(self, mock_get_db):
        """
        Req 3.2: When a translatedTranscript is available (non-None, non-empty),
        write_summary() writes it as a translatedTranscript field in summaries/{jobId}.
        """
        mock_db, mock_document = _mock_firestore_db()
        mock_get_db.return_value = mock_db

        summary_data = {
            "summary": "This is a test summary.",
            "chapters": [],
            "highlights": [],
            "sentiment": "neutral",
            "actionItems": [],
        }
        translated_transcript = [
            {"word": "Hello", "startTime": 0.0, "endTime": 0.3, "speaker": 1},
            {"word": "world", "startTime": 0.3, "endTime": 0.6, "speaker": 1},
        ]

        write_summary(
            job_id="job-123",
            summary_data=summary_data,
            translated_transcript=translated_transcript,
        )

        mock_document.set.assert_called_once()
        written_data = mock_document.set.call_args[0][0]

        # Verify translatedTranscript is present
        assert "translatedTranscript" in written_data
        assert written_data["translatedTranscript"] == translated_transcript

        # Verify other summary fields are also present
        assert written_data["jobId"] == "job-123"
        assert written_data["summary"] == "This is a test summary."
        assert "writtenAt" in written_data

    @patch("services.firestore.get_db")
    def test_write_summary_translated_transcript_preserves_structure(self, mock_get_db):
        """
        Req 3.2: translatedTranscript is stored as an array of objects each
        containing word, startTime, endTime, and speaker fields.
        """
        mock_db, mock_document = _mock_firestore_db()
        mock_get_db.return_value = mock_db

        summary_data = {"summary": "Test", "chapters": [], "highlights": [],
                        "sentiment": "neutral", "actionItems": []}
        translated_transcript = [
            {"word": "My", "startTime": 1.0, "endTime": 1.25, "speaker": 2},
            {"word": "name", "startTime": 1.25, "endTime": 1.5, "speaker": 2},
            {"word": "is", "startTime": 1.5, "endTime": 1.75, "speaker": 2},
            {"word": "Sayan", "startTime": 1.75, "endTime": 2.0, "speaker": 2},
        ]

        write_summary(
            job_id="job-struct",
            summary_data=summary_data,
            translated_transcript=translated_transcript,
        )

        mock_document.set.assert_called_once()
        written_data = mock_document.set.call_args[0][0]

        stored_transcript = written_data["translatedTranscript"]
        assert len(stored_transcript) == 4
        for entry in stored_transcript:
            assert "word" in entry
            assert "startTime" in entry
            assert "endTime" in entry
            assert "speaker" in entry


# ---------------------------------------------------------------------------
# Tests: write_summary() omits translatedTranscript when None/empty (Req 3.3)
# ---------------------------------------------------------------------------


class TestWriteSummaryOmitsTranslatedTranscript:
    """Test that write_summary() omits translatedTranscript when not available."""

    @patch("services.firestore.get_db")
    def test_write_summary_omits_translated_transcript_when_none(self, mock_get_db):
        """
        Req 3.3: When translated_transcript is None, the translatedTranscript
        field is omitted from the summaries/{jobId} document.
        """
        mock_db, mock_document = _mock_firestore_db()
        mock_get_db.return_value = mock_db

        summary_data = {
            "summary": "English video summary.",
            "chapters": [],
            "highlights": [],
            "sentiment": "positive",
            "actionItems": [],
        }

        write_summary(
            job_id="job-en",
            summary_data=summary_data,
            translated_transcript=None,
        )

        mock_document.set.assert_called_once()
        written_data = mock_document.set.call_args[0][0]

        # translatedTranscript should NOT be in the written data
        assert "translatedTranscript" not in written_data

        # Other fields should still be present
        assert written_data["jobId"] == "job-en"
        assert written_data["summary"] == "English video summary."

    @patch("services.firestore.get_db")
    def test_write_summary_omits_translated_transcript_when_empty_list(self, mock_get_db):
        """
        Req 3.3: When translated_transcript is an empty list, the
        translatedTranscript field is omitted from the document.
        """
        mock_db, mock_document = _mock_firestore_db()
        mock_get_db.return_value = mock_db

        summary_data = {
            "summary": "Summary without translation.",
            "chapters": [],
            "highlights": [],
            "sentiment": "neutral",
            "actionItems": [],
        }

        write_summary(
            job_id="job-empty",
            summary_data=summary_data,
            translated_transcript=[],
        )

        mock_document.set.assert_called_once()
        written_data = mock_document.set.call_args[0][0]

        # translatedTranscript should NOT be in the written data
        assert "translatedTranscript" not in written_data

    @patch("services.firestore.get_db")
    def test_write_summary_default_omits_translated_transcript(self, mock_get_db):
        """
        Req 3.3: When translated_transcript parameter is not provided (defaults
        to None), the translatedTranscript field is omitted.
        """
        mock_db, mock_document = _mock_firestore_db()
        mock_get_db.return_value = mock_db

        summary_data = {
            "summary": "Default call summary.",
            "chapters": [],
            "highlights": [],
            "sentiment": "neutral",
            "actionItems": [],
        }

        write_summary(
            job_id="job-default",
            summary_data=summary_data,
        )

        mock_document.set.assert_called_once()
        written_data = mock_document.set.call_args[0][0]

        assert "translatedTranscript" not in written_data


# ---------------------------------------------------------------------------
# Tests: Firestore write failure propagates exception (Req 3.5)
# ---------------------------------------------------------------------------


class TestFirestoreWriteFailurePropagation:
    """Test that Firestore write failures propagate without being silently discarded."""

    @patch("services.firestore.get_db")
    def test_write_results_propagates_firestore_exception(self, mock_get_db):
        """
        Req 3.5: If the Firestore write for detectedLanguage fails, the
        exception propagates to the orchestrator.
        """
        mock_db, mock_document = _mock_firestore_db()
        mock_get_db.return_value = mock_db

        # Make the parent document .set() raise an exception
        mock_document.set.side_effect = Exception("Firestore write failed: UNAVAILABLE")

        transcript = [
            {"word": "test", "startTime": 0.0, "endTime": 0.3, "speaker": 1},
        ]
        scenes = []

        with pytest.raises(Exception, match="Firestore write failed"):
            write_results(
                job_id="job-fail",
                transcript=transcript,
                scenes=scenes,
                detected_language="hi-IN",
            )

    @patch("services.firestore.get_db")
    def test_write_summary_propagates_firestore_exception(self, mock_get_db):
        """
        Req 3.5: If the Firestore write for translatedTranscript fails, the
        exception propagates to the orchestrator.
        """
        mock_db, mock_document = _mock_firestore_db()
        mock_get_db.return_value = mock_db

        # Make .set() raise an exception
        mock_document.set.side_effect = Exception("Firestore write failed: DEADLINE_EXCEEDED")

        summary_data = {
            "summary": "Test summary.",
            "chapters": [],
            "highlights": [],
            "sentiment": "neutral",
            "actionItems": [],
        }
        translated_transcript = [
            {"word": "Hello", "startTime": 0.0, "endTime": 0.5, "speaker": 1},
        ]

        with pytest.raises(Exception, match="Firestore write failed"):
            write_summary(
                job_id="job-fail-summary",
                summary_data=summary_data,
                translated_transcript=translated_transcript,
            )

    @patch("services.firestore.get_db")
    def test_write_results_does_not_catch_exceptions_silently(self, mock_get_db):
        """
        Req 3.5: Verify that write_results does not have a try/except that
        silently discards errors — the exception type is preserved.
        """
        mock_db, mock_document = _mock_firestore_db()
        mock_get_db.return_value = mock_db

        # Use a specific exception type to verify it's not caught and re-raised
        class CustomFirestoreError(Exception):
            pass

        mock_document.set.side_effect = CustomFirestoreError("Permission denied")

        transcript = [{"word": "x", "startTime": 0.0, "endTime": 0.1, "speaker": 1}]

        with pytest.raises(CustomFirestoreError, match="Permission denied"):
            write_results(
                job_id="job-custom-err",
                transcript=transcript,
                scenes=[],
                detected_language="hi-IN",
            )
