"""Tag model for user-created labels."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, UUIDMixin, UuidType

if TYPE_CHECKING:
    from .user import User


class Tag(UUIDMixin, TimestampMixin, Base):
    """Tag model for user-created labels.

    Tags are labels that users can create to organize gear, chains, and shootouts.
    Tag names are unique per user (case-insensitive) and normalized to lowercase.

    Attributes:
        id: Primary key (UUIDv7)
        name: Tag name (normalized to lowercase)
        user_id: Foreign key to owning user
        user: Relationship to User
        created_at: When the tag was created
        updated_at: When the tag was last updated
    """

    __tablename__ = "user_tags"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    user_id: Mapped[UUID] = mapped_column(
        UuidType(),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Relationship to user
    user: Mapped[User] = relationship(
        "User",
        back_populates="tags",
        lazy="raise",
    )

    # Unique constraint: one user cannot have duplicate tag names
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_user_tags_user_id_name"),)
