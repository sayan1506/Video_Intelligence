# Videos longer than this threshold use 8kHz instead of 16kHz FLAC extraction.
# Reduces FLAC file size ~50% for long-form content (lectures, podcasts).
# STT v2 BatchRecognize performs acceptably at 8kHz for clear speech.
ADAPTIVE_FFMPEG_THRESHOLD_SECONDS = 1800  # 30 minutes


# Chunk duration in seconds. 5 minutes = 300s.
# Chosen to keep each FLAC chunk well under BatchRecognize's inline response limit.
CHUNK_DURATION_SECONDS = 300

# Minimum video duration (in seconds) to bother chunking.
# Videos shorter than this go through the existing whole-file path — no overhead.
CHUNK_THRESHOLD_SECONDS = CHUNK_DURATION_SECONDS  # i.e., chunk if > 5 minutes


import json
import logging
import os
import asyncio
import tempfile
import subprocess
from typing import List, Dict, Any
import time as time_module
import shutil
from google.cloud.speech_v2 import SpeechClient
from google.cloud.speech_v2.types import cloud_speech
from google.api_core.exceptions import GoogleAPICallError
from google.cloud import storage as gcs_storage
from google.api_core.exceptions import ServiceUnavailable, DeadlineExceeded

from services.storage import write_processed_json

logger = logging.getLogger(__name__)



PROJECT_ID = os.getenv("GCP_PROJECT_ID")
BUCKET_NAME = os.getenv("GCP_BUCKET_NAME")

if not PROJECT_ID:
    raise RuntimeError("GCP_PROJECT_ID environment variable is not set")
if not BUCKET_NAME:
    raise RuntimeError("GCP_BUCKET_NAME environment variable is not set")

FFMPEG_PATH = shutil.which("ffmpeg") or "ffmpeg"


def get_speech_client() -> SpeechClient:
    return SpeechClient()


def build_recognition_config(sample_rate: int = 16000) -> cloud_speech.RecognitionConfig:
    return cloud_speech.RecognitionConfig(
        explicit_decoding_config=cloud_speech.ExplicitDecodingConfig(
            encoding=cloud_speech.ExplicitDecodingConfig.AudioEncoding.FLAC,
            sample_rate_hertz=sample_rate,
            audio_channel_count=1,
        ),
        language_codes=["hi-IN", "en-US"],
        model="long",
        features=cloud_speech.RecognitionFeatures(
            enable_word_time_offsets=True,
            enable_automatic_punctuation=True,
        ),
    )


def extract_audio_to_flac(video_path: str, output_path: str, sample_rate: int = 16000) -> None:
    """Extract audio from video file to mono 16kHz FLAC using ffmpeg."""
    cmd = [
        FFMPEG_PATH,
        "-threads", "2",        # ← add this, use both CPUs for decoding
        "-i", video_path,
        "-vn",                  # no video
        "-ac", "1",             # mono
        "-ar", str(sample_rate),         # sample rate
        "-f", "flac",           # FLAC format
        "-threads", "2",        # ← add this, use both CPUs for encoding
        "-y",                   # overwrite output
        output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {result.stderr}")
    logger.info(f"Audio extracted to {output_path}")


def download_from_gcs(gcs_uri: str, local_path: str) -> None:
    without_prefix = gcs_uri[5:]
    bucket_name, blob_path = without_prefix.split("/", 1)
    client = gcs_storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_path)
    blob.chunk_size = 256 * 1024 * 1024  # ← add this line
    blob.download_to_filename(local_path, timeout=600)
    logger.info(f"Downloaded {gcs_uri} to {local_path}")


def upload_flac_to_gcs(local_path: str, job_id: str) -> str:
    client = gcs_storage.Client()
    bucket = client.bucket(BUCKET_NAME)
    gcs_path = f"processed/{job_id}/audio.flac"
    blob = bucket.blob(gcs_path)
    blob.chunk_size = 256 * 1024 * 1024  # ← add this line
    blob.upload_from_filename(local_path, content_type="audio/flac", timeout=600)
    gcs_uri = f"gs://{BUCKET_NAME}/{gcs_path}"
    logger.info(f"Uploaded FLAC to {gcs_uri}")
    return gcs_uri




def get_video_duration_seconds(video_path: str) -> float:
    """
    Return the duration of a video file in seconds using ffprobe.

    Used to decide whether to chunk (duration > CHUNK_THRESHOLD_SECONDS)
    and to calculate per-chunk start offsets.

    Args:
        video_path: Local path to the video file.

    Returns:
        Duration in seconds as a float. Returns 0.0 on failure (non-fatal —
        caller falls back to whole-file STT).
    """
    ffprobe_path = shutil.which("ffprobe") or "ffprobe"
    cmd = [
        ffprobe_path,
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        video_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0 or not result.stdout.strip():
        logger.warning(f"ffprobe failed for {video_path}: {result.stderr}")
        return 0.0
    try:
        return float(result.stdout.strip())
    except ValueError:
        logger.warning(f"Could not parse ffprobe duration: {result.stdout!r}")
        return 0.0


def split_audio_to_chunks(video_path: str, output_dir: str, sample_rate: int = 16000) -> list[tuple[str, float]]:
    """
    Split a video file's audio into fixed-duration FLAC chunks using ffmpeg.

    Uses the `segment` muxer with `-c copy` — no re-encoding, just demux
    and split. Each chunk is mono {sample_rate} FLAC matching `extract_audio_to_flac()`.

    Output files are named chunk_000.flac, chunk_001.flac, etc. in output_dir.

    Args:
        video_path:  Local path to the video file.
        output_dir:  Directory where chunk files are written. Must exist.
        sample_rate: Audio sample rate for the FLAC chunks.

    Returns:
        Sorted list of (chunk_path, start_offset_seconds) tuples.
        chunk_000.flac has offset 0, chunk_001.flac has offset CHUNK_DURATION_SECONDS, etc.

    Raises:
        RuntimeError: If ffmpeg exits non-zero.
    """
    chunk_pattern = os.path.join(output_dir, "chunk_%03d.flac")

    cmd = [
        FFMPEG_PATH,
        "-threads", "2",
        "-i", video_path,
        "-vn",                             # drop video
        "-ac", "1",                        # mono
        "-ar", str(sample_rate),                    # sample rate — matches STT config
        "-f", "segment",                   # segment muxer
        "-segment_time", str(CHUNK_DURATION_SECONDS),
        "-c:a", "flac",                    # FLAC codec
        "-y",                              # overwrite
        chunk_pattern,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg chunk split failed: {result.stderr}")

    # Collect chunk files, sorted lexicographically (= numerically due to zero-padding)
    chunk_files = sorted([
        f for f in os.listdir(output_dir)
        if f.startswith("chunk_") and f.endswith(".flac")
    ])

    if not chunk_files:
        raise RuntimeError("ffmpeg produced no chunk files — check ffmpeg output")

    result_pairs = []
    for i, chunk_file in enumerate(chunk_files):
        chunk_path = os.path.join(output_dir, chunk_file)
        start_offset = i * CHUNK_DURATION_SECONDS
        result_pairs.append((chunk_path, float(start_offset)))

    logger.info(
        f"Split audio into {len(result_pairs)} chunks "
        f"({CHUNK_DURATION_SECONDS}s each) in {output_dir}"
    )
    return result_pairs



def upload_chunk_to_gcs(local_path: str, job_id: str, chunk_index: int) -> str:
    """
    Upload a single FLAC chunk to GCS.

    Path: processed/{jobId}/chunks/chunk_{index:03d}.flac

    Args:
        local_path:  Local FLAC chunk file path.
        job_id:      Used to build the GCS path.
        chunk_index: Zero-based chunk number for the GCS filename.

    Returns:
        GCS URI (gs://...) for use with BatchRecognize.
    """
    client = gcs_storage.Client()
    bucket = client.bucket(BUCKET_NAME)
    gcs_path = f"processed/{job_id}/chunks/chunk_{chunk_index:03d}.flac"
    blob = bucket.blob(gcs_path)
    blob.chunk_size = 256 * 1024 * 1024
    blob.upload_from_filename(local_path, content_type="audio/flac", timeout=300)
    gcs_uri = f"gs://{BUCKET_NAME}/{gcs_path}"
    logger.info(f"[{job_id}] Chunk {chunk_index} uploaded → {gcs_uri}")
    return gcs_uri


def delete_chunk_from_gcs(job_id: str, chunk_index: int) -> None:
    """
    Delete a single GCS chunk file after STT completes.

    Best-effort — failure is logged but not raised. Chunk files are
    intermediate artifacts; leaving them does not affect results, only cost.

    Args:
        job_id:      Used to reconstruct the GCS path.
        chunk_index: Zero-based chunk number.
    """
    try:
        client = gcs_storage.Client()
        bucket = client.bucket(BUCKET_NAME)
        gcs_path = f"processed/{job_id}/chunks/chunk_{chunk_index:03d}.flac"
        bucket.blob(gcs_path).delete()
        logger.info(f"[{job_id}] Chunk {chunk_index} deleted from GCS")
    except Exception as e:
        logger.warning(f"[{job_id}] Chunk {chunk_index} GCS delete failed (non-fatal): {e}")



async def transcribe_chunk(
    gcs_uri: str,
    chunk_index: int,
    start_offset_seconds: float,
    job_id: str,
    sample_rate: int = 16000,
) -> list[dict]:
    """
    Transcribe a single FLAC chunk and return words with absolute timestamps.

    Runs the full STT pipeline for one chunk:
        1. Submit BatchRecognize for this chunk's GCS URI.
        2. Poll to completion with retry.
        3. Parse word timestamps, add start_offset_seconds to each.
        4. Delete the chunk from GCS (cleanup).
        5. Return flat list of word dicts with absolute timestamps.

    Called concurrently via asyncio.gather() for all chunks.

    Args:
        gcs_uri:              GCS URI of the uploaded FLAC chunk.
        chunk_index:          Zero-based index — used for logging only.
        start_offset_seconds: Offset to add to all word timestamps. Equals
                              chunk_index * CHUNK_DURATION_SECONDS.
        job_id:               For logging.

    Returns:
        Flat list of word dicts: {word, startTime, endTime, speaker}.
        startTime and endTime are absolute (relative to start of full video).
    """
    client = get_speech_client()
    config = build_recognition_config(sample_rate=sample_rate)
    recognizer = f"projects/{PROJECT_ID}/locations/global/recognizers/_"

    request = cloud_speech.BatchRecognizeRequest(
        recognizer=recognizer,
        config=config,
        files=[cloud_speech.BatchRecognizeFileMetadata(uri=gcs_uri)],
        recognition_output_config=cloud_speech.RecognitionOutputConfig(
            inline_response_config=cloud_speech.InlineOutputConfig(),
        ),
    )

    logger.info(f"[{job_id}] Chunk {chunk_index}: submitting STT — offset +{start_offset_seconds:.0f}s")

    try:
        operation = client.batch_recognize(request=request)
    except GoogleAPICallError as e:
        logger.error(f"[{job_id}] Chunk {chunk_index}: STT submit failed: {e}")
        raise

    try:
        response = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: _poll_operation_with_retry(operation, job_id=f"{job_id}[chunk{chunk_index}]", timeout=3600),
        )
    except Exception as e:
        logger.error(f"[{job_id}] Chunk {chunk_index}: STT poll failed: {e}")
        raise RuntimeError(f"Chunk {chunk_index} STT failed: {e}") from e

    file_results = response.results.get(gcs_uri)
    if not file_results or not file_results.transcript:
        logger.warning(f"[{job_id}] Chunk {chunk_index}: no transcript in response")
        delete_chunk_from_gcs(job_id, chunk_index)
        return []

    raw_words = parse_transcript_response(file_results.transcript)

    # ── CRITICAL: Add chunk start offset to every word timestamp ──────────
    # STT timestamps are relative to the chunk's audio, not the full video.
    # Without this, all chunks would show timestamps starting near 0.
    words_with_offset = [
        {
            "word":      w["word"],
            "startTime": round(w["startTime"] + start_offset_seconds, 3),
            "endTime":   round(w["endTime"]   + start_offset_seconds, 3),
            "speaker":   w["speaker"],
        }
        for w in raw_words
    ]

    logger.info(
        f"[{job_id}] Chunk {chunk_index}: {len(words_with_offset)} words "
        f"(offset +{start_offset_seconds:.0f}s)"
    )

    delete_chunk_from_gcs(job_id, chunk_index)
    return words_with_offset



async def transcribe_chunked(
    video_path: str,
    job_id: str,
    sample_rate: int = 16000,
) -> list[dict]:
    """
    Full chunked STT pipeline for long videos.

    1. Split video audio into CHUNK_DURATION_SECONDS-length FLAC segments.
    2. Upload all chunks to GCS concurrently.
    3. Submit all BatchRecognize operations concurrently via asyncio.gather().
    4. Merge results in order, with corrected absolute timestamps.

    Uses a temporary directory for local chunk files — cleaned up automatically.

    Args:
        video_path: Local path to the downloaded video file.
        job_id:     For logging and GCS path construction.

    Returns:
        Flat list of word dicts with absolute timestamps, ordered by startTime.

    Raises:
        RuntimeError: If ALL chunks fail. Partial failures are tolerated
                      (missing chunk = gap in transcript, logged as warning).
    """
    with tempfile.TemporaryDirectory() as chunk_dir:
        # Step 1: split audio into FLAC chunks
        logger.info(f"[{job_id}] Chunked STT: splitting audio...")
        chunk_pairs = split_audio_to_chunks(video_path, chunk_dir, sample_rate)
        logger.info(f"[{job_id}] Chunked STT: {len(chunk_pairs)} chunks created")

        # Step 2: upload all chunks to GCS concurrently
        logger.info(f"[{job_id}] Chunked STT: uploading {len(chunk_pairs)} chunks to GCS...")
        upload_tasks = [
            asyncio.get_event_loop().run_in_executor(
                None, upload_chunk_to_gcs, chunk_path, job_id, i
            )
            for i, (chunk_path, _) in enumerate(chunk_pairs)
        ]
        gcs_uris = await asyncio.gather(*upload_tasks, return_exceptions=True)

        # Check for upload failures — a failed upload means that chunk is skipped
        valid_chunks = []
        for i, (uri_or_exc, (_, start_offset)) in enumerate(zip(gcs_uris, chunk_pairs)):
            if isinstance(uri_or_exc, Exception):
                logger.error(f"[{job_id}] Chunk {i} upload failed: {uri_or_exc} — skipping")
            else:
                valid_chunks.append((i, uri_or_exc, start_offset))

        if not valid_chunks:
            raise RuntimeError(f"[{job_id}] All {len(chunk_pairs)} chunk uploads failed")

        # Step 3: submit all STT operations concurrently
        logger.info(f"[{job_id}] Chunked STT: submitting {len(valid_chunks)} STT operations...")
        stt_tasks = [
            transcribe_chunk(gcs_uri, chunk_index, start_offset, job_id, sample_rate=sample_rate)
            for chunk_index, gcs_uri, start_offset in valid_chunks
        ]
        chunk_results = await asyncio.gather(*stt_tasks, return_exceptions=True)

    # Step 4: merge in chunk order, handle partial failures
    all_words = []
    failed_chunks = []
    for (chunk_index, _, start_offset), result in zip(valid_chunks, chunk_results):
        if isinstance(result, Exception):
            logger.error(f"[{job_id}] Chunk {chunk_index} STT failed: {result}")
            failed_chunks.append(chunk_index)
        else:
            all_words.extend(result)

    if failed_chunks:
        logger.warning(
            f"[{job_id}] Chunked STT partial failure — "
            f"{len(failed_chunks)} of {len(valid_chunks)} chunks failed: {failed_chunks}"
        )

    if not all_words and len(failed_chunks) == len(valid_chunks):
        raise RuntimeError(f"[{job_id}] All STT chunks failed — no transcript produced")

    logger.info(
        f"[{job_id}] Chunked STT complete — "
        f"{len(all_words)} words from {len(valid_chunks) - len(failed_chunks)} chunks"
    )
    return all_words







def parse_transcript_response(
    transcript: cloud_speech.BatchRecognizeResults,
) -> List[Dict[str, Any]]:
    if not transcript.results:
        logger.warning("Speech-to-Text returned empty results")
        return []

    word_timestamps = []

    for result in transcript.results:          # ← all results, not just last
        if not result.alternatives:
            continue
        for word_info in result.alternatives[0].words:
            word_timestamps.append({
                "word": word_info.word,
                "startTime": round(word_info.start_offset.total_seconds(), 3),
                "endTime": round(word_info.end_offset.total_seconds(), 3),
                "speaker": 1,
            })

    return word_timestamps


async def transcribe(
    gcs_uri: str,
    job_id: str = "unknown",
) -> list[dict]:
    """
    Transcribe a video file to a flat list of word-timestamp dicts.

    Public entry point called by orchestrator.py. Routing logic:
      - Short videos (≤ CHUNK_THRESHOLD_SECONDS): whole-file STT (existing path).
      - Long videos  (> CHUNK_THRESHOLD_SECONDS): parallel chunked STT (PERF-1).

    The split point is determined from the local video file duration using
    ffprobe. If ffprobe fails, falls back to whole-file path (safe default).

    The orchestrator sees the same output shape either way — a flat list of
    {word, startTime, endTime, speaker} dicts with absolute timestamps.

    Args:
        gcs_uri: GCS URI of the video file (gs://bucket/path/video.mp4).
        job_id:  For logging.

    Returns:
        Flat list of word dicts ordered by startTime.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        video_path = os.path.join(tmpdir, "video.mp4")

        # Step 1: download video from GCS
        logger.info(f"[{job_id}] Downloading video from GCS...")
        await asyncio.get_event_loop().run_in_executor(
            None, download_from_gcs, gcs_uri, video_path
        )

        # Step 2: check duration to decide whole-file vs chunked path
        duration = await asyncio.get_event_loop().run_in_executor(
            None, get_video_duration_seconds, video_path
        )
        logger.info(f"[{job_id}] Video duration: {duration:.1f}s — threshold: {CHUNK_THRESHOLD_SECONDS}s")

        # PERF-4: adaptive sample rate — 8kHz for long videos, 16kHz otherwise
        sample_rate = 8000 if duration > ADAPTIVE_FFMPEG_THRESHOLD_SECONDS else 16000
        if sample_rate == 8000:
            logger.info(f"[{job_id}] Long video ({duration/60:.1f} min) — using 8kHz extraction")

        # ── Chunked path for long videos ───────────────────────────────────
        if duration > CHUNK_THRESHOLD_SECONDS:
            logger.info(f"[{job_id}] Using PARALLEL CHUNKED STT ({duration:.0f}s video)")
            return await transcribe_chunked(video_path, job_id, sample_rate=sample_rate)

        # ── Whole-file path for short videos ──────────────────────────────
        logger.info(f"[{job_id}] Using whole-file STT ({duration:.0f}s video)")

        flac_path = os.path.join(tmpdir, "audio.flac")

        logger.info(f"[{job_id}] Extracting audio to FLAC...")
        await asyncio.get_event_loop().run_in_executor(
            None, extract_audio_to_flac, video_path, flac_path, sample_rate
        )

        logger.info(f"[{job_id}] Uploading FLAC to GCS...")
        flac_gcs_uri = await asyncio.get_event_loop().run_in_executor(
            None, upload_flac_to_gcs, flac_path, job_id
        )

    # Step 3 — STT (outside tempdir so local files are cleaned up)
    # ... rest of function unchanged from here ...
MAX_RETRIES = 2
RETRY_BACKOFF_SECONDS = 5


def _poll_operation_with_retry(operation, job_id: str, timeout: int = 1800):
    """
    Poll a long-running GCP operation to completion with retry on transient errors.

    Retries up to MAX_RETRIES times on ServiceUnavailable or DeadlineExceeded.
    Raises immediately on any other exception — these are permanent failures.

    Args:
        operation: A long-running GCP operation object with a .result() method.
        job_id: For logging.
        timeout: Per-attempt timeout in seconds.

    Returns:
        The operation result.

    Raises:
        RuntimeError: After all retries exhausted.
        Exception: On non-retryable errors.
    """
    last_exception = None

    for attempt in range(1, MAX_RETRIES + 2):  # +2 = initial attempt + MAX_RETRIES
        try:
            return operation.result(timeout=timeout)
        except (ServiceUnavailable, DeadlineExceeded) as e:
            last_exception = e
            if attempt <= MAX_RETRIES:
                backoff = RETRY_BACKOFF_SECONDS * attempt
                logger.warning(
                    f"[{job_id}] Operation poll attempt {attempt} failed: {e}. "
                    f"Retrying in {backoff}s..."
                )
                time_module.sleep(backoff)
            else:
                logger.error(
                    f"[{job_id}] Operation poll failed after {MAX_RETRIES} retries: {e}"
                )
        except Exception as e:
            # Non-retryable — raise immediately
            logger.error(f"[{job_id}] Non-retryable operation error: {e}")
            raise

    raise RuntimeError(
        f"[{job_id}] Operation failed after {MAX_RETRIES} retries. "
        f"Last error: {last_exception}"
    )