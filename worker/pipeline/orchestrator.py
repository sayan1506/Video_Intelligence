# worker/pipeline/orchestrator.py

import asyncio
import logging
import time
from typing import List, Dict, Any

from models.schemas import JobMessage
from pipeline.speech_to_text import transcribe
from pipeline.video_intelligence import analyse_video
from pipeline.gemini import generate_summary   # stub today, real in Week 4
from services import firestore

logger = logging.getLogger(__name__)


async def run_pipeline(job_message: JobMessage) -> bool:
    """
    Run all AI pipelines for a job and write results to Firestore.

    Execution order:
      Phase 1 (concurrent):  Speech-to-Text + Video Intelligence
      Phase 2 (sequential):  Gemini summary (depends on Phase 1 outputs)
      Phase 3 (sequential):  Write results to Firestore

    Uses asyncio.gather(return_exceptions=True) for Phase 1 so a failure
    in one pipeline does not cancel or discard the output of the other.

    Args:
        job_message: Validated JobMessage from the Pub/Sub subscriber.

    Returns:
        True if at least one pipeline succeeded and results were written.
        False if all pipelines failed and the job was marked as failed.
    """
    job_id = job_message.jobId
    gcs_uri = job_message.gcsUri
    start_time = time.time()

    logger.info(
        f"[{job_id}] Orchestrator started — "
        f"file: {job_message.filename}, "
        f"size: {job_message.fileSizeMb}MB"
    )

    # -----------------------------------------------------------------------
    # Phase 1 — Concurrent Speech-to-Text + Video Intelligence
    # -----------------------------------------------------------------------
    # Update progress to 35 — signals both pipelines are running
    firestore.update_job_status(job_id, "processing", progress=35)
    logger.info(f"[{job_id}] Phase 1 — STT + Video Intelligence running concurrently")

    phase1_results = await asyncio.gather(
        transcribe(gcs_uri, job_id=job_id),
        analyse_video(gcs_uri, job_id=job_id),
        return_exceptions=True,
    )

    transcript_result = phase1_results[0]
    scenes_result = phase1_results[1]

    # --- Handle partial failures independently ---
    transcript: List[Dict[str, Any]] = []
    scenes: List[Dict[str, Any]] = []
    phase1_errors = []

    if isinstance(transcript_result, Exception):
        error_msg = f"Speech-to-Text failed: {transcript_result}"
        logger.error(f"[{job_id}] {error_msg}")
        phase1_errors.append(error_msg)
    else:
        transcript = transcript_result
        logger.info(f"[{job_id}] STT complete — {len(transcript)} words transcribed")
        firestore.update_job_status(job_id, "processing", progress=50)

    if isinstance(scenes_result, Exception):
        error_msg = f"Video Intelligence failed: {scenes_result}"
        logger.error(f"[{job_id}] {error_msg}")
        phase1_errors.append(error_msg)
    else:
        scenes = scenes_result
        logger.info(f"[{job_id}] Video Intelligence complete — {len(scenes)} scenes detected")
        firestore.update_job_status(job_id, "processing", progress=75)

    # If both pipelines failed there is nothing to write — mark job failed
    if len(phase1_errors) == 2:
        combined_error = " | ".join(phase1_errors)
        firestore.mark_processing_failed(
            job_id,
            f"Both Phase 1 pipelines failed: {combined_error}"
        )
        logger.error(f"[{job_id}] Both pipelines failed — job marked as failed")
        return False

    # Partial failure: log which pipeline failed but continue with available data
    if len(phase1_errors) == 1:
        logger.warning(
            f"[{job_id}] Partial failure — continuing with available data. "
            f"Failed: {phase1_errors[0]}"
        )

    # -----------------------------------------------------------------------
    # Phase 2 — Gemini summary (stub today, real Vertex AI call in Week 4)
    # -----------------------------------------------------------------------
    firestore.update_job_status(job_id, "processing", progress=90)
    logger.info(f"[{job_id}] Phase 2 — Gemini summary generation")

    # Estimate duration from last scene end time
    # Will be replaced with video metadata in a future iteration
    duration_seconds = int(scenes[-1]["endTime"]) if scenes else 0

    try:
        summary_data = await generate_summary(
            transcript=transcript,
            scenes=scenes,
            duration_seconds=duration_seconds,
            job_id=job_id,
        )
        logger.info(f"[{job_id}] Gemini phase complete")
    except Exception as e:
        # Gemini failure is non-fatal — write what we have from Phase 1
        logger.error(f"[{job_id}] Gemini pipeline failed: {e} — continuing without summary")
        summary_data = {
            "summary": "Summary generation failed.",
            "chapters": [],
            "highlights": [],
            "sentiment": "neutral",
            "actionItems": [],
        }

    # -----------------------------------------------------------------------
    # Phase 3 — Write all results to Firestore
    # -----------------------------------------------------------------------
    logger.info(f"[{job_id}] Phase 3 — writing results to Firestore")

    try:
        # Write transcript + scenes to results/{jobId}
        firestore.write_results(
            job_id=job_id,
            transcript=transcript,
            scenes=scenes,
        )
    except Exception as e:
        logger.error(f"[{job_id}] Failed to write results to Firestore: {e}")
        firestore.mark_processing_failed(job_id, f"Firestore results write failed: {e}")
        return False

    try:
        # Write summary to summaries/{jobId}
        firestore.write_summary(job_id=job_id, summary_data=summary_data)
    except Exception as e:
        # Non-fatal — transcript and scenes are already written
        logger.error(f"[{job_id}] Failed to write summary to Firestore: {e}")

    # -----------------------------------------------------------------------
    # Mark job as completed
    # -----------------------------------------------------------------------
    elapsed = int(time.time() - start_time)
    firestore.mark_processing_completed(job_id, processing_time_seconds=elapsed)

    logger.info(
        f"[{job_id}] Pipeline complete — "
        f"elapsed: {elapsed}s, "
        f"words: {len(transcript)}, "
        f"scenes: {len(scenes)}"
    )
    return True