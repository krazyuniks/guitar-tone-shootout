"""Async pgmq client implementation backed by SQLAlchemy."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from sqlalchemy import text

from messaging.message_bus import MessageBus, MessageEnvelopeLike, QueueMessage

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class PgmqClient(MessageBus):
    """SQL-based pgmq wrapper.

    These methods intentionally do not commit. Callers can include queue writes
    in the same transaction as domain state changes (transactional outbox).
    """

    def __init__(
        self,
        session: AsyncSession,
        *,
        max_poll_seconds: int = 1,
        poll_interval_ms: int = 100,
    ) -> None:
        self._session = session
        self._max_poll_seconds = max_poll_seconds
        self._poll_interval_ms = poll_interval_ms

    async def send(
        self,
        queue_name: str,
        message: dict[str, Any] | MessageEnvelopeLike,
    ) -> int:
        """Publish a JSON message to the queue."""
        payload = (
            message.model_dump(mode="json") if isinstance(message, MessageEnvelopeLike) else message
        )
        stmt = text("SELECT pgmq.send(:queue, CAST(:message AS jsonb)) AS msg_id")
        result = await self._session.execute(
            stmt,
            {
                "queue": queue_name,
                "message": json.dumps(payload, default=str),
            },
        )
        return int(result.scalar_one())

    async def read(
        self,
        queue_name: str,
        *,
        visibility_timeout: int,
        batch_size: int,
    ) -> list[QueueMessage]:
        """Read queue messages with visibility timeout and batch size."""
        stmt = text(
            "SELECT * FROM pgmq.read_with_poll("
            "CAST(:queue AS text), "
            "CAST(:vt AS integer), "
            "CAST(:qty AS integer), "
            "CAST(:max_poll_seconds AS integer), "
            "CAST(:poll_interval_ms AS integer)"
            ")"
        )
        try:
            result = await self._session.execute(
                stmt,
                {
                    "queue": queue_name,
                    "vt": visibility_timeout,
                    "qty": batch_size,
                    "max_poll_seconds": self._max_poll_seconds,
                    "poll_interval_ms": self._poll_interval_ms,
                },
            )
        except Exception:
            # Clear failed transaction state so polling loops can recover.
            await self._session.rollback()
            raise

        return [
            QueueMessage(
                msg_id=int(row["msg_id"]),
                read_ct=int(row["read_ct"]),
                message=row["message"],
                enqueued_at=row["enqueued_at"],
                vt=row["vt"],
            )
            for row in result.mappings().all()
        ]

    async def archive(self, queue_name: str, msg_id: int) -> bool:
        """Archive a processed message by queue and pgmq message ID."""
        stmt = text("SELECT pgmq.archive(CAST(:queue AS text), CAST(:msg_id AS bigint))")
        result = await self._session.execute(
            stmt,
            {
                "queue": queue_name,
                "msg_id": msg_id,
            },
        )
        return bool(result.scalar_one())

    async def create_queue(self, queue_name: str) -> None:
        """Create queue if missing."""
        stmt = text("SELECT pgmq.create(CAST(:queue AS text))")
        await self._session.execute(stmt, {"queue": queue_name})

    async def drop_queue(self, queue_name: str) -> None:
        """Drop queue."""
        stmt = text("SELECT pgmq.drop_queue(CAST(:queue AS text))")
        await self._session.execute(stmt, {"queue": queue_name})
