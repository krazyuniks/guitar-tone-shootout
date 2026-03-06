"""Embedded scheduler for source sync supervision."""

from __future__ import annotations

import asyncio
import logging
import os
from typing import TYPE_CHECKING

from gts.domain.auth_gate import check_auth_status
from t3k_sync.source_sync import run_source_sync

if TYPE_CHECKING:
    from t3k_sync.health import SyncHealthTracker

logger = logging.getLogger(__name__)


class SyncScheduler:
    """Interval scheduler that keeps T3K sync running.

    Simple fixed-interval loop. If auth is bad, logs once and retries
    next cycle (no backoff — this is a small system we fully control).
    """

    def __init__(
        self,
        interval_seconds: float = 60.0,
        tracker: SyncHealthTracker | None = None,
    ) -> None:
        self.base_interval = interval_seconds
        self._tracker = tracker
        self._shutdown_event = asyncio.Event()

    def request_shutdown(self) -> None:
        """Signal the scheduler loop to stop."""
        self._shutdown_event.set()

    async def ensure_sync_running(self) -> None:
        """Run one sync cycle when sync is enabled."""
        sync_enabled = os.getenv("T3K_SYNC_ENABLED", "true").lower() == "true"
        if not sync_enabled:
            return

        auth_file = os.getenv("GTS_AUTH_FILE", "/.gts-auth.json")
        status = check_auth_status(auth_file)
        if not status.can_proceed():
            logger.info("Auth not ready (%s), will retry next cycle", status.value)
            if self._tracker is not None:
                self._tracker.record_auth_failure(status)
            return

        if self._tracker is not None:
            self._tracker.record_auth_healthy(status)

        await run_source_sync(tracker=self._tracker)

    async def run(self) -> None:
        """Run until shutdown is requested."""
        while not self._shutdown_event.is_set():
            try:
                await self.ensure_sync_running()
            except Exception:
                logger.exception("Scheduled ensure_sync_running cycle failed")

            try:
                await asyncio.wait_for(self._shutdown_event.wait(), timeout=self.base_interval)
            except TimeoutError:
                continue
