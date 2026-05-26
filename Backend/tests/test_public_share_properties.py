# Feature: public-share-links
# Property tests for Public Share Links (Property 6)

from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

from hypothesis import given, settings, strategies as st

from services.firestore import set_job_public


# ---------------------------------------------------------------------------
# Property 6: set_job_public round-trip preserves the boolean value
# Validates: Requirements 7.2
# ---------------------------------------------------------------------------

@settings(max_examples=100, deadline=None)
@given(
    job_id=st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=("L", "N", "Pd"))),
    is_public=st.booleans(),
)
def test_property6_set_job_public_round_trip(job_id, is_public):
    """
    Property 6: set_job_public round-trip preserves the boolean value

    For any existing job document and for any boolean value b,
    calling set_job_public(job_id, b) SHALL update the Firestore document
    with isPublic == b and an updatedAt timestamp that is a valid UTC datetime.

    Validates: Requirements 7.2
    """
    mock_doc_ref = MagicMock()
    mock_collection = MagicMock()
    mock_collection.document.return_value = mock_doc_ref
    mock_db = MagicMock()
    mock_db.collection.return_value = mock_collection

    with patch("services.firestore.get_db", return_value=mock_db):
        set_job_public(job_id, is_public)

    # Verify Firestore was called with the correct collection and document
    mock_db.collection.assert_called_once_with("jobs")
    mock_collection.document.assert_called_once_with(job_id)

    # Verify update was called exactly once
    mock_doc_ref.update.assert_called_once()

    # Extract the update payload
    update_payload = mock_doc_ref.update.call_args[0][0]

    # The isPublic value in the update must match the input boolean exactly
    assert "isPublic" in update_payload, "Update payload must contain 'isPublic' field"
    assert update_payload["isPublic"] is is_public, (
        f"Expected isPublic={is_public}, got {update_payload['isPublic']}"
    )

    # The updatedAt field must be a valid UTC datetime
    assert "updatedAt" in update_payload, "Update payload must contain 'updatedAt' field"
    updated_at = update_payload["updatedAt"]
    assert isinstance(updated_at, datetime), (
        f"updatedAt must be a datetime, got {type(updated_at)}"
    )
    assert updated_at.tzinfo is not None, "updatedAt must be timezone-aware"
    assert updated_at.tzinfo == timezone.utc, "updatedAt must be in UTC"
