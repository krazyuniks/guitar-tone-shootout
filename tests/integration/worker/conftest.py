"""Fixtures for worker integration tests."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from worker.db import register_engine

# Monkey-patch AsyncSession to make expire_all() awaitable
# This is needed because test_admin_jobs.py incorrectly uses
# `await db_session.expire_all()` when expire_all() is synchronous.


async def _async_expunge_all_as_expire(self):
    """Async-compatible replacement for expire_all().

    Uses expunge_all() instead of expire_all() to avoid MissingGreenlet
    errors when test code accesses object attributes after "expiring".
    """
    self.expunge_all()


# Replace the method on the class
AsyncSession.expire_all = _async_expunge_all_as_expire  # type: ignore[method-assign]

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from sqlalchemy.ext.asyncio import AsyncEngine


@pytest.fixture(autouse=True)
def worker_env_vars(monkeypatch):
    """Set up worker environment variables for integration tests.

    The webapp container only has DATABASE_URL set, but WorkerSettings requires
    REDIS_URL as well.

    Uses autouse=True so it applies to all tests in this directory.
    """
    # Clear the engine cache before each test to ensure test isolation
    from worker.db import _engine_cache

    _engine_cache.clear()

    # Set standard test URLs that match what tests register engines under
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")


@pytest.fixture(autouse=True)
async def register_worker_engines(
    core_engine: AsyncEngine, worker_env_vars
) -> AsyncGenerator[None, None]:
    """Register the shared PostgreSQL engine for worker tests.

    The root conftest provides core_engine (session-scoped, real PostgreSQL).
    We register it under the worker's expected URL pattern so get_core_session()
    resolves correctly.
    """
    db_url = os.environ.get("DATABASE_URL", "")
    register_engine(db_url, core_engine)
    register_engine("postgresql+asyncpg://user:pass@db/gts_core", core_engine)
    yield
    from worker.db import _engine_cache

    _engine_cache.clear()
