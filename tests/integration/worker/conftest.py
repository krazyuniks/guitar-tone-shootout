"""Fixtures for worker integration tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from sqlalchemy.ext.asyncio import AsyncEngine

from sqlalchemy.ext.asyncio import AsyncSession

from webapp.adapters.persistence.models.base import Base
from worker.db import async_session_factory, register_engine

# Monkey-patch AsyncSession to make expire_all() awaitable
# This is needed because test_admin_jobs.py incorrectly uses
# `await db_session.expire_all()` when expire_all() is synchronous.
#
# The test pattern is problematic: it creates objects in one session,
# updates them via the endpoint (different session), then tries to verify
# with the original session. Using expunge_all() instead of expire_all()
# removes objects from the identity map so the next query fetches fresh
# data from the database, avoiding MissingGreenlet errors from accessing
# expired attributes.


async def _async_expunge_all_as_expire(self):
    """Async-compatible replacement for expire_all().

    Uses expunge_all() instead of expire_all() to avoid MissingGreenlet
    errors when test code accesses object attributes after "expiring".
    """
    # Expunge all objects from the session (detach them)
    # This means the next query will fetch fresh data from the database
    self.expunge_all()


# Replace the method on the class
AsyncSession.expire_all = _async_expunge_all_as_expire  # type: ignore[method-assign]


@pytest.fixture
async def db_engine() -> AsyncGenerator[AsyncEngine, None]:
    """Create a test database engine using worker's async_session_factory.

    This fixture uses the worker's session factory to ensure that sessions
    created via get_session() can access the same database and tables.
    """
    # Use shared memory SQLite database so multiple connections can access it
    database_url = "sqlite+aiosqlite:///file::memory:?cache=shared&uri=true"

    # Create session factory and get the engine
    factory = async_session_factory(database_url)
    engine = factory.kw["bind"]

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Register the engine so get_session() will use it
    register_engine("sqlite+aiosqlite:///:memory:", engine)

    yield engine

    await engine.dispose()
