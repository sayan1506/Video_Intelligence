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


def confirm_params(
    job_id: str,
    gcs_path: str = "raw-videos/test-job/test.mp4",
    filename: str = "test.mp4",
    file_size_bytes: int = 1024 * 1024,
    content_type: str = "video/mp4",
) -> dict:
    return {
        "job_id": job_id,
        "gcs_path": gcs_path,
        "filename": filename,
        "file_size_bytes": file_size_bytes,
        "content_type": content_type,
    }


# ---------------------------------------------------------------------------
# Step 1: /upload-url
# ---------------------------------------------------------------------------

class TestRequestUploadUrl:

    async def test_valid_request_returns_job_id_and_upload_url(self, client: AsyncClient):
        with patch("routers.upload.firestore.create_job") as mock_create, \
             patch("routers.upload.storage.build_gcs_path", return_value="raw-videos/abc/test.mp4"), \
             patch("routers.upload.storage.get_signed_upload_url", return_value="https://storage.googleapis.com/signed"):

            mock_create.return_value = None

            response = await client.post(
                "/upload-url",
                params=upload_url_params(),
                headers={"X-File-Header": mp4_header_hex()},
            )

        assert response.status_code == 200
        data = response.json()
        assert "jobId" in data
        assert "uploadUrl" in data
        assert "gcsPath" in data
        assert len(data["jobId"]) == 36  # UUID4

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
            params=upload_url_params(filename="video.mkv", content_type="video/mp4"),
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

    async def test_signed_url_failure_returns_500(self, client: AsyncClient):
        with patch("routers.upload.firestore.create_job"), \
             patch("routers.upload.storage.build_gcs_path", return_value="raw-videos/abc/test.mp4"), \
             patch("routers.upload.storage.get_signed_upload_url") as mock_url, \
             patch("routers.upload.firestore.update_job_status"):

            mock_url.side_effect = Exception("Signing failed")

            response = await client.post(
                "/upload-url",
                params=upload_url_params(),
            )

        assert response.status_code == 500
        assert "Could not generate upload URL" in response.json()["detail"]

    async def test_no_magic_bytes_header_still_succeeds(self, client: AsyncClient):
        """Magic bytes check is optional — no X-File-Header should still return 200."""
        with patch("routers.upload.firestore.create_job"), \
             patch("routers.upload.storage.build_gcs_path", return_value="raw-videos/abc/test.mp4"), \
             patch("routers.upload.storage.get_signed_upload_url", return_value="https://signed.url"):

            response = await client.post(
                "/upload-url",
                params=upload_url_params(),
                # No X-File-Header
            )

        assert response.status_code == 200


# ---------------------------------------------------------------------------
# Step 2: /upload-confirm
# ---------------------------------------------------------------------------

class TestConfirmUpload:

    async def test_valid_confirm_returns_200_with_pending_status(self, client: AsyncClient):
        with patch("routers.upload.storage.get_signed_url", return_value="https://signed.url/video.mp4"), \
             patch("routers.upload.firestore.write_video_url"), \
             patch("routers.upload.firestore.update_job_status"), \
             patch("routers.upload.firestore.update_upload_progress"), \
             patch("routers.upload.pubsub.publish_job_message", return_value="msg-123"):

            response = await client.post(
                "/upload-confirm",
                params=confirm_params(job_id="test-job-id-1234-5678-9012-123456789012"),
            )

        assert response.status_code == 200
        data = response.json()
        assert data["jobId"] == "test-job-id-1234-5678-9012-123456789012"
        assert data["status"] == "pending"
        assert data["message"] == "Video uploaded successfully"

    async def test_confirm_calls_firestore_and_pubsub(self, client: AsyncClient):
        with patch("routers.upload.storage.get_signed_url", return_value="https://signed.url/video.mp4"), \
             patch("routers.upload.firestore.write_video_url") as mock_write_url, \
             patch("routers.upload.firestore.update_job_status") as mock_status, \
             patch("routers.upload.firestore.update_upload_progress") as mock_progress, \
             patch("routers.upload.pubsub.publish_job_message") as mock_publish:

            await client.post(
                "/upload-confirm",
                params=confirm_params(job_id="test-job-id-1234-5678-9012-123456789012"),
            )

        assert mock_write_url.call_count == 1
        assert mock_status.call_count == 1
        assert mock_progress.call_count == 1
        assert mock_publish.call_count == 1

    async def test_pubsub_failure_still_returns_200(self, client: AsyncClient):
        """Pub/Sub failure is non-fatal — job is in Firestore and recoverable."""
        with patch("routers.upload.storage.get_signed_url", return_value="https://signed.url/video.mp4"), \
             patch("routers.upload.firestore.write_video_url"), \
             patch("routers.upload.firestore.update_job_status"), \
             patch("routers.upload.firestore.update_upload_progress"), \
             patch("routers.upload.pubsub.publish_job_message") as mock_publish:

            mock_publish.side_effect = ServiceUnavailable("Pub/Sub is down")

            response = await client.post(
                "/upload-confirm",
                params=confirm_params(job_id="test-job-id-1234-5678-9012-123456789012"),
            )

        assert response.status_code == 200
        assert response.json()["status"] == "pending"

    async def test_signed_url_failure_is_non_fatal(self, client: AsyncClient):
        """Signed read URL generation failing should not block the confirm response."""
        with patch("routers.upload.storage.get_signed_url") as mock_url, \
             patch("routers.upload.firestore.write_video_url"), \
             patch("routers.upload.firestore.update_job_status"), \
             patch("routers.upload.firestore.update_upload_progress"), \
             patch("routers.upload.pubsub.publish_job_message"):

            mock_url.side_effect = Exception("Signing failed")

            response = await client.post(
                "/upload-confirm",
                params=confirm_params(job_id="test-job-id-1234-5678-9012-123456789012"),
            )

        assert response.status_code == 200