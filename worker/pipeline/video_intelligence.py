
import logging
from typing import List, Dict, Any
import time as time_module
from google.api_core.exceptions import ServiceUnavailable, DeadlineExceeded
from google.cloud import videointelligence_v1 as videointelligence

logger = logging.getLogger(__name__)

# Maximum number of labels to attach per scene.
# The API can return dozens per segment — cap for V1 cleanliness.
MAX_LABELS_PER_SCENE = 10

# Minimum confidence score to include a label.
# Below 0.6 tends to produce noisy, low-value labels.
LABEL_CONFIDENCE_THRESHOLD = 0.6


def get_video_client() -> videointelligence.VideoIntelligenceServiceClient:
    """Return a Video Intelligence client using ADC."""
    return videointelligence.VideoIntelligenceServiceClient()


def _seconds_from_offset(offset) -> float:
    """
    Convert a protobuf Duration offset to total seconds as a float.

    The Video Intelligence API returns time offsets as protobuf Duration objects
    with .seconds and .microseconds fields — not plain Python floats.
    Note: the STT pipeline uses a similar conversion but on different proto types.
    """
    return round(offset.seconds + offset.microseconds / 1_000_000, 2)


def _find_labels_for_shot(
    shot_start: float,
    shot_end: float,
    segment_labels: list,
    shot_labels: list,
) -> List[str]:
    """
    Find all label annotations that overlap a given shot time range.

    The Video Intelligence API returns labels at two granularities:
      - segment_labels: broad context labels over large time spans
      - shot_labels:    precise labels tied to individual shots

    Both sources are combined, deduplicated by taking the highest confidence
    score per label, filtered by LABEL_CONFIDENCE_THRESHOLD, and the top
    MAX_LABELS_PER_SCENE are returned sorted by confidence descending.

    Args:
        shot_start: Shot start in seconds.
        shot_end: Shot end in seconds.
        segment_labels: annotation_result.segment_label_annotations
        shot_labels: annotation_result.shot_label_annotations

    Returns:
        List of label description strings, highest confidence first.
    """
    label_scores: Dict[str, float] = {}

    def accumulate(label_list):
        for label in label_list:
            for segment in label.segments:
                seg_start = _seconds_from_offset(segment.segment.start_time_offset)
                seg_end = _seconds_from_offset(segment.segment.end_time_offset)

                # Interval overlap: A overlaps B iff A.start < B.end AND A.end > B.start
                if seg_start < shot_end and seg_end > shot_start:
                    conf = segment.confidence
                    if conf >= LABEL_CONFIDENCE_THRESHOLD:
                        desc = label.entity.description.lower()
                        # Keep the highest confidence if label appears in multiple segments
                        label_scores[desc] = max(label_scores.get(desc, 0.0), conf)

    accumulate(shot_labels)
    accumulate(segment_labels)

    sorted_labels = sorted(label_scores.items(), key=lambda x: x[1], reverse=True)
    return [lbl for lbl, _ in sorted_labels[:MAX_LABELS_PER_SCENE]]


async def analyse_video(
    gcs_uri: str,
    job_id: str = "unknown",
) -> List[Dict[str, Any]]:
    """
    Analyse a video using the GCP Video Intelligence API.

    Submits SHOT_CHANGE_DETECTION + LABEL_DETECTION in a single API call.
    The API reads directly from the GCS URI — no download or audio extraction
    needed (contrast with the STT pipeline which requires ffmpeg).

    The operation is long-running (30–90s for a 3-min video). The orchestrator
    runs this concurrently with transcribe() via asyncio.gather() — both block
    their respective threads but run in parallel at the OS level.

    Args:
        gcs_uri: Full GCS URI of the original uploaded video.
                 e.g. gs://video-intelligence-raw/raw-videos/{jobId}/video.mp4
                 This is JobMessage.gcsUri — use it directly.
        job_id: For logging and GCS raw output path.

    Returns:
        List of Scene dicts matching worker/models/schemas.py Scene shape:
            startTime (float): seconds
            endTime (float): seconds
            labels (List[str]): sorted by confidence descending

    Raises:
        RuntimeError: On API submission or polling failure.
    """
    client = get_video_client()

    features = [
        videointelligence.Feature.SHOT_CHANGE_DETECTION,
        videointelligence.Feature.LABEL_DETECTION,
    ]

    label_config = videointelligence.LabelDetectionConfig(
        label_detection_mode=videointelligence.LabelDetectionMode.SHOT_AND_FRAME_MODE,
    )

    video_context = videointelligence.VideoContext(
        label_detection_config=label_config,
    )

    logger.info(f"[{job_id}] Submitting Video Intelligence job — {gcs_uri}")

    operation = client.annotate_video(
        request={
            "features": features,
            "input_uri": gcs_uri,
            "video_context": video_context,
        }
    )

    logger.info(f"[{job_id}] Video Intelligence operation started — polling...")

    try:
        # Blocking poll — 10-minute timeout covers V1's max video length
        result = _poll_operation_with_retry(operation, job_id=job_id, timeout=600)
    except Exception as e:
        logger.error(f"[{job_id}] Video Intelligence operation failed: {e}")
        raise RuntimeError(f"Video Intelligence API failed: {e}") from e

    annotation_result = result.annotation_results[0]
    shot_annotations = annotation_result.shot_annotations
    shot_label_annotations = annotation_result.shot_label_annotations
    segment_label_annotations = annotation_result.segment_label_annotations

    logger.info(
        f"[{job_id}] Raw — "
        f"shots: {len(shot_annotations)}, "
        f"shot labels: {len(shot_label_annotations)}, "
        f"segment labels: {len(segment_label_annotations)}"
    )

    # Build Scene list from shot boundaries + matched labels
    scenes: List[Dict[str, Any]] = []

    for shot in shot_annotations:
        start_time = _seconds_from_offset(shot.start_time_offset)
        end_time = _seconds_from_offset(shot.end_time_offset)

        labels = _find_labels_for_shot(
            shot_start=start_time,
            shot_end=end_time,
            segment_labels=segment_label_annotations,
            shot_labels=shot_label_annotations,
        )

        scenes.append({
            "startTime": start_time,
            "endTime": end_time,
            "labels": labels,
        })

    logger.info(f"[{job_id}] Parsed {len(scenes)} scenes from {len(shot_annotations)} shots")

    # Persist raw API response to GCS for debugging and potential reprocessing
    # Uses the write_processed_json() helper already in worker/services/storage.py
    try:
        from services.storage import write_processed_json
        raw_data = _serialise_raw_response(annotation_result)
        raw_path = await write_processed_json(job_id, "video_intelligence.json", raw_data)
        logger.info(f"[{job_id}] Raw output → {raw_path}")
    except Exception as e:
        logger.warning(f"[{job_id}] Failed to write raw Video Intelligence output: {e}")

    return scenes


def _serialise_raw_response(annotation_result) -> dict:
    """
    Convert the raw Video Intelligence API response to a JSON-serialisable dict.
    Proto objects can't be directly JSON-serialised — extract to plain Python types.
    Written to processed/{jobId}/video_intelligence.json.
    """
    shots = [
        {
            "startTime": _seconds_from_offset(shot.start_time_offset),
            "endTime": _seconds_from_offset(shot.end_time_offset),
        }
        for shot in annotation_result.shot_annotations
    ]

    segment_labels = [
        {
            "description": label.entity.description,
            "confidence": round(seg.confidence, 4),
            "startTime": _seconds_from_offset(seg.segment.start_time_offset),
            "endTime": _seconds_from_offset(seg.segment.end_time_offset),
        }
        for label in annotation_result.segment_label_annotations
        for seg in label.segments
    ]

    shot_labels = [
        {
            "description": label.entity.description,
            "confidence": round(seg.confidence, 4),
            "startTime": _seconds_from_offset(seg.segment.start_time_offset),
            "endTime": _seconds_from_offset(seg.segment.end_time_offset),
        }
        for label in annotation_result.shot_label_annotations
        for seg in label.segments
    ]

    return {
        "shots": shots,
        "segmentLabels": segment_labels,
        "shotLabels": shot_labels,
    }









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