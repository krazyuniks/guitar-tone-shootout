"""Shootout API endpoints."""

from pathlib import Path
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from gts.domain.entities.shootout import Shootout
from gts.domain.value_objects.job_status import JobStatus, JobType
from webapp.adapters.persistence.models.job import Job as JobModel
from webapp.adapters.persistence.models.shootout import (
    Shootout as ShootoutModel,
)
from webapp.adapters.persistence.models.shootout import ShootoutStatus
from webapp.adapters.persistence.models.user import User
from webapp.api.v1.schemas.shootout import (
    ShootoutCreateRequest,
    ShootoutResponse,
)
from webapp.api.v1.schemas.shootout_comment import (
    CommentCreateRequest,
    CommentResponse,
)
from webapp.services.job_dispatch import enqueue_job
from webapp.services.shootout_comment_service import ShootoutCommentService
from webapp.services.shootout_service import ShootoutService

router = APIRouter(prefix="/api/shootouts", tags=["shootouts"])

# Session and user overrides for testing
_session_override: AsyncSession | None = None
_user_override: User | None = None


def set_session_override(session: AsyncSession | None) -> None:
    """Override the database session for testing.

    Args:
        session: Test database session or None to clear
    """
    global _session_override
    _session_override = session


def set_user_override(user: User | None) -> None:
    """Override the current user for testing.

    Args:
        user: Test user to use as CurrentUser or None to clear
    """
    global _user_override
    _user_override = user


async def get_db_session() -> AsyncSession:
    """Get database session dependency.

    Checks for test session override first, then falls back to the
    global database session factory.
    """
    if _session_override:
        return _session_override
    raise NotImplementedError("Database session dependency not configured")


async def get_current_user() -> User:
    """Get current authenticated user dependency.

    In production this would validate session/token.
    For testing, uses override if set.
    """
    if _user_override:
        return _user_override
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
    )


@router.get("/", response_model=list[ShootoutResponse])
async def list_shootouts(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[ShootoutResponse]:
    """List current user's shootouts.

    Protected endpoint - requires authentication.
    Returns only the current user's shootouts.

    Args:
        db: Database session
        current_user: Currently authenticated user

    Returns:
        List of user's shootouts
    """
    service = ShootoutService(db)
    shootouts = await service.get_by_user_id(current_user.id)

    return [
        ShootoutResponse(
            id=shootout.id,
            user_id=shootout.user_id,
            name=shootout.name,
            di_track_id=shootout.di_track_id,
            description=shootout.description,
            visibility=shootout.visibility,
            is_processed=shootout.is_processed,
            output_path=shootout.output_path,
            created_at=shootout.created_at,
            updated_at=shootout.updated_at,
        )
        for shootout in shootouts
    ]


@router.post("/", response_model=ShootoutResponse, status_code=status.HTTP_201_CREATED)
async def create_shootout(
    request: ShootoutCreateRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ShootoutResponse:
    """Create a new shootout.

    Protected endpoint - requires authentication.

    Args:
        request: Shootout creation request
        db: Database session
        current_user: Currently authenticated user

    Returns:
        The created shootout
    """
    # Create shootout entity
    shootout = Shootout(
        id=uuid4(),
        user_id=current_user.id,
        name=request.name,
        di_track_id=request.di_track_id,
        description=request.description,
        visibility=request.visibility,
    )

    # Create via service
    service = ShootoutService(db)
    created = await service.create(shootout)

    return ShootoutResponse(
        id=created.id,
        user_id=created.user_id,
        name=created.name,
        di_track_id=created.di_track_id,
        description=created.description,
        visibility=created.visibility,
        is_processed=created.is_processed,
        output_path=created.output_path,
        created_at=created.created_at,
        updated_at=created.updated_at,
    )


@router.get("/{shootout_id}", response_model=ShootoutResponse)
async def get_shootout(
    shootout_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ShootoutResponse:
    """Get a shootout by ID.

    Protected endpoint - requires authentication.
    Returns 404 if shootout not found or not owned by user.

    Args:
        shootout_id: Shootout ID to retrieve
        db: Database session
        current_user: Currently authenticated user

    Returns:
        Shootout details

    Raises:
        HTTPException: 404 if shootout not found or not owned by user
    """
    service = ShootoutService(db)
    shootout = await service.get_by_id(shootout_id, current_user.id)

    if shootout is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shootout not found",
        )

    return ShootoutResponse(
        id=shootout.id,
        user_id=shootout.user_id,
        name=shootout.name,
        di_track_id=shootout.di_track_id,
        description=shootout.description,
        visibility=shootout.visibility,
        is_processed=shootout.is_processed,
        output_path=shootout.output_path,
        created_at=shootout.created_at,
        updated_at=shootout.updated_at,
    )


@router.delete("/{shootout_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_shootout(
    shootout_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    """Delete a shootout by ID.

    Protected endpoint - requires authentication.
    Returns 404 if shootout not found or not owned by user.
    """
    service = ShootoutService(db)
    shootout = await service.get_by_id(shootout_id, current_user.id)

    if shootout is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shootout not found",
        )

    async with db.begin():
        await service.delete(shootout_id)


@router.post("/{shootout_id}/process", status_code=status.HTTP_202_ACCEPTED)
async def process_shootout(
    shootout_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Trigger processing for a shootout.

    Protected endpoint - requires authentication.
    Creates a Job and enqueues it to the worker for processing.

    Args:
        shootout_id: Shootout ID to process
        db: Database session
        current_user: Currently authenticated user

    Returns:
        Dictionary with job_id

    Raises:
        HTTPException: 404 if shootout not found or not owned by user
        HTTPException: 400 if shootout has no chains or is not in DRAFT status
    """
    # Query shootout with chains, scoped to the owning user
    stmt = (
        select(ShootoutModel)
        .where(ShootoutModel.id == shootout_id, ShootoutModel.user_id == current_user.id)
        .options(joinedload(ShootoutModel.chains))
    )
    result = await db.execute(stmt)
    shootout = result.unique().scalar_one_or_none()

    if shootout is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shootout not found",
        )

    # Return 400 if shootout has no chains
    if not shootout.chains:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Shootout has no chains",
        )

    # Return 400 if shootout is not in DRAFT status
    if shootout.status != ShootoutStatus.DRAFT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Shootout is already being processed or has been processed",
        )

    # Create Job record
    # Transactional outbox: the job-row insert, the shootout status flip, and
    # the pgmq send commit together inside enqueue_job, so processing starts
    # without waiting on the fallback dispatch sweep.
    job = JobModel(
        id=uuid4(),
        user_id=current_user.id,
        job_type=JobType.SHOOTOUT,
        entity_id=shootout_id,
        status=JobStatus.PENDING,
    )
    db.add(job)
    shootout.status = ShootoutStatus.PENDING
    await db.flush()

    await enqueue_job(db, job.id, message="Queued for shootout processing")

    return {"job_id": str(job.id)}


# --- Audio Streaming Endpoints ---

_AUDIO_CONTENT_TYPES: dict[str, str] = {
    ".wav": "audio/wav",
    ".flac": "audio/flac",
    ".ogg": "audio/ogg",
    ".mp3": "audio/mpeg",
}


@router.get("/{shootout_id}/audio/master")
async def stream_master_audio(
    shootout_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> FileResponse:
    """Stream the master FLAC audio file for a completed shootout."""
    stmt = select(ShootoutModel).where(
        ShootoutModel.id == shootout_id, ShootoutModel.user_id == current_user.id
    )
    result = await db.execute(stmt)
    shootout = result.scalar_one_or_none()

    if shootout is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shootout not found")

    if not shootout.output_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Master audio not available"
        )

    file_path = Path(shootout.output_path)
    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Master audio file not found"
        )

    ext = file_path.suffix.lower()
    media_type = _AUDIO_CONTENT_TYPES.get(ext, "application/octet-stream")

    return FileResponse(
        path=str(file_path),
        media_type=media_type,
        filename=f"{shootout.name}-master{ext}",
        headers={"Content-Disposition": f'attachment; filename="{shootout.name}-master{ext}"'},
    )


@router.get("/{shootout_id}/chains/{chain_id}/audio")
async def stream_chain_audio(
    shootout_id: UUID,
    chain_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> FileResponse:
    """Stream processed audio for a specific chain in a shootout."""
    from webapp.adapters.persistence.models.shootout import (
        ShootoutChain as ShootoutChainModel,
    )

    stmt = (
        select(ShootoutChainModel)
        .where(
            ShootoutChainModel.id == chain_id,
            ShootoutChainModel.shootout_id == shootout_id,
            select(ShootoutModel.id)
            .where(ShootoutModel.id == shootout_id, ShootoutModel.user_id == current_user.id)
            .exists(),
        )
        .options(
            joinedload(ShootoutChainModel.shootout),
            joinedload(ShootoutChainModel.segments),
        )
    )
    result = await db.execute(stmt)
    chain = result.unique().scalar_one_or_none()

    if chain is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chain not found")

    if not chain.segments:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No audio segments")

    segment = chain.segments[0]
    file_path = Path(segment.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audio file not found")

    ext = file_path.suffix.lower()
    media_type = _AUDIO_CONTENT_TYPES.get(ext, "application/octet-stream")

    return FileResponse(
        path=str(file_path),
        media_type=media_type,
        filename=f"{chain.label}{ext}",
    )


# --- Comment Endpoints ---


@router.post(
    "/{shootout_id}/comments",
    response_model=CommentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_comment(
    shootout_id: UUID,
    request: CommentCreateRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> CommentResponse:
    """Create a new comment on a shootout.

    Protected endpoint - requires authentication.

    Args:
        shootout_id: Shootout ID to comment on
        request: Comment creation request
        db: Database session
        current_user: Currently authenticated user

    Returns:
        The created comment with author info

    Raises:
        HTTPException: 404 if shootout not found
        HTTPException: 422 if content validation fails
    """
    service = ShootoutCommentService(db)

    try:
        comment = await service.create(
            shootout_id=shootout_id,
            user_id=current_user.id,
            content=request.content,
        )
    except ValueError as e:
        if "shootout" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Shootout not found",
            )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )

    return CommentResponse(
        id=comment.id,
        shootout_id=comment.shootout_id,
        user_id=comment.user_id,
        content=comment.content,
        author_username=comment.user.username,
        author_avatar_url=comment.user.avatar_url if hasattr(comment.user, "avatar_url") else None,
        created_at=comment.created_at,
    )


@router.get("/{shootout_id}/comments")
async def list_comments(
    shootout_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
    limit: int = 50,
    offset: int = 0,
) -> list[CommentResponse]:
    """List comments for a shootout, newest first.

    Protected endpoint - requires authentication.

    Args:
        shootout_id: Shootout ID to get comments for
        db: Database session
        current_user: Currently authenticated user
        limit: Maximum number of comments to return
        offset: Number of comments to skip

    Returns:
        List of comments with author info

    Raises:
        HTTPException: 404 if shootout not found
    """
    service = ShootoutCommentService(db)

    try:
        comments = await service.list_by_shootout(
            shootout_id=shootout_id,
            user_id=current_user.id,
            limit=limit,
            offset=offset,
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shootout not found",
        )

    return [
        CommentResponse(
            id=comment.id,
            shootout_id=comment.shootout_id,
            user_id=comment.user_id,
            content=comment.content,
            author_username=comment.user.username,
            author_avatar_url=comment.user.avatar_url
            if hasattr(comment.user, "avatar_url")
            else None,
            created_at=comment.created_at,
        )
        for comment in comments
    ]


@router.delete(
    "/{shootout_id}/comments/{comment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_comment(
    shootout_id: UUID,
    comment_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    """Delete a comment.

    Protected endpoint - requires authentication.
    Only the comment author can delete their comment.

    Args:
        shootout_id: Shootout ID (verified for consistency)
        comment_id: Comment ID to delete
        db: Database session
        current_user: Currently authenticated user

    Raises:
        HTTPException: 404 if shootout or comment not found or not owned by user
    """
    # Verify shootout exists (existence only). Comment-author ownership is
    # enforced separately by service.delete below; do NOT reuse the
    # ownership-scoped list_by_shootout here, or a comment author who does not
    # own the shootout would be wrongly 404'd.
    service = ShootoutCommentService(db)
    shootout_exists = (
        await db.execute(select(ShootoutModel.id).where(ShootoutModel.id == shootout_id))
    ).scalar_one_or_none()
    if not shootout_exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shootout not found",
        )

    # Delete the comment (ownership enforced at query level)
    try:
        await service.delete(comment_id=comment_id, user_id=current_user.id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comment not found",
        )
