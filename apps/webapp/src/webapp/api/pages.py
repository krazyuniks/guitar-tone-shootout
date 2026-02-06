"""SSR page routes for public and protected pages."""

from datetime import UTC
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
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
from webapp.services.shootout_service import ShootoutService
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


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db_session),
) -> User | None:
    """Get current authenticated user from session.

    Returns None for unauthenticated users (public pages still render).
    For testing, uses override if set.
    """
    if _user_override is not None:
        return _user_override
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    result = await db.execute(select(User).where(User.id == UUID(user_id)))
    return result.scalar_one_or_none()


async def require_current_user(
    current_user: Annotated[User | None, Depends(get_current_user)],
) -> User:
    """Require authenticated user — redirects to login if not authenticated."""
    if current_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    return current_user


# --- Public pages ---


@router.get("/gear", response_class=HTMLResponse)
async def gear_browse_page(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User | None, Depends(get_current_user)],
) -> HTMLResponse:
    """Render gear browse page.

    Public page showing all gear with filtering controls.
    Uses HTMX for dynamic list updates.
    """
    return templates.TemplateResponse(
        request,
        "pages/gear_browse.html",
        {"user": current_user},
    )


@router.get("/gear/{slug}", response_class=HTMLResponse)
async def gear_detail_page(
    request: Request,
    slug: str,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User | None, Depends(get_current_user)],
) -> HTMLResponse:
    """Render gear detail page.

    Public page showing full details for a specific gear item.
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
        {"gear": gear, "user": current_user},
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
    """Render gear list fragment for HTMX updates."""
    repo = SQLAlchemyGearRepository(db)

    total = await repo.count(
        query=query,
        gear_type=gear_type,
        manufacturer=manufacturer,
    )

    all_gear = await repo.search(
        query=query,
        gear_type=gear_type,
        manufacturer=manufacturer,
        limit=limit,
        offset=offset,
    )

    gear_items = [gear for gear in all_gear if gear.is_public]

    return templates.TemplateResponse(
        request,
        "fragments/gear/list.html",
        {
            "gear_items": gear_items,
            "total": total,
        },
    )


@router.get("/shootouts", response_class=HTMLResponse)
async def shootouts_page(
    request: Request,
    current_user: Annotated[User | None, Depends(get_current_user)],
) -> HTMLResponse:
    """Render public shootouts page.

    If authenticated, redirects to library shootouts.
    Otherwise shows the public shootouts landing.
    """
    if current_user:
        return RedirectResponse(url="/library/shootouts", status_code=302)
    return templates.TemplateResponse(
        request,
        "pages/shootouts.html",
        {"user": None},
    )


@router.get("/logout")
async def logout(request: Request) -> RedirectResponse:
    """Clear session and redirect to home."""
    request.session.clear()
    return RedirectResponse(url="/", status_code=302)


# --- Protected pages (require authentication) ---


@router.get("/library/my-gear", response_class=HTMLResponse)
async def library_my_gear_page(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(require_current_user)],
) -> HTMLResponse:
    """Render user's gear library page.

    Protected page showing user's personal gear collection.
    """
    result = await db.execute(
        select(UserGear, Gear)
        .join(Gear, UserGear.gear_id == Gear.id)
        .where(UserGear.user_id == current_user.id)
    )
    rows = result.all()

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
            "user": current_user,
        },
    )


@router.get("/library/chains", response_class=HTMLResponse)
async def library_chains_page(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(require_current_user)],
) -> HTMLResponse:
    """Render user's signal chain library page.

    Protected page showing user's signal chains.
    """
    repo = SQLAlchemySignalChainRepository(db)
    chains = await repo.get_by_user_id(current_user.id)

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
            "user": current_user,
        },
    )


@router.get("/fragments/chains/list", response_class=HTMLResponse)
async def chain_list_fragment(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(require_current_user)],
) -> HTMLResponse:
    """Render chain list fragment for HTMX updates."""
    repo = SQLAlchemySignalChainRepository(db)
    chains = await repo.get_by_user_id(current_user.id)

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
    current_user: Annotated[User, Depends(require_current_user)],
) -> HTMLResponse:
    """Delete a signal chain via HTMX."""
    repo = SQLAlchemySignalChainRepository(db)

    chain = await repo.get_by_id(UUID(chain_id))
    if not chain or chain.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chain not found",
        )

    async with db.begin():
        await repo.delete(UUID(chain_id))

    return HTMLResponse(content="", status_code=200)


@router.post("/fragments/chains/{chain_id}/duplicate", response_class=HTMLResponse)
async def chain_duplicate_fragment(
    request: Request,
    chain_id: str,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(require_current_user)],
) -> HTMLResponse:
    """Duplicate a signal chain via HTMX."""
    from datetime import datetime
    from uuid import uuid4

    from core.domain.entities.signal_chain import (
        SignalChain as SignalChainEntity,
    )

    repo = SQLAlchemySignalChainRepository(db)

    chain = await repo.get_by_id(UUID(chain_id))
    if not chain or chain.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chain not found",
        )

    now = datetime.now(UTC)
    new_chain = SignalChainEntity(
        id=uuid4(),
        user_id=current_user.id,
        name=f"{chain.name} (Copy)",
        description=chain.description,
        platform=chain.platform,
        blocks=chain.blocks.copy(),
        created_at=now,
        updated_at=now,
    )

    async with db.begin():
        await repo.save(new_chain)

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
    current_user: Annotated[User, Depends(require_current_user)],
    chain_id: str | None = Query(None, description="Chain ID for editing"),
) -> HTMLResponse:
    """Render chain builder page.

    Protected page for creating or editing signal chains.
    """
    return templates.TemplateResponse(
        request,
        "pages/library/chains_build.html",
        {
            "chain_id": chain_id,
            "user": current_user,
        },
    )


@router.get("/library/shootouts", response_class=HTMLResponse)
async def library_shootouts_page(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(require_current_user)],
) -> HTMLResponse:
    """Render user's shootout library page.

    Protected page showing user's shootouts.
    """
    service = ShootoutService(db)
    shootouts = await service.get_by_user_id(current_user.id)

    shootout_items = []
    for shootout in shootouts:
        shootout_items.append({
            "id": str(shootout.id),
            "name": shootout.name,
            "description": shootout.description,
            "chain_count": shootout.chain_count,
            "is_processed": shootout.is_processed,
            "created_at": shootout.created_at,
        })

    return templates.TemplateResponse(
        request,
        "pages/library/shootouts.html",
        {
            "shootouts": shootout_items,
            "user": current_user,
        },
    )


@router.get("/shootout/{shootout_id}", response_class=HTMLResponse)
async def shootout_detail_page(
    request: Request,
    shootout_id: str,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(require_current_user)],
) -> HTMLResponse:
    """Render shootout detail page.

    Protected page showing shootout details and chains.
    """
    from webapp.adapters.persistence.models.di_track import DITrack
    from webapp.adapters.persistence.models.signal_chain import (
        SignalChain as SignalChainModel,
    )

    service = ShootoutService(db)

    shootout = await service.get_by_id(UUID(shootout_id))
    if not shootout or shootout.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shootout not found",
        )

    di_track_result = await db.execute(
        select(DITrack).where(DITrack.id == shootout.di_track_id)
    )
    di_track = di_track_result.scalar_one_or_none()

    chain_items = []
    for shootout_chain in shootout.chains:
        chain_result = await db.execute(
            select(SignalChainModel).where(
                SignalChainModel.id == shootout_chain.signal_chain_id
            )
        )
        chain = chain_result.scalar_one_or_none()
        if chain:
            chain_items.append({
                "signal_chain_id": str(shootout_chain.signal_chain_id),
                "position": shootout_chain.position,
                "label": shootout_chain.label,
                "chain_name": chain.name,
            })

    chain_items.sort(key=lambda x: x["position"])

    return templates.TemplateResponse(
        request,
        "pages/shootout_detail.html",
        {
            "shootout": {
                "id": str(shootout.id),
                "name": shootout.name,
                "description": shootout.description,
                "chain_count": shootout.chain_count,
                "is_processed": shootout.is_processed,
                "output_path": shootout.output_path,
            },
            "di_track": {
                "id": str(di_track.id) if di_track else None,
                "name": di_track.name if di_track else "Unknown",
            },
            "chains": chain_items,
            "user": current_user,
        },
    )


@router.get("/fragments/shootouts/list", response_class=HTMLResponse)
async def shootout_list_fragment(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(require_current_user)],
) -> HTMLResponse:
    """Render shootout list fragment for HTMX updates."""
    service = ShootoutService(db)
    shootouts = await service.get_by_user_id(current_user.id)

    shootout_items = []
    for shootout in shootouts:
        shootout_items.append({
            "id": str(shootout.id),
            "name": shootout.name,
            "description": shootout.description,
            "chain_count": shootout.chain_count,
            "is_processed": shootout.is_processed,
            "created_at": shootout.created_at,
        })

    return templates.TemplateResponse(
        request,
        "fragments/shootouts/list.html",
        {
            "shootouts": shootout_items,
        },
    )


@router.delete("/fragments/shootouts/{shootout_id}", response_class=HTMLResponse)
async def shootout_delete_fragment(
    request: Request,
    shootout_id: str,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(require_current_user)],
) -> HTMLResponse:
    """Delete a shootout via HTMX."""
    service = ShootoutService(db)

    shootout = await service.get_by_id(UUID(shootout_id))
    if not shootout or shootout.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shootout not found",
        )

    async with db.begin():
        await service.delete(UUID(shootout_id))

    return HTMLResponse(content="", status_code=200)
