"""
Unit Tests for Pipeline Speed Refactor — All Four Changes
==========================================================

Tests for:
  Change 1 — _run_gemini_scenes() in orchestrator.py
  Change 2 — thumbnail bytes threaded out of transcribe()
  Change 3 — CHUNK_DURATION_SECONDS = 600 in speech_to_text.py
  Change 4 — conditional LABEL_DETECTION in analyse_video()

All GCP client calls are mocked — no real API calls are made.

Run with:
    pytest worker/tests/test_pipeline_fixes.py -v

Validates: Requirements 2.1, 2.2, 2.3, 2.4
"""

import asyncio
import json
import os
import sys

# Set required env vars before importing pipeline modules
os.environ.setdefault("GCP_PROJECT_ID", "test-project")
os.environ.setdefault("GCP_BUCKET_NAME", "test-bucket")
os.environ.setdefault("GCP_SERVICE_ACCOUNT_EMAIL", "test@test.iam.gserviceaccount.com")

import pytest
from unittest.mock import patch, MagicMock, call


# ---------------------------------------------------------------------------
# Change 1 — _run_gemini_scenes()
# ---------------------------------------------------------------------------

class TestRunGeminiScenes:
    """
    Tests for the new _run_gemini_scenes() function in orchestrator.py.

    Validates: Requirements 2.1, 3.1, 3.10
    """

    def test_run_gemini_scenes_output_shape(self):
        """
        Mock Gemini client to return a valid scene list.
        Assert the returned list has the correct dict shape:
        each item must have 'startTime' (float), 'endTime' (float), 'labels' (list).

        Validates: Requirements 2.1, 3.1
        """
        from pipeline.orchestrator import _run_gemini_scenes

        mock_scenes = [
            {"startTime": 0.0, "endTime": 12.5, "labels": ["presenter speaking", "slide visible"]},
            {"startTime": 12.5, "endTime": 30.0, "labels": ["outdoor", "walking"]},
        ]

        mock_response = MagicMock()
        mock_response.text = json.dumps(mock_scenes)

        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response

        with patch("pipeline.orchestrator.get_gemini_client", return_value=mock_client):
            result = asyncio.run(_run_gemini_scenes(
                "gs://test-bucket/raw-videos/job-001/video.mp4",
                "job-001",
            ))

        assert isinstance(result, list), "Result must be a list"
        assert len(result) == 2

        for scene in result:
            assert "startTime" in scene, f"Scene missing 'startTime': {scene}"
            assert "endTime" in scene, f"Scene missing 'endTime': {scene}"
            assert "labels" in scene, f"Scene missing 'labels': {scene}"
            assert isinstance(scene["startTime"], float), "'startTime' must be float"
            assert isinstance(scene["endTime"], float), "'endTime' must be float"
            assert isinstance(scene["labels"], list), "'labels' must be list"

    def test_run_gemini_scenes_empty_on_exception(self):
        """
        Mock Gemini client to raise an exception.
        Assert that _run_gemini_scenes returns [] (same failure behaviour as VI path).

        Validates: Requirements 2.1
        """
        from pipeline.orchestrator import _run_gemini_scenes

        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = RuntimeError("Gemini API unavailable")

        with patch("pipeline.orchestrator.get_gemini_client", return_value=mock_client):
            result = asyncio.run(_run_gemini_scenes(
                "gs://test-bucket/raw-videos/job-002/video.mp4",
                "job-002",
            ))

        assert result == [], (
            f"Expected [] on exception, got {result!r}"
        )

    def test_run_gemini_scenes_caps_at_50(self):
        """
        Mock Gemini to return 60 scenes.
        Assert len(output) == 50 (cap enforced by scenes[:50]).

        Validates: Requirements 2.1, 3.10
        """
        from pipeline.orchestrator import _run_gemini_scenes

        # Build 60 scenes
        mock_scenes = [
            {"startTime": float(i * 10), "endTime": float((i + 1) * 10), "labels": [f"label_{i}"]}
            for i in range(60)
        ]

        mock_response = MagicMock()
        mock_response.text = json.dumps(mock_scenes)

        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response

        with patch("pipeline.orchestrator.get_gemini_client", return_value=mock_client):
            result = asyncio.run(_run_gemini_scenes(
                "gs://test-bucket/raw-videos/job-003/video.mp4",
                "job-003",
            ))

        assert len(result) == 50, (
            f"Expected 50 scenes (cap), got {len(result)}"
        )


# ---------------------------------------------------------------------------
# Change 2 — transcribe() with extract_thumbnail
# ---------------------------------------------------------------------------

class TestTranscribeExtractThumbnail:
    """
    Tests for the extract_thumbnail parameter added to transcribe().

    Validates: Requirements 2.3, 3.5
    """

    def test_transcribe_extract_thumbnail_true(self):
        """
        When extract_thumbnail=True, transcribe() must return tuple[list, bytes].
        Mock ffmpeg, ffprobe, and all GCP calls.

        Validates: Requirements 2.3
        """
        from pipeline.speech_to_text import transcribe

        fake_thumb_bytes = b"\xff\xd8\xff\xe0fake_jpeg_bytes"

        # Mock the whole-file path: short video (duration <= CHUNK_THRESHOLD_SECONDS)
        with (
            patch("pipeline.speech_to_text.download_from_gcs"),
            patch("pipeline.speech_to_text.get_video_duration_seconds", return_value=30.0),
            patch("pipeline.speech_to_text._extract_thumbnail_bytes", return_value=fake_thumb_bytes),
            patch("pipeline.speech_to_text.extract_audio_to_flac"),
            patch("pipeline.speech_to_text.upload_flac_to_gcs",
                  return_value="gs://test-bucket/processed/job-004/audio.flac"),
            patch("pipeline.speech_to_text.get_speech_client") as mock_speech_client,
            patch("pipeline.speech_to_text.write_processed_json"),
        ):
            # Build a mock STT response
            mock_word = MagicMock()
            mock_word.word = "hello"
            mock_word.start_offset.total_seconds.return_value = 0.0
            mock_word.end_offset.total_seconds.return_value = 0.5

            mock_alternative = MagicMock()
            mock_alternative.words = [mock_word]

            mock_result = MagicMock()
            mock_result.alternatives = [mock_alternative]

            mock_transcript = MagicMock()
            mock_transcript.results = [mock_result]

            mock_file_result = MagicMock()
            mock_file_result.transcript = mock_transcript

            mock_response = MagicMock()
            mock_response.results = {
                "gs://test-bucket/processed/job-004/audio.flac": mock_file_result
            }

            mock_operation = MagicMock()
            mock_operation.result.return_value = mock_response

            mock_client_instance = MagicMock()
            mock_client_instance.batch_recognize.return_value = mock_operation
            mock_speech_client.return_value = mock_client_instance

            result = asyncio.run(transcribe(
                "gs://test-bucket/raw-videos/job-004/video.mp4",
                job_id="job-004",
                extract_thumbnail=True,
            ))

        assert isinstance(result, tuple), (
            f"Expected tuple when extract_thumbnail=True, got {type(result)}"
        )
        assert len(result) == 2, f"Expected 2-tuple, got {len(result)}-tuple"
        word_list, thumb = result
        assert isinstance(word_list, list), f"First element must be list, got {type(word_list)}"
        assert isinstance(thumb, bytes), f"Second element must be bytes, got {type(thumb)}"

    def test_transcribe_extract_thumbnail_false(self):
        """
        When extract_thumbnail=False (default), transcribe() must return list[dict]
        — backward compatible, NOT a tuple.

        Validates: Requirements 3.5
        """
        from pipeline.speech_to_text import transcribe

        with (
            patch("pipeline.speech_to_text.download_from_gcs"),
            patch("pipeline.speech_to_text.get_video_duration_seconds", return_value=30.0),
            patch("pipeline.speech_to_text.extract_audio_to_flac"),
            patch("pipeline.speech_to_text.upload_flac_to_gcs",
                  return_value="gs://test-bucket/processed/job-005/audio.flac"),
            patch("pipeline.speech_to_text.get_speech_client") as mock_speech_client,
            patch("pipeline.speech_to_text.write_processed_json"),
        ):
            mock_word = MagicMock()
            mock_word.word = "world"
            mock_word.start_offset.total_seconds.return_value = 0.0
            mock_word.end_offset.total_seconds.return_value = 0.4

            mock_alternative = MagicMock()
            mock_alternative.words = [mock_word]

            mock_result = MagicMock()
            mock_result.alternatives = [mock_alternative]

            mock_transcript = MagicMock()
            mock_transcript.results = [mock_result]

            mock_file_result = MagicMock()
            mock_file_result.transcript = mock_transcript

            mock_response = MagicMock()
            mock_response.results = {
                "gs://test-bucket/processed/job-005/audio.flac": mock_file_result
            }

            mock_operation = MagicMock()
            mock_operation.result.return_value = mock_response

            mock_client_instance = MagicMock()
            mock_client_instance.batch_recognize.return_value = mock_operation
            mock_speech_client.return_value = mock_client_instance

            result = asyncio.run(transcribe(
                "gs://test-bucket/raw-videos/job-005/video.mp4",
                job_id="job-005",
                extract_thumbnail=False,
            ))

        assert isinstance(result, list), (
            f"Expected list when extract_thumbnail=False, got {type(result)}"
        )
        # Must NOT be a tuple
        assert not isinstance(result, tuple), (
            "Return value must be a plain list, not a tuple, when extract_thumbnail=False"
        )
        # Each element must be a dict
        for item in result:
            assert isinstance(item, dict), f"Each word must be a dict, got {type(item)}"


# ---------------------------------------------------------------------------
# Change 2 — _upload_thumbnail_bytes() does NOT call download_from_gcs
# ---------------------------------------------------------------------------

class TestUploadThumbnailBytes:
    """
    Tests for the new _upload_thumbnail_bytes() helper in orchestrator.py.

    Validates: Requirements 2.3
    """

    def test_upload_thumbnail_bytes_no_download(self):
        """
        Assert download_from_gcs is NOT called when _upload_thumbnail_bytes() is used.
        The function must write bytes directly to GCS via blob.upload_from_string().

        Validates: Requirements 2.3
        """
        from pipeline.orchestrator import _upload_thumbnail_bytes

        fake_thumb_bytes = b"\xff\xd8\xff\xe0fake_jpeg_bytes"

        mock_blob = MagicMock()
        mock_bucket = MagicMock()
        mock_bucket.blob.return_value = mock_blob
        mock_gcs_client = MagicMock()
        mock_gcs_client.bucket.return_value = mock_bucket

        with (
            patch("pipeline.orchestrator.gcs_storage.Client", return_value=mock_gcs_client),
            patch("pipeline.orchestrator.BUCKET_NAME", "test-bucket"),
            patch("pipeline.orchestrator.download_from_gcs") as mock_download,
        ):
            result = asyncio.run(_upload_thumbnail_bytes(fake_thumb_bytes, "job-006"))

        # download_from_gcs must NOT be called
        mock_download.assert_not_called(), (
            "download_from_gcs MUST NOT be called inside _upload_thumbnail_bytes(). "
            "Bytes are uploaded directly via blob.upload_from_string()."
        )

        # upload_from_string must be called with the bytes
        mock_blob.upload_from_string.assert_called_once_with(
            fake_thumb_bytes, content_type="image/jpeg"
        )

        # Should return the GCS path
        assert result == "processed/job-006/thumbnail.jpg", (
            f"Expected GCS path 'processed/job-006/thumbnail.jpg', got {result!r}"
        )


# ---------------------------------------------------------------------------
# Change 4 — analyse_video() conditional LABEL_DETECTION
# ---------------------------------------------------------------------------

class TestAnalyseVideoLabelDetection:
    """
    Tests for the duration_seconds parameter added to analyse_video().

    Validates: Requirements 2.2, 3.7
    """

    def test_analyse_video_long_video_skips_label_detection(self):
        """
        Call analyse_video() with duration_seconds=3600 (> 1800).
        Assert LABEL_DETECTION is NOT in the features passed to annotate_video().

        Validates: Requirements 2.2
        """
        # Mock the videointelligence module before importing analyse_video
        mock_vi_module = MagicMock()

        # Create real-ish Feature enum values so we can check membership
        class FakeFeature:
            SHOT_CHANGE_DETECTION = "SHOT_CHANGE_DETECTION"
            LABEL_DETECTION = "LABEL_DETECTION"

        mock_vi_module.Feature = FakeFeature
        mock_vi_module.LabelDetectionConfig = MagicMock()
        mock_vi_module.LabelDetectionMode = MagicMock()
        mock_vi_module.VideoContext = MagicMock()

        captured_requests = []

        def fake_annotate_video(request):
            captured_requests.append(dict(request))
            mock_operation = MagicMock()
            mock_shot = MagicMock()
            mock_shot.start_time_offset.seconds = 0
            mock_shot.start_time_offset.microseconds = 0
            mock_shot.end_time_offset.seconds = 10
            mock_shot.end_time_offset.microseconds = 0

            mock_annotation_result = MagicMock()
            mock_annotation_result.shot_annotations = [mock_shot]
            mock_annotation_result.shot_label_annotations = []
            mock_annotation_result.segment_label_annotations = []

            mock_result = MagicMock()
            mock_result.annotation_results = [mock_annotation_result]
            mock_operation.result.return_value = mock_result
            return mock_operation

        mock_client = MagicMock()
        mock_client.annotate_video.side_effect = fake_annotate_video

        with (
            patch("pipeline.video_intelligence.get_video_client", return_value=mock_client),
            patch("pipeline.video_intelligence.write_processed_json"),
            patch("pipeline.video_intelligence.videointelligence", mock_vi_module),
        ):
            from pipeline.video_intelligence import analyse_video
            asyncio.run(analyse_video(
                "gs://test-bucket/raw-videos/job-007/video.mp4",
                job_id="job-007",
                duration_seconds=3600,
            ))

        assert len(captured_requests) == 1, "annotate_video should be called once"
        features_used = captured_requests[0]["features"]

        assert FakeFeature.LABEL_DETECTION not in features_used, (
            f"LABEL_DETECTION must NOT be in features for duration_seconds=3600. "
            f"Got features: {features_used}"
        )
        assert FakeFeature.SHOT_CHANGE_DETECTION in features_used, (
            "SHOT_CHANGE_DETECTION must still be present for long videos"
        )

    def test_analyse_video_short_video_includes_label_detection(self):
        """
        Call analyse_video() with duration_seconds=600 (<= 1800).
        Assert LABEL_DETECTION IS in the features passed to annotate_video().

        Validates: Requirements 2.2, 3.7
        """
        mock_vi_module = MagicMock()

        class FakeFeature:
            SHOT_CHANGE_DETECTION = "SHOT_CHANGE_DETECTION"
            LABEL_DETECTION = "LABEL_DETECTION"

        mock_vi_module.Feature = FakeFeature
        mock_vi_module.LabelDetectionConfig = MagicMock(return_value=MagicMock())
        mock_vi_module.LabelDetectionMode = MagicMock()
        mock_vi_module.VideoContext = MagicMock(return_value=MagicMock())

        captured_requests = []

        def fake_annotate_video(request):
            captured_requests.append(dict(request))
            mock_operation = MagicMock()
            mock_shot = MagicMock()
            mock_shot.start_time_offset.seconds = 0
            mock_shot.start_time_offset.microseconds = 0
            mock_shot.end_time_offset.seconds = 10
            mock_shot.end_time_offset.microseconds = 0

            mock_annotation_result = MagicMock()
            mock_annotation_result.shot_annotations = [mock_shot]
            mock_annotation_result.shot_label_annotations = []
            mock_annotation_result.segment_label_annotations = []

            mock_result = MagicMock()
            mock_result.annotation_results = [mock_annotation_result]
            mock_operation.result.return_value = mock_result
            return mock_operation

        mock_client = MagicMock()
        mock_client.annotate_video.side_effect = fake_annotate_video

        with (
            patch("pipeline.video_intelligence.get_video_client", return_value=mock_client),
            patch("pipeline.video_intelligence.write_processed_json"),
            patch("pipeline.video_intelligence.videointelligence", mock_vi_module),
        ):
            from pipeline.video_intelligence import analyse_video
            asyncio.run(analyse_video(
                "gs://test-bucket/raw-videos/job-008/video.mp4",
                job_id="job-008",
                duration_seconds=600,
            ))

        assert len(captured_requests) == 1, "annotate_video should be called once"
        features_used = captured_requests[0]["features"]

        assert FakeFeature.LABEL_DETECTION in features_used, (
            f"LABEL_DETECTION must be in features for duration_seconds=600. "
            f"Got features: {features_used}"
        )
        assert FakeFeature.SHOT_CHANGE_DETECTION in features_used, (
            "SHOT_CHANGE_DETECTION must be present for short videos"
        )


# ---------------------------------------------------------------------------
# Change 3 — CHUNK_DURATION_SECONDS constant
# ---------------------------------------------------------------------------

class TestChunkDurationConstants:
    """
    Tests for the CHUNK_DURATION_SECONDS and CHUNK_THRESHOLD_SECONDS constants
    in speech_to_text.py.

    Validates: Requirements 2.4, 3.6
    """

    def test_chunk_duration_constant(self):
        """
        Assert CHUNK_DURATION_SECONDS == 600.
        This was changed from 300 to halve the number of GCS uploads and
        BatchRecognize operations for long videos.

        Validates: Requirements 2.4
        """
        import pipeline.speech_to_text as stt_module

        assert stt_module.CHUNK_DURATION_SECONDS == 600, (
            f"CHUNK_DURATION_SECONDS must be 600, got {stt_module.CHUNK_DURATION_SECONDS}. "
            f"A 2-hour video (7200s) would produce "
            f"{7200 // stt_module.CHUNK_DURATION_SECONDS} chunks instead of 12."
        )

    def test_chunk_threshold_tied_to_duration(self):
        """
        Assert CHUNK_THRESHOLD_SECONDS == CHUNK_DURATION_SECONDS.
        The threshold must move with the chunk duration constant so that
        short-video detection stays consistent with chunk sizing.

        Validates: Requirements 2.4, 3.6
        """
        import pipeline.speech_to_text as stt_module

        assert stt_module.CHUNK_THRESHOLD_SECONDS == stt_module.CHUNK_DURATION_SECONDS, (
            f"CHUNK_THRESHOLD_SECONDS ({stt_module.CHUNK_THRESHOLD_SECONDS}) must equal "
            f"CHUNK_DURATION_SECONDS ({stt_module.CHUNK_DURATION_SECONDS}). "
            f"The threshold must be tied to the chunk duration constant."
        )
