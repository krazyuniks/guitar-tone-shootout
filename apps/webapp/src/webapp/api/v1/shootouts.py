"""Shootout API endpoints."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.domain.entities.shootout import Shootout
from webapp.adapters.persistence.models.user import User
from webapp.api.v1.schemas.shootout import (
    ShootoutCreateRequest,
    ShootoutResponse,
)
from webapp.services.shootout_service import ShootoutService

router = APIRouter(prefix="/api/v1/shootouts", tags=["shootouts"])

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
    shootout = await service.get_by_id(shootout_id)

    # Return 404 if shootout not found or not owned by user
    # (Return 404 instead of 403 to avoid leaking existence)
    if not shootout or shootout.user_id != current_user.id:
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
        is_processed=shootout.is_processed,
        output_path=shootout.output_path,
        created_at=shootout.created_at,
        updated_at=shootout.updated_at,
    )
