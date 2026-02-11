"""Integration tests for /api/v1/notifications endpoints."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from webapp.adapters.persistence.models.notification import UserNotification
from webapp.adapters.persistence.models.user import User

if TYPE_CHECKING:
    from fastapi import FastAPI
    from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
def app() -> FastAPI:
    """Create a FastAPI app with notifications router."""
    from fastapi import FastAPI

    from webapp.api.v1.notifications import router

    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create a test user."""
    user = User(
        id=uuid4(),
        username="testuser",
        email="test@example.com",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


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


@pytest.fixture
async def authenticated_client(
    app: FastAPI,
    db_session: AsyncSession,
    test_user: User,
) -> AsyncClient:
    """Create an authenticated HTTP client."""
    from webapp.api.v1.notifications import set_session_override, set_user_override

    set_session_override(db_session)
    set_user_override(test_user)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client

    # Cleanup
    set_session_override(None)
    set_user_override(None)


@pytest.mark.asyncio
@pytest.mark.integration
class TestGetNotifications:
    """Test GET /api/v1/notifications endpoint."""

    async def test_get_notifications_returns_all_notifications(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
    ) -> None:
        """Test GET /api/v1/notifications returns all notifications."""
        n1 = UserNotification(
            id=uuid4(),
            user_id=test_user.id,
            type="info",
            title="Notification 1",
            message="Message 1",
        )
        n2 = UserNotification(
            id=uuid4(),
            user_id=test_user.id,
            type="warning",
            title="Notification 2",
            message="Message 2",
            read_at=datetime.now(UTC),
        )
        db_session.add_all([n1, n2])
        await db_session.commit()

        response = await authenticated_client.get("/api/v1/notifications")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    async def test_get_notifications_orders_unread_first(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
    ) -> None:
        """Test GET /api/v1/notifications orders unread notifications first."""
        read = UserNotification(
            id=uuid4(),
            user_id=test_user.id,
            type="info",
            title="Read Notification",
            message="Read message",
            read_at=datetime.now(UTC),
        )
        unread = UserNotification(
            id=uuid4(),
            user_id=test_user.id,
            type="info",
            title="Unread Notification",
            message="Unread message",
        )
        db_session.add_all([read, unread])
        await db_session.commit()

        response = await authenticated_client.get("/api/v1/notifications")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["id"] == str(unread.id)
        assert data[1]["id"] == str(read.id)

    async def test_get_notifications_only_returns_users_notifications(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        other_user: User,
    ) -> None:
        """Test GET /api/v1/notifications only returns current user's notifications."""
        user_notification = UserNotification(
            id=uuid4(),
            user_id=test_user.id,
            type="info",
            title="User notification",
            message="For test user",
        )
        other_notification = UserNotification(
            id=uuid4(),
            user_id=other_user.id,
            type="info",
            title="Other notification",
            message="For other user",
        )
        db_session.add_all([user_notification, other_notification])
        await db_session.commit()

        response = await authenticated_client.get("/api/v1/notifications")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == str(user_notification.id)

    async def test_get_notifications_returns_empty_list_when_none(
        self,
        authenticated_client: AsyncClient,
    ) -> None:
        """Test GET /api/v1/notifications returns empty list when user has no notifications."""
        response = await authenticated_client.get("/api/v1/notifications")

        assert response.status_code == 200
        data = response.json()
        assert data == []

    async def test_get_notifications_requires_authentication(
        self,
        app: FastAPI,
    ) -> None:
        """Test GET /api/v1/notifications requires authentication."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/notifications")

        assert response.status_code == 401


@pytest.mark.asyncio
@pytest.mark.integration
class TestMarkNotificationRead:
    """Test PUT /api/v1/notifications/{id}/read endpoint."""

    async def test_mark_notification_read_succeeds(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
    ) -> None:
        """Test PUT /api/v1/notifications/{id}/read marks notification as read."""
        notification = UserNotification(
            id=uuid4(),
            user_id=test_user.id,
            type="info",
            title="Test",
            message="Test message",
        )
        db_session.add(notification)
        await db_session.commit()

        response = await authenticated_client.put(f"/api/v1/notifications/{notification.id}/read")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        # Verify it was marked as read
        await db_session.refresh(notification)
        assert notification.read_at is not None

    async def test_mark_notification_read_returns_404_for_nonexistent(
        self,
        authenticated_client: AsyncClient,
    ) -> None:
        """Test PUT /api/v1/notifications/{id}/read returns 404 for non-existent notification."""
        response = await authenticated_client.put(f"/api/v1/notifications/{uuid4()}/read")

        assert response.status_code == 404

    async def test_mark_notification_read_prevents_access_to_other_users_notifications(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        other_user: User,
    ) -> None:
        """Test PUT /api/v1/notifications/{id}/read prevents marking other user's notifications."""
        notification = UserNotification(
            id=uuid4(),
            user_id=other_user.id,
            type="info",
            title="Other user's notification",
            message="Test",
        )
        db_session.add(notification)
        await db_session.commit()

        response = await authenticated_client.put(f"/api/v1/notifications/{notification.id}/read")

        assert response.status_code == 404
        await db_session.refresh(notification)
        assert notification.read_at is None

    async def test_mark_notification_read_requires_authentication(
        self,
        app: FastAPI,
    ) -> None:
        """Test PUT /api/v1/notifications/{id}/read requires authentication."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.put(f"/api/v1/notifications/{uuid4()}/read")

        assert response.status_code == 401


@pytest.mark.asyncio
@pytest.mark.integration
class TestMarkAllNotificationsRead:
    """Test PUT /api/v1/notifications/read-all endpoint."""

    async def test_mark_all_notifications_read_succeeds(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
    ) -> None:
        """Test PUT /api/v1/notifications/read-all marks all notifications as read."""
        n1 = UserNotification(
            id=uuid4(),
            user_id=test_user.id,
            type="info",
            title="Notification 1",
            message="Test 1",
        )
        n2 = UserNotification(
            id=uuid4(),
            user_id=test_user.id,
            type="info",
            title="Notification 2",
            message="Test 2",
        )
        db_session.add_all([n1, n2])
        await db_session.commit()

        response = await authenticated_client.put("/api/v1/notifications/read-all")

        assert response.status_code == 200
        data = response.json()
        assert data["marked_count"] == 2

        # Verify both were marked as read
        await db_session.refresh(n1)
        await db_session.refresh(n2)
        assert n1.read_at is not None
        assert n2.read_at is not None

    async def test_mark_all_notifications_read_only_affects_current_user(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        other_user: User,
    ) -> None:
        """Test PUT /api/v1/notifications/read-all only marks current user's notifications."""
        user_notification = UserNotification(
            id=uuid4(),
            user_id=test_user.id,
            type="info",
            title="User notification",
            message="Test",
        )
        other_notification = UserNotification(
            id=uuid4(),
            user_id=other_user.id,
            type="info",
            title="Other notification",
            message="Test",
        )
        db_session.add_all([user_notification, other_notification])
        await db_session.commit()

        response = await authenticated_client.put("/api/v1/notifications/read-all")

        assert response.status_code == 200
        data = response.json()
        assert data["marked_count"] == 1

        # Verify only user's notification was marked
        await db_session.refresh(user_notification)
        await db_session.refresh(other_notification)
        assert user_notification.read_at is not None
        assert other_notification.read_at is None

    async def test_mark_all_notifications_read_returns_zero_when_none_unread(
        self,
        authenticated_client: AsyncClient,
    ) -> None:
        """Test PUT /api/v1/notifications/read-all returns 0 when no unread notifications."""
        response = await authenticated_client.put("/api/v1/notifications/read-all")

        assert response.status_code == 200
        data = response.json()
        assert data["marked_count"] == 0

    async def test_mark_all_notifications_read_requires_authentication(
        self,
        app: FastAPI,
    ) -> None:
        """Test PUT /api/v1/notifications/read-all requires authentication."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.put("/api/v1/notifications/read-all")

        assert response.status_code == 401
