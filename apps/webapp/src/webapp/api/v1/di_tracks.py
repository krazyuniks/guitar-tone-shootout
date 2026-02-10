"""DI Tracks API endpoints."""

from pathlib import Path
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from webapp.adapters.persistence.models.shootout import DITrack
from webapp.adapters.persistence.models.user import User
from webapp.adapters.persistence.repositories.di_track_repository import (
    SQLAlchemyDITrackRepository,
)
from webapp.api.v1.schemas.di_track import DITrackResponse
from webapp.auth.dependencies import (
    get_current_user_required as get_current_user,
)
from webapp.auth.dependencies import (
    get_db_session,
)
from webapp.services.di_track_service import DITrackService

router = APIRouter(prefix="/api/v1/di-tracks", tags=["di-tracks"])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=DITrackResponse)
async def upload_di_track(
    file: Annotated[UploadFile, File()],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
    name: Annotated[str | None, Form()] = None,
    description: Annotated[str | None, Form()] = None,
    guitar: Annotated[str | None, Form()] = None,
    pickup: Annotated[str | None, Form()] = None,
) -> DITrack:
    """Upload a DI track.

    Accepts multipart file upload with metadata, saves file to storage,
    creates database record via DITrackService, and returns the created track.

    Returns 201 with DITrackResponse on success.
    Returns 400 for invalid format, empty name, or duplicate checksum.
    """
    # Validate name is not empty
    if not name or not name.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Track name cannot be empty",
        )

    # Validate file was provided
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No file provided",
        )

    # Create upload directory structure: /app/uploads/di-tracks/{user_id}/
    upload_base = Path("/app/uploads/di-tracks")
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

    # Use DITrackService to validate and create database record
    service = DITrackService(db)
    try:
        async with db.begin():
            track = await service.upload(
                user_id=current_user.id,
                file_path=str(file_path),
                original_filename=file.filename,
                name=name,
                description=description,
                guitar=guitar,
                pickup=pickup,
            )
    except ValueError as e:
        # Clean up file on validation failure
        if file_path.exists():
            file_path.unlink()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e

    return track


@router.get("", response_model=list[DITrackResponse])
async def list_di_tracks(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
    limit: int = 50,
    offset: int = 0,
) -> list[DITrack]:
    """List current user's DI tracks.

    Supports pagination via limit and offset query parameters.
    """
    from sqlalchemy import select

    stmt = (
        select(DITrack)
        .where(DITrack.user_id == current_user.id)
        .order_by(DITrack.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    tracks = result.scalars().all()
    return list(tracks)


@router.get("/{track_id}", response_model=DITrackResponse)
async def get_di_track(
    track_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> DITrack:
    """Get a single DI track by ID.

    Returns 404 if track not found or not owned by user (avoids leaking existence).
    """
    from sqlalchemy import select

    stmt = select(DITrack).where(DITrack.id == track_id)
    result = await db.execute(stmt)
    track = result.scalar_one_or_none()

    if not track or track.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Track not found",
        )

    return track


@router.delete("/{track_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_di_track(
    track_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    """Delete a DI track owned by the current user.

    Returns 404 if track not found or not owned by user (avoids leaking existence).
    """
    repo = SQLAlchemyDITrackRepository(db)
    track = await repo.get_by_id(track_id)

    if not track or track.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Track not found",
        )

    async with db.begin():
        await repo.delete(track_id)
