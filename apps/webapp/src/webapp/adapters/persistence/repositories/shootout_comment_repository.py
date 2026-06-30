"""Repository for ShootoutComment persistence operations."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from webapp.adapters.persistence.models.shootout_comment import ShootoutComment


class ShootoutCommentRepository:
    """Repository for managing ShootoutComment persistence.

    Follows repository pattern with explicit eager loading for all queries.
    All relationships use lazy="raise" to prevent N+1 queries.
    """

    def __init__(self, session: AsyncSession):
        """Initialize repository with database session.

        Args:
            session: SQLAlchemy async session
        """
        self.session = session

    async def create(
        self,
        shootout_id: UUID,
        user_id: UUID,
        content: str,
    ) -> ShootoutComment:
        """Create a new comment.

        Args:
            shootout_id: ID of the shootout
            user_id: ID of the user creating the comment
            content: Comment text content

        Returns:
            Created comment with user relationship loaded
        """
        comment = ShootoutComment(
            shootout_id=shootout_id,
            user_id=user_id,
            content=content,
        )
        self.session.add(comment)
        await self.session.flush()

        # Reload with user relationship
        await self.session.refresh(comment, ["user"])

        return comment

    async def list_by_shootout(
        self,
        shootout_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ShootoutComment]:
        """List comments for a shootout, newest first.

        Args:
            shootout_id: ID of the shootout
            limit: Maximum number of comments to return
            offset: Number of comments to skip

        Returns:
            List of comments with user relationship loaded, ordered newest first
        """
        stmt = (
            select(ShootoutComment)
            .where(ShootoutComment.shootout_id == shootout_id)
            .options(joinedload(ShootoutComment.user))
            .order_by(ShootoutComment.created_at.desc())
            .limit(limit)
            .offset(offset)
        )

        result = await self.session.execute(stmt)
        return list(result.unique().scalars().all())

    async def get_by_id(self, comment_id: UUID, user_id: UUID) -> ShootoutComment | None:
        """Get a comment by ID, scoped to the owning user.

        Args:
            comment_id: ID of the comment
            user_id: The requesting user's UUID — included in the WHERE clause

        Returns:
            Comment if found and owned, None otherwise
        """
        stmt = select(ShootoutComment).where(
            ShootoutComment.id == comment_id, ShootoutComment.user_id == user_id
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def delete(self, comment_id: UUID) -> None:
        """Delete a comment.

        Args:
            comment_id: ID of the comment to delete
        """
        stmt = select(ShootoutComment).where(ShootoutComment.id == comment_id)
        result = await self.session.execute(stmt)
        comment = result.scalar_one_or_none()

        if comment:
            await self.session.delete(comment)
