"""Audio upload validation and storage.

Handles multipart audio uploads (mp3, wav, m4a). Validates:
- File extension / MIME type against the allowed list.
- File size against MAX_UPLOAD_BYTES.
- Audio duration against MAX_AUDIO_DURATION_SECONDS (using ffprobe).
- Silent / empty audio (duration == 0).

The validated file is saved into the job's upload directory and the local
path is returned for use as the STT audio_ref.
"""
from __future__ import annotations

import logging
import os

from fastapi import UploadFile

from app.api.errors import InvalidInputError
from app.config import get_settings

log = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {".mp3", ".wav", ".m4a"}
ALLOWED_MIMES = {
    "audio/mpeg", "audio/mp3", "audio/wav", "audio/x-wav", "audio/wave",
    "audio/x-m4a", "audio/mp4", "audio/m4a",
    # Browsers sometimes send these for mp3/wav/m4a:
    "application/octet-stream",
}


def validate_and_save(upload: UploadFile, upload_dir: str) -> str:
    """Validate an uploaded audio file and save it. Returns the local path."""
    settings = get_settings()
    fname = (upload.filename or "audio.bin").strip()
    ext = os.path.splitext(fname)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise InvalidInputError(
            f"Unsupported audio format {ext!r}. Allowed: {sorted(ALLOWED_EXTENSIONS)}.",
            {"filename": fname, "extension": ext},
        )
    # Validate MIME (treat octet-stream as ok; real check is on the binary).
    mime = (upload.content_type or "").lower().split(";")[0].strip()
    if mime and mime not in ALLOWED_MIMES:
        raise InvalidInputError(
            f"Unsupported audio MIME type {mime!r}.",
            {"content_type": mime},
        )
    os.makedirs(upload_dir, exist_ok=True)
    dest = os.path.join(upload_dir, fname)
    # Read in chunks to enforce size limit.
    total = 0
    limit = settings.max_upload_bytes
    with open(dest, "wb") as fh:
        while True:
            chunk = upload.file.read(1024 * 256)
            if not chunk:
                break
            total += len(chunk)
            if total > limit:
                os.unlink(dest)
                raise InvalidInputError(
                    f"Uploaded file exceeds the maximum size of {limit // (1024*1024)} MB.",
                    {"size_bytes": total, "limit_bytes": limit},
                )
            fh.write(chunk)
    if total == 0:
        os.unlink(dest)
        raise InvalidInputError("Uploaded audio file is empty.", {"filename": fname})
    # Duration check with ffprobe.
    _validate_duration(dest, settings.max_audio_duration_seconds)
    log.info("Audio uploaded: %s (%d bytes)", dest, total)
    return dest


def _validate_duration(path: str, max_seconds: int) -> None:
    """Use ffprobe to check duration. Raise InvalidInputError if invalid."""
    try:
        from app.utils.ffmpeg import video_info
        info = video_info(path)
        dur = info.get("duration", 0)
        audio = info.get("audio")
    except Exception:
        # ffprobe not available or file unreadable — treat as corrupted.
        raise InvalidInputError(
            "Could not read audio file. The file may be corrupt or unsupported.",
            {"path": os.path.basename(path)},
        )
    if dur == 0 and (audio is None):
        raise InvalidInputError(
            "Audio file appears to be empty or silent (zero duration).",
            {"path": os.path.basename(path)},
        )
    if audio is None:
        raise InvalidInputError(
            "File contains no audio stream. Only audio files (mp3/wav/m4a) are supported.",
            {"path": os.path.basename(path)},
        )
    if dur > max_seconds:
        raise InvalidInputError(
            f"Audio duration {dur:.1f}s exceeds the maximum of {max_seconds}s.",
            {"duration_seconds": round(dur, 1), "max_seconds": max_seconds},
        )
