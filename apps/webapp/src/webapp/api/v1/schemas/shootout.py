"""Pydantic schemas for Shootout API endpoints."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ShootoutCreateRequest(BaseModel):
    """Request schema for creating a shootout."""

    name: str
    di_track_id: UUID
    description: str | None = None


class ShootoutUpdateRequest(BaseModel):
    """Request schema for updating a shootout."""

    name: str | None = None
    description: str | None = None


class ShootoutResponse(BaseModel):
    """Response schema for a shootout."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    name: str
    di_track_id: UUID
    description: str | None = None
    is_processed: bool
    output_path: str | None = None
    created_at: datetime
    updated_at: datetime
