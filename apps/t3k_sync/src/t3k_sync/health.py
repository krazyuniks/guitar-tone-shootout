"""Service health tracker for t3k-sync container.

Provides a shared in-memory state model so the scheduler, health endpoint,
and monitoring tasks can coordinate instead of independently discovering
the same failures.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from enum import Enum

from gts.domain.value_objects.source_auth_status import SourceAuthStatus

logger = logging.getLogger(__name__)


class ServiceState(str, Enum):
    """Observable states of the t3k-sync service."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    WAITING_FOR_AUTH = "waiting_for_auth"


class SyncHealthTracker:
    """In-memory singleton tracking sync service health.

    All periodic tasks and the health endpoint read from this.
    The scheduler and source_sync update it.
    """

    def __init__(self) -> None:
        self.state: ServiceState = ServiceState.HEALTHY
        self.last_successful_sync: datetime | None = None
        self.last_error: str | None = None
        self.consecutive_failures: int = 0
        self.auth_status: SourceAuthStatus = SourceAuthStatus.UNKNOWN
        self._state_since: datetime = datetime.now(UTC)

    def record_sync_success(self) -> None:
        """Called after a sync batch completes successfully."""
        self.state = ServiceState.HEALTHY
        self.last_successful_sync = datetime.now(UTC)
        self.last_error = None
        self.consecutive_failures = 0
        self._state_since = datetime.now(UTC)

    def record_sync_failure(self, error: str) -> None:
        """Called when a sync batch fails (non-auth reasons)."""
        self.consecutive_failures += 1
        self.last_error = error
        if self.consecutive_failures >= 3 and self.state == ServiceState.HEALTHY:
            self.state = ServiceState.DEGRADED
            self._state_since = datetime.now(UTC)
            logger.critical(
                "SYNC_STUCK: %d consecutive failures — %s", self.consecutive_failures, error
            )

    def record_auth_failure(self, status: SourceAuthStatus) -> None:
        """Called when sync fails due to auth gate."""
        self.auth_status = status
        self.consecutive_failures += 1
        self.last_error = f"auth_{status.value}"
        if self.state != ServiceState.WAITING_FOR_AUTH:
            self.state = ServiceState.WAITING_FOR_AUTH
            self._state_since = datetime.now(UTC)
            logger.critical("SYNC_STUCK: auth status is %s — run `just t3k-login`", status.value)

    def record_auth_healthy(self, status: SourceAuthStatus) -> None:
        """Called when auth status is checked and found healthy."""
        self.auth_status = status
        if self.state == ServiceState.WAITING_FOR_AUTH:
            self.state = ServiceState.HEALTHY
            self.consecutive_failures = 0
            self._state_since = datetime.now(UTC)
            logger.info("Auth recovered to %s — resuming normal sync", status.value)

    def get_scheduler_interval(self, base_interval: float) -> float:
        """Return interval for the scheduler based on current state.

        Backs off when waiting for auth: 60s -> 300s -> 600s (capped).
        """
        if self.state != ServiceState.WAITING_FOR_AUTH:
            return base_interval
        if self.consecutive_failures <= 3:
            return 300.0
        return 600.0

    def health_response(self) -> dict[str, str | None]:
        """Build the health endpoint response body."""
        if self.state == ServiceState.HEALTHY:
            return {"status": "healthy"}
        return {
            "status": self.state.value,
            "reason": self.last_error,
            "since": self._state_since.isoformat() if self._state_since else None,
        }
