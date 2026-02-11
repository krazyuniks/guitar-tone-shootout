"""NotificationService for managing user notifications."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import select, update

from webapp.adapters.persistence.models.notification import UserNotification

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class NotificationService:
    """Service for managing user notifications.

    Handles creating, retrieving, and marking notifications as read.
    Transaction management is the caller's responsibility.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        user_id: UUID,
        notification_type: str,
        title: str,
        message: str,
    ) -> UserNotification:
        """Create a new notification for a user.

        Args:
            user_id: User to notify
            notification_type: Type of notification (info, warning, error, success)
            title: Notification title
            message: Notification message content

        Returns:
            Created notification
        """
        notification = UserNotification(
            id=uuid4(),
            user_id=user_id,
            type=notification_type,
            title=title,
            message=message,
        )
        self.session.add(notification)
        await self.session.flush()
        await self.session.refresh(notification)
        return notification

    async def get_unread(self, user_id: UUID) -> list[UserNotification]:
        """Get all unread notifications for a user.

        Args:
            user_id: User ID to get notifications for

        Returns:
            List of unread notifications
        """
        stmt = (
            select(UserNotification)
            .where(
                UserNotification.user_id == user_id,
                UserNotification.read_at.is_(None),
            )
            .order_by(UserNotification.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_all(self, user_id: UUID) -> list[UserNotification]:
        """Get all notifications for a user (unread first, then read).

        Args:
            user_id: User ID to get notifications for

        Returns:
            List of all notifications, ordered with unread first
        """
        stmt = (
            select(UserNotification)
            .where(UserNotification.user_id == user_id)
            .order_by(
                # Unread first (NULL values first in PostgreSQL)
                UserNotification.read_at.nulls_first(),
                UserNotification.created_at.desc(),
            )
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def mark_read(self, notification_id: UUID, user_id: UUID) -> bool:
        """Mark a notification as read.

        Args:
            notification_id: Notification ID to mark as read
            user_id: User ID (for ownership check)

        Returns:
            True if notification was marked as read, False if not found or not owned by user
        """
        stmt = (
            update(UserNotification)
            .where(
                UserNotification.id == notification_id,
                UserNotification.user_id == user_id,
            )
            .values(read_at=datetime.now(UTC))
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount > 0

    async def mark_all_read(self, user_id: UUID) -> int:
        """Mark all unread notifications as read for a user.

        Args:
            user_id: User ID to mark notifications for

        Returns:
            Number of notifications marked as read
        """
        stmt = (
            update(UserNotification)
            .where(
                UserNotification.user_id == user_id,
                UserNotification.read_at.is_(None),
            )
            .values(read_at=datetime.now(UTC))
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount
