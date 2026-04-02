"""Embedded scheduler for source sync supervision."""

from __future__ import annotations

import asyncio
import logging
import os
from typing import TYPE_CHECKING

import httpx

from gts.domain.auth_gate import check_auth_status
from t3k_sync.health import ServiceState
from t3k_sync.source_sync import run_source_sync

if TYPE_CHECKING:
    from source_t3k.adapters.inbound.token_manager import T3KTokenManager
    from t3k_sync.health import SyncHealthTracker

logger = logging.getLogger(__name__)


class SyncScheduler:
    """Interval scheduler that keeps T3K sync running.

    Simple fixed-interval loop. If auth is bad, backs off and optionally
    fires an alert webhook.
    """

    def __init__(
        self,
        interval_seconds: float = 60.0,
        tracker: SyncHealthTracker | None = None,
        token_manager: T3KTokenManager | None = None,
    ) -> None:
        self.base_interval = interval_seconds
        self._tracker = tracker
        self._token_manager = token_manager
        self._shutdown_event = asyncio.Event()
        self._alert_sent = False

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
            was_waiting = (
                self._tracker is not None and self._tracker.state == ServiceState.WAITING_FOR_AUTH
            )
            if self._tracker is not None:
                self._tracker.record_auth_failure(status)
            if not was_waiting and not self._alert_sent:
                await self._send_alert(
                    f"T3K sync stuck: auth is {status.value} — run `just t3k-login`"
                )
                self._alert_sent = True
            return

        if self._alert_sent:
            await self._send_alert("T3K sync recovered — auth is valid")
            self._alert_sent = False

        if self._tracker is not None:
            self._tracker.record_auth_healthy(status)

        await run_source_sync(tracker=self._tracker, token_manager=self._token_manager)

    async def run(self) -> None:
        """Run until shutdown is requested."""
        while not self._shutdown_event.is_set():
            try:
                await self.ensure_sync_running()
            except Exception:
                logger.exception("Scheduled ensure_sync_running cycle failed")

            interval = self.base_interval
            if self._tracker is not None:
                interval = self._tracker.get_scheduler_interval(self.base_interval)
            try:
                await asyncio.wait_for(self._shutdown_event.wait(), timeout=interval)
            except TimeoutError:
                continue

    async def _send_alert(self, message: str) -> None:
        """POST to SYNC_ALERT_WEBHOOK if configured. Fire-and-forget."""
        webhook = os.getenv("SYNC_ALERT_WEBHOOK")
        if not webhook:
            return
        try:
            async with httpx.AsyncClient() as client:
                await client.post(webhook, content=message, timeout=10.0)
        except Exception:
            logger.warning("Failed to send sync alert to webhook")
