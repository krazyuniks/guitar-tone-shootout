"""Worker container entrypoint - orchestrates 3 concurrent services.

This module manages 3 concurrent processes in a single worker container:
1. Admin API (uvicorn on port 8001)
2. TaskIQ worker
3. pgmq consumer (initial no-op loop)

Implements fail-fast behaviour: if any child process exits, all processes
are terminated gracefully.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import signal
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from asyncio.subprocess import Process
    from types import FrameType

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class ProcessManager:
    """Manages lifecycle of multiple child processes.

    Tracks running processes and provides graceful shutdown coordination.
    """

    def __init__(self) -> None:
        """Initialize the process manager."""
        self.processes: list[Process] = []
        self.shutdown_event = asyncio.Event()

    def add_process(self, process: Process) -> None:
        """Add a process to the tracked list.

        Args:
            process: The subprocess to track
        """
        self.processes.append(process)

    def signal_shutdown(self) -> None:
        """Signal that shutdown should begin.

        Sets the shutdown event which causes wait_for_shutdown() to return.
        """
        self.shutdown_event.set()

    async def wait_for_shutdown(self) -> None:
        """Wait until shutdown is signalled.

        Blocks until signal_shutdown() is called.
        """
        await self.shutdown_event.wait()

    async def terminate_all(self) -> None:
        """Terminate all tracked processes gracefully.

        Sends SIGTERM to each process and waits for them to exit.
        Handles ProcessLookupError if a process already exited.
        """
        for process in self.processes:
            with contextlib.suppress(ProcessLookupError):
                process.terminate()

        # Wait for all processes to exit
        for process in self.processes:
            try:
                await process.wait()
            except Exception as e:
                logger.warning(f"Error waiting for process {process.pid}: {e}")


def handle_shutdown(manager: ProcessManager, signum: int, frame: FrameType | None) -> None:
    """Signal handler for SIGTERM/SIGINT.

    Args:
        manager: The process manager to signal
        signum: The signal number received
        frame: The current stack frame (unused)
    """
    logger.info(f"Received signal {signum}, initiating graceful shutdown")
    manager.signal_shutdown()


async def run_admin_api(manager: ProcessManager) -> None:
    """Start the admin API server via uvicorn.

    Args:
        manager: The process manager to register with
    """
    logger.info("Starting admin API on port 8001")

    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "uvicorn",
        "worker.admin:app",
        "--host",
        "0.0.0.0",
        "--port",
        "8001",
    )

    manager.add_process(process)
    logger.info(f"Admin API started with PID {process.pid}")


async def run_taskiq_worker(manager: ProcessManager) -> None:
    """Start the TaskIQ worker.

    Args:
        manager: The process manager to register with
    """
    logger.info("Starting TaskIQ worker")

    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "taskiq",
        "worker",
        "worker.main:broker",
        "--workers",
        "1",
    )

    manager.add_process(process)
    logger.info(f"TaskIQ worker started with PID {process.pid}")


async def run_pgmq_consumer(manager: ProcessManager) -> None:
    """Start the pgmq consumer with real GearSyncConsumer.

    Args:
        manager: The process manager to register with
    """
    logger.info("Starting pgmq consumer")

    # Run consumer in subprocess with database session setup
    consumer_script = """
import asyncio
from worker.consumers.gear_sync import GearSyncConsumer
from worker.db import get_core_session, get_t3k_session

async def main():
    async with get_core_session() as core_session, get_t3k_session() as t3k_session:
        consumer = GearSyncConsumer(
            core_session=core_session,
            t3k_session=t3k_session,
            pack_queue_name="gear_pack_sync",
            model_queue_name="gear_model_sync",
            dead_letter_queue="sync_dead_letter",
        )
        await consumer.run()

if __name__ == "__main__":
    asyncio.run(main())
"""

    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-u",  # Unbuffered output
        "-c",
        consumer_script,
    )

    manager.add_process(process)
    logger.info(f"pgmq consumer started with PID {process.pid}")


async def monitor_process(process: Process, name: str, manager: ProcessManager) -> None:
    """Monitor a child process and trigger shutdown if it exits.

    Args:
        process: The subprocess to monitor
        name: Name of the process for logging
        manager: The process manager to signal on exit
    """
    exit_code = await process.wait()
    logger.warning(f"{name} exited with code {exit_code}")
    manager.signal_shutdown()


async def start_all_processes() -> None:
    """Start all 3 processes and wait for shutdown signal.

    This is the main entrypoint function that:
    1. Creates a ProcessManager
    2. Starts all 3 services concurrently
    3. Monitors child processes and triggers shutdown if any exit
    4. Waits for shutdown signal (from signal handler or child exit)
    5. Terminates all processes gracefully

    Raises:
        asyncio.CancelledError: If the task is cancelled
    """
    manager = ProcessManager()

    # Register signal handlers
    signal.signal(signal.SIGTERM, lambda s, f: handle_shutdown(manager, s, f))
    signal.signal(signal.SIGINT, lambda s, f: handle_shutdown(manager, s, f))

    logger.info("Starting worker container orchestration")

    try:
        # Start all 3 processes
        await run_admin_api(manager)
        await run_taskiq_worker(manager)
        await run_pgmq_consumer(manager)

        # Create monitoring tasks for each process
        monitor_tasks = [
            asyncio.create_task(monitor_process(manager.processes[0], "Admin API", manager)),
            asyncio.create_task(monitor_process(manager.processes[1], "TaskIQ worker", manager)),
            asyncio.create_task(monitor_process(manager.processes[2], "pgmq consumer", manager)),
        ]

        # Wait for shutdown signal (triggered by signal handler or child exit)
        await manager.wait_for_shutdown()

        logger.info("Shutdown signal received, terminating all processes")

        # Cancel all monitoring tasks
        for task in monitor_tasks:
            task.cancel()

        # Wait for tasks to finish cancelling
        await asyncio.gather(*monitor_tasks, return_exceptions=True)

        # Terminate all child processes
        await manager.terminate_all()

    except asyncio.CancelledError:
        logger.info("Orchestration cancelled, terminating processes")
        await manager.terminate_all()
        raise


def main() -> None:
    """Main entry point for the worker container."""
    try:
        asyncio.run(start_all_processes())
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
