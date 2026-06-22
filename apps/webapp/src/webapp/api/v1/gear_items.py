"""User gear item API endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from webapp.adapters.persistence.models.gear import Gear
from webapp.adapters.persistence.models.gear_model import GearModel
from webapp.adapters.persistence.models.user_gear import UserGear
from webapp.adapters.persistence.repositories.user_gear_repository import (
    SQLAlchemyUserGearRepository,
    UserGearListItemProjection,
)
from webapp.api.v1.schemas.gear_item import (
    GearItemListItem,
    GearItemListResponse,
    GearItemType,
    TagListItem,
)
from webapp.auth.dependencies import CurrentUser, get_db_session

router = APIRouter(prefix="/api/gear-items", tags=["gear-items"])


def _tone3000_tone_id(gear: Gear) -> int | None:
    source = gear.source
    if source is not None and source.source_name == "t3k" and source.source_record_id.isdigit():
        return int(source.source_record_id)
    return None


# The frontend GearItemType union (pedal/amp/ir/full_rig/post_effect) is narrower
# than the backend GearType enum, which also has GearType.OUTBOARD. The signal-chain
# builder already categorises outboard as a pedal (ToneSearchModal.gearToLibraryGearType
# maps 'outboard' -> 'pedal'), so the projection folds it the same way to keep the typed
# response contract intact.
_GEAR_TYPE_TO_ITEM_TYPE: dict[str, GearItemType] = {
    "amp": "amp",
    "pedal": "pedal",
    "ir": "ir",
    "full_rig": "full_rig",
    "post_effect": "post_effect",
    "outboard": "pedal",
}


def _tags_from_gear(gear: Gear) -> list[TagListItem]:
    return [TagListItem(id=str(tag.id), name=tag.name, category=None) for tag in gear.tags]


def _item_from_projection(row: UserGearListItemProjection) -> GearItemListItem:
    user_gear: UserGear = row.user_gear
    gear: Gear = row.gear
    gear_model: GearModel = row.gear_model

    return GearItemListItem(
        id=str(user_gear.id),
        gear_type=_GEAR_TYPE_TO_ITEM_TYPE[gear.gear_type.value],
        model_id=str(user_gear.gear_model_id),
        display_name=user_gear.nickname or gear.name,
        is_favorite=user_gear.is_favourite,
        tone3000_tone_id=_tone3000_tone_id(gear),
        tone3000_model_id=None,
        pack_title=gear.name,
        model_name=None,
        model_size=gear_model.size.value,
        pack_models_count=len(gear.models),
        created_at=user_gear.created_at,
        tags=_tags_from_gear(gear),
    )


@router.get("", response_model=GearItemListResponse)
async def list_gear_items(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: CurrentUser,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 100,
) -> GearItemListResponse:
    """Return the authenticated user's saved gear library."""
    offset = (page - 1) * page_size
    repository = SQLAlchemyUserGearRepository(db)
    total = await repository.count_by_user(current_user.id)
    rows = await repository.list_items_by_user(
        current_user.id,
        limit=page_size,
        offset=offset,
    )

    return GearItemListResponse(
        gear_items=[_item_from_projection(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
    )
