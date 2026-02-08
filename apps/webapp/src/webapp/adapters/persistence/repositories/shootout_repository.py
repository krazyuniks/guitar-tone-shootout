"""SQLAlchemy implementation of ShootoutRepository protocol."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import func, select
from sqlalchemy.orm import joinedload

from core.domain.entities.shootout import Shootout as ShootoutEntity
from core.domain.entities.shootout import ShootoutChain as ShootoutChainVO
from webapp.adapters.persistence.models.shootout import (
    Shootout,
    ShootoutChain,
    ShootoutStatus,
)

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession


class SQLAlchemyShootoutRepository:
    """SQLAlchemy implementation of ShootoutRepository protocol.

    Maps between domain Shootout entities and ORM Shootout models,
    handling chain relationships.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the repository with an async session.

        Args:
            session: SQLAlchemy async session
        """
        self.session = session

    async def get_by_id(self, shootout_id: UUID) -> ShootoutEntity | None:
        """Get a shootout by its ID.

        Args:
            shootout_id: The shootout's UUID

        Returns:
            The Shootout entity with all chains loaded, or None
        """
        stmt = (
            select(Shootout)
            .where(Shootout.id == shootout_id)
            .options(joinedload(Shootout.chains))
        )
        result = await self.session.execute(stmt)
        shootout = result.unique().scalar_one_or_none()

        if shootout is None:
            return None

        return self._to_entity(shootout)

    async def get_by_user_id(
        self,
        user_id: UUID,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ShootoutEntity]:
        """Get shootouts for a user.

        Args:
            user_id: The owner's UUID
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            List of Shootouts ordered by created_at desc
        """
        stmt = (
            select(Shootout)
            .where(Shootout.user_id == user_id)
            .options(joinedload(Shootout.chains))
            .order_by(Shootout.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        shootouts = result.unique().scalars().all()

        return [self._to_entity(shootout) for shootout in shootouts]

    async def count_by_user_id(self, user_id: UUID) -> int:
        """Count shootouts for a user.

        Args:
            user_id: The owner's UUID

        Returns:
            The count of shootouts
        """
        stmt = select(func.count()).select_from(Shootout).where(Shootout.user_id == user_id)
        result = await self.session.execute(stmt)
        count = result.scalar()
        return count or 0

    async def get_public(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ShootoutEntity]:
        """Get public (processed) shootouts.

        Args:
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            List of processed Shootouts ordered by created_at desc
        """
        stmt = (
            select(Shootout)
            .where(Shootout.status == ShootoutStatus.COMPLETED)
            .options(joinedload(Shootout.chains))
            .order_by(Shootout.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        shootouts = result.unique().scalars().all()

        return [self._to_entity(shootout) for shootout in shootouts]

    async def count_public(self) -> int:
        """Count public (processed) shootouts.

        Returns:
            The count of processed shootouts
        """
        stmt = (
            select(func.count())
            .select_from(Shootout)
            .where(Shootout.status == ShootoutStatus.COMPLETED)
        )
        result = await self.session.execute(stmt)
        count = result.scalar()
        return count or 0

    async def save(self, shootout: ShootoutEntity) -> None:
        """Save a shootout (create or update).

        This saves both the shootout and its chains.

        Args:
            shootout: The shootout to save
        """
        # Check if shootout exists
        stmt = (
            select(Shootout)
            .where(Shootout.id == shootout.id)
            .options(joinedload(Shootout.chains))
        )
        result = await self.session.execute(stmt)
        existing = result.unique().scalar_one_or_none()

        if existing is None:
            # Create new shootout
            status = ShootoutStatus.COMPLETED if shootout.is_processed else ShootoutStatus.PENDING
            orm_shootout = Shootout(
                id=shootout.id,
                user_id=shootout.user_id,
                di_track_id=shootout.di_track_id,
                name=shootout.name,
                description=shootout.description,
                status=status,
                video_path=shootout.output_path,
                created_at=shootout.created_at,
                updated_at=shootout.updated_at,
            )
            self.session.add(orm_shootout)
            await self.session.flush()

            # Add chains
            for chain in shootout.chains:
                orm_chain = ShootoutChain(
                    id=chain.id,
                    shootout_id=shootout.id,
                    signal_chain_id=chain.signal_chain_id,
                    position=chain.position,
                    label=chain.label,
                )
                self.session.add(orm_chain)
        else:
            # Update existing shootout
            # Refresh to ensure fresh state
            await self.session.refresh(existing, ["chains"])

            status = ShootoutStatus.COMPLETED if shootout.is_processed else ShootoutStatus.PENDING
            existing.name = shootout.name
            existing.di_track_id = shootout.di_track_id
            existing.description = shootout.description
            existing.status = status
            existing.video_path = shootout.output_path
            existing.updated_at = shootout.updated_at

            # Synchronize chains using relationship management
            # This leverages cascade="all, delete-orphan" on the relationship
            new_chain_ids = {chain.id for chain in shootout.chains}

            # Remove chains that are no longer in the entity by clearing the list
            # and rebuilding it - this triggers the cascade delete-orphan
            existing.chains = [
                orm_chain for orm_chain in existing.chains
                if orm_chain.id in new_chain_ids
            ]

            # Track which chains exist for update vs create
            existing_chain_map = {chain.id: chain for chain in existing.chains}

            # Add or update chains
            for chain in shootout.chains:
                if chain.id in existing_chain_map:
                    # Update existing chain
                    existing_chain = existing_chain_map[chain.id]
                    existing_chain.signal_chain_id = chain.signal_chain_id
                    existing_chain.position = chain.position
                    existing_chain.label = chain.label
                else:
                    # Add new chain
                    orm_chain = ShootoutChain(
                        id=chain.id,
                        shootout_id=shootout.id,
                        signal_chain_id=chain.signal_chain_id,
                        position=chain.position,
                        label=chain.label,
                    )
                    existing.chains.append(orm_chain)

        await self.session.flush()

    async def delete(self, shootout_id: UUID) -> None:
        """Delete a shootout by ID.

        This cascades delete chains via ORM relationship.

        Args:
            shootout_id: The shootout's UUID
        """
        stmt = select(Shootout).where(Shootout.id == shootout_id)
        result = await self.session.execute(stmt)
        shootout = result.scalar_one_or_none()

        if shootout is not None:
            await self.session.delete(shootout)
            await self.session.flush()

    def _to_entity(self, orm_shootout: Shootout) -> ShootoutEntity:
        """Convert ORM Shootout to domain entity.

        Args:
            orm_shootout: ORM Shootout model

        Returns:
            Domain Shootout entity
        """
        # Convert chains to value objects
        chains = [
            ShootoutChainVO(
                id=chain.id,
                shootout_id=orm_shootout.id,
                signal_chain_id=chain.signal_chain_id,
                position=chain.position,
                label=chain.label,
            )
            for chain in sorted(orm_shootout.chains, key=lambda c: c.position)
        ]

        return ShootoutEntity(
            id=orm_shootout.id,
            user_id=orm_shootout.user_id,
            name=orm_shootout.name,
            di_track_id=orm_shootout.di_track_id,
            description=orm_shootout.description,
            output_format="mp4",  # Default format
            sample_rate=44100,  # Default sample rate
            is_processed=orm_shootout.status == ShootoutStatus.COMPLETED,
            output_path=orm_shootout.video_path,
            processing_metadata=None,  # Not stored in ORM
            chains=chains,
            created_at=orm_shootout.created_at,
            updated_at=orm_shootout.updated_at,
        )
