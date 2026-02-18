"""Unit tests for UserNotification ORM model."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from webapp.adapters.persistence.models.base import Base
from webapp.adapters.persistence.models.notification import UserNotification
from webapp.adapters.persistence.models.user import User

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator


@pytest.fixture
async def db_engine() -> AsyncGenerator[AsyncEngine, None]:
    """Create a test database engine."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def session(db_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session."""
    async_session = async_sessionmaker(db_engine, expire_on_commit=False)
    async with async_session() as session:
        yield session


@pytest.fixture
async def test_user(session: AsyncSession) -> User:
    """Create a test user."""
    user = User(
        id=uuid4(),
        username="testuser",
        email="test@example.com",
        is_active=True,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


class TestUserNotificationModel:
    """Test UserNotification ORM model."""

    async def test_create_notification(self, session: AsyncSession, test_user: User) -> None:
        """Test creating a UserNotification."""
        notification = UserNotification(
            id=uuid4(),
            user_id=test_user.id,
            type="info",
            title="Test Notification",
            message="This is a test notification",
        )
        session.add(notification)
        await session.commit()

        result = await session.execute(
            select(UserNotification).where(UserNotification.id == notification.id)
        )
        saved = result.scalar_one()

        assert saved.id == notification.id
        assert saved.user_id == test_user.id
        assert saved.type == "info"
        assert saved.title == "Test Notification"
        assert saved.message == "This is a test notification"
        assert saved.read_at is None
        assert isinstance(saved.created_at, datetime)

    async def test_notification_requires_user_id(self, session: AsyncSession) -> None:
        """Test that UserNotification requires a user_id."""
        notification = UserNotification(
            id=uuid4(),
            user_id=uuid4(),  # Non-existent user
            type="info",
            title="Test",
            message="Test message",
        )
        session.add(notification)

        # SQLite doesn't enforce foreign keys by default in-memory
        # This test will fail with IntegrityError in PostgreSQL
        with pytest.raises((IntegrityError, OperationalError)):
            await session.commit()

    async def test_notification_requires_type(self, session: AsyncSession, test_user: User) -> None:
        """Test that UserNotification requires a type."""
        notification = UserNotification(
            id=uuid4(),
            user_id=test_user.id,
            type=None,  # type: ignore[arg-type]
            title="Test",
            message="Test message",
        )
        session.add(notification)

        with pytest.raises((IntegrityError, OperationalError)):
            await session.commit()

    async def test_notification_requires_title(
        self, session: AsyncSession, test_user: User
    ) -> None:
        """Test that UserNotification requires a title."""
        notification = UserNotification(
            id=uuid4(),
            user_id=test_user.id,
            type="info",
            title=None,  # type: ignore[arg-type]
            message="Test message",
        )
        session.add(notification)

        with pytest.raises((IntegrityError, OperationalError)):
            await session.commit()

    async def test_notification_requires_message(
        self, session: AsyncSession, test_user: User
    ) -> None:
        """Test that UserNotification requires a message."""
        notification = UserNotification(
            id=uuid4(),
            user_id=test_user.id,
            type="info",
            title="Test",
            message=None,  # type: ignore[arg-type]
        )
        session.add(notification)

        with pytest.raises((IntegrityError, OperationalError)):
            await session.commit()

    async def test_mark_notification_as_read(self, session: AsyncSession, test_user: User) -> None:
        """Test marking a notification as read."""
        notification = UserNotification(
            id=uuid4(),
            user_id=test_user.id,
            type="info",
            title="Test",
            message="Test message",
        )
        session.add(notification)
        await session.commit()

        # Mark as read
        now = datetime.now(UTC)
        notification.read_at = now
        await session.commit()

        result = await session.execute(
            select(UserNotification).where(UserNotification.id == notification.id)
        )
        saved = result.scalar_one()

        assert saved.read_at is not None
        assert saved.read_at == now

    async def test_notification_created_at_auto_set(
        self, session: AsyncSession, test_user: User
    ) -> None:
        """Test that created_at is automatically set."""
        notification = UserNotification(
            id=uuid4(),
            user_id=test_user.id,
            type="info",
            title="Test",
            message="Test message",
        )
        session.add(notification)
        await session.commit()
        await session.refresh(notification)

        assert notification.created_at is not None
        assert isinstance(notification.created_at, datetime)
