"""Message lease renewal while a render runs (docs/design/job-system-contract.md).

While a handler works a message, a background task on its own short-lived
session extends the pgmq visibility timeout and renews the job heartbeat every
HEARTBEAT_INTERVAL_SECONDS. A live render therefore holds its lease exactly as
long as it is genuinely alive - no speculative p99 visibility constant - and a
crashed worker's message becomes visible again within VT_EXTENSION_SECONDS.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from gts.domain.value_objects.job_status import JobStatus
from messaging.consumer_base import HEARTBEAT_INTERVAL_SECONDS, VT_EXTENSION_SECONDS
from messaging.db import get_session_no_tx as get_session
from messaging.pgmq_client import PgmqClient
from webapp.services.job_transitions import TransitionError, transition_job

if TYPE_CHECKING:
    from uuid import UUID

logger = logging.getLogger(__name__)


class MessageLease:
    """Async context manager renewing a message lease while work runs.

    Each beat, on one fresh session and one commit: set_vt pushes the message's
    visibility to now + VT_EXTENSION_SECONDS, and the RUNNING -> RUNNING
    renewal through the transition service refreshes job.last_heartbeat. A
    terminal job stops the beats (the work finished under us - e.g. reaped).
    """

    def __init__(
        self,
        database_url: str,
        queue_name: str,
        msg_id: int,
        job_id: UUID,
        *,
        interval_seconds: float = HEARTBEAT_INTERVAL_SECONDS,
    ) -> None:
        self._database_url = database_url
        self._queue_name = queue_name
        self._msg_id = msg_id
        self._job_id = job_id
        self._interval_seconds = interval_seconds
        self._task: asyncio.Task[None] | None = None

    async def __aenter__(self) -> MessageLease:
        self._task = asyncio.create_task(self._run())
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        if self._task is not None:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
            self._task = None

    async def _run(self) -> None:
        while True:
            await asyncio.sleep(self._interval_seconds)
            try:
                async with get_session(self._database_url) as session:
                    # set_vt stages on the session; transition_job's commit
                    # lands both the lease extension and the heartbeat.
                    await PgmqClient(session).set_vt(
                        self._queue_name, self._msg_id, VT_EXTENSION_SECONDS
                    )
                    await transition_job(session, self._job_id, JobStatus.RUNNING, renewal=True)
            except TransitionError as exc:
                # The job reached a state that cannot renew (terminal, or a
                # reap won the race): stop beating, let the handler finish.
                logger.info("Lease renewal stopped for job %s: %s", self._job_id, exc)
                return
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Lease renewal beat failed for job %s", self._job_id)
