"""SignalChainGroupService for managing signal chain groups with CRUD operations."""

from __future__ import annotations

from typing import TYPE_CHECKING

from webapp.adapters.persistence.repositories.signal_chain_group_repository import (
    SQLAlchemySignalChainGroupRepository,
)

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession

    from core.domain.entities.signal_chain_group import SignalChainGroup


class SignalChainGroupService:
    """Service for managing signal chain groups.

    Handles CRUD operations for signal chain groups.
    Transaction management is the caller's responsibility.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize service with database session.

        Args:
            session: SQLAlchemy async session
        """
        self.session = session
        self.repository = SQLAlchemySignalChainGroupRepository(session)

    async def create(self, group: SignalChainGroup) -> SignalChainGroup:
        """Create a new signal chain group.

        Args:
            group: SignalChainGroup entity to create

        Returns:
            The created SignalChainGroup entity
        """
        await self.repository.save(group)
        await self.session.flush()
        return group

    async def get_by_id(self, group_id: UUID) -> SignalChainGroup | None:
        """Get a signal chain group by ID.

        Args:
            group_id: Group ID to retrieve

        Returns:
            SignalChainGroup entity if found, None otherwise
        """
        return await self.repository.get_by_id(group_id)

    async def get_by_user_id(
        self,
        user_id: UUID,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[SignalChainGroup]:
        """Get all signal chain groups for a user.

        Args:
            user_id: User ID to filter by
            limit: Maximum number of groups to return
            offset: Number of groups to skip

        Returns:
            List of SignalChainGroup entities
        """
        return await self.repository.get_by_user_id(
            user_id,
            limit=limit,
            offset=offset,
        )

    async def update(self, group: SignalChainGroup) -> SignalChainGroup:
        """Update an existing signal chain group.

        Args:
            group: SignalChainGroup entity to update

        Returns:
            The updated SignalChainGroup entity
        """
        await self.repository.save(group)
        await self.session.flush()
        return group

    async def delete(self, group_id: UUID) -> None:
        """Delete a signal chain group.

        Args:
            group_id: ID of group to delete
        """
        await self.repository.delete(group_id)
        await self.session.flush()
