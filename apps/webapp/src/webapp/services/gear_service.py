"""GearService for managing gear with search, filtering, and CRUD operations."""

from __future__ import annotations

from typing import TYPE_CHECKING

from webapp.adapters.persistence.repositories.gear_repository import (
    SQLAlchemyGearRepository,
)

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession

    from core.domain.entities.gear import Gear
    from core.domain.value_objects.signal_chain_enums import GearType


class GearService:
    """Service for managing gear.

    Handles search, filtering, and CRUD operations for gear.
    Transaction management is the caller's responsibility.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = SQLAlchemyGearRepository(session)

    async def get_by_id(self, gear_id: UUID) -> Gear | None:
        return await self.repository.get_by_id(gear_id)

    async def get_by_slug(self, slug: str) -> Gear | None:
        return await self.repository.get_by_slug(slug)

    async def search(
        self,
        *,
        query: str | None = None,
        gear_type: GearType | None = None,
        manufacturer: str | None = None,
        tags: list[str] | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Gear]:
        return await self.repository.search(
            query=query,
            gear_type=gear_type,
            manufacturer=manufacturer,
            tags=tags,
            limit=limit,
            offset=offset,
        )

    async def count(
        self,
        *,
        query: str | None = None,
        gear_type: GearType | None = None,
        manufacturer: str | None = None,
        tags: list[str] | None = None,
    ) -> int:
        return await self.repository.count(
            query=query,
            gear_type=gear_type,
            manufacturer=manufacturer,
            tags=tags,
        )

    async def save(self, gear: Gear) -> None:
        await self.repository.save(gear)
        await self.session.flush()

    async def delete(self, gear_id: UUID) -> None:
        await self.repository.delete(gear_id)
        await self.session.flush()
