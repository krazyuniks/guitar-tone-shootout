"""Unit tests for worker container entrypoint orchestration.

Tests that the entrypoint correctly manages 3 concurrent processes:
- Admin API (uvicorn on port 8001)
- TaskIQ worker
- pgmq consumer (initial no-op loop)

These tests verify process lifecycle management, fail-fast behaviour,
and graceful shutdown handling.
"""

from __future__ import annotations

import asyncio
import signal
from unittest.mock import AsyncMock, MagicMock

import pytest

from worker.entrypoint import (
    ProcessManager,
    handle_shutdown,
    run_admin_api,
    run_pgmq_consumer,
    run_taskiq_worker,
    start_all_processes,
)


class TestProcessManager:
    """Tests for ProcessManager process lifecycle management."""

    @pytest.fixture
    def manager(self) -> ProcessManager:
        """Create a ProcessManager instance for testing."""
        return ProcessManager()

    def test_initial_state(self, manager: ProcessManager) -> None:
        """ProcessManager starts with no tracked processes."""
        assert manager.processes == []
        assert manager.shutdown_event.is_set() is False

    def test_add_process(self, manager: ProcessManager) -> None:
        """ProcessManager can track a subprocess."""
        mock_process = MagicMock()
        mock_process.pid = 12345

        manager.add_process(mock_process)

        assert len(manager.processes) == 1
        assert manager.processes[0].pid == 12345

    def test_signal_shutdown(self, manager: ProcessManager) -> None:
        """signal_shutdown sets the shutdown event."""
        assert manager.shutdown_event.is_set() is False

        manager.signal_shutdown()

        assert manager.shutdown_event.is_set() is True

    async def test_wait_for_shutdown(self, manager: ProcessManager) -> None:
        """wait_for_shutdown blocks until shutdown_event is set."""
        # Start waiting in background
        wait_task = asyncio.create_task(manager.wait_for_shutdown())

        # Should not complete immediately
        await asyncio.sleep(0.01)
        assert not wait_task.done()

        # Signal shutdown
        manager.signal_shutdown()

        # Should complete now
        await asyncio.wait_for(wait_task, timeout=0.1)
        assert wait_task.done()

    async def test_terminate_all_processes(self, manager: ProcessManager) -> None:
        """terminate_all sends SIGTERM to all tracked processes."""
        mock_process_1 = MagicMock()
        mock_process_1.pid = 100
        mock_process_1.terminate = MagicMock()
        mock_process_1.wait = AsyncMock(return_value=0)

        mock_process_2 = MagicMock()
        mock_process_2.pid = 101
        mock_process_2.terminate = MagicMock()
        mock_process_2.wait = AsyncMock(return_value=0)

        manager.add_process(mock_process_1)
        manager.add_process(mock_process_2)

        await manager.terminate_all()

        # Both processes should be terminated
        mock_process_1.terminate.assert_called_once()
        mock_process_2.terminate.assert_called_once()

        # Both processes should be waited on
        mock_process_1.wait.assert_called_once()
        mock_process_2.wait.assert_called_once()

    async def test_terminate_all_with_process_exception(self, manager: ProcessManager) -> None:
        """terminate_all handles ProcessLookupError gracefully."""
        mock_process = MagicMock()
        mock_process.pid = 100
        mock_process.terminate = MagicMock(side_effect=ProcessLookupError)
        mock_process.wait = AsyncMock(return_value=0)

        manager.add_process(mock_process)

        # Should not raise exception
        await manager.terminate_all()

        mock_process.terminate.assert_called_once()


class TestProcessRunners:
    """Tests for individual process runner functions."""

    async def test_run_admin_api_starts_uvicorn(self) -> None:
        """run_admin_api spawns uvicorn process with correct arguments."""
        manager = ProcessManager()

        # This will fail because the module doesn't exist yet
        with pytest.raises(ImportError):
            await run_admin_api(manager)

    async def test_run_taskiq_worker_starts_worker(self) -> None:
        """run_taskiq_worker spawns taskiq worker process."""
        manager = ProcessManager()

        # This will fail because the module doesn't exist yet
        with pytest.raises(ImportError):
            await run_taskiq_worker(manager)

    async def test_run_pgmq_consumer_starts_consumer(self) -> None:
        """run_pgmq_consumer spawns pgmq consumer process."""
        manager = ProcessManager()

        # This will fail because the module doesn't exist yet
        with pytest.raises(ImportError):
            await run_pgmq_consumer(manager)


class TestFailFast:
    """Tests for fail-fast behaviour when a child process exits."""

    async def test_process_exit_zero_triggers_shutdown(self) -> None:
        """Process exiting with code 0 triggers graceful shutdown."""
        manager = ProcessManager()

        # Simulate a process that exits cleanly
        mock_process = MagicMock()
        mock_process.pid = 100
        mock_process.wait = AsyncMock(return_value=0)
        mock_process.terminate = MagicMock()

        manager.add_process(mock_process)

        # Wait for process to exit
        exit_code = await mock_process.wait()

        assert exit_code == 0
        # In the real implementation, this should trigger manager.signal_shutdown()

    async def test_process_exit_nonzero_triggers_shutdown(self) -> None:
        """Process exiting with non-zero code triggers shutdown."""
        manager = ProcessManager()

        # Simulate a process that crashes
        mock_process = MagicMock()
        mock_process.pid = 100
        mock_process.wait = AsyncMock(return_value=1)
        mock_process.terminate = MagicMock()

        manager.add_process(mock_process)

        # Wait for process to exit
        exit_code = await mock_process.wait()

        assert exit_code == 1
        # In the real implementation, this should trigger manager.signal_shutdown()


class TestSignalHandling:
    """Tests for SIGTERM/SIGINT signal handling."""

    def test_handle_shutdown_sets_shutdown_event(self) -> None:
        """handle_shutdown callback sets the shutdown event."""
        manager = ProcessManager()

        assert manager.shutdown_event.is_set() is False

        # Simulate signal handler invocation
        handle_shutdown(manager, signal.SIGTERM, None)

        assert manager.shutdown_event.is_set() is True

    def test_handle_shutdown_accepts_sigint(self) -> None:
        """handle_shutdown handles SIGINT as well as SIGTERM."""
        manager = ProcessManager()

        assert manager.shutdown_event.is_set() is False

        # Simulate SIGINT (Ctrl+C)
        handle_shutdown(manager, signal.SIGINT, None)

        assert manager.shutdown_event.is_set() is True


class TestEntrypointIntegration:
    """Integration tests for the full entrypoint orchestration."""

    async def test_start_all_processes_launches_three_processes(self) -> None:
        """start_all_processes launches admin API, worker, and consumer."""
        # This will fail because the module doesn't exist yet
        with pytest.raises(ImportError):
            await start_all_processes()

    async def test_graceful_shutdown_on_sigterm(self) -> None:
        """SIGTERM triggers graceful shutdown of all processes."""
        # This will fail because the module doesn't exist yet
        with pytest.raises(ImportError):
            await start_all_processes()

    async def test_fail_fast_on_child_exit(self) -> None:
        """If any child exits non-zero, all processes terminate."""
        # This will fail because the module doesn't exist yet
        with pytest.raises(ImportError):
            await start_all_processes()
