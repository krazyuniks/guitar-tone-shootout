"""DI Tracks API endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from webapp.adapters.persistence.models.user import User
from webapp.adapters.persistence.repositories.di_track_repository import (
    SQLAlchemyDITrackRepository,
)

router = APIRouter(prefix="/api/v1/di-tracks", tags=["di-tracks"])

# Session and user overrides for testing
_session_override: AsyncSession | None = None
_user_override: User | None = None


def set_session_override(session: AsyncSession | None) -> None:
    """Override the database session for testing."""
    global _session_override
    _session_override = session


def set_user_override(user: User | None) -> None:
    """Override the current user for testing."""
    global _user_override
    _user_override = user


async def get_db_session() -> AsyncSession:
    """Get database session dependency."""
    if _session_override:
        return _session_override
    raise NotImplementedError("Database session dependency not configured")


async def get_current_user() -> User:
    """Get current authenticated user dependency."""
    if _user_override:
        return _user_override
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
    )


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
