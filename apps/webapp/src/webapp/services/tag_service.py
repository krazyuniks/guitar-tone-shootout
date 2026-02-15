"""Tag service for managing user-created labels."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from webapp.adapters.persistence.models.tag import Tag
from webapp.exceptions import ConflictError, NotFoundError

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession


class TagService:
    """Service for managing user tags.

    Tags are user-created labels for organizing gear, chains, and shootouts.
    Tag names are unique per user and normalized to lowercase.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the service with a database session.

        Args:
            session: SQLAlchemy async session
        """
        self.session = session

    async def create(self, *, user_id: UUID, name: str) -> Tag:
        """Create a new tag for a user.

        Tag names are normalized to lowercase and stripped of whitespace.
        Duplicate tag names for the same user raise ConflictError.

        Args:
            user_id: Owner's user ID
            name: Tag name (will be normalized to lowercase)

        Returns:
            Created Tag instance

        Raises:
            ConflictError: If a tag with the same name already exists for this user
        """
        # Normalize name: strip whitespace and convert to lowercase
        normalized_name = name.strip().lower()

        # Create tag
        tag = Tag(
            name=normalized_name,
            user_id=user_id,
        )
        self.session.add(tag)

        try:
            await self.session.flush()
        except IntegrityError as e:
            # Unique constraint violation: duplicate tag name for this user
            raise ConflictError(
                message=f"Tag '{normalized_name}' already exists",
                details={"user_id": str(user_id), "name": normalized_name},
            ) from e

        await self.session.refresh(tag)
        return tag

    async def get_by_user(self, *, user_id: UUID) -> list[Tag]:
        """Get all tags for a specific user.

        Args:
            user_id: User ID to filter by

        Returns:
            List of Tag instances owned by the user (may be empty)
        """
        stmt = select(Tag).where(Tag.user_id == user_id).order_by(Tag.name)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def delete(self, *, tag_id: UUID, user_id: UUID) -> None:
        """Delete a tag owned by a specific user.

        Ownership check is enforced: returns NotFoundError if tag doesn't exist
        or belongs to a different user (avoids leaking existence).

        Args:
            tag_id: Tag ID to delete
            user_id: Owner's user ID (for ownership check)

        Raises:
            NotFoundError: If tag not found or not owned by the user
        """
        # Delete only if both ID matches AND user_id matches
        stmt = delete(Tag).where(Tag.id == tag_id, Tag.user_id == user_id)
        result = await self.session.execute(stmt)

        if result.rowcount == 0:
            raise NotFoundError(
                message="Tag not found",
                details={"tag_id": str(tag_id)},
            )
