"""Tone search API endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, cast, get_args

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from gts.domain.value_objects.signal_chain_enums import GearType, Platform
from webapp.api.v1.schemas.tone import (
    FrontendGear,
    FrontendLicense,
    FrontendPlatform,
    PaginatedTonesResponse,
    TagResponse,
    ToneResponse,
)
from webapp.auth.dependencies import get_db_session
from webapp.services.gear_service import GearService

if TYPE_CHECKING:
    from gts.domain.entities.gear import Gear

router = APIRouter(prefix="/api/tones", tags=["tones"])

GEAR_PARAM_MAP: dict[str, GearType] = {
    "amp": GearType.AMP,
    "full-rig": GearType.FULL_RIG,
    "pedal": GearType.PEDAL,
    "outboard": GearType.OUTBOARD,
    "ir": GearType.IR,
}
PLATFORM_PARAM_MAP: dict[str, Platform] = {
    "nam": Platform.NAM,
    "ir": Platform.IR,
    "aida-x": Platform.AIDA_X,
}
GEAR_RESPONSE_MAP: dict[GearType, FrontendGear] = {
    GearType.AMP: "amp",
    GearType.FULL_RIG: "full-rig",
    GearType.PEDAL: "pedal",
    GearType.OUTBOARD: "outboard",
    GearType.IR: "ir",
    GearType.POST_EFFECT: "outboard",
}
FRONTEND_LICENSES = set(get_args(FrontendLicense))


def _parse_gear_filter(gear: str | None) -> GearType | None:
    if gear is None:
        return None
    try:
        return GEAR_PARAM_MAP[gear]
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown gear value: {gear}",
        ) from exc


def _parse_platform_filter(platform: str | None) -> Platform | None:
    if platform is None:
        return None
    try:
        return PLATFORM_PARAM_MAP[platform]
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown platform value: {platform}",
        ) from exc


def _map_gear_type(gear_type: GearType) -> FrontendGear:
    return GEAR_RESPONSE_MAP[gear_type]


def _map_platform(platform: Platform) -> FrontendPlatform:
    if platform == Platform.IR:
        return "ir"
    if platform == Platform.AIDA_X:
        return "aida-x"
    return "nam"


def _tone_platform(gear: Gear, platform_filter: Platform | None) -> FrontendPlatform:
    if platform_filter is not None:
        return _map_platform(platform_filter)
    if gear.models:
        return _map_platform(gear.models[0].platform)
    return "nam"


def _map_license(license_text: str | None) -> FrontendLicense | None:
    if license_text in FRONTEND_LICENSES:
        return cast("FrontendLicense", license_text)
    return None


def _tone_from_gear(gear: Gear, platform_filter: Platform | None) -> ToneResponse:
    return ToneResponse(
        id=str(gear.id),
        title=gear.name,
        description=gear.description,
        gear=_map_gear_type(gear.gear_type),
        platform=_tone_platform(gear, platform_filter),
        tags=[TagResponse(id=index, name=tag) for index, tag in enumerate(gear.tags)],
        makes=[],
        links=[],
        videos=[],
        images=[gear.thumbnail_url] if gear.thumbnail_url else [],
        models_count=len(gear.models),
        downloads_count=gear.downloads_count,
        favorites_count=gear.favorites_count,
        license=_map_license(gear.license_text),
        creator=None,
        created_at=gear.source_created_at or gear.created_at,
        updated_at=gear.updated_at,
    )


@router.get("/search", response_model=PaginatedTonesResponse)
async def search_tones(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    query: Annotated[str | None, Query()] = None,
    gear: Annotated[str | None, Query()] = None,
    platform: Annotated[str | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(ge=1, le=100)] = 50,
) -> PaginatedTonesResponse:
    """Search the public tone catalogue for signal-chain builder selections."""
    gear_type = _parse_gear_filter(gear)
    platform_filter = _parse_platform_filter(platform)
    offset = (page - 1) * per_page

    service = GearService(db)
    total = await service.count(
        query=query,
        gear_type=gear_type,
        platform=platform_filter,
        manufacturer=None,
        tags=None,
        is_public=True,
    )
    gear_items = await service.search(
        query=query,
        gear_type=gear_type,
        platform=platform_filter,
        manufacturer=None,
        tags=None,
        is_public=True,
        limit=per_page,
        offset=offset,
    )

    return PaginatedTonesResponse(
        data=[_tone_from_gear(item, platform_filter) for item in gear_items],
        total=total,
        page=page,
        per_page=per_page,
        has_next=offset + per_page < total,
    )
