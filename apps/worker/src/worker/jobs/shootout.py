"""Compatibility wrappers for shootout orchestration tasks.

The orchestration logic now lives in `video_worker.consumer`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import video_worker.consumer as video_consumer
from worker.main import broker

if TYPE_CHECKING:
    from uuid import UUID
else:
    UUID = Any

get_session = video_consumer.get_session
_video_dispatch_master_job = video_consumer._dispatch_master_job


def _bind_legacy_overrides() -> None:
    """Apply legacy override points before delegating into video-worker logic."""
    video_consumer.get_session = get_session  # type: ignore[assignment]
    video_consumer._dispatch_master_job = _dispatch_master_job  # type: ignore[assignment]


async def _dispatch_master_job(master_job_id: UUID, database_url: str) -> None:
    """Compatibility hook that can be monkeypatched by legacy tests."""
    await _video_dispatch_master_job(master_job_id, database_url)


@broker.task(retry_on_error=True, max_retries=2)
async def handle_shootout_job(job_id: UUID) -> None:
    """Handle SHOOTOUT via the dedicated video-worker implementation."""
    _bind_legacy_overrides()
    await video_consumer.process_shootout_job(job_id)


async def reconcile_parent_after_audio(parent_job_id: UUID, database_url: str) -> None:
    """Expose reconciliation helper for legacy worker audio task imports."""
    _bind_legacy_overrides()
    await video_consumer.reconcile_parent_after_audio(parent_job_id, database_url)


async def _update_parent_progress(parent_job_id: UUID, database_url: str) -> None:
    """Backwards-compatible alias for parent reconciliation."""
    _bind_legacy_overrides()
    await video_consumer._update_parent_progress(parent_job_id, database_url)
