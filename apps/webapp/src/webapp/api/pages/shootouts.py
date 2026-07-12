"""Shootout page handlers — browse, library, create wizard, detail, comments."""

from math import ceil
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from webapp.adapters.persistence.models.shootout import Shootout, ShootoutChain
from webapp.adapters.persistence.models.user import User
from webapp.adapters.persistence.repositories.shootout_comment_repository import (
    ShootoutCommentRepository,
)
from webapp.adapters.persistence.repositories.shootout_repository import (
    SQLAlchemyShootoutRepository,
    readable_shootout_gate,
)
from webapp.api.pages.context import (
    comment_to_context,
    shootout_detail_context,
)
from webapp.auth.dependencies import (
    get_current_user_optional,
    get_current_user_page,
    get_current_user_required,
    get_db_session,
)
from webapp.services.shootout_service import ShootoutService
from webapp.templates import _relative_time, templates

router = APIRouter(tags=["pages"])


@router.get("/shootouts", response_model=None)
async def shootouts_page(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User | None, Depends(get_current_user_optional)],
) -> HTMLResponse | RedirectResponse:
    """Render public shootouts page. Redirects authenticated users to library."""
    if current_user:
        return RedirectResponse(url="/library/shootouts", status_code=302)

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
        "pages/shootouts.html",
        {"sections": sections, "user": None},
    )


@router.get("/library/shootouts", response_class=HTMLResponse)
async def library_shootouts_page(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user_page)],
    page: int = Query(1, ge=1),
    page_size: int = Query(24, ge=1, le=100),
    sort_by: str = Query("date_added"),
    sort_order: str = Query("desc"),
) -> HTMLResponse:
    """Render user's shootout library page with full SSR."""
    if page_size % 3 != 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="page_size must be a multiple of 3 (e.g., 12, 24, 36)",
        )

    query = select(Shootout).where(Shootout.user_id == current_user.id)

    if sort_by == "name":
        order_col = Shootout.name.asc() if sort_order == "asc" else Shootout.name.desc()
        query = query.order_by(order_col)
    else:
        order_col = Shootout.created_at.asc() if sort_order == "asc" else Shootout.created_at.desc()
        query = query.order_by(order_col)

    count_q = select(func.count()).select_from(Shootout).where(Shootout.user_id == current_user.id)
    total_result = await db.execute(count_q)
    total_count = total_result.scalar() or 0

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
        "pages/library/shootouts.html",
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
            "user": current_user,
        },
    )


@router.get("/shootout/create", response_class=HTMLResponse)
async def shootout_create_page(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user_page)],
) -> HTMLResponse:
    """Render shootout creation wizard page."""
    return templates.TemplateResponse(
        request,
        "pages/shootout_create.html",
        {
            "title": "Create Shootout",
            "user": current_user,
        },
    )


@router.get("/shootout/{shootout_id}", response_class=HTMLResponse)
async def shootout_detail_page(
    request: Request,
    shootout_id: str,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User | None, Depends(get_current_user_optional)],
) -> HTMLResponse:
    """Render an owned or published shootout detail page with full SSR."""
    stmt = (
        select(Shootout)
        .where(
            Shootout.id == UUID(shootout_id),
            readable_shootout_gate(current_user.id if current_user is not None else None),
        )
        .options(
            joinedload(Shootout.user),
            joinedload(Shootout.di_track),
            joinedload(Shootout.chains).joinedload(ShootoutChain.signal_chain),
        )
    )
    result = await db.execute(stmt)
    shootout_model = result.unique().scalar_one_or_none()

    if shootout_model is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shootout not found",
        )

    context = shootout_detail_context(shootout_model)
    context["user"] = current_user
    context["title"] = shootout_model.name
    context["is_owner"] = current_user is not None and shootout_model.user_id == current_user.id

    return templates.TemplateResponse(
        request,
        "pages/shootout_detail.html",
        context,
    )


@router.get("/library/shootouts/list", response_class=HTMLResponse)
async def shootout_list_fragment(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user_page)],
) -> HTMLResponse:
    """Render shootout list fragment for HTMX updates."""
    service = ShootoutService(db)
    shootouts = await service.get_by_user_id(current_user.id)

    shootout_items = []
    for shootout in shootouts:
        shootout_items.append(
            {
                "id": str(shootout.id),
                "name": shootout.name,
                "description": shootout.description,
                "chain_count": shootout.chain_count,
                "is_processed": shootout.is_processed,
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


@router.delete("/shootout/{shootout_id}", response_class=HTMLResponse)
async def shootout_delete_fragment(
    request: Request,
    shootout_id: str,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user_page)],
) -> HTMLResponse:
    """Delete a shootout via HTMX."""
    service = ShootoutService(db)

    shootout = await service.get_by_id(UUID(shootout_id), current_user.id)
    if shootout is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shootout not found",
        )

    async with db.begin():
        await service.delete(UUID(shootout_id))

    return HTMLResponse(content="", status_code=200)


@router.get("/shootout/create/chains", response_class=HTMLResponse)
async def shootout_create_chains_fragment(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user_required)],
    search: str | None = Query(None),
) -> HTMLResponse:
    """Render chain list for shootout creation wizard."""
    from webapp.adapters.persistence.repositories.signal_chain_repository import (
        SQLAlchemySignalChainRepository,
    )

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


@router.get("/shootout/create/ditracks", response_class=HTMLResponse)
async def shootout_create_ditracks_fragment(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user_required)],
    search: str | None = Query(None, description="Filter tracks by name"),
) -> HTMLResponse:
    """Render DI track list for shootout creation wizard."""
    from webapp.adapters.persistence.models.shootout import DITrack

    query = (
        select(DITrack)
        .where(DITrack.user_id == current_user.id)
        .order_by(DITrack.created_at.desc())
    )

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


@router.post("/shootout/create", response_class=HTMLResponse)
async def shootout_create_submit(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user_required)],
) -> HTMLResponse:
    """Create a shootout from the wizard form submission."""
    from uuid import uuid4

    from gts.domain.entities.shootout import Shootout as ShootoutEntity
    from gts.domain.entities.shootout import ShootoutChain as ShootoutChainVO

    form = await request.form()
    name = form.get("name", "Untitled Shootout")
    di_track_id = form.get("di_track_id")
    chain_ids = form.getlist("chain_ids[]") or form.getlist("chain_ids")

    if not di_track_id or str(di_track_id).strip() == "":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A DI track is required to create a shootout",
        )

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


@router.get("/shootout/{shootout_id}/comments", response_class=HTMLResponse)
async def shootout_comments_fragment(
    request: Request,
    shootout_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User | None, Depends(get_current_user_optional)],
) -> HTMLResponse:
    """Render shootout comments section with real data."""
    comment_repo = ShootoutCommentRepository(db)
    if current_user is None:
        # Anonymous requests have no owner to scope by. Public shootout
        # visibility is introduced by DOM-shootout-visibility; until then
        # return nothing rather than leak another user's comments.
        comments_orm: list = []
    else:
        comments_orm = await comment_repo.list_by_shootout(shootout_id, current_user.id)

    comments = [comment_to_context(c, current_user) for c in comments_orm]

    return templates.TemplateResponse(
        request,
        "fragments/shootouts/comments.html",
        {
            "shootout_id": str(shootout_id),
            "comments": comments,
            "current_user": current_user,
        },
    )
