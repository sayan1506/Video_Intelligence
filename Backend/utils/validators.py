VIDEO_SIGNATURES = {
    "video/mp4": [
        (4, b"ftyp"),          # Standard MP4
        (4, b"free"),          # Some MP4 variants
        (4, b"mdat"),          # MP4 with mdat box first
        (0, b"\x00\x00\x00\x18ftyp"),  # MP4 with 24-byte ftyp box
    ],
    "video/quicktime": [
        (4, b"ftyp qt  "),     # QuickTime MOV
        (4, b"moov"),          # MOV with moov box first
        (4, b"free"),          # MOV free box variant
    ],
    "video/avi": [
        (0, b"RIFF"),          # All AVI files start with RIFF
    ],
    "video/x-msvideo": [
        (0, b"RIFF"),          # AVI alternate MIME type
    ],
}


# Minimum bytes to read for signature checking
MAGIC_BYTES_READ_LENGTH = 12


def check_magic_bytes(file_header: bytes, claimed_mime_type: str) -> bool:
    """
    Verify that the file's binary signature matches its claimed MIME type.

    Args:
        file_header: First MAGIC_BYTES_READ_LENGTH bytes of the file.
        claimed_mime_type: The Content-Type header value from the request.

    Returns:
        True if the magic bytes match, False otherwise.
    """
    signatures = VIDEO_SIGNATURES.get(claimed_mime_type)

    if not signatures:
        # MIME type not in our allowed list at all
        return False

    for offset, expected in signatures:
        end = offset + len(expected)
        if len(file_header) >= end and file_header[offset:end] == expected:
            return True

    return False


def get_file_extension(filename: str) -> str:
    """Return the lowercased file extension including the dot, e.g. '.mp4'"""
    if "." not in filename:
        return ""
    return "." + filename.rsplit(".", 1)[-1].lower()


ALLOWED_EXTENSIONS = {".mp4", ".mov", ".avi"}


def validate_file_extension(filename: str) -> bool:
    """Secondary check — extension must also be in the allowed set."""
    return get_file_extension(filename) in ALLOWED_EXTENSIONS