"""Fixtures for scheduler unit tests.

This conftest.py fixes the mock_redis fixture behavior and provides
environment variables needed for importing scheduler.main.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import event
from sqlalchemy.pool import Pool

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine


# Remove the base.py FK enabler and add our own FK disabler
# This allows tests to create Jobs with non-existent user_ids
@pytest.fixture(scope="session", autouse=True)
def _disable_fk_for_tests():
    """Disable foreign key constraints for SQLite in scheduler tests."""
    # Remove the base.py listener that enables FKs
    from webapp.adapters.persistence.models.base import _set_sqlite_pragma

    event.remove(Pool, "connect", _set_sqlite_pragma)

    # Add our own listener that disables FKs
    @event.listens_for(Pool, "connect")
    def _disable_sqlite_fk(dbapi_conn: Any, _connection_record: Any) -> None:
        """Disable foreign key constraints for SQLite test databases."""
        if hasattr(dbapi_conn, "execute"):
            try:
                cursor = dbapi_conn.cursor()
                cursor.execute("PRAGMA foreign_keys=OFF")
                cursor.close()
            except Exception:
                # Silently ignore errors (e.g., if not SQLite)
                pass

    yield

    # Restore the base.py listener after tests
    event.listen(Pool, "connect", _set_sqlite_pragma)


@pytest.fixture(scope="function", autouse=True)
def _scheduler_env(request):
    """Set REDIS_URL environment variable for scheduler tests.

    This allows importing scheduler.main without errors, since
    SchedulerSettings requires redis_url.

    For tests that explicitly check redis_url is required, we skip setting it.
    """
    test_name = request.node.name

    # Don't set REDIS_URL for tests that check it's required
    if "redis_url_field_is_required" in test_name:
        yield
        return

    original_value = os.environ.get("REDIS_URL")
    os.environ["REDIS_URL"] = "redis://redis:6379"
    yield
    # Restore original value
    if original_value is None:
        os.environ.pop("REDIS_URL", None)
    else:
        os.environ["REDIS_URL"] = original_value


@pytest.fixture(autouse=True)
def _fix_redis_mock(request):
    """Auto-fix mock_redis fixture to make methods async-compatible.

    The test file creates AsyncMock(spec=redis.Redis) which doesn't automatically
    make methods async. This fixture patches the mock after it's created to ensure
    redis methods (set, delete, expire) are AsyncMocks.
    """
    # Only apply if the test uses mock_redis fixture
    if "mock_redis" not in request.fixturenames:
        return

    # Get the mock_redis fixture value
    mock_redis = request.getfixturevalue("mock_redis")

    # Make Redis methods async-compatible
    mock_redis.set = AsyncMock()
    mock_redis.delete = AsyncMock()
    mock_redis.expire = AsyncMock()


@pytest.fixture(autouse=True)
def _register_test_engine(request):
    """Register db_engine in the scheduler.db engine cache for tests.

    This allows scheduled task functions to discover the test database engine
    without explicitly passing it as a parameter.
    """
    # Only apply if the test uses db_engine or session fixture
    if "db_engine" not in request.fixturenames and "session" not in request.fixturenames:
        yield  # Must yield even if not applicable
        return

    # Import here to avoid circular imports
    from scheduler.db import register_engine

    # Get the db_engine fixture value (always request it - pytest will resolve dependencies)
    try:
        db_engine: AsyncEngine = request.getfixturevalue("db_engine")
    except Exception:
        # If db_engine can't be retrieved, skip registration
        yield
        return

    # Register the engine with a test URL
    register_engine("test://memory", db_engine)

    # Also set the module-level test hooks
    from scheduler.schedules import jobs

    jobs._test_engine = db_engine

    # If the test uses a session fixture, share it so scheduled tasks
    # use the same connection (required for SQLite :memory: isolation)
    if "session" in request.fixturenames:
        try:
            session = request.getfixturevalue("session")
            jobs._test_session = session
        except Exception:
            pass

    yield

    # Clean up after test
    from scheduler.db import _engine_cache

    _engine_cache.clear()
    jobs._test_engine = None
    jobs._test_session = None
