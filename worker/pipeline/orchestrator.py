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
import json
import logging
import os
import shutil
import subprocess
import tempfile
import time
from typing import List, Dict, Any

from google.cloud import storage as gcs_storage
from google.genai import types

from models.schemas import JobMessage
from pipeline.speech_to_text import transcribe, download_from_gcs
from pipeline.video_intelligence import analyse_video
from pipeline.gemini import generate_summary, get_gemini_client
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

    if is_audio_only:
        # Audio-only path: run STT only, skip VI entirely
        logger.info(f"[{job_id}] Phase 1 — STT only (audio-only path)")

        try:
            stt_result = await _run_stt_with_progress(gcs_uri, job_id)
            transcript, _thumb_bytes = stt_result  # thumb_bytes is None for audio-only
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
            _run_gemini_scenes(gcs_uri, job_id),
            return_exceptions=True,
        )

        transcript_result = phase1_results[0]
        scenes_result = phase1_results[1]

        phase1_errors = []
        thumb_bytes: bytes | None = None

        if isinstance(transcript_result, Exception):
            logger.error(f"[{job_id}] STT failed: {transcript_result}")
            phase1_errors.append(f"Speech-to-Text: {transcript_result}")
        else:
            # _run_stt_with_progress returns (transcript, thumb_bytes)
            if transcript_result is None:
                logger.warning(f"[{job_id}] STT returned None — treating as empty transcript")
                transcript = []
            else:
                transcript, thumb_bytes = transcript_result
                transcript = transcript if transcript is not None else []
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
    # Thumbnail extraction (A5) — best-effort, never fails the pipeline
    # -----------------------------------------------------------------------
    # Skip for audio-only files — there are no video frames to extract.
    if not is_audio_only:
        try:
            if thumb_bytes is not None:
                # Fast path: upload bytes extracted inside transcribe() — no second download
                thumbnail_gcs_path = await _upload_thumbnail_bytes(thumb_bytes, job_id)
            else:
                # Fallback: thumb_bytes unavailable — download video and extract
                logger.warning(
                    f"[{job_id}] Thumbnail bytes unavailable — falling back to download"
                )
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


async def _run_stt_with_progress(gcs_uri: str, job_id: str) -> tuple[list, bytes | None]:
    """
    Wrapper around transcribe() that fires a Firestore progress update
    at progress=50 immediately after STT completes.

    Passes extract_thumbnail=True so the already-downloaded local video is
    used to extract thumbnail bytes — eliminating the second download_from_gcs()
    call that _extract_and_upload_thumbnail() would otherwise make.

    Kept separate from run_pipeline() so asyncio.gather() can still
    run it concurrently with Video Intelligence.

    Returns:
        Tuple of (transcript: list, thumb_bytes: bytes | None).
    """
    result = await transcribe(gcs_uri, job_id=job_id, extract_thumbnail=True)
    # transcribe() with extract_thumbnail=True always returns a tuple
    transcript, thumb_bytes = result
    try:
        # Only update if STT finished first — VI may have already pushed to 75
        # update_job_status with progress=None skips the progress field write,
        # so we explicitly pass 50 here
        firestore.update_job_status(job_id, "processing", progress=50)
    except Exception:
        pass   # Never fail the pipeline over a progress update
    return (transcript, thumb_bytes)


async def _run_gemini_scenes(gcs_uri: str, job_id: str) -> list:
    """
    Call Gemini Flash directly on the GCS URI to produce a scene list.

    Replaces _run_vi_with_progress() in the asyncio.gather() call.
    Returns a list of scene dicts with shape:
        [{"startTime": float, "endTime": float, "labels": list[str]}]
    capped at 50 items.

    On any exception, logs the error and returns [] — same failure
    behaviour as the existing VI path.

    Args:
        gcs_uri: GCS URI of the raw video (gs://bucket/raw-videos/...).
        job_id:  For logging.

    Returns:
        List of scene dicts (at most 50), or [] on failure.
    """
    try:
        client = get_gemini_client()

        video_part = types.Part.from_uri(gcs_uri, mime_type="video/mp4")

        prompt = (
            "Analyse this video and return a JSON array of scenes. "
            "Each scene must have exactly these keys: "
            '"startTime" (float, seconds), '
            '"endTime" (float, seconds), '
            '"labels" (list of strings describing what is happening). '
            "Return ONLY the JSON array, no explanation, no markdown, no code fences. "
            'Example: [{"startTime": 0.0, "endTime": 12.5, "labels": ["presenter speaking", "slide visible"]}]'
        )

        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.1,
            max_output_tokens=4000,
        )

        response = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: client.models.generate_content(
                model="gemini-2.0-flash",
                contents=[video_part, prompt],
                config=config,
            ),
        )

        scenes = json.loads(response.text)

        if not isinstance(scenes, list):
            logger.warning(f"[{job_id}] Gemini scenes response is not a list — returning []")
            return []

        logger.info(f"[{job_id}] Gemini scenes complete — {len(scenes)} scenes (before cap)")
        return scenes[:50]

    except Exception as e:
        logger.error(f"[{job_id}] _run_gemini_scenes failed: {e}")
        return []


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


async def _upload_thumbnail_bytes(thumb_bytes: bytes, job_id: str) -> str | None:
    """
    Upload raw thumbnail JPEG bytes directly to GCS without downloading the video.

    Writes bytes to processed/{jobId}/thumbnail.jpg via blob.upload_from_string().
    This is the primary thumbnail upload path — it reuses bytes extracted inside
    transcribe() so no second download_from_gcs() call is needed.

    Args:
        thumb_bytes: Raw JPEG bytes of the thumbnail frame.
        job_id:      For GCS path construction and logging.

    Returns:
        GCS object path "processed/{jobId}/thumbnail.jpg", or None on failure.
    """
    if not BUCKET_NAME:
        logger.warning(f"[{job_id}] Thumbnail upload: GCP_BUCKET_NAME not set — skipping")
        return None

    try:
        gcs_path = f"processed/{job_id}/thumbnail.jpg"
        client = gcs_storage.Client()
        bucket = client.bucket(BUCKET_NAME)
        blob = bucket.blob(gcs_path)

        await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: blob.upload_from_string(thumb_bytes, content_type="image/jpeg"),
        )

        logger.info(f"[{job_id}] Thumbnail uploaded (from bytes) → {gcs_path}")
        return gcs_path
    except Exception as e:
        logger.warning(f"[{job_id}] Thumbnail bytes upload failed (non-fatal): {e}")
        return None


async def _extract_and_upload_thumbnail(
    gcs_uri: str,
    job_id: str,
    local_video_path: str | None = None,
) -> str | None:
    """
    Extract a single thumbnail frame from the video at 10% of its duration
    and upload it to GCS at processed/{jobId}/thumbnail.jpg.

    Uses ffmpeg (already installed in the worker Dockerfile) and the same
    download pattern as speech_to_text.py.

    When local_video_path is provided, the download step is skipped entirely
    and the provided path is used directly. This keeps the function usable as
    a standalone fallback if thumb_bytes are unavailable.

    Args:
        gcs_uri:          GCS URI of the raw video (gs://bucket/raw-videos/...).
        job_id:           For logging and GCS path construction.
        local_video_path: Optional local path to an already-downloaded video.
                          When provided, download_from_gcs() is NOT called.

    Returns:
        GCS object path of the uploaded thumbnail, e.g.
        "processed/{jobId}/thumbnail.jpg" — or None on failure.
    """
    if not BUCKET_NAME:
        logger.warning(f"[{job_id}] Thumbnail: GCP_BUCKET_NAME not set — skipping")
        return None

    with tempfile.TemporaryDirectory() as tmpdir:
        if local_video_path is not None:
            # Use the already-downloaded file — skip download_from_gcs()
            video_path = local_video_path
            logger.info(f"[{job_id}] Thumbnail: using provided local video path — skipping download")
        else:
            video_path = os.path.join(tmpdir, "video_thumb.mp4")
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

        thumb_path = os.path.join(tmpdir, "thumbnail.jpg")

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
