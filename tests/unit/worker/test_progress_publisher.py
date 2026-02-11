"""Unit tests for worker progress publisher.

Tests that publish_progress sends job progress updates to Redis pub/sub
channels for WebSocket forwarding to clients.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest


class TestPublishProgress:
    """Test progress publisher sends messages to Redis channels."""

    async def test_function_exists_and_is_async(self) -> None:
        """publish_progress function exists and is async callable."""
        from inspect import iscoroutinefunction

        from worker.progress import publish_progress

        assert callable(publish_progress)
        assert iscoroutinefunction(publish_progress)

    async def test_publishes_to_correct_redis_channel(self) -> None:
        """Publishes to job_progress:{job_id} channel."""
        from worker.progress import publish_progress

        job_id = uuid4()
        redis_url = "redis://localhost:6379"

        with patch("worker.progress.aioredis.from_url") as mock_from_url:
            mock_redis = AsyncMock()
            mock_from_url.return_value = mock_redis

            await publish_progress(
                redis_url=redis_url,
                job_id=job_id,
                progress=50,
                status="running",
                message="Processing chain 2/5",
            )

            # Verify Redis client created with correct URL
            mock_from_url.assert_called_once_with(redis_url)

            # Verify publish called with correct channel and message
            mock_redis.publish.assert_called_once()
            call_args = mock_redis.publish.call_args
            channel = call_args[0][0]
            message = call_args[0][1]

            assert channel == f"job_progress:{job_id}"
            assert message is not None

    async def test_message_format_is_json(self) -> None:
        """Message is JSON with progress, status, and message fields."""
        import json

        from worker.progress import publish_progress

        job_id = uuid4()

        with patch("worker.progress.aioredis.from_url") as mock_from_url:
            mock_redis = AsyncMock()
            mock_from_url.return_value = mock_redis

            await publish_progress(
                redis_url="redis://localhost:6379",
                job_id=job_id,
                progress=75,
                status="running",
                message="Rendering video",
            )

            call_args = mock_redis.publish.call_args
            message = call_args[0][1]

            # Parse JSON
            data = json.loads(message)

            assert data["progress"] == 75
            assert data["status"] == "running"
            assert data["message"] == "Rendering video"

    async def test_progress_value_is_clamped_to_zero_minimum(self) -> None:
        """Progress values below 0 are clamped to 0."""
        import json

        from worker.progress import publish_progress

        with patch("worker.progress.aioredis.from_url") as mock_from_url:
            mock_redis = AsyncMock()
            mock_from_url.return_value = mock_redis

            await publish_progress(
                redis_url="redis://localhost:6379",
                job_id=uuid4(),
                progress=-10,
                status="running",
                message="Starting",
            )

            call_args = mock_redis.publish.call_args
            message = call_args[0][1]
            data = json.loads(message)

            assert data["progress"] == 0

    async def test_progress_value_is_clamped_to_hundred_maximum(self) -> None:
        """Progress values above 100 are clamped to 100."""
        import json

        from worker.progress import publish_progress

        with patch("worker.progress.aioredis.from_url") as mock_from_url:
            mock_redis = AsyncMock()
            mock_from_url.return_value = mock_redis

            await publish_progress(
                redis_url="redis://localhost:6379",
                job_id=uuid4(),
                progress=150,
                status="running",
                message="Almost done",
            )

            call_args = mock_redis.publish.call_args
            message = call_args[0][1]
            data = json.loads(message)

            assert data["progress"] == 100

    async def test_terminal_status_includes_terminal_flag(self) -> None:
        """Terminal statuses (completed, failed) include terminal=true flag."""
        import json

        from worker.progress import publish_progress

        with patch("worker.progress.aioredis.from_url") as mock_from_url:
            mock_redis = AsyncMock()
            mock_from_url.return_value = mock_redis

            await publish_progress(
                redis_url="redis://localhost:6379",
                job_id=uuid4(),
                progress=100,
                status="completed",
                message="Job finished",
            )

            call_args = mock_redis.publish.call_args
            message = call_args[0][1]
            data = json.loads(message)

            assert data["terminal"] is True

    async def test_non_terminal_status_excludes_terminal_flag(self) -> None:
        """Non-terminal statuses do not include terminal flag."""
        import json

        from worker.progress import publish_progress

        with patch("worker.progress.aioredis.from_url") as mock_from_url:
            mock_redis = AsyncMock()
            mock_from_url.return_value = mock_redis

            await publish_progress(
                redis_url="redis://localhost:6379",
                job_id=uuid4(),
                progress=50,
                status="running",
                message="Processing",
            )

            call_args = mock_redis.publish.call_args
            message = call_args[0][1]
            data = json.loads(message)

            # Terminal should be false or absent
            assert data.get("terminal", False) is False

    async def test_failed_status_includes_terminal_flag(self) -> None:
        """Failed status includes terminal=true flag."""
        import json

        from worker.progress import publish_progress

        with patch("worker.progress.aioredis.from_url") as mock_from_url:
            mock_redis = AsyncMock()
            mock_from_url.return_value = mock_redis

            await publish_progress(
                redis_url="redis://localhost:6379",
                job_id=uuid4(),
                progress=0,
                status="failed",
                message="Job failed",
            )

            call_args = mock_redis.publish.call_args
            message = call_args[0][1]
            data = json.loads(message)

            assert data["terminal"] is True

    async def test_multiple_progress_updates_can_be_published(self) -> None:
        """Multiple progress updates can be published sequentially."""

        from worker.progress import publish_progress

        job_id = uuid4()

        with patch("worker.progress.aioredis.from_url") as mock_from_url:
            mock_redis = AsyncMock()
            mock_from_url.return_value = mock_redis

            # Publish three progress updates
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

            # Verify three publishes to the same channel
            assert mock_redis.publish.call_count == 3

            # Verify all messages were for the same job
            for call in mock_redis.publish.call_args_list:
                channel = call[0][0]
                assert channel == f"job_progress:{job_id}"

    async def test_handles_redis_connection_error_gracefully(self) -> None:
        """Redis connection errors are handled gracefully (don't crash)."""
        from worker.progress import publish_progress

        with patch("worker.progress.aioredis.from_url") as mock_from_url:
            mock_from_url.side_effect = ConnectionError("Redis unavailable")

            # Should not raise exception
            try:
                await publish_progress(
                    redis_url="redis://localhost:6379",
                    job_id=uuid4(),
                    progress=50,
                    status="running",
                    message="Processing",
                )
            except ConnectionError:
                pytest.fail("publish_progress should handle connection errors gracefully")

    async def test_handles_redis_publish_error_gracefully(self) -> None:
        """Redis publish errors are handled gracefully (don't crash)."""
        from worker.progress import publish_progress

        with patch("worker.progress.aioredis.from_url") as mock_from_url:
            mock_redis = AsyncMock()
            mock_redis.publish.side_effect = Exception("Redis publish failed")
            mock_from_url.return_value = mock_redis

            # Should not raise exception
            try:
                await publish_progress(
                    redis_url="redis://localhost:6379",
                    job_id=uuid4(),
                    progress=50,
                    status="running",
                    message="Processing",
                )
            except Exception:
                pytest.fail("publish_progress should handle publish errors gracefully")

    async def test_closes_redis_connection_after_publish(self) -> None:
        """Redis connection is closed after publishing."""
        from worker.progress import publish_progress

        with patch("worker.progress.aioredis.from_url") as mock_from_url:
            mock_redis = AsyncMock()
            mock_from_url.return_value = mock_redis

            await publish_progress(
                redis_url="redis://localhost:6379",
                job_id=uuid4(),
                progress=50,
                status="running",
                message="Processing",
            )

            # Verify close was called
            mock_redis.close.assert_called_once()
            mock_redis.wait_closed.assert_called_once()

    async def test_message_includes_job_id_for_debugging(self) -> None:
        """Message includes job_id field for debugging/verification."""
        import json

        from worker.progress import publish_progress

        job_id = uuid4()

        with patch("worker.progress.aioredis.from_url") as mock_from_url:
            mock_redis = AsyncMock()
            mock_from_url.return_value = mock_redis

            await publish_progress(
                redis_url="redis://localhost:6379",
                job_id=job_id,
                progress=50,
                status="running",
                message="Processing",
            )

            call_args = mock_redis.publish.call_args
            message = call_args[0][1]
            data = json.loads(message)

            assert data["job_id"] == str(job_id)
