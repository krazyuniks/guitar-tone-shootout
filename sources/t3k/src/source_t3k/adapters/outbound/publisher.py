"""GearSyncRecord pgmq publisher for T3K source adapter.

Converts T3K staging records to GearSyncRecord format and publishes them
to pgmq queues in gts_core. Transactional: staging record
update + enqueue happen in the same database transaction.
"""

import json
import logging
from pathlib import PurePosixPath
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import text

from gts.records.gear_sync import GearSyncRecord, SyncOperation
from source_t3k.adapters.outbound.models import T3KModelStaging, T3KToneStaging

logger = logging.getLogger(__name__)

# Map T3K gear values to core GearType enum values.
_GEAR_KIND_TO_GEAR_TYPE = {
    "amp": "amp",
    "pedal": "pedal",
    "full-rig": "full_rig",
    "outboard": "outboard",
    "ir": "ir",
}

# Map T3K platform values to core Platform enum values.
_T3K_PLATFORM_TO_CORE = {
    "nam": "nam",
    "aida-x": "aida_x",
    "ir": "ir",
}


class GearSyncPublisher:
    """Publisher for converting T3K staging records to GearSyncRecord and enqueueing."""

    def __init__(self, session: AsyncSession | None, queue_name: str = "source_events") -> None:
        self.session = session
        self.queue_name = queue_name

    def create_tone_sync_record(
        self, tone: T3KToneStaging, models: list[T3KModelStaging] | None = None
    ) -> GearSyncRecord:
        """Convert T3KToneStaging to GearSyncRecord."""
        platform = _T3K_PLATFORM_TO_CORE.get(tone.platform, tone.platform)
        gear_type = _GEAR_KIND_TO_GEAR_TYPE.get(tone.gear, tone.gear)

        models = models or []
        model_payloads = [
            {
                "source_record_id": str(model.id),
                "source_updated_at": model.updated_at.isoformat(),
                "name": model.name,
                "filename": PurePosixPath(model.model_url).name or model.name,
                "download_url": model.model_url,
                "size": model.size,
                "platform": platform,
                "tone_id": str(model.tone_id),
            }
            for model in models
        ]

        thumbnail_url = tone.images[0] if tone.images else ""

        payload: dict[str, Any] = {
            "name": tone.title,
            "description": tone.description,
            "thumbnail_url": thumbnail_url,
            "platform": platform,
            "gear_type": gear_type,
            "creator_id": tone.user_id,
            "created_at": tone.created_at.isoformat(),
            "downloads_count": tone.downloads_count,
            "favorites_count": tone.favorites_count,
            "models": model_payloads,
        }

        source_updated_at = tone.updated_at
        if models:
            source_updated_at = max([tone.updated_at, *[model.updated_at for model in models]])

        return GearSyncRecord(
            source_name="t3k",
            source_record_id=str(tone.id),
            source_updated_at=source_updated_at,
            operation=SyncOperation.CREATE,
            payload=payload,
        )

    async def publish_tone(
        self, tone: T3KToneStaging, models: list[T3KModelStaging] | None = None
    ) -> None:
        """Publish tone sync record to pgmq queue."""
        if self.session is None:
            return

        record = self.create_tone_sync_record(tone, models=models)
        await self._enqueue_message(record)

    async def _enqueue_message(self, record: GearSyncRecord) -> None:
        """Enqueue GearSyncRecord to pgmq queue."""
        if self.session is None:
            return

        message = record.to_dict()

        logger.debug("Enqueuing message to queue %s: %s", self.queue_name, message)
        await self.session.execute(
            text("SELECT pgmq.send(:queue_name, CAST(:message AS jsonb))"),
            {"queue_name": self.queue_name, "message": json.dumps(message)},
        )
