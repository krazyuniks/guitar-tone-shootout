"""Message bus port for pgmq-backed command and event transport."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from datetime import datetime


@dataclass(frozen=True, slots=True)
class QueueMessage:
    """Message pulled from pgmq with retry metadata."""

    msg_id: int
    read_ct: int
    message: dict[str, Any]
    enqueued_at: datetime | None = None
    vt: datetime | None = None


@runtime_checkable
class MessageEnvelopeLike(Protocol):
    """Structural type for models that can dump themselves into queue payloads."""

    def model_dump(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        """Serialize the message to a JSON-compatible dictionary."""
        ...


class MessageBus(Protocol):
    """Protocol for queue operations used by consumers and publishers."""

    async def send(
        self,
        queue_name: str,
        message: dict[str, Any] | MessageEnvelopeLike,
    ) -> int:
        """Publish a message to a queue and return the new pgmq message ID."""
        ...

    async def read(
        self,
        queue_name: str,
        *,
        visibility_timeout: int,
        batch_size: int,
    ) -> list[QueueMessage]:
        """Read a batch of messages with a visibility timeout."""
        ...

    async def archive(self, queue_name: str, msg_id: int) -> bool:
        """Archive a processed queue message."""
        ...

    async def set_vt(self, queue_name: str, msg_id: int, visibility_timeout: int) -> None:
        """Extend an in-flight message's visibility timeout (lease renewal)."""
        ...

    async def create_queue(self, queue_name: str) -> None:
        """Create a pgmq queue if it does not exist."""
        ...

    async def drop_queue(self, queue_name: str) -> None:
        """Drop a pgmq queue."""
        ...
