"""Embedded scheduler for source sync supervision."""

from __future__ import annotations

import asyncio
import logging
import os

from t3k_sync.source_sync import run_source_sync

logger = logging.getLogger(__name__)


class SyncScheduler:
    """Simple interval scheduler that keeps T3K sync running."""

    def __init__(self, interval_seconds: float = 60.0) -> None:
        self.interval_seconds = interval_seconds
        self._shutdown_event = asyncio.Event()

    def request_shutdown(self) -> None:
        """Signal the scheduler loop to stop."""
        self._shutdown_event.set()

    async def ensure_sync_running(self) -> None:
        """Run one sync cycle when sync is enabled."""
        sync_enabled = os.getenv("T3K_SYNC_ENABLED", "true").lower() == "true"
        if not sync_enabled:
            return

        await run_source_sync()

    async def run(self) -> None:
        """Run until shutdown is requested."""
        while not self._shutdown_event.is_set():
            try:
                await self.ensure_sync_running()
            except Exception:
                logger.exception("Scheduled ensure_sync_running cycle failed")

            try:
                await asyncio.wait_for(self._shutdown_event.wait(), timeout=self.interval_seconds)
            except TimeoutError:
                continue
