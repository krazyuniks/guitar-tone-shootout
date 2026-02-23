"""Gear API endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from gts.domain.value_objects.signal_chain_enums import GearType
from webapp.adapters.persistence.repositories.gear_repository import (
    SQLAlchemyGearRepository,
)
from webapp.api.v1.schemas.gear import GearListResponse, GearResponse

router = APIRouter(prefix="/api/v1/gear", tags=["gear"])

# Session override for testing
_session_override: AsyncSession | None = None


def set_session_override(session: AsyncSession) -> None:
    """Override the database session for testing.

    Args:
        session: Test database session
    """
    global _session_override
    _session_override = session


async def get_db_session() -> AsyncSession:
    """Get database session dependency.

    This is a placeholder that will be overridden when the router is included
    in the main app with dependency_overrides, or can be overridden for testing
    via set_session_override().
    """
    if _session_override:
        return _session_override
    raise NotImplementedError("Database session dependency not configured")


@router.get("/", response_model=GearListResponse)
async def list_gear(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    query: str | None = Query(None, description="Text search on name/description"),
    gear_type: GearType | None = Query(None, description="Filter by gear type"),
    manufacturer: str | None = Query(None, description="Filter by manufacturer"),
    limit: int = Query(50, ge=1, le=100, description="Maximum items per page"),
    offset: int = Query(0, ge=0, description="Number of items to skip"),
) -> GearListResponse:
    """List all gear with optional filters.

    Public endpoint - no authentication required.
    Returns paginated list of gear with support for filtering
    by type, manufacturer, and text search.

    Args:
        db: Database session
        query: Optional text search on name/description
        gear_type: Optional filter by gear type
        manufacturer: Optional filter by manufacturer
        limit: Maximum items per page (default 50, max 100)
        offset: Number of items to skip (default 0)

    Returns:
        Paginated list of gear items with metadata
    """
    repo = SQLAlchemyGearRepository(db)

    # Get total count with same filters
    total = await repo.count(
        query=query,
        gear_type=gear_type,
        manufacturer=manufacturer,
    )

    # Get filtered and paginated gear items
    gear_items = await repo.search(
        query=query,
        gear_type=gear_type,
        manufacturer=manufacturer,
        limit=limit,
        offset=offset,
    )

    # Convert to response models
    items = [GearResponse.model_validate(gear) for gear in gear_items]

    return GearListResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{gear_id}", response_model=GearResponse)
async def get_gear(
    gear_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> GearResponse:
    """Get gear details by ID.

    Public endpoint - no authentication required.
    Returns full details for a specific gear item.

    Args:
        gear_id: Gear UUID
        db: Database session

    Returns:
        Gear details

    Raises:
        HTTPException: 404 if gear not found
    """
    repo = SQLAlchemyGearRepository(db)
    gear = await repo.get_by_id(gear_id)

    if not gear:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Gear not found",
        )

    return GearResponse.model_validate(gear)
