"""TaskIQ task for processing shootout jobs.

This module defines the background task that runs the pipeline processing
for shootout comparisons, with progress reporting via Redis pub/sub.
"""

import json
import logging
from pathlib import Path
from uuid import UUID

from app.core.database import async_session_factory
from app.core.redis import publish_job_progress
from app.models.job import JobStatus
from app.services.job_service import JobService
from app.services.pipeline_service import (
    EffectConfig,
    PipelineError,
    PipelineService,
    ShootoutConfig,
    ToneConfig,
)
from app.tasks.broker import broker

logger = logging.getLogger(__name__)


@broker.task
async def process_shootout_task(
    job_id: str,
    di_track_path: str,
    config_json: str,
) -> dict[str, str]:
    """Process a shootout job.

    This task is run by TaskIQ workers to process a shootout comparison.
    It updates job status in the database and publishes progress via Redis.

    Args:
        job_id: The job UUID as string.
        di_track_path: Path to the uploaded DI track file.
        config_json: JSON-encoded shootout configuration.

    Returns:
        Dict with output paths.

    Raises:
        PipelineError: If processing fails.
    """
    logger.info("Starting shootout task for job %s", job_id)
    job_uuid = UUID(job_id)

    async def progress_callback(percent: int, message: str) -> None:
        """Report progress to database and Redis pub/sub."""
        await _update_job_progress(job_uuid, percent, message)
        await publish_job_progress(
            job_id=job_id,
            status=JobStatus.RUNNING.value,
            progress=percent,
            message=message,
        )

    try:
        # Mark job as running
        await _update_job_status(job_uuid, JobStatus.RUNNING)
        await publish_job_progress(
            job_id=job_id,
            status=JobStatus.RUNNING.value,
            progress=0,
            message="Starting...",
        )

        # Parse configuration
        config = _parse_config(config_json)

        # Create pipeline service
        service = PipelineService(progress_callback=progress_callback)

        # Run the pipeline
        result = await service.run_shootout(
            job_id=job_id,
            config=config,
            di_track_path=Path(di_track_path),
        )

        # Mark job as completed
        await _complete_job(job_uuid, result["video"])
        await publish_job_progress(
            job_id=job_id,
            status=JobStatus.COMPLETED.value,
            progress=100,
            message="Complete!",
        )

        logger.info("Shootout task completed for job %s", job_id)
        return result

    except PipelineError as e:
        logger.error("Pipeline error for job %s: %s", job_id, e)
        await _fail_job(job_uuid, str(e))
        await publish_job_progress(
            job_id=job_id,
            status=JobStatus.FAILED.value,
            progress=0,
            message=str(e),
        )
        raise

    except Exception as e:
        logger.exception("Unexpected error for job %s: %s", job_id, e)
        await _fail_job(job_uuid, f"Unexpected error: {e}")
        await publish_job_progress(
            job_id=job_id,
            status=JobStatus.FAILED.value,
            progress=0,
            message=f"Unexpected error: {e}",
        )
        raise PipelineError(f"Unexpected error: {e}") from e


def _parse_config(config_json: str) -> ShootoutConfig:
    """Parse JSON configuration into ShootoutConfig.

    Args:
        config_json: JSON-encoded configuration.

    Returns:
        ShootoutConfig object.
    """
    data = json.loads(config_json)

    tones: list[ToneConfig] = []
    for tone_data in data.get("tones", []):
        effects: list[EffectConfig] = []
        for effect_data in tone_data.get("effects", []):
            effects.append(
                EffectConfig(
                    effect_type=effect_data["effect_type"],
                    value=effect_data["value"],
                )
            )

        tones.append(
            ToneConfig(
                name=tone_data["name"],
                model_path=tone_data.get("model_path"),
                ir_path=tone_data.get("ir_path"),
                tone3000_model_id=tone_data.get("tone3000_model_id"),
                description=tone_data.get("description"),
                highpass=tone_data.get("highpass", True),
                effects=effects,
            )
        )

    return ShootoutConfig(
        name=data["name"],
        tones=tones,
        author=data.get("author"),
        description=data.get("description"),
        guitar=data.get("guitar"),
        pickup=data.get("pickup"),
    )


async def _update_job_status(job_id: UUID, status: JobStatus) -> None:
    """Update job status in the database.

    Args:
        job_id: The job UUID.
        status: New job status.
    """
    async with async_session_factory() as db:
        service = JobService(db)
        await service.update_job_progress(
            job_id=job_id,
            status=status,
            progress=0,
        )
        await db.commit()


async def _update_job_progress(job_id: UUID, progress: int, message: str) -> None:
    """Update job progress in the database.

    Args:
        job_id: The job UUID.
        progress: Progress percentage (0-100).
        message: Status message.
    """
    async with async_session_factory() as db:
        service = JobService(db)
        await service.update_job_progress(
            job_id=job_id,
            status=JobStatus.RUNNING,
            progress=progress,
            message=message,
        )
        await db.commit()


async def _complete_job(job_id: UUID, result_path: str) -> None:
    """Mark job as completed in the database.

    Args:
        job_id: The job UUID.
        result_path: Path to the output file.
    """
    async with async_session_factory() as db:
        service = JobService(db)
        await service.complete_job(job_id=job_id, result_path=result_path)
        await db.commit()


async def _fail_job(job_id: UUID, error: str) -> None:
    """Mark job as failed in the database.

    Args:
        job_id: The job UUID.
        error: Error message.
    """
    async with async_session_factory() as db:
        service = JobService(db)
        await service.fail_job(job_id=job_id, error=error)
        await db.commit()
