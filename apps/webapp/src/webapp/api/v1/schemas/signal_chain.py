"""Pydantic schemas for SignalChain API endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class BlockRequest(BaseModel):
    """Request schema for a signal chain block."""

    user_gear_id: UUID
    position: int


class BlockResponse(BaseModel):
    """Response schema for a signal chain block."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_gear_id: UUID
    gear_type: str
    position: int


class SignalChainCreateRequest(BaseModel):
    """Request schema for creating a signal chain."""

    name: str
    platform: Literal["nam", "aida_x", "ir", "aa_snapshot", "proteus"]
    description: str | None = None
    blocks: list[BlockRequest]


class SignalChainUpdateRequest(BaseModel):
    """Request schema for updating a signal chain."""

    name: str
    platform: Literal["nam", "aida_x", "ir", "aa_snapshot", "proteus"]
    description: str | None = None
    blocks: list[BlockRequest]


class SignalChainResponse(BaseModel):
    """Response schema for a signal chain."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    name: str
    description: str | None
    platform: str
    blocks: list[BlockResponse]
    created_at: datetime
    updated_at: datetime
