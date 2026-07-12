"""Single file-serving boundary for webapp media responses."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import HTTPException, status
from fastapi.responses import FileResponse

_MEDIA_CONTENT_TYPES: dict[str, str] = {
    ".wav": "audio/wav",
    ".flac": "audio/flac",
    ".ogg": "audio/ogg",
    ".mp3": "audio/mpeg",
    ".mp4": "video/mp4",
    ".webm": "video/webm",
}


def shootout_audio_root(shootout_id: object) -> Path:
    """Return the storage boundary containing one shootout's audio versions."""
    return Path(os.environ.get("GTS_STORAGE_ROOT", "/app/storage")) / "audio" / str(shootout_id)


def media_response(
    path: str | Path,
    *,
    filename: str | None = None,
    attachment: bool = False,
    containment_root: Path | None = None,
    not_found_detail: str,
) -> FileResponse:
    """Validate and serve a media file through the common response discipline."""
    file_path = Path(path).resolve()
    if containment_root is not None and not file_path.is_relative_to(containment_root.resolve()):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=not_found_detail)
    if not file_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=not_found_detail)

    return FileResponse(
        path=str(file_path),
        media_type=_MEDIA_CONTENT_TYPES.get(file_path.suffix.lower(), "application/octet-stream"),
        filename=filename,
        content_disposition_type="attachment" if attachment else "inline",
    )
