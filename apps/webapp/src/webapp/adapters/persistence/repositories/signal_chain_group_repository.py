"""SQLAlchemy implementation of SignalChainGroupRepository protocol."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID as PyUUID

from sqlalchemy import select

from gts.domain.entities.signal_chain_group import (
    SignalChainGroup as SignalChainGroupEntity,
)
from webapp.adapters.persistence.models.signal_chain import SignalChainGroup

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession


class SQLAlchemySignalChainGroupRepository:
    """SQLAlchemy implementation of SignalChainGroupRepository protocol.

    Maps between domain SignalChainGroup entities and ORM SignalChainGroup models.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the repository with an async session.

        Args:
            session: SQLAlchemy async session
        """
        self.session = session

    async def get_by_id(self, group_id: UUID, user_id: UUID) -> SignalChainGroupEntity | None:
        """Get a group by ID, scoped to the owning user.

        Args:
            group_id: The group's UUID
            user_id: The requesting user's UUID — included in the WHERE clause

        Returns:
            The SignalChainGroup entity if found and owned, None otherwise
        """
        stmt = select(SignalChainGroup).where(
            SignalChainGroup.id == group_id, SignalChainGroup.user_id == user_id
        )
        result = await self.session.execute(stmt)
        group = result.scalar_one_or_none()

        if group is None:
            return None

        return self._to_entity(group)

    async def get_by_user_id(
        self,
        user_id: UUID,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[SignalChainGroupEntity]:
        """Get groups for a user.

        Args:
            user_id: The user's UUID
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            List of SignalChainGroups ordered by created_at desc
        """
        stmt = (
            select(SignalChainGroup)
            .where(SignalChainGroup.user_id == user_id)
            .order_by(SignalChainGroup.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        groups = result.scalars().all()

        return [self._to_entity(group) for group in groups]

    async def save(self, group: SignalChainGroupEntity) -> None:
        """Save a group (create or update).

        Args:
            group: The group to save
        """
        # Check if group exists
        stmt = select(SignalChainGroup).where(SignalChainGroup.id == group.id)
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()

        # Convert gear_options dict[int, list[UUID]] to dict[int, list[str]]
        gear_options_str: dict[int, list[str]] = {}
        for pos, gear_ids in group.gear_options.items():
            gear_options_str[pos] = [str(gear_id) for gear_id in gear_ids]

        if existing is None:
            # Create new group
            orm_group = SignalChainGroup(
                id=group.id,
                user_id=group.user_id,
                name=group.name,
                description=group.description,
                base_chain_id=group.base_chain_id,
                slot_positions=group.slot_positions,
                gear_options=gear_options_str,
                include_null=group.include_null,
                created_at=group.created_at,
                updated_at=group.updated_at,
            )
            self.session.add(orm_group)
        else:
            # Update existing group
            existing.name = group.name
            existing.description = group.description
            existing.base_chain_id = group.base_chain_id
            existing.slot_positions = group.slot_positions
            existing.gear_options = gear_options_str
            existing.include_null = group.include_null
            existing.updated_at = group.updated_at

        await self.session.flush()

    async def delete(self, group_id: UUID) -> None:
        """Delete a group by ID.

        Args:
            group_id: The group's UUID
        """
        stmt = select(SignalChainGroup).where(SignalChainGroup.id == group_id)
        result = await self.session.execute(stmt)
        group = result.scalar_one_or_none()

        if group is not None:
            await self.session.delete(group)
            await self.session.flush()

    def _to_entity(self, orm_group: SignalChainGroup) -> SignalChainGroupEntity:
        """Convert ORM SignalChainGroup to domain entity.

        Args:
            orm_group: ORM SignalChainGroup model

        Returns:
            Domain SignalChainGroup entity
        """
        # Convert gear_options dict[int, list[str]] to dict[int, list[UUID]]
        gear_options: dict[int, list[PyUUID]] = {}
        for pos, gear_ids_str in (orm_group.gear_options or {}).items():
            gear_options[int(pos)] = [PyUUID(gear_id_str) for gear_id_str in gear_ids_str]

        return SignalChainGroupEntity(
            id=orm_group.id,
            user_id=orm_group.user_id,
            name=orm_group.name,
            description=orm_group.description,
            base_chain_id=orm_group.base_chain_id,
            slot_positions=orm_group.slot_positions or [],
            gear_options=gear_options,
            include_null=orm_group.include_null,
            max_permutations=SignalChainGroupEntity.MAX_PERMUTATIONS,
            created_at=orm_group.created_at,
            updated_at=orm_group.updated_at,
        )
