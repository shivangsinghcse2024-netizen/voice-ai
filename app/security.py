import hashlib
import hmac
import os
import tempfile
from pathlib import Path

from fastapi import HTTPException, UploadFile

from .config import get_settings

ALLOWED_EXTENSIONS = {".wav", ".mp3", ".m4a", ".ogg", ".flac", ".webm", ".mp4", ".aac"}


def _digest(value: str) -> bytes:
    return hashlib.sha256(value.encode("utf-8")).digest()


def is_valid_key(candidate: str) -> bool:
    """Constant-time API key check (compares fixed-length hashes, checks every key)."""
    if not candidate:
        return False
    cand = _digest(candidate)
    ok = False
    for key in get_settings().key_list:
        if hmac.compare_digest(cand, _digest(key)):
            ok = True
    return ok


async def save_upload(file: UploadFile, max_bytes: int) -> Path:
    """Stream an upload to a private temp file, enforcing extension and size limits.
    The client-supplied filename is never used as a path."""
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(415, f"Unsupported file type. Allowed: {sorted(ALLOWED_EXTENSIONS)}")

    fd, name = tempfile.mkstemp(prefix="upload_", suffix=suffix)  # mode 0600
    os.close(fd)
    path = Path(name)
    size = 0
    try:
        with open(path, "wb") as out:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > max_bytes:
                    raise HTTPException(413, "File too large")
                out.write(chunk)
        if size == 0:
            raise HTTPException(422, "Empty file")
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return path
