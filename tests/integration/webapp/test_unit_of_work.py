"""Integration tests for UnitOfWork pattern."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from webapp.adapters.persistence.models.base import Base
from webapp.adapters.persistence.models.user import User
from webapp.adapters.persistence.unit_of_work import UnitOfWork

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator


@pytest.fixture
async def session_factory() -> AsyncGenerator[async_sessionmaker[AsyncSession], None]:
    """Create a test session factory with in-memory SQLite database."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    yield session_factory

    # Cleanup
    await engine.dispose()


@pytest.mark.asyncio
async def test_uow_context_manager(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Test UnitOfWork works as async context manager."""
    async with UnitOfWork(session_factory) as uow:
        assert uow.session is not None
        assert isinstance(uow.session, AsyncSession)


@pytest.mark.asyncio
async def test_uow_commit(session_factory: async_sessionmaker[AsyncSession]) -> None:
    """Test UnitOfWork commit persists changes."""
    user_id = uuid.uuid4()

    # Create user within UnitOfWork
    async with UnitOfWork(session_factory) as uow:
        user = User(
            id=user_id,
            username="testuser",
            email="test@example.com",
        )
        uow.session.add(user)
        await uow.commit()

    # Verify user persisted in new session
    async with UnitOfWork(session_factory) as uow:
        stmt = select(User).where(User.id == user_id)
        result = await uow.session.execute(stmt)
        user = result.scalar_one_or_none()

        assert user is not None
        assert user.username == "testuser"
        assert user.email == "test@example.com"


@pytest.mark.asyncio
async def test_uow_rollback_on_exception(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Test UnitOfWork rolls back on exception."""
    user_id = uuid.uuid4()

    # Create user then raise exception
    try:
        async with UnitOfWork(session_factory) as uow:
            user = User(
                id=user_id,
                username="testuser",
                email="test@example.com",
            )
            uow.session.add(user)
            raise ValueError("Test exception")
    except ValueError:
        pass

    # Verify user was not persisted
    async with UnitOfWork(session_factory) as uow:
        stmt = select(User).where(User.id == user_id)
        result = await uow.session.execute(stmt)
        user = result.scalar_one_or_none()

        assert user is None


@pytest.mark.asyncio
async def test_uow_explicit_rollback(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Test explicit rollback() discards changes."""
    user_id = uuid.uuid4()

    async with UnitOfWork(session_factory) as uow:
        user = User(
            id=user_id,
            username="testuser",
            email="test@example.com",
        )
        uow.session.add(user)
        await uow.rollback()

    # Verify user was not persisted
    async with UnitOfWork(session_factory) as uow:
        stmt = select(User).where(User.id == user_id)
        result = await uow.session.execute(stmt)
        user = result.scalar_one_or_none()

        assert user is None


@pytest.mark.asyncio
async def test_uow_default_rollback_without_commit(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Test UnitOfWork rolls back if commit() not called."""
    user_id = uuid.uuid4()

    # Create user but don't commit
    async with UnitOfWork(session_factory) as uow:
        user = User(
            id=user_id,
            username="testuser",
            email="test@example.com",
        )
        uow.session.add(user)
        # No commit() - should rollback on exit

    # Verify user was not persisted
    async with UnitOfWork(session_factory) as uow:
        stmt = select(User).where(User.id == user_id)
        result = await uow.session.execute(stmt)
        user = result.scalar_one_or_none()

        assert user is None


@pytest.mark.asyncio
async def test_uow_session_property_outside_context() -> None:
    """Test accessing session outside context manager raises error."""
    session_factory = async_sessionmaker(
        create_async_engine("sqlite+aiosqlite:///:memory:"),
        class_=AsyncSession,
    )
    uow = UnitOfWork(session_factory)

    with pytest.raises(RuntimeError, match="must be used as a context manager"):
        _ = uow.session


@pytest.mark.asyncio
async def test_uow_commit_outside_context() -> None:
    """Test commit() outside context manager raises error."""
    session_factory = async_sessionmaker(
        create_async_engine("sqlite+aiosqlite:///:memory:"),
        class_=AsyncSession,
    )
    uow = UnitOfWork(session_factory)

    with pytest.raises(RuntimeError, match="Cannot commit outside"):
        await uow.commit()


@pytest.mark.asyncio
async def test_uow_rollback_outside_context() -> None:
    """Test rollback() outside context manager raises error."""
    session_factory = async_sessionmaker(
        create_async_engine("sqlite+aiosqlite:///:memory:"),
        class_=AsyncSession,
    )
    uow = UnitOfWork(session_factory)

    with pytest.raises(RuntimeError, match="Cannot rollback outside"):
        await uow.rollback()


@pytest.mark.asyncio
async def test_uow_multiple_operations(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Test multiple operations within single UnitOfWork."""
    user1_id = uuid.uuid4()
    user2_id = uuid.uuid4()

    async with UnitOfWork(session_factory) as uow:
        # Create first user
        user1 = User(
            id=user1_id,
            username="user1",
            email="user1@example.com",
        )
        uow.session.add(user1)

        # Create second user
        user2 = User(
            id=user2_id,
            username="user2",
            email="user2@example.com",
        )
        uow.session.add(user2)

        await uow.commit()

    # Verify both users persisted
    async with UnitOfWork(session_factory) as uow:
        stmt = select(User).where(User.id.in_([user1_id, user2_id]))
        result = await uow.session.execute(stmt)
        users = result.scalars().all()

        assert len(users) == 2
        usernames = {u.username for u in users}
        assert usernames == {"user1", "user2"}


@pytest.mark.asyncio
async def test_uow_transaction_scoping(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Test transaction scope is properly managed."""
    user_id = uuid.uuid4()

    async with UnitOfWork(session_factory) as uow:
        # Transaction should be active
        assert uow.session.in_transaction()

        user = User(
            id=user_id,
            username="testuser",
            email="test@example.com",
        )
        uow.session.add(user)
        await uow.commit()

        # After commit, transaction should not be active
        assert not uow.session.in_transaction()
