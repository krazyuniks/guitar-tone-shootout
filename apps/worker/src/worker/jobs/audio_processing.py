"""Compatibility wrapper for AUDIO_PROCESSING tasks.

The processing implementation now lives in `audio_worker.consumer`.
"""

from uuid import UUID

from audio_worker.consumer import process_audio_job
from worker.main import broker


@broker.task(retry_on_error=True, max_retries=2)
async def handle_audio_processing(job_id: UUID) -> None:
    """Handle AUDIO_PROCESSING by delegating to audio-worker code."""
    await process_audio_job(job_id)
