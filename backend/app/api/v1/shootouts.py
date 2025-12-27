"""Shootout management API endpoints.

Provides CRUD operations for shootout configurations:
- POST /shootouts - Create a new shootout
- GET /shootouts - List user's shootouts with pagination
- GET /shootouts/public - List public (processed) shootouts for browsing
- GET /shootouts/{id} - Get shootout details
- PUT /shootouts/{id} - Update a shootout
- DELETE /shootouts/{id} - Delete a shootout
"""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentUser, CurrentUserOptional, DbSession
from app.schemas.shootout import (
    ShootoutCreate,
    ShootoutListItem,
    ShootoutListResponse,
    ShootoutResponse,
    ShootoutUpdate,
)
from app.services.shootout_service import ShootoutService

router = APIRouter(prefix="/shootouts", tags=["shootouts"])


@router.post("", response_model=ShootoutResponse, status_code=status.HTTP_201_CREATED)
async def create_shootout(
    shootout_in: ShootoutCreate,
    user: CurrentUser,
    db: DbSession,
) -> ShootoutResponse:
    """Create a new shootout configuration.

    The shootout will be created with the provided tone selections.
    After creation, you can start a processing job for this shootout.

    Args:
        shootout_in: Shootout configuration data.
        user: Current authenticated user.
        db: Database session.

    Returns:
        The created shootout with all tone selections.
    """
    service = ShootoutService(db)
    shootout = await service.create_shootout(user, shootout_in)
    return ShootoutResponse.model_validate(shootout)


@router.get("", response_model=ShootoutListResponse)
async def list_shootouts(
    user: CurrentUser,
    db: DbSession,
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page (1-100)"),
) -> ShootoutListResponse:
    """List shootouts for the current user.

    Returns a paginated list of the user's shootouts, ordered by creation
    date (newest first).

    Args:
        user: Current authenticated user.
        db: Database session.
        page: Page number (1-indexed).
        page_size: Items per page (1-100).

    Returns:
        Paginated list of shootouts with total count.
    """
    service = ShootoutService(db)
    shootouts, total = await service.list_shootouts(user, page, page_size)

    shootout_items = [
        ShootoutListItem(
            id=s.id,
            name=s.name,
            description=s.description,
            is_processed=s.is_processed,
            output_path=s.output_path,
            tone_count=len(s.tone_selections),
            created_at=s.created_at,
            updated_at=s.updated_at,
        )
        for s in shootouts
    ]

    return ShootoutListResponse(
        shootouts=shootout_items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/public", response_model=ShootoutListResponse)
async def list_public_shootouts(
    db: DbSession,
    _user: CurrentUserOptional,  # Optional auth for future personalization
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page (1-100)"),
) -> ShootoutListResponse:
    """List public (processed) shootouts for browsing.

    Returns a paginated list of all processed shootouts that are available
    for public viewing. No authentication required.

    Args:
        db: Database session.
        _user: Optional authenticated user (for future personalization).
        page: Page number (1-indexed).
        page_size: Items per page (1-100).

    Returns:
        Paginated list of public shootouts with total count.
    """
    service = ShootoutService(db)
    shootouts, total = await service.list_public_shootouts(page, page_size)

    shootout_items = [
        ShootoutListItem(
            id=s.id,
            name=s.name,
            description=s.description,
            is_processed=s.is_processed,
            output_path=s.output_path,
            tone_count=len(s.tone_selections),
            created_at=s.created_at,
            updated_at=s.updated_at,
        )
        for s in shootouts
    ]

    return ShootoutListResponse(
        shootouts=shootout_items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{shootout_id}", response_model=ShootoutResponse)
async def get_shootout(
    shootout_id: UUID,
    user: CurrentUser,
    db: DbSession,
) -> ShootoutResponse:
    """Get details of a specific shootout.

    Returns the full shootout details including all tone selections.
    Only the owner can access their own shootouts.

    Args:
        shootout_id: The shootout ID.
        user: Current authenticated user.
        db: Database session.

    Returns:
        The shootout details with all tone selections.

    Raises:
        HTTPException: If shootout not found or doesn't belong to user.
    """
    service = ShootoutService(db)
    shootout = await service.get_shootout(user, shootout_id)

    if not shootout:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shootout not found",
        )

    return ShootoutResponse.model_validate(shootout)


@router.put("/{shootout_id}", response_model=ShootoutResponse)
async def update_shootout(
    shootout_id: UUID,
    shootout_update: ShootoutUpdate,
    user: CurrentUser,
    db: DbSession,
) -> ShootoutResponse:
    """Update a shootout.

    Only the owner can update their shootouts. Only provided fields will
    be updated.

    Args:
        shootout_id: The shootout ID to update.
        shootout_update: The fields to update.
        user: Current authenticated user.
        db: Database session.

    Returns:
        The updated shootout.

    Raises:
        HTTPException: If shootout not found or doesn't belong to user.
    """
    service = ShootoutService(db)
    shootout = await service.update_shootout(user, shootout_id, shootout_update)

    if not shootout:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shootout not found",
        )

    return ShootoutResponse.model_validate(shootout)


@router.delete("/{shootout_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_shootout(
    shootout_id: UUID,
    user: CurrentUser,
    db: DbSession,
) -> None:
    """Delete a shootout.

    Only the owner can delete their shootouts. This will also delete all
    associated tone selections.

    Args:
        shootout_id: The shootout ID to delete.
        user: Current authenticated user.
        db: Database session.

    Raises:
        HTTPException: If shootout not found or doesn't belong to user.
    """
    service = ShootoutService(db)
    deleted = await service.delete_shootout(user, shootout_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shootout not found",
        )
