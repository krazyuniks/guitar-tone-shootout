"""User library API endpoints."""

from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from webapp.adapters.persistence.models.gear import Gear
from webapp.adapters.persistence.models.gear_model import GearModel
from webapp.adapters.persistence.models.user import User
from webapp.adapters.persistence.models.user_gear import UserGear
from webapp.api.v1.schemas.library import (
    AddGearToLibraryRequest,
    UserGearResponse,
)
from webapp.auth.dependencies import (
    get_current_user_required as get_current_user,
)
from webapp.auth.dependencies import (
    get_db_session,
)

router = APIRouter(prefix="/api/v1/library", tags=["library"])


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
    # Query user's gear with joined gear model and gear details
    result = await db.execute(
        select(UserGear, GearModel, Gear)
        .join(GearModel, UserGear.gear_model_id == GearModel.id)
        .join(Gear, GearModel.gear_id == Gear.id)
        .where(UserGear.user_id == current_user.id)
    )
    rows = result.all()

    # Build response models
    gear_items = []
    for user_gear, gear_model, gear in rows:
        gear_items.append(
            UserGearResponse(
                user_gear_id=user_gear.id,
                gear_model_id=gear_model.id,
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
    # Verify gear model exists and get its parent gear
    result = await db.execute(
        select(GearModel, Gear)
        .join(Gear, GearModel.gear_id == Gear.id)
        .where(GearModel.id == request_data.gear_model_id)
    )
    row = result.first()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Gear model not found",
        )

    gear_model, gear = row

    # Create user gear entry
    user_gear = UserGear(
        id=uuid4(),
        user_id=current_user.id,
        gear_model_id=request_data.gear_model_id,
        nickname=request_data.nickname,
        is_favourite=request_data.is_favourite,
    )

    try:
        db.add(user_gear)
        await db.flush()
        await db.commit()
    except IntegrityError:
        await db.rollback()
        # Unique constraint violation - gear model already in library
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Gear is already in library",
        )

    return UserGearResponse(
        user_gear_id=user_gear.id,
        gear_model_id=gear_model.id,
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
