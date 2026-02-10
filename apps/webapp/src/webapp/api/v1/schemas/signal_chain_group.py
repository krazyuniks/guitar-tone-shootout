"""Pydantic schemas for SignalChainGroup API endpoints."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class SignalChainGroupCreateRequest(BaseModel):
    """Request schema for creating a signal chain group."""

    name: str
    description: str | None = None
    base_chain_id: UUID
    slot_positions: list[int]
    gear_options: dict[int, list[UUID]]
    include_null: bool = False


class SignalChainGroupUpdateRequest(BaseModel):
    """Request schema for updating a signal chain group."""

    name: str | None = None
    description: str | None = None
    slot_positions: list[int] | None = None
    gear_options: dict[int, list[UUID]] | None = None
    include_null: bool | None = None


class SignalChainGroupResponse(BaseModel):
    """Response schema for a signal chain group."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    name: str
    description: str | None = None
    base_chain_id: UUID | None = None
    slot_positions: list[int]
    gear_options: dict[int, list[UUID]]
    include_null: bool
    created_at: datetime
    updated_at: datetime
