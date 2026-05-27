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
import os
import shutil
import subprocess
import tempfile
import time
from typing import List, Dict, Any

from google.cloud import storage as gcs_storage

from models.schemas import JobMessage
from pipeline.speech_to_text import transcribe, transcribe_with_language, download_from_gcs
from pipeline.video_intelligence import analyse_video
from pipeline.gemini import generate_summary, translate_transcript
from pipeline.embeddings import embed_transcript_chunks
from services import firestore

logger = logging.getLogger(__name__)

BUCKET_NAME = os.getenv("GCP_BUCKET_NAME")
FFMPEG_PATH = shutil.which("ffmpeg") or "ffmpeg"


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
    detected_language: str = ""
    stt_cost: float = 0.0
    vi_cost: float = 0.0

    if is_audio_only:
        # Audio-only path: run STT only, skip VI entirely
        logger.info(f"[{job_id}] Phase 1 — STT only (audio-only path)")

        try:
            transcript, detected_language = await _run_stt_with_progress(gcs_uri, job_id)
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

        # C1: write STT cost estimate (derive duration from transcript end time)
        duration = transcript[-1]["endTime"] if transcript else 0.0
        stt_minutes = round(duration / 60, 3)
        stt_cost = round(stt_minutes * 0.016, 4)   # $0.016 per minute (STT v2 BatchRecognize)
        firestore.write_job_fields(job_id, {
            "sttAudioMinutes": stt_minutes,
            "sttEstimatedCostUsd": stt_cost,
        })

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
            if transcript_result is not None:
                transcript, detected_language = transcript_result
            else:
                transcript = []
                detected_language = ""
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

        # C1: write STT cost estimate (derive duration from transcript end time)
        duration = transcript[-1]["endTime"] if transcript else 0.0
        stt_minutes = round(duration / 60, 3)
        stt_cost = round(stt_minutes * 0.016, 4)   # $0.016 per minute (STT v2 BatchRecognize)
        firestore.write_job_fields(job_id, {
            "sttAudioMinutes": stt_minutes,
            "sttEstimatedCostUsd": stt_cost,
        })

        # C1: write VI cost estimate (derive duration from scenes or transcript)
        vi_duration = scenes[-1]["endTime"] if scenes else duration
        vi_minutes = round(vi_duration / 60, 3)
        vi_cost = round(vi_minutes * 0.10, 4)   # $0.10 per minute (Video Intelligence API)
        firestore.write_job_fields(job_id, {
            "viVideoMinutes": vi_minutes,
            "viEstimatedCostUsd": vi_cost,
        })

    # -----------------------------------------------------------------------
    # Thumbnail extraction (A5) — best-effort, never fails the pipeline
    # -----------------------------------------------------------------------
    # Skip for audio-only files — there are no video frames to extract.
    if not is_audio_only:
        try:
            thumbnail_gcs_path = await _extract_and_upload_thumbnail(
                gcs_uri=gcs_uri,
                job_id=job_id,
            )
            if thumbnail_gcs_path:
                firestore.write_thumbnail_gcs_path(job_id, thumbnail_gcs_path)
        except Exception as e:
            # Non-fatal — dashboard will show a placeholder if thumbnail is missing
            logger.warning(f"[{job_id}] Thumbnail extraction failed (non-fatal): {e}")

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

    # C1: compute total cost
    # geminiEstimatedCostUsd is already written by write_gemini_usage() in gemini.py
    job_doc = firestore.get_job(job_id)
    gemini_cost = job_doc.get("geminiEstimatedCostUsd", 0.0) if job_doc else 0.0
    total_cost = round(stt_cost + vi_cost + gemini_cost, 4)
    firestore.write_job_fields(job_id, {"totalEstimatedCostUsd": total_cost})

    # -----------------------------------------------------------------------
    # Phase 3 — Write results to Firestore
    # -----------------------------------------------------------------------

    logger.info(f"[{job_id}] Phase 3 — writing results")

    try:
        firestore.write_results(job_id=job_id, transcript=transcript, scenes=scenes, detected_language=detected_language)
    except Exception as e:
        logger.error(f"[{job_id}] Firestore write_results failed: {e}")
        firestore.mark_processing_failed(job_id, f"Results write failed: {e}")
        return False

    # -------------------------------------------------------------------
    # Conditional translation step (between write_results and write_summary)
    # Translate iff detected_language is NOT "en-US", NOT "en-IN", and NOT ""
    # -------------------------------------------------------------------
    translated_transcript = None
    if detected_language and detected_language not in ("en-US", "en-IN"):
        try:
            logger.info(f"[{job_id}] Translation step — translating from {detected_language}")
            translated_transcript = await translate_transcript(
                transcript=transcript,
                source_language=detected_language,
                job_id=job_id,
            )
            if translated_transcript is not None:
                logger.info(f"[{job_id}] Translation complete — {len(translated_transcript)} words")
            else:
                logger.warning(f"[{job_id}] Translation returned None")
        except Exception as e:
            logger.error(f"[{job_id}] Translation failed (non-fatal): {e}")
            translated_transcript = None
    else:
        logger.info(f"[{job_id}] Translation skipped — detected_language={detected_language!r}")

    try:
        firestore.write_summary(job_id=job_id, summary_data=summary_data, translated_transcript=translated_transcript)
    except Exception as e:
        logger.error(f"[{job_id}] Firestore write_summary failed (non-fatal): {e}")

    # -------------------------------------------------------------------
    # Phase 4 — Embed transcript chunks for RAG (non-fatal)
    # -------------------------------------------------------------------
    try:
        chunk_count = firestore.get_transcript_chunk_count(job_id)
        if chunk_count > 0:
            await embed_transcript_chunks(job_id, chunk_count)
    except Exception as e:
        logger.error(f"[{job_id}] Embedding pipeline failed (non-fatal): {e}")

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


async def _run_stt_with_progress(gcs_uri: str, job_id: str) -> tuple[list, str]:
    """
    Wrapper around transcribe_with_language() that fires a Firestore progress update
    at progress=50 immediately after STT completes.

    Returns a tuple of (transcript, detected_language).

    Kept separate from run_pipeline() so asyncio.gather() can still
    run it concurrently with Video Intelligence.
    """
    transcript, detected_language = await transcribe_with_language(gcs_uri, job_id=job_id)
    try:
        # Only update if STT finished first — VI may have already pushed to 75
        # update_job_status with progress=None skips the progress field write,
        # so we explicitly pass 50 here
        firestore.update_job_status(job_id, "processing", progress=50)
    except Exception:
        pass   # Never fail the pipeline over a progress update
    return (transcript, detected_language)


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


async def _extract_and_upload_thumbnail(gcs_uri: str, job_id: str) -> str | None:
    """
    Extract a single thumbnail frame from the video at 10% of its duration
    and upload it to GCS at processed/{jobId}/thumbnail.jpg.

    Uses ffmpeg (already installed in the worker Dockerfile) and the same
    download pattern as speech_to_text.py.

    Args:
        gcs_uri: GCS URI of the raw video (gs://bucket/raw-videos/...).
        job_id:  For logging and GCS path construction.

    Returns:
        GCS object path of the uploaded thumbnail, e.g.
        "processed/{jobId}/thumbnail.jpg" — or None on failure.
    """
    if not BUCKET_NAME:
        logger.warning(f"[{job_id}] Thumbnail: GCP_BUCKET_NAME not set — skipping")
        return None

    with tempfile.TemporaryDirectory() as tmpdir:
        video_path = os.path.join(tmpdir, "video_thumb.mp4")
        thumb_path = os.path.join(tmpdir, "thumbnail.jpg")

        # Step 1: download video
        logger.info(f"[{job_id}] Thumbnail: downloading video for frame extraction")
        await asyncio.get_event_loop().run_in_executor(
            None, download_from_gcs, gcs_uri, video_path
        )

        # Step 2: get duration via ffprobe
        ffprobe_path = shutil.which("ffprobe") or "ffprobe"
        probe_cmd = [
            ffprobe_path,
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            video_path,
        ]
        probe_result = subprocess.run(probe_cmd, capture_output=True, text=True)
        duration = 0.0
        if probe_result.returncode == 0 and probe_result.stdout.strip():
            try:
                duration = float(probe_result.stdout.strip())
            except ValueError:
                pass

        # Seek to 10% of duration; fall back to 5s for very short clips
        seek_time = max(duration * 0.1, 5.0) if duration > 10 else 1.0
        logger.info(f"[{job_id}] Thumbnail: extracting frame at {seek_time:.1f}s (duration={duration:.1f}s)")

        # Step 3: extract frame with ffmpeg
        ffmpeg_cmd = [
            FFMPEG_PATH,
            "-ss", str(seek_time),
            "-i", video_path,
            "-vframes", "1",
            "-q:v", "2",          # JPEG quality 2 = high quality, ~50–100 KB
            "-y",
            thumb_path,
        ]
        ffmpeg_result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
        if ffmpeg_result.returncode != 0:
            raise RuntimeError(f"ffmpeg thumbnail extraction failed: {ffmpeg_result.stderr}")

        if not os.path.exists(thumb_path) or os.path.getsize(thumb_path) == 0:
            raise RuntimeError("ffmpeg produced an empty thumbnail file")

        # Step 4: upload to GCS
        gcs_path = f"processed/{job_id}/thumbnail.jpg"
        client = gcs_storage.Client()
        bucket = client.bucket(BUCKET_NAME)
        blob = bucket.blob(gcs_path)

        await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: blob.upload_from_filename(thumb_path, content_type="image/jpeg"),
        )

        logger.info(f"[{job_id}] Thumbnail uploaded → {gcs_path}")
        return gcs_path
