# worker/pipeline/embeddings.py

import logging
import os

from google import genai
from google.genai import types

from services import firestore

logger = logging.getLogger(__name__)

PROJECT_ID = os.getenv("GCP_PROJECT_ID")
LOCATION = os.getenv("GCP_REGION", "us-central1")

_client: genai.Client | None = None


def get_embedding_client() -> genai.Client:
    """
    Return an initialised genai client for embedding operations.
    Lazy-init singleton — matches the pattern in gemini.py.
    """
    global _client
    if _client is None:
        _client = genai.Client(
            vertexai=True,
            project=PROJECT_ID,
            location=LOCATION,
        )
        logger.info(
            f"Embedding client initialised — project: {PROJECT_ID}, location: {LOCATION}"
        )
    return _client


async def embed_transcript_chunks(job_id: str, chunk_count: int) -> None:
    """
    Embed all transcript chunks for a completed job.

    Reads each chunk from Firestore, generates a 768-dim embedding via
    text-embedding-004, and writes it back to the chunk document.

    Non-fatal: logs errors but never raises — pipeline continues regardless.
    Individual chunk failures are logged and skipped; remaining chunks still processed.
    """
    try:
        logger.info(
            f"[{job_id}] Embedding pipeline started — {chunk_count} chunks to embed"
        )
        client = get_embedding_client()

        for i in range(chunk_count):
            try:
                # Read chunk from Firestore
                chunk = firestore.get_transcript_chunk(job_id, i)
                if chunk is None:
                    logger.warning(f"[{job_id}] Chunk {i} not found — skipping")
                    continue

                # Join words into text
                words = chunk.get("words", [])
                if not words:
                    logger.warning(f"[{job_id}] Chunk {i} has no words — skipping")
                    continue

                chunk_text = " ".join(w.get("word", "") for w in words)

                # Generate embedding
                response = client.models.embed_content(
                    model="text-embedding-004",
                    contents=chunk_text,
                    config=types.EmbedContentConfig(
                        task_type="RETRIEVAL_DOCUMENT",
                        output_dimensionality=768,
                    ),
                )
                vector = response.embeddings[0].values

                # Write embedding to Firestore
                firestore.write_chunk_embedding(job_id, i, vector)

            except Exception as e:
                logger.warning(
                    f"[{job_id}] Failed to embed chunk {i} — skipping: {e}"
                )
                continue

        logger.info(f"[{job_id}] Embedding pipeline completed")

    except Exception as e:
        logger.error(f"[{job_id}] Embedding pipeline failed: {e}")
