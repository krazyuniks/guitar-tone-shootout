"""UserNotification ORM model."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from .user import User


class UserNotification(UUIDMixin, TimestampMixin, Base):
    """User notification model.

    Represents in-app notifications for users. Not email/push notifications.

    Attributes:
        id: Primary key (UUIDv7)
        user_id: Foreign key to users table
        type: Notification type (info, warning, error, success)
        title: Notification title
        message: Notification message content
        read_at: When the notification was marked as read (None = unread)
        created_at: When the notification was created (from TimestampMixin)
        updated_at: When the notification was last updated (from TimestampMixin)
        user: Relationship to User
    """

    __tablename__ = "core_user_notifications"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("core_users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
    )

    # Relationships
    user: Mapped[User] = relationship(
        "User",
        back_populates="notifications",
        lazy="raise",
    )
