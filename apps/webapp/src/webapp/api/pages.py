"""SSR page routes for public pages."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from core.domain.value_objects.signal_chain_enums import GearType
from webapp.adapters.persistence.repositories.gear_repository import (
    SQLAlchemyGearRepository,
)
from webapp.templates import templates

router = APIRouter(tags=["pages"])

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

    Checks for test session override first, then falls back to the
    global database session factory.
    """
    if _session_override:
        return _session_override
    # Fall back to global database session factory
    from webapp.dependencies import get_db

    async for session in get_db():
        return session
    raise RuntimeError("Failed to obtain database session")


@router.get("/gear", response_class=HTMLResponse)
async def gear_browse_page(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> HTMLResponse:
    """Render gear browse page.

    Public page showing all gear with filtering controls.
    Uses HTMX for dynamic list updates.

    Args:
        request: FastAPI request object
        db: Database session

    Returns:
        Rendered HTML page
    """
    return templates.TemplateResponse(
        request,
        "pages/gear_browse.html",
        {},
    )


@router.get("/gear/{slug}", response_class=HTMLResponse)
async def gear_detail_page(
    request: Request,
    slug: str,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> HTMLResponse:
    """Render gear detail page.

    Public page showing full details for a specific gear item.

    Args:
        request: FastAPI request object
        slug: Gear URL slug
        db: Database session

    Returns:
        Rendered HTML page

    Raises:
        HTTPException: 404 if gear not found or not public
    """
    repo = SQLAlchemyGearRepository(db)
    gear = await repo.get_by_slug(slug)

    # Return 404 if gear not found or not public (hide existence)
    if not gear or not gear.is_public:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Gear not found",
        )

    return templates.TemplateResponse(
        request,
        "pages/gear_detail.html",
        {"gear": gear},
    )


@router.get("/fragments/gear/list", response_class=HTMLResponse)
async def gear_list_fragment(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    query: str | None = Query(None, description="Text search on name/description"),
    gear_type: GearType | None = Query(None, description="Filter by gear type"),
    manufacturer: str | None = Query(None, description="Filter by manufacturer"),
    limit: int = Query(50, ge=1, le=100, description="Maximum items per page"),
    offset: int = Query(0, ge=0, description="Number of items to skip"),
) -> HTMLResponse:
    """Render gear list fragment for HTMX updates.

    Returns just the list of gear cards without page wrapper.
    Used by HTMX to update the gear list dynamically.

    Args:
        request: FastAPI request object
        db: Database session
        query: Optional text search on name/description
        gear_type: Optional filter by gear type
        manufacturer: Optional filter by manufacturer
        limit: Maximum items per page
        offset: Number of items to skip

    Returns:
        Rendered HTML fragment
    """
    repo = SQLAlchemyGearRepository(db)

    # Get total count with filters
    total = await repo.count(
        query=query,
        gear_type=gear_type,
        manufacturer=manufacturer,
    )

    # Get filtered and paginated gear items (only public ones)
    all_gear = await repo.search(
        query=query,
        gear_type=gear_type,
        manufacturer=manufacturer,
        limit=limit,
        offset=offset,
    )

    # Filter to only public gear
    gear_items = [gear for gear in all_gear if gear.is_public]

    return templates.TemplateResponse(
        request,
        "fragments/gear/list.html",
        {
            "gear_items": gear_items,
            "total": total,
        },
    )
