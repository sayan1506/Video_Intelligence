import json
import logging
import os
import asyncio
import tempfile
import subprocess
from typing import List, Dict, Any
import time as time_module

from google.cloud.speech_v2 import SpeechClient
from google.cloud.speech_v2.types import cloud_speech
from google.api_core.exceptions import GoogleAPICallError
from google.cloud import storage as gcs_storage
from google.api_core.exceptions import ServiceUnavailable, DeadlineExceeded

from services.storage import write_processed_json

logger = logging.getLogger(__name__)

PROJECT_ID = os.getenv("GCP_PROJECT_ID", "video-intelligence-v1")
BUCKET_NAME = os.getenv("GCP_BUCKET_NAME", "video-intelligence-raw")
FFMPEG_PATH = r"C:\Program Files\DownloadHelper CoApp\ffmpeg.exe"


def get_speech_client() -> SpeechClient:
    return SpeechClient()


def build_recognition_config() -> cloud_speech.RecognitionConfig:
    return cloud_speech.RecognitionConfig(
        explicit_decoding_config=cloud_speech.ExplicitDecodingConfig(
            encoding=cloud_speech.ExplicitDecodingConfig.AudioEncoding.FLAC,
            sample_rate_hertz=16000,
            audio_channel_count=1,
        ),
        language_codes=["hi-IN", "en-US"],
        model="long",
        features=cloud_speech.RecognitionFeatures(
            enable_word_time_offsets=True,
            enable_automatic_punctuation=True,
        ),
    )


def extract_audio_to_flac(video_path: str, output_path: str) -> None:
    """Extract audio from video file to mono 16kHz FLAC using ffmpeg."""
    cmd = [
        FFMPEG_PATH,
        "-i", video_path,
        "-vn",              # no video
        "-ac", "1",         # mono
        "-ar", "16000",     # 16kHz sample rate
        "-f", "flac",       # FLAC format
        "-y",               # overwrite output
        output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {result.stderr}")
    logger.info(f"Audio extracted to {output_path}")


def download_from_gcs(gcs_uri: str, local_path: str) -> None:
    """Download a GCS object to a local path."""
    # Parse gs://bucket/path
    without_prefix = gcs_uri[5:]
    bucket_name, blob_path = without_prefix.split("/", 1)
    client = gcs_storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_path)
    blob.download_to_filename(local_path)
    logger.info(f"Downloaded {gcs_uri} to {local_path}")


def upload_flac_to_gcs(local_path: str, job_id: str) -> str:
    """Upload extracted FLAC to GCS, return GCS URI."""
    client = gcs_storage.Client()
    bucket = client.bucket(BUCKET_NAME)
    gcs_path = f"processed/{job_id}/audio.flac"
    blob = bucket.blob(gcs_path)
    blob.upload_from_filename(local_path, content_type="audio/flac")
    gcs_uri = f"gs://{BUCKET_NAME}/{gcs_path}"
    logger.info(f"Uploaded FLAC to {gcs_uri}")
    return gcs_uri


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
) -> List[Dict[str, Any]]:
    client = get_speech_client()

    # Step 1 — download video, extract audio to FLAC, upload FLAC to GCS
    with tempfile.TemporaryDirectory() as tmpdir:
        video_path = os.path.join(tmpdir, "video.mp4")
        flac_path = os.path.join(tmpdir, "audio.flac")

        logger.info(f"[{job_id}] Downloading video from GCS...")
        await asyncio.get_event_loop().run_in_executor(
            None, download_from_gcs, gcs_uri, video_path
        )

        logger.info(f"[{job_id}] Extracting audio to FLAC...")
        await asyncio.get_event_loop().run_in_executor(
            None, extract_audio_to_flac, video_path, flac_path
        )

        logger.info(f"[{job_id}] Uploading FLAC to GCS...")
        flac_gcs_uri = await asyncio.get_event_loop().run_in_executor(
            None, upload_flac_to_gcs, flac_path, job_id
        )

    # Step 2 — send FLAC GCS URI to Speech-to-Text
    config = build_recognition_config()
    recognizer = f"projects/{PROJECT_ID}/locations/global/recognizers/_"

    request = cloud_speech.BatchRecognizeRequest(
        recognizer=recognizer,
        config=config,
        files=[cloud_speech.BatchRecognizeFileMetadata(uri=flac_gcs_uri)],
        recognition_output_config=cloud_speech.RecognitionOutputConfig(
            inline_response_config=cloud_speech.InlineOutputConfig(),
        ),
    )

    logger.info(f"[{job_id}] STT v2: Starting BatchRecognize — uri: {flac_gcs_uri}")

    try:
        operation = client.batch_recognize(request=request)
    except GoogleAPICallError as e:
        logger.error(f"[{job_id}] STT v2: Failed to start operation: {e}")
        raise

    logger.info(f"[{job_id}] STT v2: Polling for completion...")

    try:
        response = _poll_operation_with_retry(operation, job_id=job_id, timeout=600)
    except Exception as e:
        logger.error(f"[{job_id}] STT v2: Operation failed: {e}")
        raise RuntimeError(f"Speech-to-Text operation failed: {e}") from e

    logger.info(f"[{job_id}] STT v2: Complete — parsing response")

    file_results = response.results.get(flac_gcs_uri)
    if not file_results or not file_results.transcript:
        logger.warning(f"[{job_id}] STT v2: No transcript in response")
        return []

    word_timestamps = parse_transcript_response(file_results.transcript)
    logger.info(f"[{job_id}] STT v2: Parsed {len(word_timestamps)} words")

    # Write raw output to GCS
    try:
        raw_output = {
            "results": [
                {
                    "alternatives": [
                        {
                            "transcript": alt.transcript,
                            "confidence": alt.confidence,
                            "words": [
                                {
                                    "word": w.word,
                                    "startTime": w.start_offset.total_seconds(),
                                    "endTime": w.end_offset.total_seconds(),
                                }
                                for w in alt.words
                            ],
                        }
                        for alt in result.alternatives
                    ]
                }
                for result in file_results.transcript.results
            ]
        }
        await write_processed_json(job_id, "transcript.json", raw_output)
        logger.info(f"[{job_id}] STT v2: Raw output written to GCS")
    except Exception as e:
        logger.warning(f"[{job_id}] STT v2: Failed to write raw output (non-fatal): {e}")

    return word_timestamps



MAX_RETRIES = 2
RETRY_BACKOFF_SECONDS = 5


def _poll_operation_with_retry(operation, job_id: str, timeout: int = 600):
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