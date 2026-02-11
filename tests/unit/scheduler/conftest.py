"""Fixtures for scheduler unit tests.

This conftest.py fixes the mock_redis fixture behavior and provides
environment variables needed for importing scheduler.main.
"""

import os
from unittest.mock import AsyncMock

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
