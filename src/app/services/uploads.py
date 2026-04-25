from app.errors import PayloadTooLargeError, UnsupportedMediaTypeError

_MAGIC = [
    (b"%PDF-", "application/pdf"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"II*\x00", "image/tiff"),
    (b"MM\x00*", "image/tiff"),
]


def detect_mime(prefix: bytes) -> str:
    for sig, mime in _MAGIC:
        if prefix.startswith(sig):
            return mime
    raise UnsupportedMediaTypeError(
        "unsupported file type", detail="expected one of: pdf, png, jpeg, tiff"
    )


def validate_size(size_bytes: int, *, max_mb: int) -> None:
    if size_bytes > max_mb * 1024 * 1024:
        raise PayloadTooLargeError(
            "file too large", detail=f"file_size={size_bytes} max={max_mb} MB"
        )
