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


@pytest.fixture(autouse=True)
def worker_env_vars(monkeypatch):
    """Set up worker environment variables for integration tests.

    The webapp container only has DATABASE_URL set, but WorkerSettings requires
    REDIS_URL and T3K_DATABASE_URL as well. This fixture ensures all required
    environment variables are available for tests that instantiate WorkerSettings.

    Sets URLs to match the test patterns so that engine registration works correctly.

    Uses autouse=True so it applies to all tests in this directory without
    needing explicit fixture declarations.
    """
    # Clear the engine cache before each test to ensure test isolation
    from worker.db import _engine_cache

    _engine_cache.clear()

    # Set standard test URLs that match what tests register engines under
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:pass@db/gts_core")
    monkeypatch.setenv("T3K_DATABASE_URL", "postgresql+asyncpg://user:pass@db/gts_t3k_source")


@pytest.fixture(autouse=True)
async def db_engine(worker_env_vars) -> AsyncGenerator[AsyncEngine, None]:
    """Create a test database engine using worker's async_session_factory.

    This fixture uses the worker's session factory to ensure that sessions
    created via get_session() can access the same database and tables.

    Registers the engine under multiple keys to handle different URL patterns:
    - Original :memory: format
    - Shared cache format (what async_session_factory converts to)
    - PostgreSQL URLs from worker_env_vars (for get_core_session/get_t3k_session)

    This fixture is autouse=True to ensure that the test database is always
    available, even for tests that don't explicitly depend on it. This is
    necessary because endpoints in admin.py always require database access
    via Depends(get_db_session), and the engine must be registered before
    any request can be processed.
    """
    # Use shared memory SQLite database so multiple connections can access it
    database_url = "sqlite+aiosqlite:///file::memory:?cache=shared&uri=true"

    # Create session factory and get the engine
    factory = async_session_factory(database_url)
    engine = factory.kw["bind"]

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Register the engine under all possible URL patterns
    # 1. Original :memory: format
    register_engine("sqlite+aiosqlite:///:memory:", engine)

    # 2. Shared cache format (what async_session_factory converts to)
    register_engine(database_url, engine)

    # 3. PostgreSQL URLs from worker_env_vars (so get_core_session/get_t3k_session work)
    register_engine("postgresql+asyncpg://user:pass@db/gts_core", engine)
    register_engine("postgresql+asyncpg://user:pass@db/gts_t3k_source", engine)

    yield engine

    await engine.dispose()
