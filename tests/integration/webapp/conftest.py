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
    """Create a test database session."""
    # Create session factory
    async_session = async_sessionmaker(db_engine, expire_on_commit=False)

    async with async_session() as session:
        yield session


def pytest_runtest_call(item: pytest.Item) -> None:
    """Hook that runs during test execution to wire test_user as current user.

    This hook examines the test's fixtures after they're all resolved
    and wires test_user as the current authenticated user for library endpoints.
    """
    from webapp.api import pages
    from webapp.api.v1.library import set_user_override

    # Check if test_user fixture was used
    if hasattr(item, "funcargs") and "test_user" in item.funcargs:
        test_user = item.funcargs["test_user"]
        set_user_override(test_user)
        pages.set_user_override(test_user)
        print(f"[HOOK] Setting current user: {test_user.username}")


@pytest.fixture(autouse=True)
async def _wire_auth_session(db_session: AsyncSession) -> AsyncGenerator[None, None]:
    """Auto-wire test DB session into auth, pages, and library modules.

    The auth, pages, and library endpoints use a module-level session override so tests that
    create their own FastAPI() app (without dependency_overrides) still
    get the test session.
    """
    from webapp.api import pages
    from webapp.api.v1.auth import set_session_override as set_auth_session_override
    from webapp.api.v1.library import (
        set_session_override as set_library_session_override,
    )

    print(f"[FIXTURE] Setting session override: {db_session}")
    set_auth_session_override(db_session)
    pages.set_session_override(db_session)
    set_library_session_override(db_session)
    print(f"[FIXTURE] pages._session_override is now: {pages._session_override}")
    yield
    set_auth_session_override(None)
    pages.set_session_override(None)
    set_library_session_override(None)


