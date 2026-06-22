"""SQLAlchemy implementation of UserGearRepository protocol."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from sqlalchemy import delete, func, select
from sqlalchemy.orm import joinedload

from gts.domain.entities.gear import UserGear as UserGearEntity
from webapp.adapters.persistence.models.gear import Gear
from webapp.adapters.persistence.models.gear_model import GearModel
from webapp.adapters.persistence.models.user_gear import UserGear

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession

    from gts.domain.value_objects.signal_chain_enums import GearType


@dataclass(frozen=True, slots=True)
class UserGearListItemProjection:
    """Joined user-gear row for API list projections."""

    user_gear: UserGear
    gear: Gear
    gear_model: GearModel


class SQLAlchemyUserGearRepository:
    """SQLAlchemy implementation of UserGearRepository protocol.

    Maps between domain UserGear entities and ORM UserGear models.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the repository with an async session.

        Args:
            session: SQLAlchemy async session
        """
        self.session = session

    async def add(self, user_gear: UserGearEntity) -> None:
        """Add gear to user's library.

        Args:
            user_gear: The UserGear entity to add
        """
        # Check if already exists (for update case)
        existing = await self.session.get(UserGear, user_gear.id)

        if existing:
            # Update existing
            existing.user_id = user_gear.user_id
            existing.gear_model_id = user_gear.gear_model_id
            existing.nickname = user_gear.nickname
            existing.notes = user_gear.notes
            existing.is_favourite = user_gear.is_favourite
            existing.updated_at = user_gear.updated_at
        else:
            # Create new
            new_user_gear = UserGear(
                id=user_gear.id,
                user_id=user_gear.user_id,
                gear_model_id=user_gear.gear_model_id,
                nickname=user_gear.nickname,
                notes=user_gear.notes,
                is_favourite=user_gear.is_favourite,
                created_at=user_gear.created_at,
                updated_at=user_gear.updated_at,
            )
            self.session.add(new_user_gear)

    async def remove(self, user_id: UUID, gear_model_id: UUID) -> None:
        """Remove gear from user's library.

        Args:
            user_id: The user's ID
            gear_model_id: The gear model's ID
        """
        stmt = delete(UserGear).where(
            UserGear.user_id == user_id,
            UserGear.gear_model_id == gear_model_id,
        )
        await self.session.execute(stmt)

    async def get_by_user_and_gear(
        self,
        user_id: UUID,
        gear_model_id: UUID,
    ) -> UserGearEntity | None:
        """Get user_gear entry by user and gear model ID.

        Args:
            user_id: The user's ID
            gear_model_id: The gear model's ID

        Returns:
            The UserGear entity if found, None otherwise
        """
        stmt = select(UserGear).where(
            UserGear.user_id == user_id,
            UserGear.gear_model_id == gear_model_id,
        )
        result = await self.session.execute(stmt)
        user_gear = result.scalar_one_or_none()
        return self._to_entity(user_gear) if user_gear else None

    async def list_by_user(self, user_id: UUID) -> list[UserGearEntity]:
        """List all gear in user's library.

        Args:
            user_id: The user's ID

        Returns:
            List of UserGear entities
        """
        stmt = select(UserGear).where(UserGear.user_id == user_id)
        result = await self.session.execute(stmt)
        user_gear_items = result.scalars().all()
        return [self._to_entity(ug) for ug in user_gear_items]

    async def list_items_by_user(
        self,
        user_id: UUID,
        *,
        limit: int,
        offset: int,
    ) -> list[UserGearListItemProjection]:
        """List joined user-gear rows for the API item projection."""
        stmt = (
            select(UserGear, Gear, GearModel)
            .join(GearModel, UserGear.gear_model_id == GearModel.id)
            .join(Gear, GearModel.gear_id == Gear.id)
            .where(UserGear.user_id == user_id)
            .options(
                joinedload(Gear.models),
                joinedload(Gear.source),
                joinedload(Gear.tags),
            )
            .order_by(UserGear.created_at.desc(), UserGear.id.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return [
            UserGearListItemProjection(user_gear=user_gear, gear=gear, gear_model=gear_model)
            for user_gear, gear, gear_model in result.unique().all()
        ]

    async def gear_types_by_user_gear_ids(
        self,
        user_id: UUID,
        user_gear_ids: list[UUID],
    ) -> dict[UUID, GearType]:
        """Return gear types for user-gear IDs owned by the given user."""
        if not user_gear_ids:
            return {}

        stmt = (
            select(UserGear.id, Gear.gear_type)
            .join(GearModel, UserGear.gear_model_id == GearModel.id)
            .join(Gear, GearModel.gear_id == Gear.id)
            .where(UserGear.user_id == user_id, UserGear.id.in_(user_gear_ids))
        )
        result = await self.session.execute(stmt)
        return dict(result.all())

    async def get_gear_type_for_user_gear(
        self,
        user_id: UUID,
        user_gear_id: UUID,
    ) -> GearType | None:
        """Return the gear type for one user-gear row owned by the given user."""
        gear_types = await self.gear_types_by_user_gear_ids(user_id, [user_gear_id])
        return gear_types.get(user_gear_id)

    async def count_by_user(self, user_id: UUID) -> int:
        """Count items in user's library.

        Args:
            user_id: The user's ID

        Returns:
            Count of items in library
        """
        stmt = select(func.count(UserGear.id)).where(UserGear.user_id == user_id)
        result = await self.session.execute(stmt)
        return result.scalar_one()

    def _to_entity(self, user_gear: UserGear) -> UserGearEntity:
        """Convert ORM UserGear to domain UserGearEntity.

        Args:
            user_gear: The ORM UserGear model

        Returns:
            The domain UserGearEntity
        """
        return UserGearEntity(
            id=user_gear.id,
            user_id=user_gear.user_id,
            gear_model_id=user_gear.gear_model_id,
            nickname=user_gear.nickname,
            notes=user_gear.notes,
            is_favourite=user_gear.is_favourite,
            created_at=user_gear.created_at,
            updated_at=user_gear.updated_at,
        )
