"""GTS Messaging Infrastructure.

Provides pgmq client, consumer base class, and message envelope contracts
for cross-BC command and event transport.
"""

from messaging.commands import ProcessAudioCommand, RenderVideoCommand, SyncGearCommand
from messaging.consumer_base import BaseConsumer
from messaging.envelope import MessageEnvelope
from messaging.events import AudioProcessedEvent, GearSyncedEvent, VideoRenderedEvent
from messaging.message_bus import MessageBus, MessageEnvelopeLike, QueueMessage
from messaging.pgmq_client import PgmqClient

__all__ = [
    "AudioProcessedEvent",
    "BaseConsumer",
    "GearSyncedEvent",
    "MessageBus",
    "MessageEnvelope",
    "MessageEnvelopeLike",
    "PgmqClient",
    "ProcessAudioCommand",
    "QueueMessage",
    "RenderVideoCommand",
    "SyncGearCommand",
    "VideoRenderedEvent",
]
