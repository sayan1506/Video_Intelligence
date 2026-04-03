# tests/helpers.py

def make_mp4_header() -> bytes:
    """
    Minimal valid MP4 header (magic bytes only).
    Real MP4: [4 bytes size][4 bytes 'ftyp'][rest of file]
    We only need the first 12 bytes to pass the validator.
    """
    return b'\x00\x00\x00\x20' + b'ftyp' + b'isom' + b'\x00' * 200


def make_fake_file_bytes() -> bytes:
    """Plain text content that will fail magic bytes validation."""
    return b'This is definitely not a video file content at all.'