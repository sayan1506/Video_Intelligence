import pytest
from unittest.mock import patch, MagicMock
from httpx import AsyncClient
from google.api_core.exceptions import ServiceUnavailable
from tests.helpers import make_mp4_header, make_fake_file_bytes

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def mp4_header_hex() -> str:
    """First 12 bytes of a valid MP4 file as hex string (sent in X-File-Header)."""
    return make_mp4_header()[:12].hex()


def fake_file_hex() -> str:
    """First 12 bytes of non-video content as hex string."""
    return make_fake_file_bytes()[:12].hex()


def upload_url_params(
    filename: str = "test.mp4",
    content_type: str = "video/mp4",
    file_size_bytes: int = 1024 * 1024,  # 1 MB
) -> dict:
    return {
        "filename": filename,
        "content_type": content_type,
        "file_size_bytes": file_size_bytes,
    }


# ---------------------------------------------------------------------------
# Step 1: /upload-url
# ---------------------------------------------------------------------------

class TestRequestUploadUrl:

    async def test_unsupported_mime_type_returns_400(self, client: AsyncClient):
        response = await client.post(
            "/upload-url",
            params=upload_url_params(filename="doc.pdf", content_type="application/pdf"),
        )
        assert response.status_code == 400
        assert "Unsupported file type" in response.json()["detail"]

    async def test_unsupported_extension_returns_400(self, client: AsyncClient):
        response = await client.post(
            "/upload-url",
            params=upload_url_params(filename="video.flv", content_type="video/mp4"),
        )
        assert response.status_code == 400
        assert "extension" in response.json()["detail"].lower()

    async def test_magic_bytes_mismatch_returns_400(self, client: AsyncClient):
        response = await client.post(
            "/upload-url",
            params=upload_url_params(),
            headers={"X-File-Header": fake_file_hex()},
        )
        assert response.status_code == 400
        assert "content does not match" in response.json()["detail"].lower()

    async def test_invalid_x_file_header_format_returns_400(self, client: AsyncClient):
        response = await client.post(
            "/upload-url",
            params=upload_url_params(),
            headers={"X-File-Header": "not-valid-hex!!!"},
        )
        assert response.status_code == 400
        assert "X-File-Header" in response.json()["detail"]

    async def test_file_too_large_returns_400(self, client: AsyncClient):
        too_large = 600 * 1024 * 1024  # 600 MB — over default 500 MB limit
        response = await client.post(
            "/upload-url",
            params=upload_url_params(file_size_bytes=too_large),
        )
        assert response.status_code == 400
        assert "too large" in response.json()["detail"].lower()

    async def test_firestore_unavailable_returns_503(self, client: AsyncClient):
        with patch("routers.upload.storage.build_gcs_path", return_value="raw-videos/abc/test.mp4"), \
             patch("routers.upload.firestore.create_job") as mock_create:

            mock_create.side_effect = ServiceUnavailable("Firestore is down")

            response = await client.post(
                "/upload-url",
                params=upload_url_params(),
            )

        assert response.status_code == 503
        assert "Database unavailable" in response.json()["detail"]
