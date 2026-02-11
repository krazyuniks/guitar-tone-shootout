"""GTS Scheduler - TaskIQ scheduled job definitions.

This module provides the TaskIQ scheduler configuration and scheduled tasks.
"""

from taskiq import TaskiqScheduler
from taskiq.schedule_sources import LabelScheduleSource
from taskiq_redis import ListQueueBroker

from scheduler.config import SchedulerSettings

# Load settings
# In production, REDIS_URL env var will be set by docker-compose
# In tests, conftest.py sets it
settings = SchedulerSettings()  # type: ignore[call-arg]

# Redis broker (shared with worker)
broker = ListQueueBroker(settings.redis_url)

# Store redis_url for test introspection
# (ListQueueBroker doesn't expose this directly)
broker._redis_url = settings.redis_url  # type: ignore[attr-defined]

# Scheduler instance
scheduler = TaskiqScheduler(
    broker=broker,
    sources=[LabelScheduleSource(broker)],
)
