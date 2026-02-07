"""UserGear ORM model for persistence layer.

Join table between User and Gear for user's personal gear library.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Index, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from .gear import Gear
    from .user import User


class UserGear(UUIDMixin, TimestampMixin, Base):
    """UserGear model representing gear in a user's library.

    Links a user to gear they've added to their collection.
    This allows users to have their own copy of public gear
    with personalised settings.

    Attributes:
        id: Primary key (UUIDv7)
        user_id: Foreign key to users table
        gear_id: Foreign key to gear table
        nickname: User's custom name for this gear
        notes: User's notes about this gear
        is_favourite: Whether marked as favourite
        created_at: When added to library
        updated_at: When last updated
        user: Relationship to User model
        gear: Relationship to Gear model
    """

    __tablename__ = "user_gear"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    gear_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("gear.id", ondelete="CASCADE"),
        nullable=False,
    )
    nickname: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_favourite: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Relationships
    user: Mapped[User] = relationship(
        "User",
        back_populates="user_gear",
        lazy="selectin",
    )
    gear: Mapped[Gear] = relationship(
        "Gear",
        back_populates="user_gear",
        lazy="selectin",
    )

    # Unique constraint: a user can't add the same gear twice
    __table_args__ = (
        UniqueConstraint("user_id", "gear_id", name="uq_user_gear_user_gear"),
        Index("ix_user_gear_user_id", "user_id"),
        Index("ix_user_gear_gear_id", "gear_id"),
        Index("ix_user_gear_is_favourite", "is_favourite"),
    )
