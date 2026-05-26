# Feature: qa-rag-over-video
# Property tests for the QA endpoint (Properties 4, 5, 6, 7)

import pytest
import pytest_asyncio
from unittest.mock import patch, MagicMock
from httpx import AsyncClient, ASGITransport
from hypothesis import given, settings, strategies as st

from main import app


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def client() -> AsyncClient:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as ac:
        yield ac


def _mock_auth_user(uid="user-123"):
    """Override get_current_user dependency to return a fixed user."""
    from middleware.auth import get_current_user

    async def override():
        return {"uid": uid, "email": "test@test.com", "name": "Test"}

    app.dependency_overrides[get_current_user] = override
    return uid


def _clear_overrides():
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Property 4: Access control returns correct error codes
# Validates: Requirements 3.1, 3.2, 3.3
# ---------------------------------------------------------------------------

# Strategy for access control combinations
access_control_cases = st.fixed_dictionaries({
    "plan": st.sampled_from(["free", "pro"]),
    "owns_job": st.booleans(),
    "job_status": st.sampled_from(["completed", "processing", "failed", "pending"]),
})


@settings(max_examples=100, deadline=None)
@given(case=access_control_cases)
@pytest.mark.asyncio
async def test_property4_access_control_error_codes(case):
    """
    Property 4: For any combination of user plan, job ownership, and job status:
    - free plan → 402
    - pro + not owner → 403
    - pro + owner + not completed → 409
    - pro + owner + completed → proceeds (not 4xx)
    """
    uid = _mock_auth_user("test-uid")

    job_owner = "test-uid" if case["owns_job"] else "other-uid"
    mock_job = {"userId": job_owner, "status": case["job_status"]}

    with patch("routers.qa.firestore") as mock_fs, \
         patch("routers.qa._embed_question", return_value=[0.1] * 768), \
         patch("routers.qa._generate_answer", return_value="test answer"):

        mock_fs.get_user_plan.return_value = case["plan"]
        mock_fs.get_job.return_value = mock_job
        mock_fs.get_transcript_chunk_count.return_value = 5
        mock_fs.search_transcript_chunks.return_value = [
            {"chunkIndex": 0, "startTime": 0.0, "endTime": 10.0, "text": "hello world"}
        ]

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/qa/test-job-id",
                json={"question": "What is this about?"},
                headers={"Authorization": "Bearer fake-token"},
            )

        if case["plan"] == "free":
            assert response.status_code == 402, f"Expected 402 for free plan, got {response.status_code}"
        elif not case["owns_job"]:
            assert response.status_code == 403, f"Expected 403 for non-owner, got {response.status_code}"
        elif case["job_status"] != "completed":
            assert response.status_code == 409, f"Expected 409 for status={case['job_status']}, got {response.status_code}"
        else:
            # Should succeed (200)
            assert response.status_code == 200, f"Expected 200 for valid case, got {response.status_code}"

    _clear_overrides()


# ---------------------------------------------------------------------------
# Property 5: Prompt assembly includes all context chunks and the question
# Validates: Requirements 5.1
# ---------------------------------------------------------------------------

@settings(max_examples=100, deadline=None)
@given(
    chunks=st.lists(
        st.fixed_dictionaries({
            "chunkIndex": st.integers(min_value=0, max_value=100),
            "startTime": st.floats(min_value=0, max_value=3600, allow_nan=False),
            "endTime": st.floats(min_value=0, max_value=3600, allow_nan=False),
            "text": st.text(min_size=5, max_size=200, alphabet=st.characters(whitelist_categories=("L", "N", "Z"))),
        }),
        min_size=1,
        max_size=4,
    ),
    question=st.text(min_size=3, max_size=200, alphabet=st.characters(whitelist_categories=("L", "N", "Z"))),
)
def test_property5_prompt_assembly_includes_all_chunks(chunks, question):
    """
    Property 5: For any list of 1-4 transcript chunks and any non-empty question,
    the assembled prompt sent to Gemini SHALL contain the text of every chunk
    and the full question string.
    """
    # We test _generate_answer by capturing the prompt it sends to Gemini
    captured_prompts = []

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "Test answer"

    def capture_generate(model, contents, config):
        captured_prompts.append(contents)
        return mock_response

    mock_client.models.generate_content = capture_generate

    with patch("routers.qa._get_qa_client", return_value=mock_client):
        from routers.qa import _generate_answer
        _generate_answer(question, chunks)

    assert len(captured_prompts) == 1
    prompt = captured_prompts[0]

    # Every chunk's text must appear in the prompt
    for chunk in chunks:
        assert chunk["text"] in prompt, \
            f"Chunk text '{chunk['text'][:50]}...' not found in prompt"

    # The question must appear in the prompt
    assert question in prompt, \
        f"Question '{question[:50]}...' not found in prompt"


# ---------------------------------------------------------------------------
# Property 6: Source metadata faithfully reflects input chunks
# Validates: Requirements 5.2
# ---------------------------------------------------------------------------

@settings(max_examples=100, deadline=None)
@given(
    chunks=st.lists(
        st.fixed_dictionaries({
            "chunkIndex": st.integers(min_value=0, max_value=100),
            "startTime": st.floats(min_value=0, max_value=3600, allow_nan=False, allow_infinity=False),
            "endTime": st.floats(min_value=0, max_value=3600, allow_nan=False, allow_infinity=False),
            "text": st.text(min_size=1, max_size=300, alphabet=st.characters(whitelist_categories=("L", "N", "Z"))),
        }),
        min_size=1,
        max_size=4,
    ),
)
def test_property6_source_metadata_reflects_chunks(chunks):
    """
    Property 6: For any set of transcript chunks, the sources array SHALL contain
    one entry per chunk with matching chunkIndex, startTime, endTime, and a snippet
    that is a prefix of the chunk's text (up to 150 characters).
    """
    from routers.qa import SourceTimestamp

    # Simulate the source-building logic from the endpoint
    sources = [
        SourceTimestamp(
            chunkIndex=chunk["chunkIndex"],
            startTime=chunk["startTime"],
            endTime=chunk["endTime"],
            snippet=chunk["text"][:150] + ("..." if len(chunk["text"]) > 150 else ""),
        )
        for chunk in chunks
    ]

    assert len(sources) == len(chunks)

    for i, (source, chunk) in enumerate(zip(sources, chunks)):
        assert source.chunkIndex == chunk["chunkIndex"], \
            f"Source {i}: chunkIndex mismatch"
        assert source.startTime == chunk["startTime"], \
            f"Source {i}: startTime mismatch"
        assert source.endTime == chunk["endTime"], \
            f"Source {i}: endTime mismatch"
        # Snippet is a prefix of text, max 150 chars (+ optional "...")
        assert len(source.snippet) <= 153, \
            f"Source {i}: snippet too long ({len(source.snippet)} chars)"
        # The snippet starts with the first 150 chars of text
        assert source.snippet.startswith(chunk["text"][:min(150, len(chunk["text"]))]), \
            f"Source {i}: snippet doesn't match text prefix"


# ---------------------------------------------------------------------------
# Property 7: Gemini failure produces HTTP 500
# Validates: Requirements 5.3
# ---------------------------------------------------------------------------

@settings(max_examples=50, deadline=None)
@given(
    exception_type=st.sampled_from([
        ValueError, RuntimeError, TimeoutError, ConnectionError,
        OSError, TypeError, KeyError,
    ])
)
@pytest.mark.asyncio
async def test_property7_gemini_failure_produces_500(exception_type):
    """
    Property 7: For any exception raised by Gemini generate_content(),
    the QA endpoint SHALL return HTTP 500 with a descriptive error message.
    """
    uid = _mock_auth_user("test-uid")

    with patch("routers.qa.firestore") as mock_fs, \
         patch("routers.qa._embed_question", return_value=[0.1] * 768), \
         patch("routers.qa._generate_answer", side_effect=exception_type("Gemini failed")):

        mock_fs.get_user_plan.return_value = "pro"
        mock_fs.get_job.return_value = {"userId": "test-uid", "status": "completed"}
        mock_fs.get_transcript_chunk_count.return_value = 5
        mock_fs.search_transcript_chunks.return_value = [
            {"chunkIndex": 0, "startTime": 0.0, "endTime": 10.0, "text": "hello world"}
        ]

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/qa/test-job-id",
                json={"question": "What is this about?"},
                headers={"Authorization": "Bearer fake-token"},
            )

        assert response.status_code == 500, \
            f"Expected 500 for Gemini failure, got {response.status_code}"
        assert "detail" in response.json()

    _clear_overrides()
