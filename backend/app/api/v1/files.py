"""File upload endpoints for DI tracks.

Handles uploading audio files for processing.
"""

import uuid
from pathlib import Path

import aiofiles
from fastapi import APIRouter, HTTPException, UploadFile, status

from app.api.deps import CurrentUser
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/files", tags=["files"])

# Allowed audio file extensions
ALLOWED_EXTENSIONS = {".wav", ".mp3", ".flac", ".aiff", ".aif"}
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB


@router.post("/upload")
async def upload_file(
    file: UploadFile,
    current_user: CurrentUser,
) -> dict[str, str]:
    """Upload a DI track file.

    Args:
        file: The uploaded audio file
        current_user: The authenticated user

    Returns:
        Dictionary with the uploaded file path

    Raises:
        HTTPException: If file type not allowed or file too large
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No filename provided",
        )

    # Validate file extension
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        allowed = ", ".join(ALLOWED_EXTENSIONS)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type not allowed. Allowed: {allowed}",
        )

    # Read file content and check size
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large. Maximum size: {MAX_FILE_SIZE // (1024 * 1024)}MB",
        )

    # Create upload directory for user
    upload_dir = Path(settings.upload_dir) / str(current_user.id)
    upload_dir.mkdir(parents=True, exist_ok=True)

    # Generate unique filename
    unique_id = uuid.uuid4().hex[:8]
    safe_filename = f"{unique_id}_{Path(file.filename).stem}{ext}"
    file_path = upload_dir / safe_filename

    # Save file
    async with aiofiles.open(file_path, "wb") as f:
        await f.write(content)

    logger.info(
        "File uploaded: %s by user %s (%d bytes)",
        safe_filename,
        current_user.username,
        len(content),
    )

    # Return relative path from upload dir
    relative_path = f"{current_user.id}/{safe_filename}"
    return {"path": relative_path}
