"""Unit tests for worker progress publisher.

Tests that publish_progress sends job progress updates to Redis pub/sub
channels for WebSocket forwarding to clients.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from uuid import uuid4

if TYPE_CHECKING:
    import pytest


class FakeRedis:
    """Test double for redis.asyncio client that records calls."""

    def __init__(self) -> None:
        self.publish_calls: list[tuple[str, str]] = []
        self.closed = False
        self.wait_closed_called = False

    async def publish(self, channel: str, message: str) -> None:
        self.publish_calls.append((channel, message))

    async def close(self) -> None:
        self.closed = True

    async def wait_closed(self) -> None:
        self.wait_closed_called = True


class FakeRedisFactory:
    """Tracks from_url calls and returns a FakeRedis instance."""

    def __init__(self, *, redis: FakeRedis | None = None, error: Exception | None = None) -> None:
        self.redis = redis or FakeRedis()
        self.error = error
        self.calls: list[str] = []

    def from_url(self, url: str) -> FakeRedis:
        self.calls.append(url)
        if self.error:
            raise self.error
        return self.redis


class TestPublishProgress:
    """Test progress publisher sends messages to Redis channels."""

    async def test_function_exists_and_is_async(self) -> None:
        """publish_progress function exists and is async callable."""
        from inspect import iscoroutinefunction

        from worker.progress import publish_progress

        assert callable(publish_progress)
        assert iscoroutinefunction(publish_progress)

    async def test_publishes_to_correct_redis_channel(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Publishes to job_progress:{job_id} channel."""
        from worker.progress import publish_progress

        job_id = uuid4()
        factory = FakeRedisFactory()
        monkeypatch.setattr("worker.progress.aioredis.from_url", factory.from_url)

        await publish_progress(
            redis_url="redis://localhost:6379",
            job_id=job_id,
            progress=50,
            status="running",
            message="Processing chain 2/5",
        )

        assert factory.calls == ["redis://localhost:6379"]
        assert len(factory.redis.publish_calls) == 1
        channel, _message = factory.redis.publish_calls[0]
        assert channel == f"job_progress:{job_id}"

    async def test_message_format_is_json(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Message is JSON with progress, status, and message fields."""
        from worker.progress import publish_progress

        factory = FakeRedisFactory()
        monkeypatch.setattr("worker.progress.aioredis.from_url", factory.from_url)

        await publish_progress(
            redis_url="redis://localhost:6379",
            job_id=uuid4(),
            progress=75,
            status="running",
            message="Rendering video",
        )

        _channel, raw_message = factory.redis.publish_calls[0]
        data = json.loads(raw_message)

        assert data["progress"] == 75
        assert data["status"] == "running"
        assert data["message"] == "Rendering video"

    async def test_progress_value_is_clamped_to_zero_minimum(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Progress values below 0 are clamped to 0."""
        from worker.progress import publish_progress

        factory = FakeRedisFactory()
        monkeypatch.setattr("worker.progress.aioredis.from_url", factory.from_url)

        await publish_progress(
            redis_url="redis://localhost:6379",
            job_id=uuid4(),
            progress=-10,
            status="running",
            message="Starting",
        )

        _channel, raw_message = factory.redis.publish_calls[0]
        data = json.loads(raw_message)
        assert data["progress"] == 0

    async def test_progress_value_is_clamped_to_hundred_maximum(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Progress values above 100 are clamped to 100."""
        from worker.progress import publish_progress

        factory = FakeRedisFactory()
        monkeypatch.setattr("worker.progress.aioredis.from_url", factory.from_url)

        await publish_progress(
            redis_url="redis://localhost:6379",
            job_id=uuid4(),
            progress=150,
            status="running",
            message="Almost done",
        )

        _channel, raw_message = factory.redis.publish_calls[0]
        data = json.loads(raw_message)
        assert data["progress"] == 100

    async def test_terminal_status_includes_terminal_flag(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Terminal statuses (completed, failed) include terminal=true flag."""
        from worker.progress import publish_progress

        factory = FakeRedisFactory()
        monkeypatch.setattr("worker.progress.aioredis.from_url", factory.from_url)

        await publish_progress(
            redis_url="redis://localhost:6379",
            job_id=uuid4(),
            progress=100,
            status="completed",
            message="Job finished",
        )

        _channel, raw_message = factory.redis.publish_calls[0]
        data = json.loads(raw_message)
        assert data["terminal"] is True

    async def test_non_terminal_status_excludes_terminal_flag(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Non-terminal statuses do not include terminal flag."""
        from worker.progress import publish_progress

        factory = FakeRedisFactory()
        monkeypatch.setattr("worker.progress.aioredis.from_url", factory.from_url)

        await publish_progress(
            redis_url="redis://localhost:6379",
            job_id=uuid4(),
            progress=50,
            status="running",
            message="Processing",
        )

        _channel, raw_message = factory.redis.publish_calls[0]
        data = json.loads(raw_message)
        assert data.get("terminal", False) is False

    async def test_failed_status_includes_terminal_flag(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Failed status includes terminal=true flag."""
        from worker.progress import publish_progress

        factory = FakeRedisFactory()
        monkeypatch.setattr("worker.progress.aioredis.from_url", factory.from_url)

        await publish_progress(
            redis_url="redis://localhost:6379",
            job_id=uuid4(),
            progress=0,
            status="failed",
            message="Job failed",
        )

        _channel, raw_message = factory.redis.publish_calls[0]
        data = json.loads(raw_message)
        assert data["terminal"] is True

    async def test_multiple_progress_updates_can_be_published(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Multiple progress updates can be published sequentially."""
        from worker.progress import publish_progress

        job_id = uuid4()
        factory = FakeRedisFactory()
        monkeypatch.setattr("worker.progress.aioredis.from_url", factory.from_url)

        await publish_progress(
            redis_url="redis://localhost:6379",
            job_id=job_id,
            progress=25,
            status="running",
            message="Step 1",
        )
        await publish_progress(
            redis_url="redis://localhost:6379",
            job_id=job_id,
            progress=50,
            status="running",
            message="Step 2",
        )
        await publish_progress(
            redis_url="redis://localhost:6379",
            job_id=job_id,
            progress=75,
            status="running",
            message="Step 3",
        )

        # Each call creates a new redis client, so check factory calls
        assert len(factory.calls) == 3
        # All publishes to same channel
        for channel, _msg in factory.redis.publish_calls:
            assert channel == f"job_progress:{job_id}"

    async def test_handles_redis_connection_error_gracefully(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Redis connection errors are handled gracefully (don't crash)."""
        from worker.progress import publish_progress

        factory = FakeRedisFactory(error=ConnectionError("Redis unavailable"))
        monkeypatch.setattr("worker.progress.aioredis.from_url", factory.from_url)

        # Should not raise exception
        await publish_progress(
            redis_url="redis://localhost:6379",
            job_id=uuid4(),
            progress=50,
            status="running",
            message="Processing",
        )

    async def test_handles_redis_publish_error_gracefully(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Redis publish errors are handled gracefully (don't crash)."""
        from worker.progress import publish_progress

        fake_redis = FakeRedis()

        async def _publish_error(_channel: str, _message: str) -> None:
            raise RuntimeError("Redis publish failed")

        fake_redis.publish = _publish_error  # type: ignore[assignment]
        factory = FakeRedisFactory(redis=fake_redis)
        monkeypatch.setattr("worker.progress.aioredis.from_url", factory.from_url)

        # Should not raise exception
        await publish_progress(
            redis_url="redis://localhost:6379",
            job_id=uuid4(),
            progress=50,
            status="running",
            message="Processing",
        )

    async def test_closes_redis_connection_after_publish(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Redis connection is closed after publishing."""
        from worker.progress import publish_progress

        factory = FakeRedisFactory()
        monkeypatch.setattr("worker.progress.aioredis.from_url", factory.from_url)

        await publish_progress(
            redis_url="redis://localhost:6379",
            job_id=uuid4(),
            progress=50,
            status="running",
            message="Processing",
        )

        assert factory.redis.closed is True
        assert factory.redis.wait_closed_called is True

    async def test_message_includes_job_id_for_debugging(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Message includes job_id field for debugging/verification."""
        from worker.progress import publish_progress

        job_id = uuid4()
        factory = FakeRedisFactory()
        monkeypatch.setattr("worker.progress.aioredis.from_url", factory.from_url)

        await publish_progress(
            redis_url="redis://localhost:6379",
            job_id=job_id,
            progress=50,
            status="running",
            message="Processing",
        )

        _channel, raw_message = factory.redis.publish_calls[0]
        data = json.loads(raw_message)
        assert data["job_id"] == str(job_id)
