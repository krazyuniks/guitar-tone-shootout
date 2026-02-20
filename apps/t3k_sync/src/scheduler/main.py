"""Scheduler compatibility entrypoint."""

import logging

from taskiq import TaskiqScheduler
from taskiq.scheduler.scheduled_task import ScheduledTask
from taskiq_redis import ListQueueBroker

from scheduler.config import SchedulerSettings
from scheduler.schedules import auth, backup, jobs
from scheduler.source import InProcessScheduleSource

logger = logging.getLogger(__name__)

settings = SchedulerSettings()  # type: ignore[call-arg]

broker = ListQueueBroker(settings.redis_url)
broker._redis_url = settings.redis_url  # type: ignore[attr-defined]

_schedule_source = InProcessScheduleSource(jobs, backup, auth)


class InProcessScheduler(TaskiqScheduler):
    """Execute scheduled tasks directly in the scheduler process."""

    async def on_ready(self, source: object, task: ScheduledTask) -> None:
        """Execute the task in-process instead of dispatching to broker."""
        if not isinstance(source, InProcessScheduleSource):
            await super().on_ready(source, task)  # type: ignore[arg-type]
            return

        handler = source.get_handler(task.task_name)
        if handler is None:
            logger.error("Unknown scheduled task: %s", task.task_name)
            return

        logger.info("Running scheduled task: %s", task.task_name)
        try:
            await handler(*task.args, **task.kwargs)
        except Exception:
            logger.exception("Scheduled task %s failed", task.task_name)

        source.post_send(task)


scheduler = InProcessScheduler(
    broker=broker,
    sources=[_schedule_source],
)


async def startup_self_check() -> None:
    """Log all discovered scheduled tasks; fail fast if none registered."""
    await _schedule_source.startup()
    schedules = await _schedule_source.get_schedules()

    if not schedules:
        logger.critical(
            "Scheduler startup failed: zero scheduled tasks discovered. "
            "Check that schedule modules are correctly imported.",
        )
        raise RuntimeError("No scheduled tasks registered — aborting startup")

    for task in schedules:
        logger.info(
            "Registered scheduled task: %s (interval=%s, cron=%s)",
            task.task_name,
            task.interval,
            task.cron,
        )
    logger.info("Scheduler startup complete: %d task(s) registered", len(schedules))
