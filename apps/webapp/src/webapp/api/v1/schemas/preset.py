"""Pydantic schemas for Preset API."""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class PresetCreateRequest(BaseModel):
    """Request schema for creating a preset."""

    name: str = Field(..., min_length=1, max_length=100, description="Preset name")
    description: str | None = Field(None, description="Optional preset description")
    signal_chain_block_id: UUID = Field(..., description="ID of the signal chain block")
    chain_parameters: dict[str, Any] = Field(
        ...,
        description="Parameter values for the preset",
    )


class PresetUpdateRequest(BaseModel):
    """Request schema for updating a preset."""

    name: str = Field(..., min_length=1, max_length=100, description="Preset name")
    description: str | None = Field(None, description="Optional preset description")
    chain_parameters: dict[str, Any] = Field(
        ...,
        description="Parameter values for the preset",
    )


class PresetResponse(BaseModel):
    """Response schema for preset endpoints."""

    id: UUID
    name: str
    description: str | None
    signal_chain_block_id: UUID
    chain_parameters: dict[str, Any]

    model_config = {"from_attributes": True}

    @staticmethod
    def from_orm_preset(preset: Any) -> "PresetResponse":
        """Convert ORM Preset to response schema.

        Args:
            preset: Preset ORM instance

        Returns:
            PresetResponse instance
        """
        return PresetResponse(
            id=preset.id,
            name=preset.name,
            description=preset.description,
            signal_chain_block_id=preset.signal_chain_block_id,
            chain_parameters=preset.params,
        )
