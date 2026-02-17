"""In-process schedule source for TaskIQ.

Discovers async functions with schedule labels from imported modules
and executes them directly in the scheduler process (no broker dispatch).
"""

import logging
import uuid
from collections.abc import Callable, Coroutine
from types import ModuleType
from typing import Any

from taskiq.abc.schedule_source import ScheduleSource
from taskiq.scheduler.scheduled_task import ScheduledTask

logger = logging.getLogger(__name__)


class InProcessScheduleSource(ScheduleSource):
    """Schedule source that discovers tasks from module-level functions.

    Unlike LabelScheduleSource (which reads from broker-registered tasks),
    this source discovers plain async functions that have a ``labels``
    attribute containing ``{"schedule": [{"interval": N}]}`` metadata.
    """

    def __init__(self, *modules: ModuleType) -> None:
        self._modules = modules
        self._handlers: dict[str, Callable[..., Coroutine[Any, Any, Any]]] = {}
        self.schedules: dict[str, ScheduledTask] = {}

    async def startup(self) -> None:
        """Scan modules for functions with schedule labels."""
        self.schedules.clear()
        self._handlers.clear()

        for module in self._modules:
            for attr_name in dir(module):
                obj = getattr(module, attr_name)
                if not callable(obj):
                    continue
                labels = getattr(obj, "labels", None)
                if not isinstance(labels, dict):
                    continue
                schedule_list = labels.get("schedule", [])
                if not schedule_list:
                    continue

                task_name = f"{module.__name__}:{attr_name}"
                self._handlers[task_name] = obj

                for schedule in schedule_list:
                    if not isinstance(schedule, dict):
                        continue
                    if not {"cron", "interval", "time"} & schedule.keys():
                        continue

                    schedule_id = schedule.get("schedule_id", uuid.uuid4().hex)
                    self.schedules[schedule_id] = ScheduledTask(
                        task_name=task_name,
                        labels={},
                        schedule_id=schedule_id,
                        args=schedule.get("args", []),
                        kwargs=schedule.get("kwargs", {}),
                        cron=schedule.get("cron"),
                        time=schedule.get("time"),
                        cron_offset=schedule.get("cron_offset"),
                        interval=schedule.get("interval"),
                    )

        logger.info(
            "Discovered %d scheduled tasks from %d modules",
            len(self.schedules),
            len(self._modules),
        )

    async def get_schedules(self) -> list[ScheduledTask]:
        """Return all discovered schedules."""
        return list(self.schedules.values())

    def get_handler(self, task_name: str) -> Callable[..., Coroutine[Any, Any, Any]] | None:
        """Look up the original handler function by task name."""
        return self._handlers.get(task_name)

    def post_send(self, task: ScheduledTask) -> None:
        """Remove one-shot time tasks after firing."""
        if task.cron or not task.time:
            return
        self.schedules.pop(task.schedule_id, None)
