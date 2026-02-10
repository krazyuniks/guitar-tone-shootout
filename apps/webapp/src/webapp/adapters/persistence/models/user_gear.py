"""UserGear ORM model for persistence layer.

Join table between User and Gear for user's personal gear library.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, UUIDMixin, UuidType

if TYPE_CHECKING:
    from .gear_model import GearModel
    from .user import User


class UserGear(UUIDMixin, TimestampMixin, Base):
    """UserGear model representing gear model in a user's library.

    Links a user to a specific gear model they've added to their collection.
    This allows users to have their own copy of public gear models
    with personalised settings.

    Attributes:
        id: Primary key (UUIDv7)
        user_id: Foreign key to users table
        gear_model_id: Foreign key to gear_models table
        nickname: User's custom name for this gear
        notes: User's notes about this gear
        is_favourite: Whether marked as favourite
        created_at: When added to library
        updated_at: When last updated
        user: Relationship to User model
        gear_model: Relationship to GearModel model
    """

    __tablename__ = "user_gear"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UuidType(),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    gear_model_id: Mapped[uuid.UUID] = mapped_column(
        UuidType(),
        ForeignKey("gear_models.id", ondelete="CASCADE"),
        nullable=False,
    )
    nickname: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_favourite: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Relationships
    user: Mapped[User] = relationship(
        "User",
        back_populates="user_gear",
        lazy="raise",
    )
    gear_model: Mapped[GearModel] = relationship(
        "GearModel",
        back_populates="user_gear",
        lazy="raise",
    )

    # Unique constraint: a user can't add the same gear model twice
    __table_args__ = (
        UniqueConstraint("user_id", "gear_model_id", name="uq_user_gear_user_gear_model"),
        Index("ix_user_gear_user_id", "user_id"),
        Index("ix_user_gear_gear_model_id", "gear_model_id"),
        Index("ix_user_gear_is_favourite", "is_favourite"),
    )
