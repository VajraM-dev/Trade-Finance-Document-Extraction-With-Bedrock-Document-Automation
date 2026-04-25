import pytest

from app.errors import PayloadTooLargeError, UnsupportedMediaTypeError
from app.services.uploads import detect_mime, validate_size

PDF_BYTES = b"%PDF-1.4\n%..."
PNG_BYTES = b"\x89PNG\r\n\x1a\n"
JPG_BYTES = b"\xff\xd8\xff\xe0\x00"
TIFF_BYTES_LE = b"II*\x00"
JUNK = b"junkdata12345"


def test_detect_mime_pdf():
    assert detect_mime(PDF_BYTES) == "application/pdf"


def test_detect_mime_png():
    assert detect_mime(PNG_BYTES) == "image/png"


def test_detect_mime_jpeg():
    assert detect_mime(JPG_BYTES) == "image/jpeg"


def test_detect_mime_tiff():
    assert detect_mime(TIFF_BYTES_LE) == "image/tiff"


def test_detect_mime_unsupported_raises():
    with pytest.raises(UnsupportedMediaTypeError):
        detect_mime(JUNK)


def test_validate_size_rejects_oversize():
    with pytest.raises(PayloadTooLargeError):
        validate_size(11 * 1024 * 1024, max_mb=10)


def test_validate_size_accepts_under_limit():
    validate_size(5 * 1024 * 1024, max_mb=10)
