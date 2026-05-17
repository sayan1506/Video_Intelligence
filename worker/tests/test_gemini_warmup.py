"""
Tests for PERF-2: Gemini warm-up in worker/main.py.

Verifies:
- ping_gemini() calls get_gemini_client() to initialise the singleton
- ping_gemini() calls generate_content() with max_output_tokens=1
- ping_gemini() does not raise on exception (non-fatal contract)
- ping_gemini() logs a warning on failure
"""
import logging
from unittest.mock import MagicMock, patch

import pytest

from main import ping_gemini


class TestPingGeminiSuccess:
    def test_calls_get_gemini_client(self):
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = MagicMock()

        with patch("pipeline.gemini.get_gemini_client", return_value=mock_client) as mock_get:
            ping_gemini()
            mock_get.assert_called_once()

    def test_calls_generate_content(self):
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = MagicMock()

        with patch("pipeline.gemini.get_gemini_client", return_value=mock_client):
            ping_gemini()
            mock_client.models.generate_content.assert_called_once()

    def test_generate_content_called_with_max_tokens_1(self):
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = MagicMock()

        with patch("pipeline.gemini.get_gemini_client", return_value=mock_client):
            ping_gemini()
            call_kwargs = mock_client.models.generate_content.call_args
            config = call_kwargs.kwargs.get("config") or call_kwargs[1].get("config")
            assert config.max_output_tokens == 1


class TestPingGeminiFailure:
    def test_does_not_raise_on_exception(self):
        with patch("pipeline.gemini.get_gemini_client", side_effect=Exception("network error")):
            # Must not raise
            ping_gemini()

    def test_logs_warning_on_failure(self, caplog):
        with patch("pipeline.gemini.get_gemini_client", side_effect=Exception("timeout")):
            with caplog.at_level(logging.WARNING, logger="worker"):
                ping_gemini()
            assert any("warm-up failed" in r.message for r in caplog.records)

    def test_generate_content_exception_does_not_raise(self):
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = Exception("gRPC error")

        with patch("pipeline.gemini.get_gemini_client", return_value=mock_client):
            ping_gemini()  # must not raise
