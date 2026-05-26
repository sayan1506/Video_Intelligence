# Backend/routers/qa.py
"""
Phase 4 — B1: Q&A over video via RAG.

POST /qa/{job_id}
  - Verifies Pro plan, job ownership, and completed status.
  - Embeds the user question via text-embedding-004.
  - Performs Firestore vector similarity search over transcript_chunks.
  - Assembles top-K chunks as context.
  - Calls Gemini 2.5 Flash with context + question.
  - Returns answer text + source timestamps.
"""

import os
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from middleware.auth import get_current_user
from services import firestore

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

router = APIRouter(tags=["qa"])

TOP_K = 4

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class QuestionRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000)


class SourceTimestamp(BaseModel):
    chunkIndex: int
    startTime: float
    endTime: float
    snippet: str


class AnswerResponse(BaseModel):
    answer: str
    sources: list[SourceTimestamp]


# ---------------------------------------------------------------------------
# Singleton genai client (lazy init, matches worker pattern)
# ---------------------------------------------------------------------------

_qa_client: genai.Client | None = None


def _get_qa_client() -> genai.Client:
    global _qa_client
    if _qa_client is None:
        _qa_client = genai.Client(
            vertexai=True,
            project=os.getenv("GCP_PROJECT_ID"),
            location=os.getenv("GCP_REGION", "us-central1"),
        )
        logger.info("QA genai client initialised")
    return _qa_client


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.post("/qa/{job_id}", response_model=AnswerResponse)
async def ask_question(
    job_id: str,
    body: QuestionRequest,
    current_user: dict = Depends(get_current_user),
):
    uid = current_user["uid"]

    # 1. Plan check — Q&A is Pro only
    plan = firestore.get_user_plan(uid)
    if plan != "pro":
        raise HTTPException(
            status_code=402,
            detail="Pro plan required for Q&A.",
        )

    # 2. Ownership check
    job = firestore.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    if job.get("userId") != uid:
        raise HTTPException(status_code=403, detail="Access denied.")

    # 3. Status check
    if job.get("status") != "completed":
        raise HTTPException(status_code=409, detail="Job is still processing.")

    question = body.question.strip()

    # 4. Check transcript chunks exist
    chunk_count = firestore.get_transcript_chunk_count(job_id)
    if chunk_count == 0:
        raise HTTPException(status_code=404, detail="No transcript found for this job.")

    # 5. Embed question
    try:
        query_vector = _embed_question(question)
    except Exception as e:
        logger.error(f"[{job_id}] Question embedding failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to embed question.")

    # 6. Vector similarity search
    try:
        top_chunks = firestore.search_transcript_chunks(job_id, query_vector, top_k=TOP_K)
    except Exception as e:
        logger.error(f"[{job_id}] Vector search failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Vector search failed.")

    if not top_chunks:
        return AnswerResponse(
            answer="No relevant transcript sections found for your question.",
            sources=[],
        )

    # 7. Assemble prompt and call Gemini
    try:
        answer_text = _generate_answer(question, top_chunks)
    except Exception as e:
        logger.error(f"[{job_id}] Gemini Q&A call failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to generate answer.")

    # 8. Build source list
    sources = [
        SourceTimestamp(
            chunkIndex=chunk["chunkIndex"],
            startTime=chunk["startTime"],
            endTime=chunk["endTime"],
            snippet=chunk["text"][:150] + ("..." if len(chunk["text"]) > 150 else ""),
        )
        for chunk in top_chunks
    ]

    logger.info(f"[{job_id}] Q&A answered for uid={uid}, question='{question[:60]}'")
    return AnswerResponse(answer=answer_text, sources=sources)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _embed_question(question: str) -> list:
    """Embed a question string using text-embedding-004 with RETRIEVAL_QUERY task type."""
    client = _get_qa_client()
    response = client.models.embed_content(
        model="text-embedding-004",
        contents=question,
        config=types.EmbedContentConfig(
            task_type="RETRIEVAL_QUERY",
            output_dimensionality=768,
        ),
    )
    return response.embeddings[0].values


def _generate_answer(question: str, chunks: list) -> str:
    """Assemble context from chunks and call Gemini 2.5 Flash."""
    client = _get_qa_client()

    context_blocks = []
    for chunk in chunks:
        start = _fmt_time(chunk["startTime"])
        end = _fmt_time(chunk["endTime"])
        context_blocks.append(f"[{start} – {end}]\n{chunk['text']}")

    context_text = "\n\n".join(context_blocks)

    prompt = (
        "You are a helpful assistant answering questions about a video based on its transcript.\n\n"
        f"Relevant transcript sections:\n{context_text}\n\n"
        f"Question: {question}\n\n"
        "Answer the question based only on the transcript sections above. "
        "If the answer is not in the transcript, say so. "
        "Be concise. Reference timestamps when helpful (e.g. 'At 2:30, ...')."
    )

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            max_output_tokens=2048,
            temperature=0.2,
        ),
    )
    return response.text


def _fmt_time(seconds: float) -> str:
    """Format seconds as M:SS for display."""
    s = int(seconds)
    m, rem = divmod(s, 60)
    return f"{m}:{rem:02d}"
