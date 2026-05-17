# worker/tests/test_transcribe_chunked_sample_rate.py
"""
Unit tests for transcribe_chunked sample_rate parameter threading.

Validates:
- Req 4.1: transcribe_chunked accepts sample_rate with default 16000
- Req 4.2: transcribe_chunked passes sample_rate to split_audio_to_chunks
- Req 4.5: transcribe_chunked uses sample_rate in ExplicitDecodingConfig for each chunk
- Req 5.3: split_audio_to_chunks defaults to 16000 Hz when no explicit sample_rate
"""

import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock

import pytest_asyncio


# We need to mock environment variables before importing the module
@pytest.fixture(autouse=True)
def mock_env(monkeypatch):
    """Set required environment variables for the speech_to_text module."""
    monkeypatch.setenv("GCP_PROJECT_ID", "test-project")
    monkeypatch.setenv("GCP_BUCKET_NAME", "test-bucket")


@pytest.fixture
def mock_split_audio():
    """Mock split_audio_to_chunks to return fake chunk pairs."""
    with patch("pipeline.speech_to_text.split_audio_to_chunks") as mock:
        mock.return_value = [
            ("/tmp/chunks/chunk_000.flac", 0.0),
            ("/tmp/chunks/chunk_001.flac", 300.0),
        ]
        yield mock


@pytest.fixture
def mock_upload_chunk():
    """Mock upload_chunk_to_gcs to return fake GCS URIs."""
    with patch("pipeline.speech_to_text.upload_chunk_to_gcs") as mock:
        def side_effect(local_path, job_id, chunk_index):
            return f"gs://test-bucket/processed/{job_id}/chunks/chunk_{chunk_index:03d}.flac"
        mock.side_effect = side_effect
        yield mock


@pytest.fixture
def mock_transcribe_chunk():
    """Mock transcribe_chunk to return empty word lists."""
    with patch("pipeline.speech_to_text.transcribe_chunk") as mock:
        async def side_effect(*args, **kwargs):
            return [{"word": "hello", "startTime": 0.0, "endTime": 0.5, "speaker": 1}]
        mock.side_effect = side_effect
        yield mock


class TestTranscribeChunkedSampleRatePropagation:
    """Tests that sample_rate is correctly passed to split_audio_to_chunks."""

    @pytest.mark.asyncio
    async def test_explicit_sample_rate_8000_passed_to_split_audio(
        self, mock_split_audio, mock_upload_chunk, mock_transcribe_chunk
    ):
        """
        Req 4.2: WHEN transcribe_chunked is called with sample_rate=8000,
        it SHALL pass 8000 to split_audio_to_chunks.
        """
        from pipeline.speech_to_text import transcribe_chunked

        await transcribe_chunked("/tmp/video.mp4", "job-123", sample_rate=8000)

        mock_split_audio.assert_called_once()
        call_args = mock_split_audio.call_args
        # split_audio_to_chunks(video_path, chunk_dir, sample_rate)
        assert call_args[0][2] == 8000

    @pytest.mark.asyncio
    async def test_explicit_sample_rate_16000_passed_to_split_audio(
        self, mock_split_audio, mock_upload_chunk, mock_transcribe_chunk
    ):
        """
        Req 4.2: WHEN transcribe_chunked is called with sample_rate=16000,
        it SHALL pass 16000 to split_audio_to_chunks.
        """
        from pipeline.speech_to_text import transcribe_chunked

        await transcribe_chunked("/tmp/video.mp4", "job-456", sample_rate=16000)

        mock_split_audio.assert_called_once()
        call_args = mock_split_audio.call_args
        assert call_args[0][2] == 16000


class TestTranscribeChunkedDefaultSampleRate:
    """Tests that sample_rate defaults to 16000 when not specified."""

    @pytest.mark.asyncio
    async def test_default_sample_rate_is_16000(
        self, mock_split_audio, mock_upload_chunk, mock_transcribe_chunk
    ):
        """
        Req 4.1: transcribe_chunked SHALL accept sample_rate with default 16000.
        Req 5.3: split_audio_to_chunks SHALL default to 16000 Hz.
        """
        from pipeline.speech_to_text import transcribe_chunked

        await transcribe_chunked("/tmp/video.mp4", "job-789")

        mock_split_audio.assert_called_once()
        call_args = mock_split_audio.call_args
        # When no sample_rate is passed, default 16000 should be forwarded
        assert call_args[0][2] == 16000


class TestTranscribeChunkedRecognitionConfig:
    """Tests that the recognition config uses the correct sample_rate_hertz for each chunk."""

    @pytest.mark.asyncio
    async def test_recognition_config_uses_8000_for_each_chunk(
        self, mock_split_audio, mock_upload_chunk
    ):
        """
        Req 4.5: WHEN transcribe_chunked is called with sample_rate=8000,
        THE recognition config SHALL use sample_rate_hertz=8000 for each chunk.
        """
        from pipeline.speech_to_text import transcribe_chunked

        with patch("pipeline.speech_to_text.transcribe_chunk") as mock_tc:
            async def capture_calls(*args, **kwargs):
                return []
            mock_tc.side_effect = capture_calls

            await transcribe_chunked("/tmp/video.mp4", "job-sr8k", sample_rate=8000)

            # transcribe_chunk is called for each valid chunk
            assert mock_tc.call_count == 2

            # Verify sample_rate=8000 is passed to each transcribe_chunk call
            for call in mock_tc.call_args_list:
                assert call.kwargs.get("sample_rate") == 8000 or (
                    len(call.args) >= 5 and call.args[4] == 8000
                )

    @pytest.mark.asyncio
    async def test_recognition_config_uses_16000_for_each_chunk(
        self, mock_split_audio, mock_upload_chunk
    ):
        """
        Req 4.5: WHEN transcribe_chunked is called with sample_rate=16000,
        THE recognition config SHALL use sample_rate_hertz=16000 for each chunk.
        """
        from pipeline.speech_to_text import transcribe_chunked

        with patch("pipeline.speech_to_text.transcribe_chunk") as mock_tc:
            async def capture_calls(*args, **kwargs):
                return []
            mock_tc.side_effect = capture_calls

            await transcribe_chunked("/tmp/video.mp4", "job-sr16k", sample_rate=16000)

            assert mock_tc.call_count == 2

            for call in mock_tc.call_args_list:
                assert call.kwargs.get("sample_rate") == 16000 or (
                    len(call.args) >= 5 and call.args[4] == 16000
                )

    @pytest.mark.asyncio
    async def test_recognition_config_uses_default_16000_for_each_chunk(
        self, mock_split_audio, mock_upload_chunk
    ):
        """
        Req 4.1, 4.5: WHEN transcribe_chunked is called without sample_rate,
        THE recognition config SHALL use sample_rate_hertz=16000 (default) for each chunk.
        """
        from pipeline.speech_to_text import transcribe_chunked

        with patch("pipeline.speech_to_text.transcribe_chunk") as mock_tc:
            async def capture_calls(*args, **kwargs):
                return []
            mock_tc.side_effect = capture_calls

            await transcribe_chunked("/tmp/video.mp4", "job-default")

            assert mock_tc.call_count == 2

            for call in mock_tc.call_args_list:
                assert call.kwargs.get("sample_rate") == 16000 or (
                    len(call.args) >= 5 and call.args[4] == 16000
                )


class TestBuildRecognitionConfigSampleRate:
    """Tests that build_recognition_config correctly sets sample_rate_hertz."""

    def test_build_recognition_config_with_8000(self):
        """
        Req 4.5: ExplicitDecodingConfig.sample_rate_hertz SHALL match the sample_rate.
        """
        from pipeline.speech_to_text import build_recognition_config

        config = build_recognition_config(sample_rate=8000)
        assert config.explicit_decoding_config.sample_rate_hertz == 8000

    def test_build_recognition_config_with_16000(self):
        """
        Req 4.5: ExplicitDecodingConfig.sample_rate_hertz SHALL match the sample_rate.
        """
        from pipeline.speech_to_text import build_recognition_config

        config = build_recognition_config(sample_rate=16000)
        assert config.explicit_decoding_config.sample_rate_hertz == 16000

    def test_build_recognition_config_default_is_16000(self):
        """
        Req 4.1: Default sample_rate SHALL be 16000.
        """
        from pipeline.speech_to_text import build_recognition_config

        config = build_recognition_config()
        assert config.explicit_decoding_config.sample_rate_hertz == 16000
