"""User library API endpoints."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from webapp.adapters.persistence.models.gear import Gear
from webapp.adapters.persistence.models.user import User
from webapp.adapters.persistence.models.user_gear import UserGear
from webapp.api.v1.schemas.library import (
    AddGearToLibraryRequest,
    UserGearResponse,
)

router = APIRouter(prefix="/api/v1/library", tags=["library"])

# Session override for testing
_session_override: AsyncSession | None = None
_user_override: User | None = None


def set_session_override(session: AsyncSession) -> None:
    """Override the database session for testing.

    Args:
        session: Test database session
    """
    global _session_override
    _session_override = session


def set_user_override(user: User | None) -> None:
    """Override the current user for testing.

    Args:
        user: Test user to use as CurrentUser
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


@router.get("/gear", response_model=list[UserGearResponse])
async def list_user_gear(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[UserGearResponse]:
    """List current user's gear library.

    Protected endpoint - requires authentication.
    Returns only the current user's gear items.

    Args:
        db: Database session
        current_user: Currently authenticated user

    Returns:
        List of user's gear library items
    """
    # Query user's gear with joined gear details
    result = await db.execute(
        select(UserGear, Gear)
        .join(Gear, UserGear.gear_id == Gear.id)
        .where(UserGear.user_id == current_user.id)
    )
    rows = result.all()

    # Build response models
    gear_items = []
    for user_gear, gear in rows:
        gear_items.append(
            UserGearResponse(
                user_gear_id=user_gear.id,
                gear_id=gear.id,
                gear_name=gear.name,
                gear_type=gear.gear_type,
                nickname=user_gear.nickname,
                is_favourite=user_gear.is_favourite,
            )
        )

    return gear_items


@router.post("/gear", response_model=UserGearResponse, status_code=status.HTTP_201_CREATED)
async def add_gear_to_library(
    request_data: AddGearToLibraryRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserGearResponse:
    """Add gear to current user's library.

    Protected endpoint - requires authentication.
    Validates that the gear exists and isn't already in library.

    Args:
        request_data: Gear to add with optional nickname
        db: Database session
        current_user: Currently authenticated user

    Returns:
        Created user gear library item

    Raises:
        HTTPException: 404 if gear not found
        HTTPException: 409 if gear already in library
    """
    # Verify gear exists
    result = await db.execute(
        select(Gear).where(Gear.id == request_data.gear_id)
    )
    gear = result.scalar_one_or_none()

    if not gear:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Gear not found",
        )

    # Create user gear entry
    user_gear = UserGear(
        id=uuid4(),
        user_id=current_user.id,
        gear_id=request_data.gear_id,
        nickname=request_data.nickname,
        is_favourite=request_data.is_favourite,
    )

    try:
        db.add(user_gear)
        await db.flush()
        await db.commit()
    except IntegrityError:
        await db.rollback()
        # Unique constraint violation - gear already in library
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Gear is already in library",
        )

    await db.refresh(gear)

    return UserGearResponse(
        user_gear_id=user_gear.id,
        gear_id=gear.id,
        gear_name=gear.name,
        gear_type=gear.gear_type,
        nickname=user_gear.nickname,
        is_favourite=user_gear.is_favourite,
    )


@router.delete("/gear/{user_gear_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_gear_from_library(
    user_gear_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    """Remove gear from current user's library.

    Protected endpoint - requires authentication.
    Only allows user to remove their own gear.
    Returns 404 for both nonexistent gear and other users' gear
    to avoid leaking existence.

    Args:
        user_gear_id: ID of user gear entry to remove
        db: Database session
        current_user: Currently authenticated user

    Raises:
        HTTPException: 404 if gear not found or not owned by user
    """
    # Find user gear entry for current user only
    result = await db.execute(
        select(UserGear).where(
            UserGear.id == user_gear_id,
            UserGear.user_id == current_user.id,
        )
    )
    user_gear = result.scalar_one_or_none()

    if not user_gear:
        # Return 404 for both not found and not owned
        # to avoid leaking existence
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Gear not found",
        )

    await db.delete(user_gear)
    await db.commit()
