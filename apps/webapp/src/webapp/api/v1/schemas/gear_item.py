"""Pydantic schemas for user gear item API responses."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

GearItemType = Literal["pedal", "amp", "ir", "full_rig", "post_effect"]


class TagListItem(BaseModel):
    """Tag shape expected by the signal-chain builder."""

    id: str
    name: str
    category: str | None


class GearItemListItem(BaseModel):
    """User gear item list shape expected by the frontend."""

    id: str
    gear_type: GearItemType
    model_id: str
    display_name: str | None
    is_favorite: bool
    tone3000_tone_id: int | None
    tone3000_model_id: int | None
    pack_title: str | None
    model_name: str | None
    model_size: str | None
    pack_models_count: int | None
    created_at: datetime
    tags: list[TagListItem]


class GearItemListResponse(BaseModel):
    """Paginated user gear item response."""

    gear_items: list[GearItemListItem]
    total: int
    page: int
    page_size: int
