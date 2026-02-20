"""GTS Worker.

TaskIQ background jobs and pgmq message consumer.
Runs against the unified gts_core database.
"""

__version__ = "0.1.0"

from worker import config

__all__ = ["broker", "config"]


def __getattr__(name: str):
    """Lazily expose broker to avoid importing worker.main at package import time."""
    if name == "broker":
        from worker.main import broker

        return broker
    raise AttributeError(f"module 'worker' has no attribute {name!r}")
