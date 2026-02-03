"""GTS Scheduler - TaskIQ scheduled job definitions.

This module provides the TaskIQ scheduler configuration and scheduled tasks.
"""

# Import broker from worker
# In production this will be the shared Redis broker
from taskiq import InMemoryBroker, TaskiqScheduler
from taskiq.schedule_sources import LabelScheduleSource

broker = InMemoryBroker()

# Scheduler instance
scheduler = TaskiqScheduler(
    broker=broker,
    sources=[LabelScheduleSource(broker)],
)
