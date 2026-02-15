"""IR upload API endpoints."""

from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from webapp.adapters.persistence.models.user import User
from webapp.auth.dependencies import (
    get_current_user_required as get_current_user,
)
from webapp.auth.dependencies import (
    get_db_session,
)
from webapp.config.uploads import get_upload_base
from webapp.services.ir_upload_service import IRUploadService

router = APIRouter(prefix="/api/v1/irs", tags=["irs"])


class IRUploadResponse(BaseModel):
    """Response model for IR upload."""

    id: str
    name: str
    description: str | None
    gear_type: str

    model_config = {"from_attributes": True}


@router.post("/upload", status_code=status.HTTP_201_CREATED, response_model=IRUploadResponse)
async def upload_ir(
    file: Annotated[UploadFile, File()],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
    name: Annotated[str, Form()],
    description: Annotated[str | None, Form()] = None,
) -> IRUploadResponse:
    """Upload an IR (Impulse Response) file.

    Accepts multipart file upload with metadata, saves file to storage,
    creates Gear + GearModel entities via IRUploadService, and returns the created gear.

    Returns 201 with IRUploadResponse on success.
    Returns 400 for invalid format or duplicate checksum.
    Returns 401 if not authenticated.
    """
    # Validate file was provided
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No file provided",
        )

    # Create upload directory structure: {base}/irs/{user_id}/
    upload_base = get_upload_base() / "irs"
    user_dir = upload_base / str(current_user.id)
    user_dir.mkdir(parents=True, exist_ok=True)

    # Generate unique filename: {uuid}.{ext}
    file_ext = Path(file.filename).suffix or ".wav"
    unique_filename = f"{uuid4()}{file_ext}"
    file_path = user_dir / unique_filename

    # Save uploaded file
    try:
        contents = await file.read()
        file_path.write_bytes(contents)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save file: {e!s}",
        ) from e

    # Use IRUploadService to validate and create database records
    service = IRUploadService(db)
    try:
        async with db.begin():
            gear = await service.upload(
                user_id=current_user.id,
                file_path=str(file_path),
                original_filename=file.filename,
                name=name,
                description=description,
            )
    except ValueError as e:
        # Clean up file on validation failure
        if file_path.exists():
            file_path.unlink()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e

    return IRUploadResponse(
        id=str(gear.id),
        name=gear.name,
        description=gear.description,
        gear_type=gear.gear_type.value,
    )
