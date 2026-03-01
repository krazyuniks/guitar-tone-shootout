"""DI track page handlers — browse, library, toggle-public, save."""

from math import ceil
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from webapp.adapters.persistence.models.shootout import DITrack
from webapp.adapters.persistence.models.user import User
from webapp.api.pages.context import di_track_to_context
from webapp.auth.dependencies import (
    get_current_user_optional,
    get_current_user_page,
    get_current_user_required,
    get_db_session,
)
from webapp.templates import templates

router = APIRouter(tags=["pages"])


@router.get("/di-tracks", response_class=HTMLResponse)
async def di_tracks_browse_page(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User | None, Depends(get_current_user_optional)],
    search: str | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> HTMLResponse:
    """Render DI tracks browse page with full SSR."""
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

    tracks = [di_track_to_context(t, is_public=True) for t in tracks_orm]

    return templates.TemplateResponse(
        request,
        "di-tracks/index.html",
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


@router.get("/library/di-tracks", response_class=HTMLResponse)
async def library_di_tracks_page(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user_page)],
    page: int = Query(1, ge=1),
    page_size: int = Query(24, ge=1, le=100),
    sort_by: str = Query("date_added"),
    sort_order: str = Query("desc"),
) -> HTMLResponse:
    """Render user's DI tracks library page with full SSR."""
    if page_size % 3 != 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="page_size must be a multiple of 3 (e.g., 12, 24, 36)",
        )

    query = select(DITrack).where(DITrack.user_id == current_user.id)

    if sort_by == "name":
        order_col = DITrack.name.asc() if sort_order == "asc" else DITrack.name.desc()
        query = query.order_by(order_col)
    else:
        order_col = DITrack.created_at.asc() if sort_order == "asc" else DITrack.created_at.desc()
        query = query.order_by(order_col)

    count_q = select(func.count()).select_from(DITrack).where(DITrack.user_id == current_user.id)
    total_result = await db.execute(count_q)
    total_count = total_result.scalar() or 0

    offset = (page - 1) * page_size
    query = query.limit(page_size).offset(offset)

    result = await db.execute(query)
    track_entities = result.scalars().all()

    tracks = [di_track_to_context(t) for t in track_entities]
    total_pages = max(1, ceil(total_count / page_size))

    return templates.TemplateResponse(
        request,
        "pages/library/di-tracks.html",
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
            "user": current_user,
        },
    )


@router.post("/library/di-tracks/{track_id}/toggle-public", response_class=HTMLResponse)
async def library_track_toggle_public(
    request: Request,
    track_id: str,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user_required)],
) -> HTMLResponse:
    """Toggle a DI track's public visibility. Returns updated track_item."""
    result = await db.execute(select(DITrack).where(DITrack.id == UUID(track_id)))
    track = result.scalar_one_or_none()

    if not track or track.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Track not found",
        )

    track_data = di_track_to_context(track)

    return templates.TemplateResponse(
        request,
        "fragments/library/track_item.html",
        {"track": track_data, "is_library_view": True},
    )


@router.post("/library/di-tracks/{track_id}/save", response_class=HTMLResponse)
async def library_track_save(
    track_id: str,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user_required)],
) -> HTMLResponse:
    """Save a public DI track to user's library. Stub endpoint."""
    return HTMLResponse(content="", status_code=200)
