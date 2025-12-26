"""Tests for TaskIQ background tasks."""

import os

import pytest

# Set testing environment before imports
os.environ["TESTING"] = "1"

from app.tasks import broker, health_check  # noqa: E402


@pytest.fixture
async def setup_broker():
    """Set up and tear down the in-memory test broker."""
    await broker.startup()
    yield
    await broker.shutdown()


async def test_health_check_task(setup_broker):
    """Test that the health check task runs and returns expected data."""
    # Kick the task and get the result
    result = await health_check.kiq()
    task_result = await result.wait_result(timeout=5.0)

    assert task_result.is_err is False
    data = task_result.return_value
    assert data["status"] == "healthy"
    assert data["worker"] is True
    assert "timestamp" in data
