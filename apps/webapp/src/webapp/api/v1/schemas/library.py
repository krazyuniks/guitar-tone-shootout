"""Pydantic schemas for Library API endpoints."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, computed_field

from core.domain.value_objects.signal_chain_enums import GearType


class AddGearToLibraryRequest(BaseModel):
    """Request schema for adding gear model to user library."""

    gear_model_id: UUID
    nickname: str | None = None
    is_favourite: bool = False


class UserGearResponse(BaseModel):
    """Response schema for a user's gear library item.

    For the SignalChainBuilder, this represents gear items in the user's library
    that can be added to signal chains.

    Provides both simple names (id, name) for builder and explicit names
    (user_gear_id, gear_name) for API clarity.
    """

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    # Both simple and explicit field names via computed_field
    user_gear_id: UUID       # UserGear.id
    gear_model_id: UUID      # GearModel.id
    gear_name: str           # Gear.name
    gear_type: GearType
    nickname: str | None = None
    is_favourite: bool = False

    # Computed fields for builder compatibility
    @computed_field  # type: ignore[prop-decorator]
    @property
    def id(self) -> UUID:
        """Alias for user_gear_id for builder compatibility."""
        return self.user_gear_id

    @computed_field  # type: ignore[prop-decorator]
    @property
    def name(self) -> str:
        """Alias for gear_name for builder compatibility."""
        return self.gear_name
