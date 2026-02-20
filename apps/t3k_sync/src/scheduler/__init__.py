"""Scheduler compatibility module backed by the t3k-sync app."""

__version__ = "0.1.0"

from scheduler import config, lock

__all__ = ["config", "lock"]


def _get_scheduler():  # type: ignore[no-untyped-def]
    """Lazy import of scheduler to avoid requiring env vars at import time."""
    from scheduler.main import scheduler

    return scheduler
