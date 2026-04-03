from utils.validators import (
    check_magic_bytes,
    validate_file_extension,
    MAGIC_BYTES_READ_LENGTH,
)


class TestMagicBytesValidator:

    def test_valid_mp4_ftyp_header(self):
        header = b'\x00\x00\x00\x20' + b'ftyp' + b'isom' + b'\x00' * 4
        assert check_magic_bytes(header, "video/mp4") is True

    def test_valid_avi_riff_header(self):
        header = b'RIFF' + b'\x00' * 8
        assert check_magic_bytes(header, "video/avi") is True

    def test_valid_avi_alternate_mime(self):
        header = b'RIFF' + b'\x00' * 8
        assert check_magic_bytes(header, "video/x-msvideo") is True

    def test_fake_mp4_text_content_rejected(self):
        header = b'This is a text file pretending to be a video!!!'
        assert check_magic_bytes(header, "video/mp4") is False

    def test_unknown_mime_type_rejected(self):
        header = b'\x00\x00\x00\x20' + b'ftyp' + b'isom' + b'\x00' * 4
        assert check_magic_bytes(header, "application/pdf") is False

    def test_empty_header_rejected(self):
        assert check_magic_bytes(b'', "video/mp4") is False

    def test_header_too_short_rejected(self):
        # Only 3 bytes — not enough to check ftyp at offset 4
        assert check_magic_bytes(b'\x00\x00\x00', "video/mp4") is False

    def test_magic_bytes_read_length_is_12(self):
        assert MAGIC_BYTES_READ_LENGTH == 12


class TestExtensionValidator:

    def test_mp4_extension_valid(self):
        assert validate_file_extension("video.mp4") is True

    def test_mov_extension_valid(self):
        assert validate_file_extension("clip.mov") is True

    def test_avi_extension_valid(self):
        assert validate_file_extension("recording.avi") is True

    def test_mp4_uppercase_valid(self):
        # Extensions are lowercased before checking
        assert validate_file_extension("VIDEO.MP4") is True

    def test_exe_extension_rejected(self):
        assert validate_file_extension("malware.exe") is False

    def test_no_extension_rejected(self):
        assert validate_file_extension("noextension") is False

    def test_empty_filename_rejected(self):
        assert validate_file_extension("") is False

    def test_double_extension_uses_last(self):
        # video.mp4.exe should be rejected — last extension is .exe
        assert validate_file_extension("video.mp4.exe") is False