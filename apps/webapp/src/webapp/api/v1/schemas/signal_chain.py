"""Pydantic schemas for SignalChain API endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

GuidanceGearType = Literal["pedal", "amp", "ir"]


class GuidanceBlockRequest(BaseModel):
    """A representative block from the builder's v1 template signature."""

    gear_type: GuidanceGearType


class GuidanceRequest(BaseModel):
    """Request schema for stateless signal-chain guidance."""

    blocks: list[GuidanceBlockRequest] = Field(max_length=3)


class GuidanceResponse(BaseModel):
    """Guidance derived from the signal-chain grammar."""

    next_valid_gear_types: list[GuidanceGearType]
    guidance_message: str
    is_complete: bool


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
