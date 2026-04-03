import pytest

import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from main import app

@pytest_asyncio.fixture
async def client() -> AsyncClient:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as ac:
        yield ac


def make_mp4_header() -> bytes:
    """
    Construct a minimal valid MP4 file header (magic bytes only).
    Used to create fake video files that pass magic bytes validation.

    Real MP4 structure: [4 bytes size][4 bytes 'ftyp'][rest of file]
    We only need the first 12 bytes to pass the validator.
    """
    return b'\x00\x00\x00\x20' + b'ftyp' + b'isom' + b'\x00' * 200


def make_fake_file_bytes() -> bytes:
    """Plain text content that will fail magic bytes validation."""
    return b'This is definitely not a video file content at all.'