# worker/pipeline/orchestrator.py


# MIME types that are audio-only — Video Intelligence API is skipped for these.
# STT still runs normally. Add new audio types here as needed.
AUDIO_ONLY_MIME_TYPES = {
    "audio/mpeg",
    "audio/wav",
    "audio/x-wav",
    "audio/mp4",
    "audio/x-m4a",
    "audio/ogg",
    "audio/flac",
    "audio/aac",
}


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
    job_id = job_message.jobId
    gcs_uri = job_message.gcsUri
    start_time = time.time()

    logger.info(
        f"[{job_id}] Orchestrator started — "
        f"file: {job_message.filename}, size: {job_message.fileSizeMb}MB"
    )

    # -----------------------------------------------------------------------
    # Determine if the file is audio-only based on contentType
    # -----------------------------------------------------------------------
    is_audio_only = _is_audio_only(job_message.contentType)

    if is_audio_only:
        logger.info(f"[{job_id}] Audio-only file detected (contentType={job_message.contentType!r}) — skipping Video Intelligence")

    # -----------------------------------------------------------------------
    # Phase 1 — STT only (audio) or Concurrent STT + Video Intelligence (video)
    # -----------------------------------------------------------------------

    firestore.update_job_status(job_id, "processing", progress=35)

    transcript: list = []
    scenes: list = []

    if is_audio_only:
        # Audio-only path: run STT only, skip VI entirely
        logger.info(f"[{job_id}] Phase 1 — STT only (audio-only path)")

        try:
            transcript = await _run_stt_with_progress(gcs_uri, job_id)
        except Exception as e:
            logger.error(f"[{job_id}] STT failed for audio-only file: {e}")
            firestore.mark_processing_failed(
                job_id,
                f"Speech-to-Text failed: {e}"
            )
            return False

        scenes = []
        logger.info(f"[{job_id}] STT complete — {len(transcript)} words")
        firestore.update_job_status(job_id, "processing", progress=75)

    else:
        # Video path: run STT + VI concurrently (existing behavior)
        logger.info(f"[{job_id}] Phase 1 — STT + VideoIntel running concurrently")

        phase1_results = await asyncio.gather(
            _run_stt_with_progress(gcs_uri, job_id),
            _run_vi_with_progress(gcs_uri, job_id),
            return_exceptions=True,
        )

        transcript_result = phase1_results[0]
        scenes_result = phase1_results[1]

        phase1_errors = []

        if isinstance(transcript_result, Exception):
            logger.error(f"[{job_id}] STT failed: {transcript_result}")
            phase1_errors.append(f"Speech-to-Text: {transcript_result}")
        else:
            transcript = transcript_result if transcript_result is not None else []
            if transcript_result is None:
                logger.warning(f"[{job_id}] STT returned None — treating as empty transcript")
            logger.info(f"[{job_id}] STT complete — {len(transcript)} words")

        if isinstance(scenes_result, Exception):
            logger.error(f"[{job_id}] VideoIntel failed: {scenes_result}")
            phase1_errors.append(f"Video Intelligence: {scenes_result}")
        else:
            scenes = scenes_result
            logger.info(f"[{job_id}] VideoIntel complete — {len(scenes)} scenes")

        if len(phase1_errors) == 2:
            firestore.mark_processing_failed(
                job_id,
                f"Both pipelines failed: {' | '.join(phase1_errors)}"
            )
            logger.error(f"[{job_id}] Both Phase 1 pipelines failed — job marked failed")
            return False

        if len(phase1_errors) == 1:
            logger.warning(f"[{job_id}] Partial failure: {phase1_errors[0]}")

        # Both done — set progress=75 regardless of which finished first
        firestore.update_job_status(job_id, "processing", progress=75)

    # -----------------------------------------------------------------------
    # Phase 2 — Gemini summary
    # -----------------------------------------------------------------------

    firestore.update_job_status(job_id, "processing", progress=90)
    logger.info(f"[{job_id}] Phase 2 — Gemini summary")

    duration_seconds = int(scenes[-1]["endTime"]) if scenes else 0

    try:
        summary_data = await generate_summary(
            transcript=transcript,
            scenes=scenes,
            duration_seconds=duration_seconds,
            job_id=job_id,
        )
    except Exception as e:
        logger.error(f"[{job_id}] Gemini failed: {e} — continuing without summary")
        summary_data = {
            "summary": "Summary generation failed.",
            "chapters": [],
            "highlights": [],
            "sentiment": "neutral",
            "actionItems": [],
        }

    # -----------------------------------------------------------------------
    # Phase 3 — Write results to Firestore
    # -----------------------------------------------------------------------

    logger.info(f"[{job_id}] Phase 3 — writing results")

    try:
        firestore.write_results(job_id=job_id, transcript=transcript, scenes=scenes)
    except Exception as e:
        logger.error(f"[{job_id}] Firestore write_results failed: {e}")
        firestore.mark_processing_failed(job_id, f"Results write failed: {e}")
        return False

    try:
        firestore.write_summary(job_id=job_id, summary_data=summary_data)
    except Exception as e:
        logger.error(f"[{job_id}] Firestore write_summary failed (non-fatal): {e}")

    elapsed = int(time.time() - start_time)
    firestore.mark_processing_completed(job_id, processing_time_seconds=elapsed)

    logger.info(
        f"[{job_id}] Pipeline complete — elapsed: {elapsed}s, "
        f"words: {len(transcript)}, scenes: {len(scenes)}"
    )
    return True


def _is_audio_only(content_type: str) -> bool:
    """
    Determine if a file is audio-only based on its MIME type.

    Performs case-insensitive matching and strips MIME parameters
    after semicolons (e.g., "audio/mpeg; charset=utf-8" → "audio/mpeg").

    Returns False for empty/null/missing contentType values.
    """
    if not content_type:
        return False

    # Strip MIME parameters after semicolon and normalize
    normalized = content_type.split(";")[0].strip().lower()

    return normalized in AUDIO_ONLY_MIME_TYPES


async def _run_stt_with_progress(gcs_uri: str, job_id: str) -> list:
    """
    Wrapper around transcribe() that fires a Firestore progress update
    at progress=50 immediately after STT completes.

    Kept separate from run_pipeline() so asyncio.gather() can still
    run it concurrently with Video Intelligence.
    """
    result = await transcribe(gcs_uri, job_id=job_id)
    try:
        # Only update if STT finished first — VI may have already pushed to 75
        # update_job_status with progress=None skips the progress field write,
        # so we explicitly pass 50 here
        firestore.update_job_status(job_id, "processing", progress=50)
    except Exception:
        pass   # Never fail the pipeline over a progress update
    return result


async def _run_vi_with_progress(gcs_uri: str, job_id: str) -> list:
    """
    Wrapper around analyse_video() that fires a Firestore progress update
    at progress=60 immediately after Video Intelligence completes.

    Uses 60 rather than 75 so STT and VI updates don't collide at 75.
    The orchestrator sets 75 after both complete.
    """
    result = await analyse_video(gcs_uri, job_id=job_id)
    try:
        firestore.update_job_status(job_id, "processing", progress=60)
    except Exception:
        pass
    return result