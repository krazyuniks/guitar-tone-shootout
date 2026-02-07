"""ShootoutService for managing shootouts with CRUD and lifecycle operations."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from webapp.adapters.persistence.repositories.shootout_repository import (
    SQLAlchemyShootoutRepository,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from core.domain.entities.shootout import Shootout


class ShootoutService:
    """Service for managing shootouts.

    Handles CRUD operations and lifecycle management for shootouts.
    Transaction management is the caller's responsibility.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize service with database session.

        Args:
            session: SQLAlchemy async session
        """
        self.session = session
        self.repository = SQLAlchemyShootoutRepository(session)

    async def create(self, shootout: Shootout) -> Shootout:
        """Create a new shootout.

        Args:
            shootout: Shootout entity to create

        Returns:
            The created Shootout entity
        """
        await self.repository.save(shootout)
        await self.session.flush()
        return shootout

    async def get_by_id(self, shootout_id: UUID) -> Shootout | None:
        """Get a shootout by ID.

        Args:
            shootout_id: Shootout ID to retrieve

        Returns:
            Shootout entity if found, None otherwise
        """
        return await self.repository.get_by_id(shootout_id)

    async def get_by_user_id(
        self,
        user_id: UUID,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Shootout]:
        """Get all shootouts for a user.

        Args:
            user_id: User ID to filter by
            limit: Maximum number of shootouts to return
            offset: Number of shootouts to skip

        Returns:
            List of Shootout entities
        """
        return await self.repository.get_by_user_id(
            user_id,
            limit=limit,
            offset=offset,
        )

    async def update(self, shootout: Shootout) -> Shootout:
        """Update an existing shootout.

        Args:
            shootout: Shootout entity to update

        Returns:
            The updated Shootout entity
        """
        await self.repository.save(shootout)
        await self.session.flush()
        return shootout

    async def delete(self, shootout_id: UUID) -> None:
        """Delete a shootout.

        Args:
            shootout_id: ID of shootout to delete
        """
        await self.repository.delete(shootout_id)
        await self.session.flush()
