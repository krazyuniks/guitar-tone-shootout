"""Pydantic schemas for Tag API."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class TagCreateRequest(BaseModel):
    """Request schema for creating a tag."""

    name: str = Field(..., min_length=1, description="Tag name (will be normalized to lowercase)")

    @field_validator("name")
    @classmethod
    def name_not_whitespace_only(cls, v: str) -> str:
        """Validate that name is not empty or whitespace-only."""
        if not v.strip():
            raise ValueError("Tag name cannot be empty or whitespace-only")
        return v


class TagResponse(BaseModel):
    """Response schema for tag endpoints."""

    id: UUID
    name: str
    user_id: UUID
    created_at: datetime

    model_config = {"from_attributes": True}
