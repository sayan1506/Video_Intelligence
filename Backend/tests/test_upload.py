import io
from unittest.mock import patch, AsyncMock, MagicMock
from httpx import AsyncClient
from tests.helpers import make_mp4_header, make_fake_file_bytes    

# --- Helper to build a multipart upload request ---

def make_upload_files(content: bytes, filename: str = "test.mp4", content_type: str = "video/mp4"):
    """Returns the files dict for httpx multipart upload."""
    return {"file": (filename, io.BytesIO(content), content_type)}


# --- Success path ---

class TestUploadSuccess:

    async def test_valid_mp4_returns_200_with_job_id(self, client: AsyncClient):
        with patch("routers.upload.storage.upload_to_gcs", new_callable=AsyncMock) as mock_gcs, \
             patch("routers.upload.storage.get_signed_url", return_value="https://signed.url/video.mp4"), \
             patch("routers.upload.firestore.create_job") as mock_create, \
             patch("routers.upload.firestore.write_video_url") as mock_write_url, \
             patch("routers.upload.firestore.update_job_status") as mock_status, \
             patch("routers.upload.firestore.update_upload_progress") as mock_progress, \
             patch("routers.upload.pubsub.publish_job_message", return_value="msg-123"):

            mock_gcs.return_value = "raw-videos/test-job/test.mp4"

            response = await client.post(
                "/upload",
                files=make_upload_files(make_mp4_header())
            )

        assert response.status_code == 200
        data = response.json()
        assert "jobId" in data
        assert data["status"] == "pending"
        assert data["message"] == "Video uploaded successfully"
        assert len(data["jobId"]) == 36  # UUID4 format

    async def test_valid_upload_calls_all_three_services(self, client: AsyncClient):
        with patch("routers.upload.storage.upload_to_gcs", new_callable=AsyncMock) as mock_gcs, \
             patch("routers.upload.storage.get_signed_url", return_value="https://signed.url/video.mp4"), \
             patch("routers.upload.firestore.create_job") as mock_create, \
             patch("routers.upload.firestore.write_video_url"), \
             patch("routers.upload.firestore.update_job_status"), \
             patch("routers.upload.firestore.update_upload_progress"), \
             patch("routers.upload.pubsub.publish_job_message", return_value="msg-123") as mock_publish:

            mock_gcs.return_value = "raw-videos/test-job/test.mp4"

            await client.post(
                "/upload",
                files=make_upload_files(make_mp4_header())
            )

        # All three core services must be called exactly once
        assert mock_gcs.call_count == 1
        assert mock_create.call_count == 1
        assert mock_publish.call_count == 1


# --- File validation failures ---

class TestUploadValidation:

    async def test_unsupported_mime_type_returns_400(self, client: AsyncClient):
        response = await client.post(
            "/upload",
            files=make_upload_files(
                content=b"fake content",
                filename="doc.pdf",
                content_type="application/pdf"
            )
        )
        assert response.status_code == 400
        assert "Unsupported file type" in response.json()["detail"]

    async def test_unsupported_extension_returns_400(self, client: AsyncClient):
        response = await client.post(
            "/upload",
            files=make_upload_files(
                content=make_mp4_header(),
                filename="video.mkv",
                content_type="video/mp4"
            )
        )
        assert response.status_code == 400
        assert "extension" in response.json()["detail"].lower()

    async def test_magic_bytes_mismatch_returns_400(self, client: AsyncClient):
        response = await client.post(
            "/upload",
            files=make_upload_files(
                content=make_fake_file_bytes(),  # text content, not MP4 bytes
                filename="fake.mp4",
                content_type="video/mp4"
            )
        )
        assert response.status_code == 400
        assert "content does not match" in response.json()["detail"].lower()

    async def test_validation_fails_before_gcs_upload(self, client: AsyncClient):
        """Confirm GCS is never called when validation fails — no wasted GCP calls."""
        with patch("routers.upload.storage.upload_to_gcs", new_callable=AsyncMock) as mock_gcs:
            await client.post(
                "/upload",
                files=make_upload_files(
                    content=make_fake_file_bytes(),
                    filename="fake.mp4",
                    content_type="video/mp4"
                )
            )
        assert mock_gcs.call_count == 0


# --- GCP service failures ---

class TestUploadServiceFailures:

    async def test_gcs_unavailable_returns_503(self, client: AsyncClient):
        from google.api_core.exceptions import ServiceUnavailable

        with patch("routers.upload.firestore.create_job"), \
             patch("routers.upload.firestore.update_job_status"), \
             patch("routers.upload.storage.upload_to_gcs", new_callable=AsyncMock) as mock_gcs:

            mock_gcs.side_effect = ServiceUnavailable("GCS is down")

            response = await client.post(
                "/upload",
                files=make_upload_files(make_mp4_header())
            )

        assert response.status_code == 503
        assert "Storage unavailable" in response.json()["detail"]

    async def test_firestore_unavailable_returns_503(self, client: AsyncClient):
        from google.api_core.exceptions import ServiceUnavailable

        with patch("routers.upload.firestore.create_job") as mock_create:
            mock_create.side_effect = ServiceUnavailable("Firestore is down")

            response = await client.post(
                "/upload",
                files=make_upload_files(make_mp4_header())
            )

        assert response.status_code == 503
        assert "Database unavailable" in response.json()["detail"]

    async def test_pubsub_failure_still_returns_200(self, client: AsyncClient):
        """
        Pub/Sub failure after a successful GCS upload should NOT fail the request.
        The file is uploaded and the job exists in Firestore — situation is recoverable.
        """
        from google.api_core.exceptions import ServiceUnavailable

        with patch("routers.upload.storage.upload_to_gcs", new_callable=AsyncMock) as mock_gcs, \
             patch("routers.upload.storage.get_signed_url", return_value="https://signed.url/video.mp4"), \
             patch("routers.upload.firestore.create_job"), \
             patch("routers.upload.firestore.write_video_url"), \
             patch("routers.upload.firestore.update_job_status"), \
             patch("routers.upload.firestore.update_upload_progress"), \
             patch("routers.upload.pubsub.publish_job_message") as mock_publish:

            mock_gcs.return_value = "raw-videos/test-job/test.mp4"
            mock_publish.side_effect = ServiceUnavailable("Pub/Sub is down")

            response = await client.post(
                "/upload",
                files=make_upload_files(make_mp4_header())
            )

        # Upload should still succeed — Pub/Sub failure is non-fatal
        assert response.status_code == 200
        assert response.json()["status"] == "pending"