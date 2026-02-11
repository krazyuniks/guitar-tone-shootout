"""GTS Scheduler.

TaskIQ cron job scheduling.
"""

__version__ = "0.1.0"

# Make config and lock modules importable
from scheduler import config, lock

__all__ = ["config", "lock"]


def _get_scheduler():  # type: ignore[no-untyped-def]
    """Lazy import of scheduler to avoid requiring env vars at import time."""
    from scheduler.main import scheduler

    return scheduler
