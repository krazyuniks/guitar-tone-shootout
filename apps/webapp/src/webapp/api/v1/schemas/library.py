"""Pydantic schemas for Library API endpoints."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from core.domain.value_objects.signal_chain_enums import GearType


class AddGearToLibraryRequest(BaseModel):
    """Request schema for adding gear to user library."""

    gear_id: UUID
    nickname: str | None = None
    is_favourite: bool = False


class UserGearResponse(BaseModel):
    """Response schema for a user's gear library item."""

    model_config = ConfigDict(from_attributes=True)

    user_gear_id: UUID
    gear_id: UUID
    nickname: str | None = None
    is_favourite: bool = False
    gear_name: str
    gear_type: GearType
