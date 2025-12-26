"""Background tasks module.

This module configures TaskIQ with Redis for background job processing.
Import the broker from here to register tasks.
"""

from app.tasks.broker import broker
from app.tasks.health import health_check

__all__ = ["broker", "health_check"]
