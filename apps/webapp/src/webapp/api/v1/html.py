"""HTMX fragment endpoints for partial page updates.

This module provides HTML fragment endpoints under /api/v1/html/ namespace.
Fragments are used by HTMX for dynamic page updates without full page reloads.
All fragments return HTMLResponse with Jinja2 templates.
"""

from html import escape
from math import ceil
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from core.domain.value_objects.job_status import JobStatus
from core.domain.value_objects.signal_chain_enums import GearType
from webapp.adapters.persistence.models.gear import Gear
from webapp.adapters.persistence.models.gear_model import GearModel
from webapp.adapters.persistence.models.job import Job
from webapp.adapters.persistence.models.shootout import DITrack, Shootout, ShootoutChain
from webapp.adapters.persistence.models.user import User
from webapp.adapters.persistence.models.user_gear import UserGear
from webapp.adapters.persistence.repositories.gear_repository import (
    SQLAlchemyGearRepository,
)
from webapp.adapters.persistence.repositories.shootout_comment_repository import (
    ShootoutCommentRepository,
)
from webapp.adapters.persistence.repositories.shootout_repository import (
    SQLAlchemyShootoutRepository,
)
from webapp.adapters.persistence.repositories.signal_chain_repository import (
    SQLAlchemySignalChainRepository,
)
from webapp.api.pages import _gear_to_pack
from webapp.auth.dependencies import (
    get_current_user_optional as get_optional_user,
)
from webapp.auth.dependencies import (
    get_current_user_required as get_current_user,
)
from webapp.auth.dependencies import (
    get_db_session,
)
from webapp.templates import _relative_time, templates

router = APIRouter(prefix="/api/v1/html", tags=["html-fragments"])


def _format_duration(seconds: float | None) -> str:
    """Format seconds to mm:ss string."""
    if seconds is None:
        return "0:00"
    mins = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{mins}:{secs:02d}"


def _build_shootout_detail_context(shootout: Shootout) -> dict[str, object]:
    """Build template context for shootout detail fragment."""
    chains = sorted(shootout.chains, key=lambda chain: chain.position)
    chain_items = [
        {
            "id": str(chain.id),
            "position": chain.position + 1,  # Display is 1-indexed in UI labels.
            "label": chain.label,
            "chain_name": chain.signal_chain.name if chain.signal_chain else chain.label,
        }
        for chain in chains
    ]

    duration = _format_duration(shootout.di_track.duration_seconds) if shootout.di_track else None
    di_track = (
        {
            "id": str(shootout.di_track.id),
            "name": shootout.di_track.name,
            "duration": duration,
        }
        if shootout.di_track
        else None
    )

    shootout_context = {
        "id": str(shootout.id),
        "name": shootout.name,
        "description": shootout.description,
        "status": shootout.status.value,
        "output_path": shootout.output_path,
        "video_path": shootout.video_path,
    }

    creator = (
        {
            "id": str(shootout.user.id),
            "username": shootout.user.username,
        }
        if shootout.user
        else None
    )

    return {
        "shootout": shootout_context,
        "creator": creator,
        "relative_time": _relative_time(shootout.created_at),
        "tone_count": len(chain_items),
        "di_track": di_track,
        "chains": chain_items,
        "is_owner": True,
    }


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
        .join(GearModel, UserGear.gear_model_id == GearModel.id)
        .join(Gear, GearModel.gear_id == Gear.id)
        .where(UserGear.user_id == current_user.id)
        .options(joinedload(Gear.models))
    )

    # Apply gear type filter if provided
    if gear_type:
        query = query.where(Gear.gear_type == gear_type)

    # Apply pagination
    query = query.limit(limit).offset(offset)

    result = await db.execute(query)
    rows = result.unique().all()

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
        chain_items.append(
            {
                "id": str(chain.id),
                "name": chain.name,
                "description": chain.description,
                "platform": chain.platform.value,
                "created_at": chain.created_at,
            }
        )

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
        shootout_items.append(
            {
                "id": str(shootout.id),
                "name": shootout.name,
                "description": shootout.description,
                "status": shootout.status,
                "created_at": shootout.created_at,
            }
        )

    return templates.TemplateResponse(
        request,
        "fragments/shootouts/list.html",
        {
            "shootouts": shootout_items,
        },
    )


# --- New fragment endpoints matching restored frontend templates ---


# Library My-Gear Results (page-based)


@router.get("/my-gear/results", response_class=HTMLResponse)
async def my_gear_results_fragment(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
    search: str | None = Query(None),
    gear_type: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(24, ge=1, le=100),
    sort_by: str = Query("date_added", description="Sort field: name, date_added, type"),
    sort_order: str = Query("desc", description="Sort order: asc, desc"),
) -> HTMLResponse:
    """Render user's saved gear with filters, sorting, and pagination.

    Page size must be a multiple of 3 (12, 24, 36) for grid alignment.
    """
    # Validate page_size is multiple of 3
    if page_size % 3 != 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="page_size must be a multiple of 3 (e.g., 12, 24, 36)",
        )

    query = (
        select(UserGear, Gear)
        .join(GearModel, UserGear.gear_model_id == GearModel.id)
        .join(Gear, GearModel.gear_id == Gear.id)
        .where(UserGear.user_id == current_user.id)
        .options(joinedload(Gear.models))
    )

    if gear_type:
        try:
            gt = GearType(gear_type.replace("-", "_"))
            query = query.where(Gear.gear_type == gt)
        except ValueError:
            pass

    if search:
        query = query.where(Gear.name.ilike(f"%{search}%"))

    # Apply sorting
    if sort_by == "name":
        if sort_order == "asc":
            query = query.order_by(Gear.name.asc())
        else:
            query = query.order_by(Gear.name.desc())
    elif sort_by == "type":
        if sort_order == "asc":
            query = query.order_by(Gear.gear_type.asc(), Gear.name.asc())
        else:
            query = query.order_by(Gear.gear_type.desc(), Gear.name.desc())
    else:  # date_added (default)
        if sort_order == "asc":
            query = query.order_by(UserGear.created_at.asc())
        else:
            query = query.order_by(UserGear.created_at.desc())

    # Count total
    count_q = (
        select(func.count())
        .select_from(UserGear)
        .join(GearModel, UserGear.gear_model_id == GearModel.id)
        .join(Gear, GearModel.gear_id == Gear.id)
        .where(UserGear.user_id == current_user.id)
    )
    if gear_type:
        try:
            gt = GearType(gear_type.replace("-", "_"))
            count_q = count_q.where(Gear.gear_type == gt)
        except ValueError:
            pass
    if search:
        count_q = count_q.where(Gear.name.ilike(f"%{search}%"))

    total_result = await db.execute(count_q)
    total_count = total_result.scalar() or 0

    offset = (page - 1) * page_size
    query = query.limit(page_size).offset(offset)
    result = await db.execute(query)
    rows = result.unique().all()

    # Group by gear and count saved models per gear
    gear_saved_counts: dict[str, int] = {}
    gear_map: dict[str, object] = {}
    for _ug, gear in rows:
        gid = str(gear.id)
        gear_saved_counts[gid] = gear_saved_counts.get(gid, 0) + 1
        gear_map[gid] = gear

    packs = []
    for gid, gear in gear_map.items():
        pack = _gear_to_pack(gear)
        pack["saved_count"] = gear_saved_counts[gid]
        packs.append(pack)
    total_models = sum(p["models_count"] for p in packs)
    total_pages = max(1, ceil(total_count / page_size))

    return templates.TemplateResponse(
        request,
        "fragments/library/my_gear.html",
        {
            "packs": packs,
            "total_models": total_models,
            "total_packs": total_count,
            "gear_type_filter": gear_type or "",
            "search": search or "",
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "has_prev": page > 1,
            "has_next": page < total_pages,
            "sort_by": sort_by,
            "sort_order": sort_order,
        },
    )


# Public DI Tracks Browse


@router.get("/di-tracks/results", response_class=HTMLResponse)
async def di_tracks_results_fragment(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User | None, Depends(get_optional_user)],
    search: str | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> HTMLResponse:
    """Render public DI tracks browse results."""
    query = select(DITrack).order_by(DITrack.created_at.desc()).limit(limit).offset(offset)
    if search:
        query = query.where(DITrack.name.ilike(f"%{search}%"))

    count_q = select(func.count()).select_from(DITrack)
    if search:
        count_q = count_q.where(DITrack.name.ilike(f"%{search}%"))

    total_result = await db.execute(count_q)
    total_count = total_result.scalar() or 0

    result = await db.execute(query)
    tracks_orm = result.scalars().all()

    tracks = []
    for t in tracks_orm:
        tracks.append(
            {
                "id": str(t.id),
                "title": t.name,
                "description": t.description,
                "is_public": True,
                "duration_seconds": t.duration_seconds,
                "duration_formatted": _format_duration(t.duration_seconds),
                "sample_rate": t.sample_rate,
                "guitar": t.guitar,
                "tuning": t.tuning,
                "pickups": t.pickup,
                "is_system_track": False,
                "relative_time": _relative_time(t.created_at),
            }
        )

    return templates.TemplateResponse(
        request,
        "fragments/di-tracks/public_browse.html",
        {
            "tracks": tracks,
            "total_count": total_count,
            "offset": offset,
            "search": search or "",
            "tuning_filter": "",
            "user": current_user,
            "prev_url": f"/di-tracks?offset={max(0, offset - limit)}" if offset > 0 else None,
            "next_url": f"/di-tracks?offset={offset + limit}"
            if offset + limit < total_count
            else None,
        },
    )


# Library DI Tracks


@router.get("/library/tracks", response_class=HTMLResponse)
async def library_tracks_fragment(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
    page: int = Query(1, ge=1),
    page_size: int = Query(24, ge=1, le=100),
    sort_by: str = Query("date_added", description="Sort field: name, date_added"),
    sort_order: str = Query("desc", description="Sort order: asc, desc"),
) -> HTMLResponse:
    """Render user's DI tracks list with sorting and pagination.

    Page size must be a multiple of 3 (12, 24, 36) for grid alignment.
    """
    # Validate page_size is multiple of 3
    if page_size % 3 != 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="page_size must be a multiple of 3 (e.g., 12, 24, 36)",
        )

    # Build query with sorting
    query = select(DITrack).where(DITrack.user_id == current_user.id)

    if sort_by == "name":
        if sort_order == "asc":
            query = query.order_by(DITrack.name.asc())
        else:
            query = query.order_by(DITrack.name.desc())
    else:  # date_added (default)
        if sort_order == "asc":
            query = query.order_by(DITrack.created_at.asc())
        else:
            query = query.order_by(DITrack.created_at.desc())

    # Count total
    count_q = select(func.count()).select_from(DITrack).where(DITrack.user_id == current_user.id)
    total_result = await db.execute(count_q)
    total_count = total_result.scalar() or 0

    # Apply pagination
    offset = (page - 1) * page_size
    query = query.limit(page_size).offset(offset)

    result = await db.execute(query)
    track_entities = result.scalars().all()

    tracks = []
    for t in track_entities:
        tracks.append(
            {
                "id": str(t.id),
                "title": t.name,
                "description": t.description,
                "is_public": False,
                "duration_seconds": t.duration_seconds,
                "duration_formatted": _format_duration(t.duration_seconds),
                "sample_rate": t.sample_rate,
                "guitar": t.guitar,
                "tuning": t.tuning,
                "pickups": t.pickup,
                "is_system_track": False,
                "relative_time": _relative_time(t.created_at),
            }
        )

    total_pages = max(1, ceil(total_count / page_size))

    return templates.TemplateResponse(
        request,
        "fragments/library/tracks.html",
        {
            "tracks": tracks,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "total_count": total_count,
            "has_prev": page > 1,
            "has_next": page < total_pages,
            "sort_by": sort_by,
            "sort_order": sort_order,
        },
    )


# Toggle DI Track Public/Private


@router.post("/library/tracks/{track_id}/toggle-public", response_class=HTMLResponse)
async def library_track_toggle_public(
    request: Request,
    track_id: str,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> HTMLResponse:
    """Toggle a DI track's public visibility. Returns updated track_item."""
    result = await db.execute(select(DITrack).where(DITrack.id == UUID(track_id)))
    track = result.scalar_one_or_none()

    if not track or track.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Track not found",
        )

    # DITrack doesn't have is_public field yet — stub: return the same card
    track_data = {
        "id": str(track.id),
        "title": track.name,
        "description": track.description,
        "is_public": False,
        "duration_seconds": track.duration_seconds,
        "duration_formatted": _format_duration(track.duration_seconds),
        "sample_rate": track.sample_rate,
        "guitar": track.guitar,
        "tuning": None,
        "pickups": track.pickup,
        "is_system_track": False,
        "relative_time": _relative_time(track.created_at),
    }

    return templates.TemplateResponse(
        request,
        "fragments/library/track_item.html",
        {"track": track_data, "is_library_view": True},
    )


# Save DI Track to Library (stub)


@router.post("/library/tracks/{track_id}/save", response_class=HTMLResponse)
async def library_track_save(
    track_id: str,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> HTMLResponse:
    """Save a public DI track to user's library. Stub endpoint."""
    return HTMLResponse(content="", status_code=200)


# Library Chains (new URL, same data as /library/chains/list)


@router.get("/library/chains", response_class=HTMLResponse)
async def library_chains_fragment(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
    page: int = Query(1, ge=1),
    page_size: int = Query(24, ge=1, le=100),
    sort_by: str = Query("date_added", description="Sort field: name, date_added"),
    sort_order: str = Query("desc", description="Sort order: asc, desc"),
) -> HTMLResponse:
    """Render user's signal chains list with sorting and pagination.

    Page size must be a multiple of 3 (12, 24, 36) for grid alignment.
    """
    # Validate page_size is multiple of 3
    if page_size % 3 != 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="page_size must be a multiple of 3 (e.g., 12, 24, 36)",
        )

    from webapp.adapters.persistence.models.signal_chain import SignalChain

    # Build query with sorting
    query = select(SignalChain).where(SignalChain.user_id == current_user.id)

    if sort_by == "name":
        if sort_order == "asc":
            query = query.order_by(SignalChain.name.asc())
        else:
            query = query.order_by(SignalChain.name.desc())
    else:  # date_added (default)
        if sort_order == "asc":
            query = query.order_by(SignalChain.created_at.asc())
        else:
            query = query.order_by(SignalChain.created_at.desc())

    # Count total
    count_q = (
        select(func.count()).select_from(SignalChain).where(SignalChain.user_id == current_user.id)
    )
    total_result = await db.execute(count_q)
    total_count = total_result.scalar() or 0

    # Apply pagination
    offset = (page - 1) * page_size
    query = query.limit(page_size).offset(offset)

    result = await db.execute(query)
    chains = result.scalars().all()

    chain_items = []
    for chain in chains:
        chain_items.append(
            {
                "id": str(chain.id),
                "name": chain.name,
                "description": chain.description,
                "platform": chain.platform.value,
                "relative_time": _relative_time(chain.created_at),
            }
        )

    total_pages = max(1, ceil(total_count / page_size))

    return templates.TemplateResponse(
        request,
        "fragments/library/chains.html",
        {
            "chains": chain_items,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "total_count": total_count,
            "has_prev": page > 1,
            "has_next": page < total_pages,
            "sort_by": sort_by,
            "sort_order": sort_order,
        },
    )


# Library Shootouts (new URL, same data)


@router.get("/library/shootouts", response_class=HTMLResponse)
async def library_shootouts_fragment(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
    page: int = Query(1, ge=1),
    page_size: int = Query(24, ge=1, le=100),
    sort_by: str = Query("date_added", description="Sort field: name, date_added"),
    sort_order: str = Query("desc", description="Sort order: asc, desc"),
) -> HTMLResponse:
    """Render user's shootouts list with sorting and pagination.

    Page size must be a multiple of 3 (12, 24, 36) for grid alignment.
    """
    # Validate page_size is multiple of 3
    if page_size % 3 != 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="page_size must be a multiple of 3 (e.g., 12, 24, 36)",
        )

    # Build query with sorting
    query = select(Shootout).where(Shootout.user_id == current_user.id)

    if sort_by == "name":
        if sort_order == "asc":
            query = query.order_by(Shootout.name.asc())
        else:
            query = query.order_by(Shootout.name.desc())
    else:  # date_added (default)
        if sort_order == "asc":
            query = query.order_by(Shootout.created_at.asc())
        else:
            query = query.order_by(Shootout.created_at.desc())

    # Count total
    count_q = select(func.count()).select_from(Shootout).where(Shootout.user_id == current_user.id)
    total_result = await db.execute(count_q)
    total_count = total_result.scalar() or 0

    # Apply pagination
    offset = (page - 1) * page_size
    query = query.limit(page_size).offset(offset)

    result = await db.execute(query)
    shootouts_orm = result.scalars().all()

    shootout_items = []
    for s in shootouts_orm:
        shootout_items.append(
            {
                "id": str(s.id),
                "name": s.name,
                "description": s.description,
                "status": s.status.value if hasattr(s.status, "value") else str(s.status),
                "relative_time": _relative_time(s.created_at),
            }
        )

    total_pages = max(1, ceil(total_count / page_size))

    return templates.TemplateResponse(
        request,
        "fragments/library/shootouts.html",
        {
            "shootouts": shootout_items,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "total_count": total_count,
            "has_prev": page > 1,
            "has_next": page < total_pages,
            "sort_by": sort_by,
            "sort_order": sort_order,
        },
    )


# Library Groups


@router.get("/library/groups", response_class=HTMLResponse)
async def library_groups_fragment(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> HTMLResponse:
    """Render user's signal chain groups list for library page.

    Returns HTML fragment with group list showing name, base chain,
    and estimated permutation count for each group.

    Args:
        request: FastAPI request object
        db: Database session
        current_user: Currently authenticated user

    Returns:
        Rendered HTML fragment
    """
    from webapp.adapters.persistence.repositories.signal_chain_group_repository import (
        SQLAlchemySignalChainGroupRepository,
    )

    repo = SQLAlchemySignalChainGroupRepository(db)
    groups = await repo.get_by_user_id(current_user.id)

    # Convert to dicts for template
    group_items = []
    for group in groups:
        # Calculate estimated permutation count
        permutation_count = 1
        for gear_list in group.gear_options.values():
            count = len(gear_list)
            if group.include_null:
                count += 1
            permutation_count *= count

        # Get base chain name if exists
        base_chain_name = None
        if group.base_chain_id:
            chain_repo = SQLAlchemySignalChainRepository(db)
            base_chain = await chain_repo.get_by_id(group.base_chain_id)
            if base_chain:
                base_chain_name = base_chain.name

        group_items.append(
            {
                "id": str(group.id),
                "name": group.name,
                "description": group.description,
                "base_chain": base_chain_name or str(group.base_chain_id)
                if group.base_chain_id
                else "No base chain",
                "permutation_count": permutation_count,
                "relative_time": _relative_time(group.created_at),
            }
        )

    return templates.TemplateResponse(
        request,
        "fragments/library/groups.html",
        {"groups": group_items},
    )


# Shootout Create Wizard - Group Chains


@router.get("/shootout-create/group-chains/{group_id}", response_class=HTMLResponse)
async def shootout_create_group_chains_fragment(
    request: Request,
    group_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> HTMLResponse:
    """Render chains generated from a signal chain group for shootout creation.

    Returns HTML fragment listing all chains that belong to the specified group.
    Only accessible by the group owner.

    Args:
        request: FastAPI request object
        group_id: UUID of the signal chain group
        db: Database session
        current_user: Currently authenticated user

    Returns:
        Rendered HTML fragment with chain checkboxes

    Raises:
        HTTPException: 404 if group not found or not owned by user
    """
    from webapp.adapters.persistence.models.signal_chain import (
        SignalChain as SignalChainModel,
    )
    from webapp.adapters.persistence.models.signal_chain import (
        SignalChainGroup as SignalChainGroupModel,
    )

    # Verify group exists and belongs to current user
    result = await db.execute(
        select(SignalChainGroupModel).where(SignalChainGroupModel.id == group_id)
    )
    group = result.scalar_one_or_none()

    if not group or group.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found",
        )

    # Get chains belonging to this group
    result = await db.execute(
        select(SignalChainModel)
        .where(SignalChainModel.group_id == group_id)
        .order_by(SignalChainModel.name)
    )
    chains = result.scalars().all()

    chain_items = []
    for chain in chains:
        chain_items.append(
            {
                "id": str(chain.id),
                "name": chain.name,
                "platform": chain.platform.value
                if hasattr(chain.platform, "value")
                else str(chain.platform),
            }
        )

    return templates.TemplateResponse(
        request,
        "fragments/shootouts/create/group-chains.html",
        {
            "group_name": group.name,
            "chains": chain_items,
        },
    )


# Shootout Create Wizard - Step 1: Chain List


@router.get("/shootout-create/chains", response_class=HTMLResponse)
async def shootout_create_chains_fragment(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
    search: str | None = Query(None),
) -> HTMLResponse:
    """Render chain list for shootout creation wizard."""
    repo = SQLAlchemySignalChainRepository(db)
    chains = await repo.get_by_user_id(current_user.id)

    chain_items = []
    for chain in chains:
        if search and search.lower() not in chain.name.lower():
            continue
        chain_items.append(
            {
                "id": str(chain.id),
                "name": chain.name,
                "block_count": chain.block_count,
                "platform": chain.platform.value,
            }
        )

    return templates.TemplateResponse(
        request,
        "fragments/shootouts/create/chain-list.html",
        {"chains": chain_items, "search": search or ""},
    )


# Shootout Create Wizard - Step 2: DI Track List


@router.get("/shootout-create/ditracks", response_class=HTMLResponse)
async def shootout_create_ditracks_fragment(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
    search: str | None = Query(None, description="Filter tracks by name"),
) -> HTMLResponse:
    """Render DI track list for shootout creation wizard.

    Args:
        request: FastAPI request object
        db: Database session
        current_user: Currently authenticated user
        search: Optional search filter for track name (case-insensitive)

    Returns:
        Rendered HTML fragment with filtered tracks
    """
    # Query tracks directly from DB for filtering
    query = (
        select(DITrack)
        .where(DITrack.user_id == current_user.id)
        .order_by(DITrack.created_at.desc())
    )

    # Apply search filter if provided
    if search:
        query = query.where(DITrack.name.ilike(f"%{search}%"))

    result = await db.execute(query)
    track_entities = result.scalars().all()

    tracks = []
    for t in track_entities:
        tracks.append(
            {
                "id": str(t.id),
                "title": t.name,
                "duration_seconds": t.duration_seconds,
                "sample_rate": t.sample_rate,
                "guitar": t.guitar,
                "description": t.description,
            }
        )

    return templates.TemplateResponse(
        request,
        "fragments/shootouts/create/ditrack-list.html",
        {"tracks": tracks},
    )


# Shootout Create - POST (create shootout from form)


@router.post("/shootout-create", response_class=HTMLResponse)
async def shootout_create_submit(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> HTMLResponse:
    """Create a shootout from the wizard form submission."""
    from uuid import uuid4

    from core.domain.entities.shootout import Shootout as ShootoutEntity
    from core.domain.entities.shootout import ShootoutChain as ShootoutChainVO
    from webapp.services.shootout_service import ShootoutService

    form = await request.form()
    name = form.get("name", "Untitled Shootout")
    di_track_id = form.get("di_track_id")
    chain_ids = form.getlist("chain_ids[]") or form.getlist("chain_ids")

    # Validate DI track required
    if not di_track_id or str(di_track_id).strip() == "":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A DI track is required to create a shootout",
        )

    # Validate chain count (minimum 2, maximum 20)
    if len(chain_ids) < 2:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least 2 chains are required to create a shootout",
        )

    if len(chain_ids) > ShootoutEntity.MAX_CHAINS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Cannot add more than {ShootoutEntity.MAX_CHAINS} chains to a shootout",
        )

    chains = []
    for i, chain_id in enumerate(chain_ids):
        chains.append(
            ShootoutChainVO(
                id=uuid4(),
                shootout_id=uuid4(),  # placeholder, overwritten
                signal_chain_id=UUID(chain_id),
                position=i,
                label=f"Chain {i + 1}",
            )
        )

    shootout_id = uuid4()
    for chain in chains:
        object.__setattr__(chain, "shootout_id", shootout_id)

    shootout = ShootoutEntity(
        id=shootout_id,
        user_id=current_user.id,
        name=str(name),
        di_track_id=UUID(str(di_track_id)) if di_track_id else None,
        chains=chains,
    )

    service = ShootoutService(db)
    async with db.begin():
        await service.create(shootout)

    response = HTMLResponse(content="", status_code=200)
    response.headers["HX-Redirect"] = f"/shootout/{shootout_id}"
    return response


# Public Shootouts Sections (trending/latest)


@router.get("/shootouts/sections", response_class=HTMLResponse)
async def shootouts_sections_fragment(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> HTMLResponse:
    """Render public shootouts sections (trending, latest)."""
    repo = SQLAlchemyShootoutRepository(db)
    recent = await repo.get_public(limit=10)

    sections = []
    if recent:
        shootout_cards = []
        for s in recent:
            shootout_cards.append(
                {
                    "id": str(s.id),
                    "name": s.name,
                    "description": s.description,
                    "chain_count": len(s.chains) if s.chains else 0,
                    "relative_time": _relative_time(s.created_at),
                }
            )

        sections.append(
            {
                "category": "latest",
                "icon": None,
                "title": "Latest Shootouts",
                "view_all_href": None,
                "shootouts": shootout_cards,
                "empty_message": "No shootouts yet",
            }
        )

    return templates.TemplateResponse(
        request,
        "fragments/shootouts/sections.html",
        {"sections": sections},
    )


# Shootout Detail + Actions


@router.get("/shootouts/{shootout_id}", response_class=HTMLResponse)
async def shootout_detail_fragment(
    request: Request,
    shootout_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> HTMLResponse:
    """Render shootout detail fragment for owned shootouts."""
    stmt = (
        select(Shootout)
        .where(Shootout.id == shootout_id)
        .options(
            joinedload(Shootout.user),
            joinedload(Shootout.di_track),
            joinedload(Shootout.chains).joinedload(ShootoutChain.signal_chain),
        )
    )
    result = await db.execute(stmt)
    shootout = result.unique().scalar_one_or_none()

    if shootout is None or shootout.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shootout not found")

    return templates.TemplateResponse(
        request,
        "fragments/shootouts/detail.html",
        _build_shootout_detail_context(shootout),
    )


@router.delete("/shootouts/{shootout_id}", response_class=HTMLResponse)
async def shootout_delete_fragment(
    shootout_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> HTMLResponse:
    """Delete an owned shootout and redirect back to shootout list."""
    stmt = select(Shootout).where(Shootout.id == shootout_id)
    result = await db.execute(stmt)
    shootout = result.scalar_one_or_none()

    if shootout is None or shootout.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shootout not found")

    await db.delete(shootout)
    await db.commit()

    response = HTMLResponse(content="", status_code=status.HTTP_200_OK)
    response.headers["HX-Redirect"] = "/shootouts"
    return response


@router.patch("/shootouts/{shootout_id}/title", response_class=HTMLResponse)
async def shootout_title_update_fragment(
    request: Request,
    shootout_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> HTMLResponse:
    """Update an owned shootout title and return refreshed detail fragment."""
    form = await request.form()
    new_name = str(form.get("name", "")).strip()
    if not new_name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Shootout name cannot be empty",
        )

    stmt = (
        select(Shootout)
        .where(Shootout.id == shootout_id)
        .options(
            joinedload(Shootout.user),
            joinedload(Shootout.di_track),
            joinedload(Shootout.chains).joinedload(ShootoutChain.signal_chain),
        )
    )
    result = await db.execute(stmt)
    shootout = result.unique().scalar_one_or_none()

    if shootout is None or shootout.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shootout not found")

    shootout.name = new_name
    await db.commit()
    refreshed_result = await db.execute(stmt)
    refreshed_shootout = refreshed_result.unique().scalar_one_or_none()
    if refreshed_shootout is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shootout not found")

    return templates.TemplateResponse(
        request,
        "fragments/shootouts/detail.html",
        _build_shootout_detail_context(refreshed_shootout),
    )


# Shootout Comments


@router.get("/shootouts/{shootout_id}/comments", response_class=HTMLResponse)
async def shootout_comments_fragment(
    request: Request,
    shootout_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User | None, Depends(get_optional_user)],
) -> HTMLResponse:
    """Render shootout comments section with real data."""
    # Load comments for shootout
    comment_repo = ShootoutCommentRepository(db)
    comments_orm = await comment_repo.list_by_shootout(shootout_id)

    # Format comments for template
    comments = []
    for comment in comments_orm:
        comments.append(
            {
                "id": str(comment.id),
                "author": comment.user.username,
                "text": comment.content,
                "relative_time": _relative_time(comment.created_at),
                "is_own": current_user is not None and comment.user_id == current_user.id,
            }
        )

    return templates.TemplateResponse(
        request,
        "fragments/shootouts/comments.html",
        {
            "shootout_id": str(shootout_id),
            "comments": comments,
            "current_user": current_user,
        },
    )


# Job Fragments


@router.get("/jobs/{job_id}", response_class=HTMLResponse)
async def job_status_fragment(
    job_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> HTMLResponse:
    """Render an HTMX fragment with current job status for the owner."""
    stmt = select(Job).where(Job.id == job_id)
    result = await db.execute(stmt)
    job = result.scalar_one_or_none()

    if job is None or job.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    status_value = job.status.value if hasattr(job.status, "value") else str(job.status)
    should_poll = job.status in JobStatus.active_states()
    message = escape(job.message or "")
    error = escape(job.error or "")
    job_type = escape(job.job_type.value if hasattr(job.job_type, "value") else str(job.job_type))

    html = [
        '<div class="container mx-auto px-4 py-8 max-w-2xl">',
        '<div class="bg-[var(--color-bg-surface)] rounded-lg border border-[var(--border)] p-6" '
        f'data-polling="{str(should_poll).lower()}">',
        f'<h1 class="text-xl font-semibold text-[var(--color-text-primary)] mb-2">Job {escape(str(job.id))}</h1>',
        f'<p class="text-sm text-[var(--color-text-secondary)] mb-1">Type: {job_type}</p>',
        f'<p class="text-sm text-[var(--color-text-secondary)] mb-1">Status: {escape(status_value)}</p>',
        f'<p class="text-sm text-[var(--color-text-secondary)] mb-4">Progress: {job.progress}%</p>',
    ]

    if message:
        html.append(
            f'<p class="text-sm text-[var(--color-text-primary)] mb-2" data-testid="job-message">{message}</p>'
        )
    if error:
        html.append(f'<p class="text-sm text-red-400" data-testid="job-error">Error: {error}</p>')

    html.append("</div></div>")
    return HTMLResponse(content="".join(html), status_code=status.HTTP_200_OK)


# Gear Model Toggle (save/unsave)


@router.post("/gear/model/{model_id}/toggle", response_class=HTMLResponse)
async def gear_model_toggle(
    request: Request,
    model_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> HTMLResponse:
    """Toggle a gear model in/out of the user's library.

    Returns the updated model row fragment for HTMX swap.
    """
    # Verify gear model exists (load gear for name)
    result = await db.execute(
        select(GearModel).where(GearModel.id == model_id).options(joinedload(GearModel.gear))
    )
    gear_model = result.unique().scalar_one_or_none()

    if not gear_model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Gear model not found",
        )

    # Check if already in library
    result = await db.execute(
        select(UserGear).where(
            UserGear.user_id == current_user.id,
            UserGear.gear_model_id == model_id,
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        await db.delete(existing)
        await db.commit()
        is_saved = False
    else:
        user_gear = UserGear(
            id=uuid4(),
            user_id=current_user.id,
            gear_model_id=model_id,
        )
        db.add(user_gear)
        await db.commit()
        is_saved = True

    # Build model context matching _gear_to_pack format
    gear_name = gear_model.gear.name if gear_model.gear else ""
    size_value = (
        gear_model.size.value if hasattr(gear_model.size, "value") else str(gear_model.size)
    )
    download_status_value = (
        gear_model.download_status.value
        if hasattr(gear_model.download_status, "value")
        else str(gear_model.download_status)
    )
    model_context = {
        "id": str(gear_model.id),
        "name": f"{gear_name} ({size_value})" if gear_name else size_value,
        "model_size": size_value,
        "is_saved": is_saved,
        "download_status": download_status_value,
    }

    return templates.TemplateResponse(
        request,
        "fragments/gear/model_row.html",
        {"model": model_context},
    )


# Bulk Gear Model Toggle (save/unsave multiple models)


@router.post("/gear/models/bulk-toggle", response_class=HTMLResponse)
async def gear_models_bulk_toggle(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> HTMLResponse:
    """Bulk add or remove multiple gear models from the user's library.

    Expects JSON payload:
    {
        "model_ids": ["uuid1", "uuid2", ...],
        "action": "add" or "remove"
    }

    Returns 200 on success.
    """
    from pydantic import BaseModel

    class BulkToggleRequest(BaseModel):
        model_ids: list[str]
        action: str  # "add" or "remove"

    try:
        body = await request.json()
        bulk_request = BulkToggleRequest(**body)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid request body: {e}",
        ) from e

    if bulk_request.action not in ["add", "remove"]:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="action must be 'add' or 'remove'",
        )

    # Convert string IDs to UUIDs
    try:
        model_uuids = [UUID(mid) for mid in bulk_request.model_ids]
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid UUID format: {e}",
        ) from e

    # Verify all models exist
    result = await db.execute(select(GearModel.id).where(GearModel.id.in_(model_uuids)))
    existing_model_ids = {row[0] for row in result.all()}

    if len(existing_model_ids) != len(model_uuids):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="One or more models not found",
        )

    if bulk_request.action == "add":
        # Get currently saved models to avoid duplicates
        result = await db.execute(
            select(UserGear.gear_model_id)
            .where(UserGear.user_id == current_user.id)
            .where(UserGear.gear_model_id.in_(model_uuids))
        )
        already_saved = {row[0] for row in result.all()}

        # Add models that aren't already saved
        for model_id in model_uuids:
            if model_id not in already_saved:
                user_gear = UserGear(
                    id=uuid4(),
                    user_id=current_user.id,
                    gear_model_id=model_id,
                )
                db.add(user_gear)

        await db.commit()

    elif bulk_request.action == "remove":
        # Delete all matching UserGear entries
        result = await db.execute(
            select(UserGear)
            .where(UserGear.user_id == current_user.id)
            .where(UserGear.gear_model_id.in_(model_uuids))
        )
        to_delete = result.scalars().all()

        for user_gear in to_delete:
            await db.delete(user_gear)

        await db.commit()

    return HTMLResponse(content="", status_code=200)
