"""Pydantic schemas for Gear API endpoints."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from core.domain.value_objects.signal_chain_enums import GearType


class GearResponse(BaseModel):
    """Response schema for a single gear item.

    Represents gear data returned from the API, including all
    details needed for display and identification.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    slug: str
    gear_type: GearType
    description: str | None = None
    manufacturer: str | None = None
    tags: list[str] = Field(default_factory=list)
    thumbnail_url: str | None = None
    is_public: bool
    created_at: datetime
    updated_at: datetime


class GearListResponse(BaseModel):
    """Paginated response schema for gear list endpoint.

    Contains a list of gear items along with pagination metadata.
    """

    items: list[GearResponse]
    total: int = Field(..., description="Total number of items matching filters")
    limit: int = Field(..., description="Maximum items per page")
    offset: int = Field(..., description="Number of items skipped")
