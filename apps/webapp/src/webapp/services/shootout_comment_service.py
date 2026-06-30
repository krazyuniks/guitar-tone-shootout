"""Service for shootout comment business logic."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from webapp.adapters.persistence.models.shootout import Shootout
from webapp.adapters.persistence.models.shootout_comment import ShootoutComment
from webapp.adapters.persistence.repositories.shootout_comment_repository import (
    ShootoutCommentRepository,
)


class ShootoutCommentService:
    """Service for managing shootout comments.

    Handles validation and coordination between repositories.
    Owns transaction boundaries.
    """

    def __init__(self, session: AsyncSession):
        """Initialize service with database session.

        Args:
            session: SQLAlchemy async session
        """
        self.session = session
        self.repository = ShootoutCommentRepository(session)

    async def create(
        self,
        shootout_id: UUID,
        user_id: UUID,
        content: str,
    ) -> ShootoutComment:
        """Create a new comment on a shootout.

        Args:
            shootout_id: ID of the shootout
            user_id: ID of the user creating the comment
            content: Comment text content

        Returns:
            Created comment with user relationship loaded

        Raises:
            ValueError: If content is empty/whitespace, exceeds 2000 chars,
                       or shootout doesn't exist
        """
        # Validate content
        content = content.strip()
        if not content:
            raise ValueError("Content cannot be empty")
        if len(content) > 2000:
            raise ValueError("Content cannot exceed 2000 characters")

        # Verify shootout exists
        stmt = select(Shootout).where(Shootout.id == shootout_id)
        result = await self.session.execute(stmt)
        shootout = result.scalar_one_or_none()
        if not shootout:
            raise ValueError("Shootout not found")

        comment = await self.repository.create(
            shootout_id=shootout_id,
            user_id=user_id,
            content=content,
        )

        return comment

    async def list_by_shootout(
        self,
        shootout_id: UUID,
        user_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ShootoutComment]:
        """List comments for a shootout owned by ``user_id``, newest first.

        Args:
            shootout_id: ID of the shootout
            user_id: The requesting user's UUID; must own the shootout
            limit: Maximum number of comments to return
            offset: Number of comments to skip

        Returns:
            List of comments with user relationship loaded

        Raises:
            ValueError: If shootout doesn't exist or is not owned by user_id
        """
        # Verify the shootout exists AND is owned by the requesting user
        # (ownership enforced at query level, not a caller-side filter).
        stmt = select(Shootout).where(
            Shootout.id == shootout_id,
            Shootout.user_id == user_id,
        )
        result = await self.session.execute(stmt)
        shootout = result.scalar_one_or_none()
        if not shootout:
            raise ValueError("Shootout not found")

        return await self.repository.list_by_shootout(
            shootout_id=shootout_id,
            user_id=user_id,
            limit=limit,
            offset=offset,
        )

    async def delete(self, comment_id: UUID, user_id: UUID) -> None:
        """Delete a comment.

        Only the comment author can delete their comment.

        Args:
            comment_id: ID of the comment to delete
            user_id: ID of the user attempting deletion — scopes the lookup

        Raises:
            ValueError: If comment not found or not owned by user
        """
        comment = await self.repository.get_by_id(comment_id, user_id)
        if not comment:
            raise ValueError("Comment not found")

        await self.repository.delete(comment_id)
