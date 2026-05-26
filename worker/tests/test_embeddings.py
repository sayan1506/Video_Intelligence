# Feature: qa-rag-over-video
# Property tests for the embedding pipeline (Properties 1, 2, 3)

import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
import pytest
from hypothesis import given, settings, strategies as st


# ---------------------------------------------------------------------------
# Property 1: Embedding pipeline processes all chunks
# Validates: Requirements 1.1, 1.2
# ---------------------------------------------------------------------------

def _make_fake_chunk(index: int, word_count: int = 5):
    """Create a fake transcript chunk document."""
    return {
        "chunkIndex": index,
        "words": [{"word": f"word{j}", "startTime": j * 0.5, "endTime": (j + 1) * 0.5, "speaker": 1} for j in range(word_count)],
        "wordCount": word_count,
    }


def _make_fake_embedding_response():
    """Create a mock embedding response with 768-dim vector."""
    mock_response = MagicMock()
    mock_embedding = MagicMock()
    mock_embedding.values = [0.01] * 768
    mock_response.embeddings = [mock_embedding]
    return mock_response


@settings(max_examples=100, deadline=None)
@given(chunk_count=st.integers(min_value=1, max_value=50))
def test_property1_embedding_processes_all_chunks(chunk_count):
    """
    Property 1: For any job with N transcript chunks (1 <= N <= 50),
    embed_transcript_chunks should attempt to write an embedding for each chunk.
    """
    written_chunks = []

    def mock_get_chunk(job_id, idx):
        return _make_fake_chunk(idx)

    def mock_write_embedding(job_id, idx, vector):
        written_chunks.append(idx)

    with patch("pipeline.embeddings.firestore") as mock_fs, \
         patch("pipeline.embeddings.get_embedding_client") as mock_client_fn:

        mock_fs.get_transcript_chunk = mock_get_chunk
        mock_fs.write_chunk_embedding = mock_write_embedding

        mock_client = MagicMock()
        mock_client.models.embed_content.return_value = _make_fake_embedding_response()
        mock_client_fn.return_value = mock_client

        from pipeline.embeddings import embed_transcript_chunks

        written_chunks.clear()
        asyncio.run(embed_transcript_chunks("test-job", chunk_count))

        # All chunks should have been written
        assert sorted(written_chunks) == list(range(chunk_count)), \
            f"Expected chunks 0..{chunk_count-1}, got {sorted(written_chunks)}"


# ---------------------------------------------------------------------------
# Property 2: Embedding pipeline is non-fatal
# Validates: Requirements 1.3
# ---------------------------------------------------------------------------

@settings(max_examples=100, deadline=None)
@given(
    exception_type=st.sampled_from([
        ValueError, RuntimeError, TimeoutError, ConnectionError,
        OSError, TypeError, KeyError, AttributeError,
    ])
)
def test_property2_embedding_pipeline_is_non_fatal(exception_type):
    """
    Property 2: For any exception raised during embedding generation,
    embed_transcript_chunks SHALL catch the error and return without raising.
    """
    with patch("pipeline.embeddings.firestore") as mock_fs, \
         patch("pipeline.embeddings.get_embedding_client") as mock_client_fn:

        mock_fs.get_transcript_chunk.return_value = _make_fake_chunk(0)

        mock_client = MagicMock()
        mock_client.models.embed_content.side_effect = exception_type("simulated failure")
        mock_client_fn.return_value = mock_client

        from pipeline.embeddings import embed_transcript_chunks

        # Should NOT raise — non-fatal by design
        asyncio.run(embed_transcript_chunks("test-job", 3))


# ---------------------------------------------------------------------------
# Property 3: write_chunk_embedding preserves existing document fields
# Validates: Requirements 2.2, 2.3
# ---------------------------------------------------------------------------

@settings(max_examples=100, deadline=None)
@given(
    existing_fields=st.dictionaries(
        keys=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("L", "N"))),
        values=st.one_of(st.integers(), st.text(max_size=50), st.floats(allow_nan=False)),
        min_size=1,
        max_size=10,
    )
)
def test_property3_write_chunk_embedding_preserves_fields(existing_fields):
    """
    Property 3: For any existing transcript chunk document with arbitrary fields,
    calling write_chunk_embedding SHALL add the embedding field without removing
    or modifying any pre-existing fields.

    This test verifies the merge=True behavior by checking that set() is called
    with merge=True and only the embedding field.
    """
    mock_db = MagicMock()
    mock_doc_ref = MagicMock()
    mock_db.collection.return_value.document.return_value.collection.return_value.document.return_value = mock_doc_ref

    with patch("services.firestore.get_db", return_value=mock_db):
        from services.firestore import write_chunk_embedding

        test_vector = [0.1] * 768
        write_chunk_embedding("test-job", 0, test_vector)

        # Verify set() was called with merge=True and only the embedding field
        mock_doc_ref.set.assert_called_once_with(
            {"embedding": test_vector},
            merge=True,
        )
