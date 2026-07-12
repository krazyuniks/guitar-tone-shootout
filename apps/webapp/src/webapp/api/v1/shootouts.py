"""Shootout API endpoints."""

from pathlib import Path
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased, joinedload

from gts.domain.entities.shootout import Shootout
from gts.domain.value_objects.job_status import JobStatus, JobType
from webapp.adapters.persistence.models.job import Job as JobModel
from webapp.adapters.persistence.models.shootout import (
    AudioSegment as AudioSegmentModel,
)
from webapp.adapters.persistence.models.shootout import (
    Shootout as ShootoutModel,
)
from webapp.adapters.persistence.models.shootout import (
    ShootoutManifest,
    ShootoutStatus,
)
from webapp.adapters.persistence.models.user import User
from webapp.adapters.persistence.repositories.shootout_repository import (
    published_shootout_gate,
    readable_shootout_gate,
)
from webapp.api.v1.schemas.shootout import (
    ShootoutArtefactChain,
    ShootoutArtefactCreator,
    ShootoutArtefactDI,
    ShootoutArtefactProvenanceBlock,
    ShootoutArtefactResponse,
    ShootoutArtefactTimeline,
    ShootoutArtefactWaveform,
    ShootoutCreateRequest,
    ShootoutResponse,
)
from webapp.api.v1.schemas.shootout_comment import (
    CommentCreateRequest,
    CommentResponse,
)
from webapp.auth.dependencies import CurrentUserOptional
from webapp.services.job_dispatch import enqueue_job
from webapp.services.media_service import media_response, shootout_audio_root
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


def _project_artefact(
    shootout: ShootoutModel,
    manifest: ShootoutManifest,
) -> ShootoutArtefactResponse:
    """Build the public allow-list without serialising the raw manifest."""
    payload = manifest.payload
    shootout_payload = payload["shootout"]
    creator = shootout_payload["creator"]
    di = payload["di"]
    timeline = payload["timeline"]
    chains = [
        ShootoutArtefactChain(
            label=chain["label"],
            media_url=f"/api/shootouts/{shootout.id}/media/{UUID(chain['segment_id'])}",
            duration_seconds=chain["duration_seconds"],
            waveform=ShootoutArtefactWaveform(
                peaks=chain["waveform"]["peaks"],
                sample_rate=chain["waveform"]["sample_rate"],
                duration_seconds=chain["waveform"].get("duration_seconds"),
                samples_per_peak=chain["waveform"].get("samples_per_peak"),
            ),
            integrated_lufs=chain["integrated_lufs"],
            peak_dbfs=chain["peak_dbfs"],
            provenance=[
                ShootoutArtefactProvenanceBlock(
                    position=block["position"],
                    gear_type=block["gear_type"],
                    display_name=block["display_name"],
                    platform=block["platform"],
                    icon_asset_id=block["icon_asset_id"],
                )
                for block in chain["provenance"]
            ],
        )
        for chain in payload["chains"]
    ]
    return ShootoutArtefactResponse(
        id=shootout_payload["id"],
        title=shootout_payload["title"],
        description=shootout_payload["description"],
        creator=ShootoutArtefactCreator(
            username=creator["username"],
            avatar_url=creator["avatar_url"],
        ),
        created_at=shootout_payload["created_at"],
        di=ShootoutArtefactDI(
            name=di["name"],
            guitar=di["guitar"],
            pickup=di["pickup"],
            tuning=di["tuning"],
            duration_seconds=di["duration_seconds"],
        ),
        timeline=ShootoutArtefactTimeline(
            aligned=timeline["aligned"],
            duration_seconds=timeline["duration_seconds"],
        ),
        chains=chains,
        montage_url=(
            f"/api/shootouts/{shootout.id}/media/montage/{manifest.id}"
            if shootout.output_path is not None
            else None
        ),
    )


@router.get("/{shootout_id}/artefact", response_model=ShootoutArtefactResponse)
async def get_shootout_artefact(
    shootout_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: CurrentUserOptional,
) -> ShootoutArtefactResponse:
    """Return the latest manifested artefact when the caller may read it."""
    latest_version = (
        select(func.max(ShootoutManifest.version))
        .where(ShootoutManifest.shootout_id == shootout_id)
        .scalar_subquery()
    )
    latest_manifest = aliased(ShootoutManifest)
    stmt = (
        select(ShootoutModel, latest_manifest)
        .join(latest_manifest, latest_manifest.shootout_id == ShootoutModel.id)
        .where(
            ShootoutModel.id == shootout_id,
            latest_manifest.version == latest_version,
            readable_shootout_gate(current_user.id if current_user is not None else None),
        )
    )
    row = (await db.execute(stmt)).one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shootout not found",
        )

    shootout, manifest = row
    return _project_artefact(shootout, manifest)


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
    is_published = and_(*published_shootout_gate(include_unlisted=True)).label("is_published")
    stmt = (
        select(ShootoutModel, is_published)
        .where(ShootoutModel.id == shootout_id, ShootoutModel.user_id == current_user.id)
        .options(joinedload(ShootoutModel.chains))
        .with_for_update(of=ShootoutModel)
    )
    result = await db.execute(stmt)
    row = result.unique().one_or_none()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shootout not found",
        )
    shootout, published = row

    if published:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Published shootouts are immutable; create a new shootout for another run",
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
            detail="Shootout has already been run; create a new shootout for another run",
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


# --- Media Streaming Endpoints ---


@router.get("/{shootout_id}/media/{media_id}")
async def stream_public_media(
    shootout_id: UUID,
    media_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> Response:
    """Stream one manifest-pinned segment after rechecking the public gate."""
    current_manifest = aliased(ShootoutManifest)
    stmt = (
        select(ShootoutModel, current_manifest)
        .join(
            current_manifest,
            and_(
                current_manifest.shootout_id == ShootoutModel.id,
                current_manifest.version == ShootoutModel.render_version,
            ),
        )
        .where(
            ShootoutModel.id == shootout_id,
            *published_shootout_gate(include_unlisted=True),
        )
    )
    row = (await db.execute(stmt)).one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media not found")

    shootout, manifest = row
    matching = [
        chain for chain in manifest.payload["chains"] if chain["segment_id"] == str(media_id)
    ]
    if not matching:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media not found")

    root = shootout_audio_root(shootout.id)
    relative_path = Path(matching[0]["media_path"])
    if relative_path.is_absolute():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media not found")
    return media_response(
        root / relative_path,
        containment_root=root,
        not_found_detail="Media not found",
    )


@router.get("/{shootout_id}/media/montage/{media_id}")
async def stream_public_montage(
    shootout_id: UUID,
    media_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> Response:
    """Stream a montage pointer bound to the published manifest version."""
    current_manifest = aliased(ShootoutManifest)
    stmt = (
        select(ShootoutModel, current_manifest)
        .join(
            current_manifest,
            and_(
                current_manifest.shootout_id == ShootoutModel.id,
                current_manifest.version == ShootoutModel.render_version,
            ),
        )
        .where(
            ShootoutModel.id == shootout_id,
            current_manifest.id == media_id,
            *published_shootout_gate(include_unlisted=True),
        )
    )
    row = (await db.execute(stmt)).one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media not found")

    shootout, manifest = row
    if shootout.output_path is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media not found")

    version_root = shootout_audio_root(shootout.id) / f"v{manifest.version}"
    return media_response(
        shootout.output_path,
        filename=f"{shootout.name}-sequential-montage{Path(shootout.output_path).suffix.lower()}",
        attachment=True,
        containment_root=version_root,
        not_found_detail="Media not found",
    )


@router.get("/{shootout_id}/audio/master")
async def stream_master_audio(
    shootout_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Response:
    """Download the sequential montage enrichment for a completed shootout."""
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

    ext = Path(shootout.output_path).suffix.lower()
    return media_response(
        shootout.output_path,
        filename=f"{shootout.name}-sequential-montage{ext}",
        attachment=True,
        not_found_detail="Master audio file not found",
    )


@router.get("/{shootout_id}/chains/{chain_id}/audio")
async def stream_chain_audio(
    shootout_id: UUID,
    chain_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Response:
    """Stream processed audio for a specific chain in a shootout."""
    from webapp.adapters.persistence.models.shootout import (
        ShootoutChain as ShootoutChainModel,
    )

    stmt = (
        select(ShootoutChainModel, AudioSegmentModel)
        .join(ShootoutModel, ShootoutModel.id == ShootoutChainModel.shootout_id)
        .join(
            AudioSegmentModel,
            and_(
                AudioSegmentModel.shootout_chain_id == ShootoutChainModel.id,
                AudioSegmentModel.version == ShootoutModel.render_version,
            ),
        )
        .where(
            ShootoutChainModel.id == chain_id,
            ShootoutChainModel.shootout_id == shootout_id,
            ShootoutModel.user_id == current_user.id,
        )
    )
    result = await db.execute(stmt)
    row = result.one_or_none()

    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chain not found")

    chain, segment = row
    ext = Path(segment.file_path).suffix.lower()
    return media_response(
        segment.file_path,
        filename=f"{chain.label}{ext}",
        not_found_detail="Audio file not found",
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
