"""Signal chain page handlers — library, detail, builder, list/delete/duplicate fragments."""

from datetime import UTC
from math import ceil
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from webapp.adapters.persistence.models.gear import Gear
from webapp.adapters.persistence.models.gear_model import GearModel
from webapp.adapters.persistence.models.signal_chain import SignalChain
from webapp.adapters.persistence.models.user import User
from webapp.adapters.persistence.models.user_gear import UserGear
from webapp.adapters.persistence.repositories.signal_chain_repository import (
    SQLAlchemySignalChainRepository,
)
from webapp.api.pages.context import chain_to_library_context
from webapp.auth.dependencies import get_current_user_page, get_db_session
from webapp.templates import templates

router = APIRouter(tags=["pages"])


@router.get("/library/chains", response_class=HTMLResponse)
async def library_chains_page(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user_page)],
    page: int = Query(1, ge=1),
    page_size: int = Query(24, ge=1, le=100),
    sort_by: str = Query("date_added"),
    sort_order: str = Query("desc"),
) -> HTMLResponse:
    """Render user's signal chain library page with full SSR."""
    if page_size % 3 != 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="page_size must be a multiple of 3 (e.g., 12, 24, 36)",
        )

    query = select(SignalChain).where(SignalChain.user_id == current_user.id)

    if sort_by == "name":
        order_col = SignalChain.name.asc() if sort_order == "asc" else SignalChain.name.desc()
        query = query.order_by(order_col)
    else:
        order_col = (
            SignalChain.created_at.asc() if sort_order == "asc" else SignalChain.created_at.desc()
        )
        query = query.order_by(order_col)

    count_q = (
        select(func.count()).select_from(SignalChain).where(SignalChain.user_id == current_user.id)
    )
    total_result = await db.execute(count_q)
    total_count = total_result.scalar() or 0

    offset = (page - 1) * page_size
    query = query.limit(page_size).offset(offset)

    result = await db.execute(query)
    chains = result.scalars().all()

    chain_items = [chain_to_library_context(c) for c in chains]
    total_pages = max(1, ceil(total_count / page_size))

    return templates.TemplateResponse(
        request,
        "pages/library/chains.html",
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
            "user": current_user,
        },
    )


@router.get("/library/chains/build", response_class=HTMLResponse)
async def chain_builder_page(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user_page)],
    chain_id: str | None = Query(None, description="Chain ID for editing"),
) -> HTMLResponse:
    """Render chain builder page."""
    return templates.TemplateResponse(
        request,
        "pages/library/chains_build.html",
        {
            "title": "Chain Builder",
            "chain_id": chain_id,
            "user": current_user,
        },
    )


@router.get("/chain/{chain_id}", response_class=HTMLResponse)
async def chain_detail_page(
    request: Request,
    chain_id: str,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user_page)],
) -> HTMLResponse:
    """Render signal chain detail page."""
    repo = SQLAlchemySignalChainRepository(db)
    chain = await repo.get_by_id(UUID(chain_id), current_user.id)

    if chain is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chain not found",
        )

    block_items = []
    for block in chain.blocks:
        gear_name = block.gear_type.value.replace("_", " ").title()
        if block.user_gear_id:
            ug_result = await db.execute(
                select(UserGear, GearModel, Gear)
                .join(GearModel, UserGear.gear_model_id == GearModel.id)
                .join(Gear, GearModel.gear_id == Gear.id)
                .where(UserGear.id == block.user_gear_id)
            )
            row = ug_result.first()
            if row:
                _, _, gear = row
                gear_name = gear.name

        block_items.append(
            {
                "gear_type": block.gear_type.value.replace("_", "-"),
                "gear_name": gear_name,
                "position": block.position,
            }
        )

    block_items.sort(
        key=lambda x: int(x["position"]) if isinstance(x["position"], int | str) else 0
    )

    return templates.TemplateResponse(
        request,
        "pages/chain_detail.html",
        {
            "chain": {
                "id": str(chain.id),
                "name": chain.name,
                "description": chain.description,
                "platform": chain.platform.value,
                "block_count": chain.block_count,
                "is_complete": chain.is_complete(),
                "blocks": block_items,
                "created_at": chain.created_at,
                "updated_at": chain.updated_at,
            },
            "user": current_user,
        },
    )


@router.get("/library/chains/list", response_class=HTMLResponse)
async def chain_list_fragment(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user_page)],
) -> HTMLResponse:
    """Render chain list fragment for HTMX updates."""
    repo = SQLAlchemySignalChainRepository(db)
    chains = await repo.get_by_user_id(current_user.id)

    chain_items = [chain_to_library_context(c) for c in chains]

    return templates.TemplateResponse(
        request,
        "fragments/chains/list.html",
        {
            "chains": chain_items,
        },
    )


@router.delete("/chain/{chain_id}", response_class=HTMLResponse)
async def chain_delete_fragment(
    request: Request,
    chain_id: str,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user_page)],
) -> HTMLResponse:
    """Delete a signal chain via HTMX."""
    repo = SQLAlchemySignalChainRepository(db)

    chain = await repo.get_by_id(UUID(chain_id), current_user.id)
    if chain is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chain not found",
        )

    async with db.begin():
        await repo.delete(UUID(chain_id))

    return HTMLResponse(content="", status_code=200)


@router.post("/chain/{chain_id}/duplicate", response_class=HTMLResponse)
async def chain_duplicate_fragment(
    request: Request,
    chain_id: str,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user_page)],
) -> HTMLResponse:
    """Duplicate a signal chain via HTMX."""
    from datetime import datetime
    from uuid import uuid4

    from gts.domain.entities.signal_chain import SignalChain as SignalChainEntity

    repo = SQLAlchemySignalChainRepository(db)

    chain = await repo.get_by_id(UUID(chain_id), current_user.id)
    if chain is None:
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
    chain_items = [chain_to_library_context(c) for c in chains]

    return templates.TemplateResponse(
        request,
        "fragments/chains/list.html",
        {
            "chains": chain_items,
        },
    )
