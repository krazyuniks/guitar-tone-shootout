"""Pydantic schemas for DI track API responses."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class DITrackResponse(BaseModel):
    """Response schema for DI track endpoints."""

    id: UUID
    user_id: UUID
    name: str
    file_path: str
    original_filename: str
    duration_seconds: float
    sample_rate: int
    channels: int | None = None
    waveform: Any | None = None
    description: str | None = None
    guitar: str | None = None
    pickup: str | None = None
    tuning: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
