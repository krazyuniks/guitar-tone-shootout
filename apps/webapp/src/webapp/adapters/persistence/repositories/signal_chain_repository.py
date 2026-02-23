"""SQLAlchemy implementation of SignalChainRepository protocol."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import func, select
from sqlalchemy.orm import joinedload

from gts.domain.entities.signal_chain import (
    SignalChain as SignalChainEntity,
)
from gts.domain.entities.signal_chain import SignalChainBlock as BlockEntity
from webapp.adapters.persistence.models.signal_chain import (
    SignalChain,
    SignalChainBlock,
)

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession


class SQLAlchemySignalChainRepository:
    """SQLAlchemy implementation of SignalChainRepository protocol.

    Maps between domain SignalChain entities and ORM SignalChain models,
    handling blocks relationships.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the repository with an async session.

        Args:
            session: SQLAlchemy async session
        """
        self.session = session

    async def get_by_id(self, chain_id: UUID) -> SignalChainEntity | None:
        """Get a signal chain by its ID.

        Args:
            chain_id: The chain's UUID

        Returns:
            The SignalChain with all blocks loaded, or None
        """
        stmt = (
            select(SignalChain)
            .where(SignalChain.id == chain_id)
            .options(joinedload(SignalChain.blocks))
        )
        result = await self.session.execute(stmt)
        chain = result.unique().scalar_one_or_none()
        return self._to_entity(chain) if chain else None

    async def get_by_user_id(
        self,
        user_id: UUID,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[SignalChainEntity]:
        """Get signal chains for a user.

        Args:
            user_id: The user's UUID
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            List of SignalChains ordered by created_at desc
        """
        stmt = (
            select(SignalChain)
            .where(SignalChain.user_id == user_id)
            .options(joinedload(SignalChain.blocks))
            .order_by(SignalChain.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        chains = result.scalars().unique().all()
        return [self._to_entity(chain) for chain in chains]

    async def count_by_user_id(self, user_id: UUID) -> int:
        """Count signal chains for a user.

        Args:
            user_id: The user's UUID

        Returns:
            Count of chains
        """
        stmt = select(func.count(SignalChain.id)).where(SignalChain.user_id == user_id)
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def save(self, chain: SignalChainEntity) -> None:
        """Save a signal chain (create or update).

        This saves both the chain and its blocks.

        Args:
            chain: The chain to save
        """
        # Check if chain exists - use joinedload to load blocks relationship
        stmt = (
            select(SignalChain)
            .where(SignalChain.id == chain.id)
            .options(joinedload(SignalChain.blocks))
        )
        result = await self.session.execute(stmt)
        existing = result.unique().scalar_one_or_none()

        if existing:
            # Update existing chain
            existing.user_id = chain.user_id
            existing.name = chain.name
            existing.description = chain.description
            existing.platform = chain.platform
            existing.updated_at = chain.updated_at

            # Mark as modified (in case session doesn't auto-detect changes)
            self.session.add(existing)

            # Update blocks
            await self._update_blocks(existing, chain.blocks)
        else:
            # Create new chain
            new_chain = SignalChain(
                id=chain.id,
                user_id=chain.user_id,
                name=chain.name,
                description=chain.description,
                platform=chain.platform,
                created_at=chain.created_at,
                updated_at=chain.updated_at,
            )
            self.session.add(new_chain)
            await self.session.flush()

            # Add blocks
            for block in chain.blocks:
                new_block = SignalChainBlock(
                    id=block.id,
                    signal_chain_id=new_chain.id,
                    position=block.position,
                    user_gear_id=block.user_gear_id,
                    gear_type=block.gear_type,
                )
                self.session.add(new_block)

        await self.session.flush()

    async def delete(self, chain_id: UUID) -> None:
        """Delete a signal chain by ID.

        This cascades delete to blocks.

        Args:
            chain_id: The chain's UUID
        """
        chain = await self.session.get(SignalChain, chain_id)
        if chain:
            await self.session.delete(chain)
            await self.session.flush()

    async def _update_blocks(
        self,
        chain: SignalChain,
        block_entities: list[BlockEntity],
    ) -> None:
        """Update blocks for a signal chain.

        Args:
            chain: The ORM SignalChain model
            block_entities: List of block entities
        """
        # Get existing block IDs
        existing_ids = {block.id for block in chain.blocks}
        new_ids = {block.id for block in block_entities}

        # Delete removed blocks
        blocks_to_delete = [block for block in chain.blocks if block.id not in new_ids]
        for block in blocks_to_delete:
            await self.session.delete(block)

        # Flush deletions before proceeding
        if blocks_to_delete:
            await self.session.flush()

        # Update or create blocks
        for block_entity in block_entities:
            if block_entity.id in existing_ids:
                # Update existing block
                existing_block = next(b for b in chain.blocks if b.id == block_entity.id)
                existing_block.position = block_entity.position
                existing_block.user_gear_id = block_entity.user_gear_id
                existing_block.gear_type = block_entity.gear_type
            else:
                # Create new block
                new_block = SignalChainBlock(
                    id=block_entity.id,
                    signal_chain_id=chain.id,
                    position=block_entity.position,
                    user_gear_id=block_entity.user_gear_id,
                    gear_type=block_entity.gear_type,
                )
                self.session.add(new_block)

    def _to_entity(self, chain: SignalChain) -> SignalChainEntity:
        """Convert ORM SignalChain to domain SignalChainEntity.

        Args:
            chain: The ORM SignalChain model

        Returns:
            The domain SignalChainEntity
        """
        # Convert blocks
        blocks = [
            BlockEntity(
                id=block.id,
                signal_chain_id=chain.id,
                position=block.position,
                user_gear_id=block.user_gear_id,
                gear_type=block.gear_type,
            )
            for block in sorted(chain.blocks, key=lambda b: b.position)
        ]

        return SignalChainEntity(
            id=chain.id,
            user_id=chain.user_id,
            name=chain.name,
            description=chain.description,
            platform=chain.platform,
            blocks=blocks,
            created_at=chain.created_at,
            updated_at=chain.updated_at,
        )
