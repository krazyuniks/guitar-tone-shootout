"""Integration tests for pgmq consumer wiring in worker entrypoint.

Verifies that the worker entrypoint spawns a real GearSyncConsumer
instead of the no-op sleep loop, with correct queue configuration
and core database session.

These tests will FAIL until the entrypoint is updated to wire
the real consumer (T113).
"""

from __future__ import annotations

import asyncio
import inspect

from worker.entrypoint import run_pgmq_consumer


class TestPgmqConsumerWiring:
    """Tests that entrypoint wires the real GearSyncConsumer."""

    def test_run_pgmq_consumer_uses_gear_sync_consumer(self) -> None:
        """run_pgmq_consumer should reference GearSyncConsumer, not a sleep loop.

        The current no-op implementation uses a blocking sleep in a subprocess.
        After wiring, it must use GearSyncConsumer to poll pgmq queues.
        """
        source = inspect.getsource(run_pgmq_consumer)

        # Must reference the real consumer
        assert "GearSyncConsumer" in source, "run_pgmq_consumer should instantiate GearSyncConsumer"

        # Must NOT contain the old sleep-loop
        assert "time.sleep" not in source, (
            "run_pgmq_consumer should not use time.sleep (no-op loop)"
        )

    def test_run_pgmq_consumer_uses_core_session(self) -> None:
        """run_pgmq_consumer should obtain a core database session.

        The consumer needs a core session for GearMapperService writes
        and pgmq queue polling (single database architecture).
        """
        source = inspect.getsource(run_pgmq_consumer)

        assert "get_core_session" in source or "core_session" in source, (
            "run_pgmq_consumer should use a core database session"
        )

    def test_consumer_configured_with_correct_queue_names(self) -> None:
        """Consumer should poll the unified gear_sync queue."""
        source = inspect.getsource(run_pgmq_consumer)

        assert "gear_sync" in source, (
            "Consumer should be configured with unified gear_sync queue name"
        )

    def test_consumer_configured_with_dead_letter_queue(self) -> None:
        """Consumer should have gear_sync_dlq queue for failed messages."""
        source = inspect.getsource(run_pgmq_consumer)

        assert "gear_sync_dlq" in source, (
            "Consumer should be configured with gear_sync_dlq queue name"
        )

    def test_run_pgmq_consumer_calls_consumer_run(self) -> None:
        """run_pgmq_consumer must invoke the consumer's run() method.

        GearSyncConsumer.run() is the main polling loop. The entrypoint
        must call it (not just instantiate the consumer).
        """
        source = inspect.getsource(run_pgmq_consumer)

        # Should call .run() on the consumer instance
        assert ".run()" in source, "run_pgmq_consumer should call consumer.run() to start polling"


class TestConsumerFailFast:
    """Tests that consumer exit triggers fail-fast shutdown."""

    def test_run_pgmq_consumer_accepts_process_manager(self) -> None:
        """run_pgmq_consumer should still accept a ProcessManager argument.

        The fail-fast pattern requires that run_pgmq_consumer integrates
        with the ProcessManager so the orchestrator can monitor and
        terminate the consumer alongside other processes.
        """
        sig = inspect.signature(run_pgmq_consumer)
        param_names = list(sig.parameters.keys())

        assert "manager" in param_names, (
            "run_pgmq_consumer must accept a 'manager' parameter for fail-fast"
        )

    def test_run_pgmq_consumer_is_async(self) -> None:
        """run_pgmq_consumer should be an async function.

        The consumer runs as an async coroutine (GearSyncConsumer.run()
        is async), so the entrypoint function must also be async.
        """
        assert asyncio.iscoroutinefunction(run_pgmq_consumer), (
            "run_pgmq_consumer must be an async function"
        )
