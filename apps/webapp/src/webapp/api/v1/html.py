"""HTMX fragment endpoints for partial page updates.

This module provides HTML fragment endpoints under /api/v1/html/ namespace.
Fragments are used by HTMX for dynamic page updates without full page reloads.
All fragments return HTMLResponse with Jinja2 templates.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.domain.value_objects.signal_chain_enums import GearType
from webapp.adapters.persistence.models.gear import Gear
from webapp.adapters.persistence.models.shootout import Shootout
from webapp.adapters.persistence.models.user import User
from webapp.adapters.persistence.models.user_gear import UserGear
from webapp.adapters.persistence.repositories.gear_repository import (
    SQLAlchemyGearRepository,
)
from webapp.adapters.persistence.repositories.signal_chain_repository import (
    SQLAlchemySignalChainRepository,
)
from webapp.templates import templates

router = APIRouter(prefix="/api/v1/html", tags=["html-fragments"])

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
    # Fall back to global database session factory
    from webapp.dependencies import get_db

    async for session in get_db():
        return session
    raise RuntimeError("Failed to obtain database session")


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db_session),
) -> User:
    """Get current authenticated user from session.

    For testing, uses override if set.
    """
    if _user_override:
        return _user_override
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    result = await db.execute(select(User).where(User.id == UUID(user_id)))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    return user


@router.get("/", response_class=HTMLResponse)
async def html_namespace_root() -> HTMLResponse:
    """HTML namespace root endpoint.

    Returns 404 as there is no content at the namespace root.
    This exists to make the namespace routable.
    """
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="No content at namespace root",
    )


# Gear Browse Fragments


@router.get("/gear/list", response_class=HTMLResponse)
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
    Public endpoint - no authentication required.

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


# Library My-Gear Fragments


@router.get("/library/my-gear/list", response_class=HTMLResponse)
async def library_my_gear_list_fragment(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
    gear_type: GearType | None = Query(None, description="Filter by gear type"),
    limit: int = Query(50, ge=1, le=100, description="Maximum items per page"),
    offset: int = Query(0, ge=0, description="Number of items to skip"),
) -> HTMLResponse:
    """Render user's gear library list fragment for HTMX updates.

    Returns just the list of user's gear without page wrapper.
    Protected endpoint - requires authentication.

    Args:
        request: FastAPI request object
        db: Database session
        current_user: Currently authenticated user
        gear_type: Optional filter by gear type
        limit: Maximum items per page
        offset: Number of items to skip

    Returns:
        Rendered HTML fragment
    """
    # Build query for user's gear with filters
    query = (
        select(UserGear, Gear)
        .join(Gear, UserGear.gear_id == Gear.id)
        .where(UserGear.user_id == current_user.id)
    )

    # Apply gear type filter if provided
    if gear_type:
        query = query.where(Gear.gear_type == gear_type)

    # Apply pagination
    query = query.limit(limit).offset(offset)

    result = await db.execute(query)
    rows = result.all()

    # Build gear items list
    gear_items = []
    for _user_gear, gear in rows:
        gear_items.append(gear)

    return templates.TemplateResponse(
        request,
        "fragments/gear/list.html",
        {
            "gear_items": gear_items,
            "total": len(gear_items),
        },
    )


# Library Chains Fragments


@router.get("/library/chains/list", response_class=HTMLResponse)
async def library_chains_list_fragment(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
    limit: int = Query(50, ge=1, le=100, description="Maximum items per page"),
    offset: int = Query(0, ge=0, description="Number of items to skip"),
) -> HTMLResponse:
    """Render user's signal chain library list fragment for HTMX updates.

    Returns just the list of user's chains without page wrapper.
    Protected endpoint - requires authentication.

    Args:
        request: FastAPI request object
        db: Database session
        current_user: Currently authenticated user
        limit: Maximum items per page
        offset: Number of items to skip

    Returns:
        Rendered HTML fragment
    """
    repo = SQLAlchemySignalChainRepository(db)
    chains = await repo.get_by_user_id(current_user.id, limit=limit, offset=offset)

    # Convert to dict for template
    chain_items = []
    for chain in chains:
        chain_items.append({
            "id": str(chain.id),
            "name": chain.name,
            "description": chain.description,
            "platform": chain.platform.value,
            "created_at": chain.created_at,
        })

    return templates.TemplateResponse(
        request,
        "fragments/chains/list.html",
        {
            "chains": chain_items,
        },
    )


# Library Shootouts Fragments


@router.get("/library/shootouts/list", response_class=HTMLResponse)
async def library_shootouts_list_fragment(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
    status: str | None = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=100, description="Maximum items per page"),
    offset: int = Query(0, ge=0, description="Number of items to skip"),
) -> HTMLResponse:
    """Render user's shootout library list fragment for HTMX updates.

    Returns just the list of user's shootouts without page wrapper.
    Protected endpoint - requires authentication.

    Args:
        request: FastAPI request object
        db: Database session
        current_user: Currently authenticated user
        status: Optional filter by status
        limit: Maximum items per page
        offset: Number of items to skip

    Returns:
        Rendered HTML fragment
    """
    # Build query for user's shootouts
    query = (
        select(Shootout)
        .where(Shootout.user_id == current_user.id)
        .order_by(Shootout.created_at.desc())
    )

    # Apply status filter if provided
    if status:
        query = query.where(Shootout.status == status)

    # Apply pagination
    query = query.limit(limit).offset(offset)

    result = await db.execute(query)
    shootouts = result.scalars().all()

    # Convert to dict for template
    shootout_items = []
    for shootout in shootouts:
        shootout_items.append({
            "id": str(shootout.id),
            "name": shootout.name,
            "description": shootout.description,
            "status": shootout.status,
            "created_at": shootout.created_at,
        })

    return templates.TemplateResponse(
        request,
        "fragments/shootouts/list.html",
        {
            "shootouts": shootout_items,
        },
    )
