"""Integration tests for pgmq consumer wiring in worker entrypoint.

Verifies that the worker entrypoint's run_pgmq_consumer compatibility
shim delegates to the t3k-sync container process with correct wiring.
"""

from __future__ import annotations

import asyncio
import inspect

from worker.entrypoint import run_pgmq_consumer


class TestPgmqConsumerWiring:
    """Tests that entrypoint delegates to t3k-sync process."""

    def test_run_pgmq_consumer_delegates_to_t3k_sync(self) -> None:
        """run_pgmq_consumer should delegate to the t3k_sync app.

        PGMQ consumption moved to the dedicated t3k-sync container.
        The compatibility shim launches t3k_sync.main:app via uvicorn.
        """
        source = inspect.getsource(run_pgmq_consumer)

        assert "t3k_sync" in source, "run_pgmq_consumer should delegate to t3k_sync app"

    def test_run_pgmq_consumer_uses_uvicorn(self) -> None:
        """run_pgmq_consumer should launch via uvicorn."""
        source = inspect.getsource(run_pgmq_consumer)

        assert "uvicorn" in source, "run_pgmq_consumer should launch t3k-sync via uvicorn"


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

        The compatibility shim creates a subprocess asynchronously,
        so the entrypoint function must also be async.
        """
        assert asyncio.iscoroutinefunction(run_pgmq_consumer), (
            "run_pgmq_consumer must be an async function"
        )
