# Feature: public-share-links
# Property 6: set_job_public round-trip preserves the boolean value

import pytest
from unittest.mock import patch, MagicMock
from hypothesis import given, settings, strategies as st


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Job IDs (UUIDs as strings)
job_id_strategy = st.uuids().map(str)

# Boolean values for isPublic
is_public_strategy = st.booleans()


# ---------------------------------------------------------------------------
# Property 6: set_job_public round-trip preserves the boolean value
# Validates: Requirements 7.2
# ---------------------------------------------------------------------------

@settings(max_examples=100, deadline=None)
@given(
    job_id=job_id_strategy,
    is_public=is_public_strategy,
)
def test_property6_set_job_public_round_trip_preserves_boolean(job_id, is_public):
    """
    Property 6: set_job_public round-trip preserves the boolean value

    For any existing job document and for any boolean value b, calling
    set_job_public(job_id, b) SHALL update the Firestore document with
    isPublic == b and an updatedAt timestamp.

    **Validates: Requirements 7.2**
    """
    # Mock the Firestore client
    mock_doc = MagicMock()
    mock_collection = MagicMock()
    mock_collection.document.return_value = mock_doc
    mock_db = MagicMock()
    mock_db.collection.return_value = mock_collection

    with patch("services.firestore.get_db", return_value=mock_db):
        from services.firestore import set_job_public

        set_job_public(job_id=job_id, is_public=is_public)

    # Verify Firestore was called with the correct collection and document
    mock_db.collection.assert_called_once_with("jobs")
    mock_collection.document.assert_called_once_with(job_id)
    mock_doc.update.assert_called_once()

    # Extract the update data passed to Firestore
    update_data = mock_doc.update.call_args[0][0]

    # Core property: isPublic field matches the input boolean exactly
    assert "isPublic" in update_data, \
        f"isPublic field missing from update for job_id={job_id}"
    assert update_data["isPublic"] is is_public, \
        f"isPublic should be {is_public} but got {update_data['isPublic']} for job_id={job_id}"

    # Core property: updatedAt timestamp is present and is a datetime
    assert "updatedAt" in update_data, \
        f"updatedAt field missing from update for job_id={job_id}"

    from datetime import datetime
    assert isinstance(update_data["updatedAt"], datetime), \
        f"updatedAt should be a datetime but got {type(update_data['updatedAt'])} for job_id={job_id}"
