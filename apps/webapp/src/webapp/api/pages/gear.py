"""Gear page handlers — browse, detail, my-gear, model toggle."""

import contextlib
import os
from math import ceil
from typing import Annotated
from urllib.parse import urlencode
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from gts.domain.value_objects.signal_chain_enums import GearType
from webapp.adapters.persistence.models.gear import Gear
from webapp.adapters.persistence.models.gear_model import GearModel
from webapp.adapters.persistence.models.user import User
from webapp.adapters.persistence.models.user_gear import UserGear
from webapp.api.pages.context import (
    gear_model_to_row_context,
    gear_to_browse_context,
    gear_to_detail_context,
)
from webapp.auth.dependencies import (
    get_current_user_optional,
    get_current_user_page,
    get_current_user_required,
    get_db_session,
)
from webapp.services.gear_service import GearService
from webapp.templates import templates

router = APIRouter(tags=["pages"])


@router.get("/gear", response_class=HTMLResponse)
async def gear_browse_page(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User | None, Depends(get_current_user_optional)],
    search: str | None = Query(None),
    gear_type: str | None = Query(None),
    sort: str = Query("newest"),
    tags: str | None = Query(None),
    makes: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(24, ge=1, le=100),
) -> HTMLResponse:
    """Render gear browse page with full SSR."""
    service = GearService(db)

    gt_filter = None
    if gear_type:
        with contextlib.suppress(ValueError):
            gt_filter = GearType(gear_type.replace("-", "_"))

    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else None

    offset = (page - 1) * page_size
    total = await service.count(query=search, gear_type=gt_filter, tags=tag_list)
    gear_items = await service.search(
        query=search,
        gear_type=gt_filter,
        tags=tag_list,
        sort=sort,
        limit=page_size,
        offset=offset,
    )

    packs = [gear_to_browse_context(g) for g in gear_items if g.is_public]
    total_pages = max(1, ceil(total / page_size))

    def build_url(**overrides: object) -> str:
        params = {
            k: v
            for k, v in {
                "search": search,
                "gear_type": gear_type,
                "sort": sort,
                "tags": tags,
                "makes": makes,
                **overrides,
            }.items()
            if v
        }
        qs = urlencode(params)
        return f"/gear?{qs}" if qs else "/gear"

    return templates.TemplateResponse(
        request,
        "pages/gear.html",
        {
            "packs": packs,
            "total_count": total,
            "page": page,
            "total_pages": total_pages,
            "has_prev": page > 1,
            "has_next": page < total_pages,
            "prev_url": build_url(page=page - 1) if page > 1 else "",
            "next_url": build_url(page=page + 1) if page < total_pages else "",
            "gear_type_filter": gear_type or "",
            "search": search or "",
            "sort_order": sort,
            "tags_filter": tag_list or [],
            "makes_filter": [],
            "creator_filter": "",
            "user": current_user,
        },
    )


@router.get("/gear/search", response_class=HTMLResponse)
async def gear_search_fragment(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    query: str | None = Query(None, description="Text search on name/description"),
    gear_type: GearType | None = Query(None, description="Filter by gear type"),
    manufacturer: str | None = Query(None, description="Filter by manufacturer"),
    limit: int = Query(50, ge=1, le=100, description="Maximum items per page"),
    offset: int = Query(0, ge=0, description="Number of items to skip"),
) -> HTMLResponse:
    """Render gear list fragment for HTMX updates."""
    service = GearService(db)

    total = await service.count(
        query=query,
        gear_type=gear_type,
        manufacturer=manufacturer,
    )

    all_gear = await service.search(
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


@router.get("/gear/{slug}", response_class=HTMLResponse)
async def gear_detail_page(
    request: Request,
    slug: str,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User | None, Depends(get_current_user_optional)],
) -> HTMLResponse:
    """Render gear detail page with full SSR."""
    service = GearService(db)
    gear = await service.get_by_slug(slug)

    if not gear or not gear.is_public:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Gear not found",
        )

    pack = gear_to_detail_context(gear)

    # For authenticated users, check which models are in their library
    if current_user:
        model_ids = [m.id for m in gear.models]
        result = await db.execute(
            select(UserGear.gear_model_id)
            .where(UserGear.user_id == current_user.id)
            .where(UserGear.gear_model_id.in_(model_ids))
        )
        saved_model_ids = {row[0] for row in result.all()}
        for model_dict in pack["models"]:
            model_dict["is_saved"] = UUID(model_dict["id"]) in saved_model_ids

    description = gear.description or f"{gear.name} - guitar tone capture"
    public_url = os.getenv("PUBLIC_URL", str(request.base_url).rstrip("/"))
    canonical = f"{public_url}/gear/{slug}"

    return templates.TemplateResponse(
        request,
        "gear/detail.html",
        {
            "pack": pack,
            "user": current_user,
            "description": description,
            "canonical_url": canonical,
        },
    )


@router.get("/library/my-gear", response_class=HTMLResponse)
async def library_my_gear_page(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user_page)],
    search: str | None = Query(None),
    gear_type: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(24, ge=1, le=100),
    sort_by: str = Query("date_added"),
    sort_order: str = Query("desc"),
) -> HTMLResponse:
    """Render user's gear library page with full SSR."""
    if page_size % 3 != 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="page_size must be a multiple of 3 (e.g., 12, 24, 36)",
        )

    query_stmt = (
        select(UserGear, Gear)
        .join(GearModel, UserGear.gear_model_id == GearModel.id)
        .join(Gear, GearModel.gear_id == Gear.id)
        .where(UserGear.user_id == current_user.id)
        .options(joinedload(Gear.models), joinedload(Gear.source))
    )

    if gear_type:
        with contextlib.suppress(ValueError):
            gt = GearType(gear_type.replace("-", "_"))
            query_stmt = query_stmt.where(Gear.gear_type == gt)

    if search:
        query_stmt = query_stmt.where(Gear.name.ilike(f"%{search}%"))

    if sort_by == "name":
        order_col = Gear.name.asc() if sort_order == "asc" else Gear.name.desc()
        query_stmt = query_stmt.order_by(order_col)
    elif sort_by == "type":
        if sort_order == "asc":
            query_stmt = query_stmt.order_by(Gear.gear_type.asc(), Gear.name.asc())
        else:
            query_stmt = query_stmt.order_by(Gear.gear_type.desc(), Gear.name.desc())
    else:
        order_col = UserGear.created_at.asc() if sort_order == "asc" else UserGear.created_at.desc()
        query_stmt = query_stmt.order_by(order_col)

    count_q = (
        select(func.count())
        .select_from(UserGear)
        .join(GearModel, UserGear.gear_model_id == GearModel.id)
        .join(Gear, GearModel.gear_id == Gear.id)
        .where(UserGear.user_id == current_user.id)
    )
    if gear_type:
        with contextlib.suppress(ValueError):
            gt = GearType(gear_type.replace("-", "_"))
            count_q = count_q.where(Gear.gear_type == gt)
    if search:
        count_q = count_q.where(Gear.name.ilike(f"%{search}%"))

    total_result = await db.execute(count_q)
    total_count = total_result.scalar() or 0

    offset = (page - 1) * page_size
    query_stmt = query_stmt.limit(page_size).offset(offset)
    result = await db.execute(query_stmt)
    rows = result.unique().all()

    gear_saved_counts: dict[str, int] = {}
    gear_map: dict[str, object] = {}
    for _ug, gear_item in rows:
        gid = str(gear_item.id)
        gear_saved_counts[gid] = gear_saved_counts.get(gid, 0) + 1
        gear_map[gid] = gear_item

    packs = []
    for gid, gear_item in gear_map.items():
        pack = gear_to_browse_context(gear_item)
        pack["saved_count"] = gear_saved_counts[gid]
        packs.append(pack)
    total_models = sum(p["models_count"] for p in packs)
    total_pages = max(1, ceil(total_count / page_size))

    return templates.TemplateResponse(
        request,
        "pages/library/my_gear.html",
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
            "user": current_user,
        },
    )


@router.post("/gear/model/{model_id}/toggle", response_class=HTMLResponse)
async def gear_model_toggle(
    request: Request,
    model_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user_required)],
) -> HTMLResponse:
    """Toggle a gear model in/out of the user's library."""
    from uuid import uuid4

    result = await db.execute(
        select(GearModel).where(GearModel.id == model_id).options(joinedload(GearModel.gear))
    )
    gear_model = result.unique().scalar_one_or_none()

    if not gear_model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Gear model not found",
        )

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

    gear_name = gear_model.gear.name if gear_model.gear else ""
    model_context = gear_model_to_row_context(gear_model, gear_name, is_saved=is_saved)

    return templates.TemplateResponse(
        request,
        "fragments/gear/model_row.html",
        {"model": model_context},
    )


@router.post("/gear/models/bulk-toggle", response_class=HTMLResponse)
async def gear_models_bulk_toggle(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user_required)],
) -> HTMLResponse:
    """Bulk add or remove multiple gear models from the user's library."""
    from uuid import uuid4

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

    try:
        model_uuids = [UUID(mid) for mid in bulk_request.model_ids]
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid UUID format: {e}",
        ) from e

    result = await db.execute(select(GearModel.id).where(GearModel.id.in_(model_uuids)))
    existing_model_ids = {row[0] for row in result.all()}

    if len(existing_model_ids) != len(model_uuids):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="One or more models not found",
        )

    if bulk_request.action == "add":
        result = await db.execute(
            select(UserGear.gear_model_id)
            .where(UserGear.user_id == current_user.id)
            .where(UserGear.gear_model_id.in_(model_uuids))
        )
        already_saved = {row[0] for row in result.all()}

        for mid in model_uuids:
            if mid not in already_saved:
                user_gear = UserGear(
                    id=uuid4(),
                    user_id=current_user.id,
                    gear_model_id=mid,
                )
                db.add(user_gear)

        await db.commit()

    elif bulk_request.action == "remove":
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
