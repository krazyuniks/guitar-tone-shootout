"""Integration tests for NotificationService."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from sqlalchemy import select

from webapp.adapters.persistence.models.notification import UserNotification
from webapp.adapters.persistence.models.user import User
from webapp.services.notification_service import NotificationService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
async def notification_service(db_session: AsyncSession) -> NotificationService:
    """Create a NotificationService instance."""
    return NotificationService(db_session)


@pytest.fixture
async def other_user(db_session: AsyncSession) -> User:
    """Create another test user for isolation tests."""
    user = User(
        id=uuid4(),
        username="otheruser",
        email="other@example.com",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.mark.asyncio
@pytest.mark.integration
class TestNotificationServiceCreate:
    """Test NotificationService.create method."""

    async def test_create_notification(
        self,
        notification_service: NotificationService,
        db_session: AsyncSession,
        test_user: User,
    ) -> None:
        """Test creating a notification via service."""
        notification = await notification_service.create(
            user_id=test_user.id,
            notification_type="info",
            title="Test Notification",
            message="This is a test",
        )

        assert notification.id is not None
        assert notification.user_id == test_user.id
        assert notification.type == "info"
        assert notification.title == "Test Notification"
        assert notification.message == "This is a test"
        assert notification.read_at is None
        assert isinstance(notification.created_at, datetime)

        # Verify it was persisted
        result = await db_session.execute(
            select(UserNotification).where(UserNotification.id == notification.id)
        )
        saved = result.scalar_one()
        assert saved.id == notification.id


@pytest.mark.asyncio
@pytest.mark.integration
class TestNotificationServiceGetUnread:
    """Test NotificationService.get_unread method."""

    async def test_get_unread_returns_only_unread_notifications(
        self,
        notification_service: NotificationService,
        db_session: AsyncSession,
        test_user: User,
    ) -> None:
        """Test get_unread returns only unread notifications."""
        # Create unread notification
        unread = UserNotification(
            id=uuid4(),
            user_id=test_user.id,
            type="info",
            title="Unread",
            message="Unread message",
        )
        db_session.add(unread)

        # Create read notification
        read = UserNotification(
            id=uuid4(),
            user_id=test_user.id,
            type="info",
            title="Read",
            message="Read message",
            read_at=datetime.now(UTC),
        )
        db_session.add(read)
        await db_session.commit()

        notifications = await notification_service.get_unread(test_user.id)

        assert len(notifications) == 1
        assert notifications[0].id == unread.id
        assert notifications[0].read_at is None

    async def test_get_unread_filters_by_user(
        self,
        notification_service: NotificationService,
        db_session: AsyncSession,
        test_user: User,
        other_user: User,
    ) -> None:
        """Test get_unread only returns notifications for the specified user."""
        # Create notification for test_user
        user_notification = UserNotification(
            id=uuid4(),
            user_id=test_user.id,
            type="info",
            title="For test user",
            message="Test",
        )
        db_session.add(user_notification)

        # Create notification for other_user
        other_notification = UserNotification(
            id=uuid4(),
            user_id=other_user.id,
            type="info",
            title="For other user",
            message="Test",
        )
        db_session.add(other_notification)
        await db_session.commit()

        notifications = await notification_service.get_unread(test_user.id)

        assert len(notifications) == 1
        assert notifications[0].id == user_notification.id

    async def test_get_unread_returns_empty_list_when_none(
        self,
        notification_service: NotificationService,
        test_user: User,
    ) -> None:
        """Test get_unread returns empty list when user has no unread notifications."""
        notifications = await notification_service.get_unread(test_user.id)
        assert notifications == []


@pytest.mark.asyncio
@pytest.mark.integration
class TestNotificationServiceGetAll:
    """Test NotificationService.get_all method."""

    async def test_get_all_returns_all_notifications(
        self,
        notification_service: NotificationService,
        db_session: AsyncSession,
        test_user: User,
    ) -> None:
        """Test get_all returns both read and unread notifications."""
        unread = UserNotification(
            id=uuid4(),
            user_id=test_user.id,
            type="info",
            title="Unread",
            message="Unread message",
        )
        db_session.add(unread)

        read = UserNotification(
            id=uuid4(),
            user_id=test_user.id,
            type="info",
            title="Read",
            message="Read message",
            read_at=datetime.now(UTC),
        )
        db_session.add(read)
        await db_session.commit()

        notifications = await notification_service.get_all(test_user.id)

        assert len(notifications) == 2
        notification_ids = {n.id for n in notifications}
        assert unread.id in notification_ids
        assert read.id in notification_ids

    async def test_get_all_orders_unread_first(
        self,
        notification_service: NotificationService,
        db_session: AsyncSession,
        test_user: User,
    ) -> None:
        """Test get_all orders unread notifications first."""
        read = UserNotification(
            id=uuid4(),
            user_id=test_user.id,
            type="info",
            title="Read",
            message="Read message",
            read_at=datetime.now(UTC),
        )
        db_session.add(read)

        unread = UserNotification(
            id=uuid4(),
            user_id=test_user.id,
            type="info",
            title="Unread",
            message="Unread message",
        )
        db_session.add(unread)
        await db_session.commit()

        notifications = await notification_service.get_all(test_user.id)

        assert len(notifications) == 2
        assert notifications[0].id == unread.id
        assert notifications[1].id == read.id

    async def test_get_all_filters_by_user(
        self,
        notification_service: NotificationService,
        db_session: AsyncSession,
        test_user: User,
        other_user: User,
    ) -> None:
        """Test get_all only returns notifications for the specified user."""
        user_notification = UserNotification(
            id=uuid4(),
            user_id=test_user.id,
            type="info",
            title="For test user",
            message="Test",
        )
        db_session.add(user_notification)

        other_notification = UserNotification(
            id=uuid4(),
            user_id=other_user.id,
            type="info",
            title="For other user",
            message="Test",
        )
        db_session.add(other_notification)
        await db_session.commit()

        notifications = await notification_service.get_all(test_user.id)

        assert len(notifications) == 1
        assert notifications[0].id == user_notification.id


@pytest.mark.asyncio
@pytest.mark.integration
class TestNotificationServiceMarkRead:
    """Test NotificationService.mark_read method."""

    async def test_mark_read_sets_read_at_timestamp(
        self,
        notification_service: NotificationService,
        db_session: AsyncSession,
        test_user: User,
    ) -> None:
        """Test mark_read sets read_at timestamp."""
        notification = UserNotification(
            id=uuid4(),
            user_id=test_user.id,
            type="info",
            title="Test",
            message="Test message",
        )
        db_session.add(notification)
        await db_session.commit()

        result = await notification_service.mark_read(notification.id, test_user.id)

        assert result is True
        await db_session.refresh(notification)
        assert notification.read_at is not None
        assert isinstance(notification.read_at, datetime)

    async def test_mark_read_returns_false_for_nonexistent_notification(
        self,
        notification_service: NotificationService,
        test_user: User,
    ) -> None:
        """Test mark_read returns False for non-existent notification."""
        result = await notification_service.mark_read(uuid4(), test_user.id)
        assert result is False

    async def test_mark_read_prevents_access_to_other_users_notifications(
        self,
        notification_service: NotificationService,
        db_session: AsyncSession,
        test_user: User,
        other_user: User,
    ) -> None:
        """Test mark_read prevents marking another user's notification as read."""
        notification = UserNotification(
            id=uuid4(),
            user_id=other_user.id,
            type="info",
            title="Other user's notification",
            message="Test",
        )
        db_session.add(notification)
        await db_session.commit()

        result = await notification_service.mark_read(notification.id, test_user.id)

        assert result is False
        await db_session.refresh(notification)
        assert notification.read_at is None


@pytest.mark.asyncio
@pytest.mark.integration
class TestNotificationServiceMarkAllRead:
    """Test NotificationService.mark_all_read method."""

    async def test_mark_all_read_marks_all_unread_notifications(
        self,
        notification_service: NotificationService,
        db_session: AsyncSession,
        test_user: User,
    ) -> None:
        """Test mark_all_read marks all unread notifications as read."""
        n1 = UserNotification(
            id=uuid4(),
            user_id=test_user.id,
            type="info",
            title="Notification 1",
            message="Test",
        )
        n2 = UserNotification(
            id=uuid4(),
            user_id=test_user.id,
            type="info",
            title="Notification 2",
            message="Test",
        )
        db_session.add_all([n1, n2])
        await db_session.commit()

        count = await notification_service.mark_all_read(test_user.id)

        assert count == 2
        await db_session.refresh(n1)
        await db_session.refresh(n2)
        assert n1.read_at is not None
        assert n2.read_at is not None

    async def test_mark_all_read_only_affects_users_notifications(
        self,
        notification_service: NotificationService,
        db_session: AsyncSession,
        test_user: User,
        other_user: User,
    ) -> None:
        """Test mark_all_read only marks notifications for the specified user."""
        user_notification = UserNotification(
            id=uuid4(),
            user_id=test_user.id,
            type="info",
            title="Test user",
            message="Test",
        )
        other_notification = UserNotification(
            id=uuid4(),
            user_id=other_user.id,
            type="info",
            title="Other user",
            message="Test",
        )
        db_session.add_all([user_notification, other_notification])
        await db_session.commit()

        count = await notification_service.mark_all_read(test_user.id)

        assert count == 1
        await db_session.refresh(user_notification)
        await db_session.refresh(other_notification)
        assert user_notification.read_at is not None
        assert other_notification.read_at is None

    async def test_mark_all_read_returns_zero_when_none_unread(
        self,
        notification_service: NotificationService,
        test_user: User,
    ) -> None:
        """Test mark_all_read returns 0 when there are no unread notifications."""
        count = await notification_service.mark_all_read(test_user.id)
        assert count == 0
