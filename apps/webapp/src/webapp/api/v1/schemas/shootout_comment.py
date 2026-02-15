"""Pydantic schemas for shootout comment API requests and responses."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CommentCreateRequest(BaseModel):
    """Request schema for creating a comment."""

    content: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Comment text content",
    )

    @field_validator("content")
    @classmethod
    def strip_and_validate_content(cls, v: str) -> str:
        """Strip whitespace and validate content is not empty."""
        v = v.strip()
        if not v:
            raise ValueError("Content cannot be empty or whitespace only")
        return v


class CommentResponse(BaseModel):
    """Response schema for a comment."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    shootout_id: UUID
    user_id: UUID
    content: str
    author_username: str
    author_avatar_url: str | None
    created_at: datetime
