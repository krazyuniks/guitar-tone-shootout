"""Pydantic schemas for Block Types API."""

from typing import Any
from uuid import UUID

from pydantic import BaseModel

from core.domain.value_objects.block_category import BlockCategory


class BlockTypeResponse(BaseModel):
    """Response schema for block type endpoints."""

    id: UUID
    name: str
    description: str | None
    category: BlockCategory
    default_params: dict[str, Any]

    model_config = {"from_attributes": True}
