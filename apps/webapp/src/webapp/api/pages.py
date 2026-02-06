"""SSR page routes for public pages."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.domain.value_objects.signal_chain_enums import GearType
from webapp.adapters.persistence.models.gear import Gear
from webapp.adapters.persistence.models.user import User
from webapp.adapters.persistence.models.user_gear import UserGear
from webapp.adapters.persistence.repositories.gear_repository import (
    SQLAlchemyGearRepository,
)
from webapp.adapters.persistence.repositories.signal_chain_repository import (
    SQLAlchemySignalChainRepository,
)
from webapp.templates import templates

router = APIRouter(tags=["pages"])

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


@router.get("/library/my-gear", response_class=HTMLResponse)
async def library_my_gear_page(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> HTMLResponse:
    """Render user's gear library page.

    Protected page showing user's personal gear collection.
    Uses HTMX for dynamic add/remove operations.

    Args:
        request: FastAPI request object
        db: Database session
        current_user: Currently authenticated user

    Returns:
        Rendered HTML page
    """
    # Query user's gear with joined gear details
    result = await db.execute(
        select(UserGear, Gear)
        .join(Gear, UserGear.gear_id == Gear.id)
        .where(UserGear.user_id == current_user.id)
    )
    rows = result.all()

    # Build gear items list with all necessary details
    gear_items = []
    for user_gear, gear in rows:
        gear_items.append({
            "user_gear_id": str(user_gear.id),
            "gear_id": str(gear.id),
            "nickname": user_gear.nickname,
            "is_favourite": user_gear.is_favourite,
            "gear_name": gear.name,
            "gear_type": gear.gear_type.value,
            "manufacturer": gear.manufacturer,
        })

    return templates.TemplateResponse(
        request,
        "pages/library/my_gear.html",
        {
            "gear_items": gear_items,
        },
    )


@router.get("/library/chains", response_class=HTMLResponse)
async def library_chains_page(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> HTMLResponse:
    """Render user's signal chain library page.

    Protected page showing user's signal chains.
    Uses HTMX for dynamic operations (delete, duplicate).

    Args:
        request: FastAPI request object
        db: Database session
        current_user: Currently authenticated user

    Returns:
        Rendered HTML page
    """
    repo = SQLAlchemySignalChainRepository(db)
    chains = await repo.get_by_user_id(current_user.id)

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
        "pages/library/chains.html",
        {
            "chains": chain_items,
        },
    )


@router.get("/fragments/chains/list", response_class=HTMLResponse)
async def chain_list_fragment(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> HTMLResponse:
    """Render chain list fragment for HTMX updates.

    Returns just the list of chain items without page wrapper.
    Used by HTMX to update the chain list dynamically.

    Args:
        request: FastAPI request object
        db: Database session
        current_user: Currently authenticated user

    Returns:
        Rendered HTML fragment
    """
    repo = SQLAlchemySignalChainRepository(db)
    chains = await repo.get_by_user_id(current_user.id)

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


@router.delete("/fragments/chains/{chain_id}", response_class=HTMLResponse)
async def chain_delete_fragment(
    request: Request,
    chain_id: str,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> HTMLResponse:
    """Delete a signal chain via HTMX.

    Args:
        request: FastAPI request object
        chain_id: Chain UUID as string
        db: Database session
        current_user: Currently authenticated user

    Returns:
        Empty response (HTMX will swap out the element)

    Raises:
        HTTPException: 404 if chain not found or not owned by user
    """
    from uuid import UUID

    repo = SQLAlchemySignalChainRepository(db)

    # Get chain and verify ownership
    chain = await repo.get_by_id(UUID(chain_id))
    if not chain or chain.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chain not found",
        )

    # Delete via transaction
    async with db.begin():
        await repo.delete(UUID(chain_id))

    # Return empty response - HTMX will swap out the element
    return HTMLResponse(content="", status_code=200)


@router.post("/fragments/chains/{chain_id}/duplicate", response_class=HTMLResponse)
async def chain_duplicate_fragment(
    request: Request,
    chain_id: str,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> HTMLResponse:
    """Duplicate a signal chain via HTMX.

    Args:
        request: FastAPI request object
        chain_id: Chain UUID as string
        db: Database session
        current_user: Currently authenticated user

    Returns:
        HTML fragment with updated chain list

    Raises:
        HTTPException: 404 if chain not found or not owned by user
    """
    from datetime import datetime, timezone
    from uuid import UUID, uuid4

    from core.domain.entities.signal_chain import (
        SignalChain as SignalChainEntity,
    )

    repo = SQLAlchemySignalChainRepository(db)

    # Get chain and verify ownership
    chain = await repo.get_by_id(UUID(chain_id))
    if not chain or chain.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chain not found",
        )

    # Create duplicate with new ID and updated name
    now = datetime.now(timezone.utc)
    new_chain = SignalChainEntity(
        id=uuid4(),
        user_id=current_user.id,
        name=f"{chain.name} (Copy)",
        description=chain.description,
        platform=chain.platform,
        blocks=chain.blocks.copy(),  # Shallow copy blocks list
        created_at=now,
        updated_at=now,
    )

    # Save via transaction
    async with db.begin():
        await repo.save(new_chain)

    # Return updated chain list fragment
    chains = await repo.get_by_user_id(current_user.id)
    chain_items = []
    for c in chains:
        chain_items.append({
            "id": str(c.id),
            "name": c.name,
            "description": c.description,
            "platform": c.platform.value,
            "created_at": c.created_at,
        })

    return templates.TemplateResponse(
        request,
        "fragments/chains/list.html",
        {
            "chains": chain_items,
        },
    )


@router.get("/library/chains/build", response_class=HTMLResponse)
async def chain_builder_page(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
    chain_id: str | None = Query(None, description="Chain ID for editing"),
) -> HTMLResponse:
    """Render chain builder page.

    Protected page for creating or editing signal chains.
    Mounts React SignalChainBuilder component.

    Args:
        request: FastAPI request object
        db: Database session
        current_user: Currently authenticated user
        chain_id: Optional chain ID for editing mode

    Returns:
        Rendered HTML page
    """
    return templates.TemplateResponse(
        request,
        "pages/library/chains_build.html",
        {
            "chain_id": chain_id,
        },
    )
