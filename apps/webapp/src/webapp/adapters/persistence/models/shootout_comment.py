"""ShootoutComment ORM model for persistence layer."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, UUIDMixin, UuidType

if TYPE_CHECKING:
    from .shootout import Shootout
    from .user import User


class ShootoutComment(UUIDMixin, TimestampMixin, Base):
    """ShootoutComment model for user comments on shootouts.

    Represents a user comment on a shootout for discussion.

    Attributes:
        id: Primary key (UUIDv7)
        shootout_id: Foreign key to shootouts table
        user_id: Foreign key to users table
        content: The comment text content
        created_at: When the comment was created
        updated_at: When the comment was last updated
        shootout: Reference to the Shootout
        user: Reference to the User
    """

    __tablename__ = "shootout_comments"

    shootout_id: Mapped[uuid.UUID] = mapped_column(
        UuidType(),
        ForeignKey("shootouts.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UuidType(),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Relationships
    shootout: Mapped[Shootout] = relationship(
        "Shootout",
        back_populates="comments",
        lazy="raise",
    )
    user: Mapped[User] = relationship(
        "User",
        lazy="raise",
    )

    # Indexes
    __table_args__ = (
        Index("ix_shootout_comments_shootout_id", "shootout_id"),
        Index("ix_shootout_comments_user_id", "user_id"),
    )
