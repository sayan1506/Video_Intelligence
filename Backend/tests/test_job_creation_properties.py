# Feature: public-share-links
# Property 5: Job creation always defaults isPublic to false

import pytest
from unittest.mock import patch, MagicMock
from hypothesis import given, settings, strategies as st


# ---------------------------------------------------------------------------
# Strategies for valid job creation parameters
# ---------------------------------------------------------------------------

# UUIDs as job IDs
job_id_strategy = st.uuids().map(str)

# Filenames: non-empty strings with common video extensions
filename_strategy = st.text(
    min_size=1,
    max_size=100,
    alphabet=st.characters(whitelist_categories=("L", "N", "P")),
).map(lambda s: s.strip() or "video").map(lambda s: f"{s}.mp4")

# GCS paths
gcs_path_strategy = st.text(
    min_size=1,
    max_size=200,
    alphabet=st.characters(whitelist_categories=("L", "N", "P", "Z")),
).map(lambda s: f"uploads/{s.strip() or 'file'}.mp4")

# User IDs (Firebase UIDs are typically alphanumeric strings)
user_id_strategy = st.text(
    min_size=0,
    max_size=128,
    alphabet=st.characters(whitelist_categories=("L", "N")),
)

# User emails
user_email_strategy = st.from_regex(
    r"[a-z]{1,20}@[a-z]{1,10}\.[a-z]{2,4}", fullmatch=True
) | st.just("")


# ---------------------------------------------------------------------------
# Property 5: Job creation always defaults isPublic to false
# Validates: Requirements 7.1
# ---------------------------------------------------------------------------

@settings(max_examples=100, deadline=None)
@given(
    job_id=job_id_strategy,
    filename=filename_strategy,
    gcs_path=gcs_path_strategy,
    user_id=user_id_strategy,
    user_email=user_email_strategy,
)
def test_property5_job_creation_defaults_is_public_to_false(
    job_id, filename, gcs_path, user_id, user_email
):
    """
    Property 5: Job creation always defaults isPublic to false

    For any valid combination of job creation parameters (job_id, filename,
    gcs_path, user_id, user_email), the resulting Firestore document SHALL
    have isPublic set to false.

    **Validates: Requirements 7.1**
    """
    # Capture the data written to Firestore
    mock_doc = MagicMock()
    mock_collection = MagicMock()
    mock_collection.document.return_value = mock_doc
    mock_db = MagicMock()
    mock_db.collection.return_value = mock_collection

    with patch("services.firestore.get_db", return_value=mock_db):
        from services.firestore import create_job

        result = create_job(
            job_id=job_id,
            filename=filename,
            gcs_path=gcs_path,
            user_id=user_id,
            user_email=user_email,
        )

    # Verify create_job returns the job_id
    assert result == job_id

    # Verify Firestore document was written
    mock_db.collection.assert_called_once_with("jobs")
    mock_collection.document.assert_called_once_with(job_id)
    mock_doc.set.assert_called_once()

    # Extract the document data that was written
    written_data = mock_doc.set.call_args[0][0]

    # The core property: isPublic MUST always be False
    assert "isPublic" in written_data, \
        f"isPublic field missing from job document for job_id={job_id}"
    assert written_data["isPublic"] is False, \
        f"isPublic should be False but got {written_data['isPublic']} for job_id={job_id}"
