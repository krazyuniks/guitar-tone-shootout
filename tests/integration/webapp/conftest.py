"""Shared pytest fixtures for webapp integration tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


class _TestAsyncSession(AsyncSession):
    """Test session that falls back to begin_nested() when already in a transaction.

    Fixtures call flush() which triggers autobegin. Tests then call begin()
    expecting nested transaction (SAVEPOINT) semantics. SQLAlchemy 2.0's begin()
    raises on double-begin, so we intercept and use begin_nested() instead.
    """

    def begin(self, **kw):  # type: ignore[override]
        if self.in_transaction():
            return self.begin_nested(**kw)
        return super().begin(**kw)

from uuid import uuid4

from webapp.adapters.persistence.models.base import Base
from webapp.adapters.persistence.models.user import User


@pytest.fixture
async def db_engine() -> AsyncGenerator[AsyncEngine, None]:
    """Create a test database engine."""
    # Use in-memory SQLite for fast tests
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Clean up
    await engine.dispose()


@pytest.fixture
async def db_session(db_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session with transaction management.

    The session auto-begins a transaction on first use. Tests can:
    - Use `async with db_session.begin():` for nested transactions (SAVEPOINT)
    - Use `await db_session.commit()` to commit changes

    All changes are rolled back after each test for isolation.
    """
    # Create session factory with custom session class
    async_session = async_sessionmaker(
        db_engine, class_=_TestAsyncSession, expire_on_commit=False,
    )

    # Create session
    session = async_session()

    try:
        yield session
    finally:
        # Rollback any active transaction and close session
        if session.in_transaction():
            await session.rollback()
        await session.close()


def pytest_runtest_call(item: pytest.Item) -> None:
    """Hook that runs during test execution to wire test_user as current user."""
    from webapp.auth.dependencies import set_user_override

    # Check if test_user fixture was used
    if hasattr(item, "funcargs") and "test_user" in item.funcargs:
        test_user = item.funcargs["test_user"]
        set_user_override(test_user)
        print(f"[HOOK] Setting current user: {test_user.username}")


@pytest.fixture(autouse=True)
async def _wire_auth_session(db_session: AsyncSession) -> AsyncGenerator[None, None]:
    """Auto-wire test DB session into the centralised auth dependencies.

    All route modules (auth, pages, html, library) now import from
    webapp.auth.dependencies, so we only need to set the override once.
    """
    from webapp.auth.dependencies import set_session_override, set_user_override

    print(f"[FIXTURE] Setting session override: {db_session}")
    set_session_override(db_session)
    yield
    set_session_override(None)
    set_user_override(None)
