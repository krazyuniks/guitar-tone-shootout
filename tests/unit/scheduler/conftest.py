"""Fixtures for scheduler unit tests.

Provides environment variables needed for importing scheduler.main
and registers test database engines for scheduled tasks.
"""

from __future__ import annotations

import os

import pytest


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
def _register_test_engine(request):
    """Register core_engine in the scheduler.db engine cache for tests.

    This allows scheduled task functions to discover the test database engine
    without explicitly passing it as a parameter.
    """
    # Only apply if the test uses core_engine or session fixture
    if "core_engine" not in request.fixturenames and "session" not in request.fixturenames:
        yield
        return

    from scheduler.db import register_engine

    try:
        db_engine = request.getfixturevalue("core_engine")
    except Exception:
        yield
        return

    register_engine(os.environ.get("DATABASE_URL", "test://memory"), db_engine)

    from scheduler.schedules import jobs

    jobs._test_engine = db_engine

    if "session" in request.fixturenames:
        try:
            session = request.getfixturevalue("session")
            jobs._test_session = session
        except Exception:
            pass

    yield

    from scheduler.db import _engine_cache

    _engine_cache.clear()
    jobs._test_engine = None
    jobs._test_session = None
