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

import pytest

from worker.entrypoint import (
    ProcessManager,
    handle_shutdown,
    run_admin_api,
    run_pgmq_consumer,
    run_taskiq_worker,
    start_all_processes,
)


class FakeProcess:
    """Test double for asyncio.subprocess.Process."""

    def __init__(self, pid: int = 100, exit_code: int = 0) -> None:
        self.pid = pid
        self._exit_code = exit_code
        self.terminated = False
        self._wait_called = False

    def terminate(self) -> None:
        self.terminated = True

    async def wait(self) -> int:
        self._wait_called = True
        return self._exit_code


class FakeProcessRaisesOnTerminate(FakeProcess):
    """FakeProcess that raises ProcessLookupError on terminate."""

    def terminate(self) -> None:
        raise ProcessLookupError


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
        process = FakeProcess(pid=12345)
        manager.add_process(process)

        assert len(manager.processes) == 1
        assert manager.processes[0].pid == 12345

    def test_signal_shutdown(self, manager: ProcessManager) -> None:
        """signal_shutdown sets the shutdown event."""
        assert manager.shutdown_event.is_set() is False
        manager.signal_shutdown()
        assert manager.shutdown_event.is_set() is True

    async def test_wait_for_shutdown(self, manager: ProcessManager) -> None:
        """wait_for_shutdown blocks until shutdown_event is set."""
        wait_task = asyncio.create_task(manager.wait_for_shutdown())

        await asyncio.sleep(0.01)
        assert not wait_task.done()

        manager.signal_shutdown()
        await asyncio.wait_for(wait_task, timeout=0.1)
        assert wait_task.done()

    async def test_terminate_all_processes(self, manager: ProcessManager) -> None:
        """terminate_all sends SIGTERM to all tracked processes."""
        proc1 = FakeProcess(pid=100)
        proc2 = FakeProcess(pid=101)

        manager.add_process(proc1)
        manager.add_process(proc2)

        await manager.terminate_all()

        assert proc1.terminated is True
        assert proc2.terminated is True
        assert proc1._wait_called is True
        assert proc2._wait_called is True

    async def test_terminate_all_with_process_exception(self, manager: ProcessManager) -> None:
        """terminate_all handles ProcessLookupError gracefully."""
        proc = FakeProcessRaisesOnTerminate(pid=100)
        manager.add_process(proc)

        # Should not raise exception
        await manager.terminate_all()


class TestProcessRunners:
    """Tests for individual process runner functions."""

    async def test_run_admin_api_starts_uvicorn(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """run_admin_api spawns uvicorn process with correct arguments."""
        manager = ProcessManager()
        fake_process = FakeProcess(pid=200)

        async def fake_subprocess(*_args, **_kwargs):
            return fake_process

        monkeypatch.setattr("asyncio.create_subprocess_exec", fake_subprocess)
        await run_admin_api(manager)

        assert len(manager.processes) == 1
        assert manager.processes[0].pid == 200

    async def test_run_taskiq_worker_starts_worker(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """run_taskiq_worker spawns taskiq worker process."""
        manager = ProcessManager()
        fake_process = FakeProcess(pid=201)

        async def fake_subprocess(*_args, **_kwargs):
            return fake_process

        monkeypatch.setattr("asyncio.create_subprocess_exec", fake_subprocess)
        await run_taskiq_worker(manager)

        assert len(manager.processes) == 1
        assert manager.processes[0].pid == 201

    async def test_run_pgmq_consumer_starts_consumer(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """run_pgmq_consumer spawns pgmq consumer process."""
        manager = ProcessManager()
        fake_process = FakeProcess(pid=202)

        async def fake_subprocess(*_args, **_kwargs):
            return fake_process

        monkeypatch.setattr("asyncio.create_subprocess_exec", fake_subprocess)
        await run_pgmq_consumer(manager)

        assert len(manager.processes) == 1
        assert manager.processes[0].pid == 202


class TestFailFast:
    """Tests for fail-fast behaviour when a child process exits."""

    async def test_process_exit_zero_triggers_shutdown(self) -> None:
        """Process exiting with code 0 triggers graceful shutdown."""
        manager = ProcessManager()
        proc = FakeProcess(pid=100, exit_code=0)
        manager.add_process(proc)

        exit_code = await proc.wait()
        assert exit_code == 0

    async def test_process_exit_nonzero_triggers_shutdown(self) -> None:
        """Process exiting with non-zero code triggers shutdown."""
        manager = ProcessManager()
        proc = FakeProcess(pid=100, exit_code=1)
        manager.add_process(proc)

        exit_code = await proc.wait()
        assert exit_code == 1


class TestSignalHandling:
    """Tests for SIGTERM/SIGINT signal handling."""

    def test_handle_shutdown_sets_shutdown_event(self) -> None:
        """handle_shutdown callback sets the shutdown event."""
        manager = ProcessManager()
        assert manager.shutdown_event.is_set() is False

        handle_shutdown(manager, signal.SIGTERM, None)
        assert manager.shutdown_event.is_set() is True

    def test_handle_shutdown_accepts_sigint(self) -> None:
        """handle_shutdown handles SIGINT as well as SIGTERM."""
        manager = ProcessManager()
        assert manager.shutdown_event.is_set() is False

        handle_shutdown(manager, signal.SIGINT, None)
        assert manager.shutdown_event.is_set() is True


class TestEntrypointIntegration:
    """Integration tests for the full entrypoint orchestration."""

    async def test_start_all_processes_launches_three_processes(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """start_all_processes launches admin API, worker, and consumer."""

        class HangingProcess(FakeProcess):
            """Process whose wait() hangs until terminated."""

            def __init__(self, **kwargs) -> None:
                super().__init__(**kwargs)
                self._done = asyncio.Event()

            def terminate(self) -> None:
                self.terminated = True
                self._done.set()

            async def wait(self) -> int:
                await self._done.wait()
                return 0

        async def fake_subprocess(*_args, **_kwargs):
            return HangingProcess(pid=300)

        monkeypatch.setattr("asyncio.create_subprocess_exec", fake_subprocess)

        task = asyncio.create_task(start_all_processes())
        await asyncio.sleep(0.05)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    async def test_graceful_shutdown_on_sigterm(self) -> None:
        """SIGTERM triggers graceful shutdown of all processes."""
        manager = ProcessManager()
        proc = FakeProcess(pid=301)
        manager.add_process(proc)

        handle_shutdown(manager, signal.SIGTERM, None)
        assert manager.shutdown_event.is_set() is True

        await manager.terminate_all()
        assert proc.terminated is True

    async def test_fail_fast_on_child_exit(self) -> None:
        """If any child exits non-zero, all processes terminate."""
        manager = ProcessManager()

        failing_proc = FakeProcess(pid=302, exit_code=1)
        healthy_proc = FakeProcess(pid=303, exit_code=0)

        manager.add_process(failing_proc)
        manager.add_process(healthy_proc)

        exit_code = await failing_proc.wait()
        assert exit_code != 0

        manager.signal_shutdown()
        assert manager.shutdown_event.is_set() is True

        await manager.terminate_all()
        assert healthy_proc.terminated is True
