"""SSR page routes for public and protected pages."""

import contextlib
import os
from datetime import UTC, datetime
from math import ceil
from typing import Annotated
from urllib.parse import urlencode
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from core.domain.value_objects.signal_chain_enums import GearType
from webapp.adapters.persistence.models.gear import Gear
from webapp.adapters.persistence.models.gear_model import GearModel
from webapp.adapters.persistence.models.shootout import Shootout, ShootoutStatus
from webapp.adapters.persistence.models.user import User
from webapp.adapters.persistence.models.user_gear import UserGear
from webapp.adapters.persistence.repositories.signal_chain_repository import (
    SQLAlchemySignalChainRepository,
)
from webapp.auth.dependencies import (
    get_current_user_optional,
    get_current_user_page,
    get_db_session,
)
from webapp.services.gear_service import GearService
from webapp.services.shootout_service import ShootoutService
from webapp.templates import _relative_time, templates

router = APIRouter(tags=["pages"])

# Session and user overrides for testing
_session_override: AsyncSession | None = None
_user_override: User | None = None


def set_session_override(session: AsyncSession | None) -> None:
    """Override the database session for testing.

    Args:
        session: Test database session or None to clear
    """
    global _session_override
    _session_override = session


def set_user_override(user: User | None) -> None:
    """Override the current user for testing.

    Args:
        user: Test user to use as CurrentUser or None to clear
    """
    global _user_override
    _user_override = user


# --- Gear mapping helpers ---


def _gear_to_pack(gear) -> dict:
    """Map Gear domain entity to pack dict for browse templates."""
    platform = "nam"
    if gear.models:
        p = gear.models[0].platform
        platform = p.value if hasattr(p, "value") else str(p)

    return {
        "id": str(gear.id),
        "slug": gear.slug,
        "title": gear.name,
        "gear_type": (
            gear.gear_type.value if hasattr(gear.gear_type, "value") else str(gear.gear_type)
        ).replace("_", "-"),
        "platform": platform,
        "image_url": gear.thumbnail_url,
        "downloads_count": 0,
        "favorites_count": 0,
        "models_count": len(gear.models),
        "saved_count": 0,
        "creator_username": gear.manufacturer,
        "creator_avatar": None,
        "relative_time": _relative_time(gear.created_at),
    }


def _gear_to_detail_pack(gear) -> dict:
    """Map Gear domain entity to detailed pack dict for detail template."""
    pack = _gear_to_pack(gear)
    pack.update(
        {
            "description": gear.description,
            "tags": gear.tags,
            "makes": [],
            "videos": [],
            "external_links": [],
            "t3k_url": (
                f"https://www.tone3000.com/tones/{gear.source.source_record_id}"
                if gear.source
                else "#"
            ),
            "created_at": (gear.created_at.strftime("%B %d, %Y") if gear.created_at else None),
            "models": [
                {
                    "id": str(m.id),
                    "name": (
                        f"{gear.name} ({m.size.value})" if hasattr(m.size, "value") else gear.name
                    ),
                    "model_size": (m.size.value if hasattr(m.size, "value") else str(m.size)),
                    "is_saved": False,
                }
                for m in gear.models
            ],
        }
    )
    return pack


# --- Public pages ---


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
    """Render gear browse page with full SSR.

    All data rendered server-side — no HTMX, no client-side loading.
    Filters and pagination via standard form submissions and links.
    """
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
        limit=page_size,
        offset=offset,
    )

    packs = [_gear_to_pack(g) for g in gear_items if g.is_public]
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


@router.get("/gear/{slug}", response_class=HTMLResponse)
async def gear_detail_page(
    request: Request,
    slug: str,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User | None, Depends(get_current_user_optional)],
) -> HTMLResponse:
    """Render gear detail page with full SSR.

    All data rendered server-side — pack dict includes models, tags, creator info.
    For authenticated users, marks which models are in their library.
    """
    service = GearService(db)
    gear = await service.get_by_slug(slug)

    if not gear or not gear.is_public:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Gear not found",
        )

    pack = _gear_to_detail_pack(gear)

    # For authenticated users, check which models are in their library
    if current_user:
        # Get all model IDs for this gear
        model_ids = [m.id for m in gear.models]

        # Query UserGear to find which models the user has saved
        result = await db.execute(
            select(UserGear.gear_model_id)
            .where(UserGear.user_id == current_user.id)
            .where(UserGear.gear_model_id.in_(model_ids))
        )
        saved_model_ids = {row[0] for row in result.all()}

        # Mark saved models in pack
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


@router.get("/shootouts", response_class=HTMLResponse)
async def shootouts_page(
    request: Request,
    current_user: Annotated[User | None, Depends(get_current_user_optional)],
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


@router.get("/di-tracks", response_class=HTMLResponse)
async def di_tracks_browse_page(
    request: Request,
    current_user: Annotated[User | None, Depends(get_current_user_optional)],
) -> HTMLResponse:
    """Render DI tracks browse page.

    Public page with HTMX-loaded content.
    """
    return templates.TemplateResponse(
        request,
        "di-tracks/index.html",
        {"user": current_user},
    )


@router.get("/sitemap.xml", response_class=Response)
async def sitemap_xml(
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> Response:
    """Generate dynamic sitemap.xml for search engines.

    Returns valid XML sitemap including:
    - Static pages (homepage, about, gear browse, shootouts)
    - Public gear detail pages
    - Completed shootout pages

    Uses PUBLIC_URL env var for absolute URLs.
    No authentication required.
    """
    public_url = os.getenv("PUBLIC_URL", "http://testserver")

    # Static pages with priority and update frequency
    now = datetime.now(UTC)
    static_pages = [
        ("/", "daily", "1.0", now),
        ("/about", "monthly", "0.5", now),
        ("/gear", "daily", "0.9", now),
        ("/shootouts", "daily", "0.8", now),
    ]

    # Fetch public gear items
    gear_result = await db.execute(
        select(Gear).where(Gear.is_public.is_(True)).order_by(Gear.updated_at.desc())
    )
    public_gear = gear_result.scalars().all()

    # Fetch completed shootouts
    shootout_result = await db.execute(
        select(Shootout)
        .where(Shootout.status == ShootoutStatus.COMPLETED)
        .order_by(Shootout.updated_at.desc())
    )
    completed_shootouts = shootout_result.scalars().all()

    # Build sitemap XML
    xml_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]

    # Add static pages
    for path, changefreq, priority, lastmod in static_pages:
        xml_lines.extend(
            [
                "  <url>",
                f"    <loc>{public_url}{path}</loc>",
                f"    <lastmod>{lastmod.isoformat()}</lastmod>",
                f"    <changefreq>{changefreq}</changefreq>",
                f"    <priority>{priority}</priority>",
                "  </url>",
            ]
        )

    # Add public gear detail pages
    for gear in public_gear:
        lastmod = gear.updated_at if gear.updated_at else gear.created_at
        xml_lines.extend(
            [
                "  <url>",
                f"    <loc>{public_url}/gear/{gear.slug}</loc>",
                f"    <lastmod>{lastmod.isoformat()}</lastmod>",
                "    <changefreq>weekly</changefreq>",
                "    <priority>0.7</priority>",
                "  </url>",
            ]
        )

    # Add completed shootout pages
    for shootout in completed_shootouts:
        lastmod = shootout.updated_at if shootout.updated_at else shootout.created_at
        xml_lines.extend(
            [
                "  <url>",
                f"    <loc>{public_url}/shootouts/{shootout.id}</loc>",
                f"    <lastmod>{lastmod.isoformat()}</lastmod>",
                "    <changefreq>weekly</changefreq>",
                "    <priority>0.6</priority>",
                "  </url>",
            ]
        )

    xml_lines.append("</urlset>")
    xml_content = "\n".join(xml_lines)

    return Response(content=xml_content, media_type="application/xml")


# --- Protected pages (require authentication) ---


@router.get("/library/my-gear", response_class=HTMLResponse)
async def library_my_gear_page(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user_page)],
) -> HTMLResponse:
    """Render user's gear library page.

    Protected page showing user's personal gear collection.
    """
    result = await db.execute(
        select(UserGear, GearModel, Gear)
        .join(GearModel, UserGear.gear_model_id == GearModel.id)
        .join(Gear, GearModel.gear_id == Gear.id)
        .where(UserGear.user_id == current_user.id)
    )
    rows = result.all()

    gear_items = []
    for user_gear, gear_model, gear in rows:
        gear_items.append(
            {
                "user_gear_id": str(user_gear.id),
                "gear_model_id": str(gear_model.id),
                "nickname": user_gear.nickname,
                "is_favourite": user_gear.is_favourite,
                "gear_name": gear.name,
                "gear_type": gear.gear_type.value,
                "manufacturer": gear.manufacturer,
            }
        )

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
    current_user: Annotated[User, Depends(get_current_user_page)],
) -> HTMLResponse:
    """Render user's signal chain library page.

    Protected page showing user's signal chains.
    """
    repo = SQLAlchemySignalChainRepository(db)
    chains = await repo.get_by_user_id(current_user.id)

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
    current_user: Annotated[User, Depends(get_current_user_page)],
) -> HTMLResponse:
    """Render chain list fragment for HTMX updates."""
    repo = SQLAlchemySignalChainRepository(db)
    chains = await repo.get_by_user_id(current_user.id)

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


@router.delete("/fragments/chains/{chain_id}", response_class=HTMLResponse)
async def chain_delete_fragment(
    request: Request,
    chain_id: str,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user_page)],
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
    current_user: Annotated[User, Depends(get_current_user_page)],
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
        chain_items.append(
            {
                "id": str(c.id),
                "name": c.name,
                "description": c.description,
                "platform": c.platform.value,
                "created_at": c.created_at,
            }
        )

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
    current_user: Annotated[User, Depends(get_current_user_page)],
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
    current_user: Annotated[User, Depends(get_current_user_page)],
) -> HTMLResponse:
    """Render user's shootout library page.

    Protected page showing user's shootouts.
    """
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
    current_user: Annotated[User, Depends(get_current_user_page)],
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

    di_track_result = await db.execute(select(DITrack).where(DITrack.id == shootout.di_track_id))
    di_track = di_track_result.scalar_one_or_none()

    chain_items = []
    for shootout_chain in shootout.chains:
        chain_result = await db.execute(
            select(SignalChainModel).where(SignalChainModel.id == shootout_chain.signal_chain_id)
        )
        chain = chain_result.scalar_one_or_none()
        if chain:
            chain_items.append(
                {
                    "signal_chain_id": str(shootout_chain.signal_chain_id),
                    "position": shootout_chain.position,
                    "label": shootout_chain.label,
                    "chain_name": chain.name,
                }
            )

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


@router.delete("/fragments/shootouts/{shootout_id}", response_class=HTMLResponse)
async def shootout_delete_fragment(
    request: Request,
    shootout_id: str,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user_page)],
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


@router.get("/chain/{chain_id}", response_class=HTMLResponse)
async def chain_detail_page(
    request: Request,
    chain_id: str,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user_page)],
) -> HTMLResponse:
    """Render signal chain detail page.

    Protected page showing full chain details with blocks.
    """
    from webapp.adapters.persistence.models.gear import Gear

    repo = SQLAlchemySignalChainRepository(db)
    chain = await repo.get_by_id(UUID(chain_id))

    if not chain or chain.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chain not found",
        )

    # Build block data with gear names (join through UserGear → Gear)
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

    block_items.sort(key=lambda x: x["position"])

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


@router.get("/shootout/create", response_class=HTMLResponse)
async def shootout_create_page(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user_page)],
) -> HTMLResponse:
    """Render shootout creation wizard page.

    Protected page — wizard steps load via HTMX.
    """
    return templates.TemplateResponse(
        request,
        "pages/shootout_create.html",
        {
            "title": "Create Shootout",
            "user": current_user,
        },
    )


@router.get("/library/di-tracks", response_class=HTMLResponse)
async def library_di_tracks_page(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user_page)],
) -> HTMLResponse:
    """Render user's DI tracks library page.

    Protected page — content loads via HTMX.
    """
    return templates.TemplateResponse(
        request,
        "pages/library/di-tracks.html",
        {"user": current_user},
    )


@router.get("/settings/account", response_class=HTMLResponse)
async def settings_account_page(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user_page)],
) -> HTMLResponse:
    """Render account settings page with linked provider status."""
    from webapp.adapters.persistence.models.user_identity import UserIdentity

    # Re-query user with identities eagerly loaded (auth dep doesn't load them)
    result = await db.execute(
        select(User)
        .where(User.id == current_user.id)
        .options(joinedload(User.identities).joinedload(UserIdentity.provider))
    )
    user_with_identities = result.unique().scalar_one_or_none()

    # Build provider status list
    identities = user_with_identities.identities if user_with_identities else []
    linked_providers = {
        identity.provider.name: identity for identity in identities if identity.provider
    }

    provider_defs = [
        ("t3k", "Tone3000", True),
        ("google", "Google", False),
        ("github", "GitHub", False),
        ("facebook", "Facebook", False),
    ]

    providers = []
    for name, display_name, available in provider_defs:
        identity = linked_providers.get(name)
        providers.append(
            {
                "name": name,
                "display_name": display_name,
                "available": available,
                "linked": identity is not None,
                "username": identity.username if identity else None,
                "is_last_provider": len(linked_providers) <= 1 and identity is not None,
            }
        )

    return templates.TemplateResponse(
        request,
        "pages/settings_account.html",
        {
            "user": current_user,
            "providers": providers,
        },
    )
