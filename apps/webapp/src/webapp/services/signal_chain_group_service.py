"""SignalChainGroupService for managing signal chain groups with CRUD operations."""

from __future__ import annotations

import itertools
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import select

from core.domain.value_objects.signal_chain_enums import Platform
from webapp.adapters.persistence.models.signal_chain import (
    SignalChain as SignalChainModel,
)
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

    async def generate_permutations(self, group_id: UUID) -> list[str]:
        """Generate signal chain permutations from a group's gear options.

        Computes the cartesian product of gear options across slots, then
        creates a SignalChain for each permutation.

        Args:
            group_id: ID of the group to generate permutations for

        Returns:
            List of created chain IDs as strings

        Raises:
            ValueError: If group not found or exceeds max_permutations
        """
        group = await self.repository.get_by_id(group_id)
        if group is None:
            raise ValueError(f"Group not found: {group_id}")

        # Validate permutation count
        if group.exceeds_max_permutations():
            raise ValueError(
                f"Too many permutations ({group.estimated_permutation_count()}). "
                f"Maximum is {group.max_permutations}."
            )

        # Build option lists for each slot position
        # include_null adds a None option only to slots that have no gear options
        slot_options: list[list[UUID | None]] = []
        for pos in group.slot_positions:
            options: list[UUID | None] = list(group.gear_options.get(pos, []))
            if group.include_null and len(options) == 0:
                options.append(None)
            slot_options.append(options)

        # Compute cartesian product
        permutations = list(itertools.product(*slot_options))

        # Look up base chain platform (default to NAM)
        platform_value = Platform.NAM.value
        if group.base_chain_id:
            stmt = select(SignalChainModel).where(
                SignalChainModel.id == group.base_chain_id
            )
            result = await self.session.execute(stmt)
            base_chain = result.scalar_one_or_none()
            if base_chain and base_chain.platform:
                platform_value = base_chain.platform.value if hasattr(base_chain.platform, 'value') else str(base_chain.platform)

        # Create a SignalChain for each permutation
        chain_ids: list[str] = []
        for i, perm in enumerate(permutations):
            chain_id = uuid4()

            # Build descriptive name
            parts = []
            for slot_idx, gear_id in enumerate(perm):
                if gear_id is None:
                    parts.append("none")
                else:
                    parts.append(f"slot{group.slot_positions[slot_idx]}")
            perm_label = " / ".join(parts)
            chain_name = f"{group.name} — #{i + 1} ({perm_label})"

            chain = SignalChainModel(
                id=chain_id,
                user_id=group.user_id,
                name=chain_name,
                platform=platform_value,
                blocks=[],
            )
            self.session.add(chain)
            chain_ids.append(str(chain_id))

        await self.session.flush()
        return chain_ids
