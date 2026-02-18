"""In-memory API call tracker with time-windowed metrics.

Provides a circular buffer of API call records with success/failure tracking.
Thread-safe via Lock. Module-level singleton via get_tracker().
"""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class APICallMetrics:
    """Aggregated metrics for a time window."""

    window_seconds: int
    successful: int
    failed: int
    avg_success_per_minute: float
    avg_failure_per_minute: float


# 24 hours of retention
_MAX_AGE_SECONDS = 86400


class APICallTracker:
    """Thread-safe in-memory tracker for API call success/failure."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._records: deque[tuple[float, bool]] = deque()

    def record_success(self) -> None:
        """Record a successful API call."""
        self._append(success=True)

    def record_failure(self) -> None:
        """Record a failed API call."""
        self._append(success=False)

    def get_metrics(self) -> list[APICallMetrics]:
        """Return aggregated metrics for 1m, 5m, 1h, 1d windows."""
        windows = [60, 300, 3600, 86400]
        now = time.monotonic()
        with self._lock:
            self._prune(now)
            results = []
            for window in windows:
                cutoff = now - window
                success = 0
                failed = 0
                for ts, ok in self._records:
                    if ts >= cutoff:
                        if ok:
                            success += 1
                        else:
                            failed += 1
                minutes = window / 60
                results.append(
                    APICallMetrics(
                        window_seconds=window,
                        successful=success,
                        failed=failed,
                        avg_success_per_minute=round(success / minutes, 2),
                        avg_failure_per_minute=round(failed / minutes, 2),
                    )
                )
            return results

    def _append(self, *, success: bool) -> None:
        now = time.monotonic()
        with self._lock:
            self._records.append((now, success))
            self._prune(now)

    def _prune(self, now: float) -> None:
        cutoff = now - _MAX_AGE_SECONDS
        while self._records and self._records[0][0] < cutoff:
            self._records.popleft()


_tracker: APICallTracker | None = None
_tracker_lock = threading.Lock()


def get_tracker() -> APICallTracker:
    """Return the module-level singleton tracker."""
    global _tracker
    if _tracker is None:
        with _tracker_lock:
            if _tracker is None:
                _tracker = APICallTracker()
    return _tracker
