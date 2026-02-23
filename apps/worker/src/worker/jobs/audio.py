"""Per-Chain Audio Processing Job Handler.

This module provides the SHOOTOUT_AUDIO job handler that processes
a single signal chain through the audio pipeline, saves output,
measures loudness, and tracks progress.
"""

import os
from datetime import UTC, datetime
from logging import getLogger
from pathlib import Path
from uuid import UUID

import soundfile as sf
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from audio.processing.chain_executor import execute_signal_chain
from audio.processing.loudness import measure_loudness
from gts.domain.value_objects.job_status import JobStatus
from webapp.adapters.persistence.models.job import Job
from webapp.adapters.persistence.models.shootout import (
    AudioSegment,
    Shootout,
    ShootoutChain,
)
from webapp.adapters.persistence.models.signal_chain import SignalChain
from webapp.adapters.persistence.models.user_gear import UserGear
from worker.db import get_session_no_tx as get_session
from worker.main import broker

STORAGE_ROOT = Path(os.environ["GTS_STORAGE_ROOT"])
logger = getLogger(__name__)


async def _reconcile_parent(parent_job_id: UUID, database_url: str) -> None:
    """Best-effort parent reconciliation after child completion/failure."""
    try:
        from worker.jobs.shootout import reconcile_parent_after_audio

        await reconcile_parent_after_audio(parent_job_id, database_url)
    except Exception:
        logger.exception("Failed to reconcile parent shootout job %s", parent_job_id)


async def _resolve_gear_paths(
    session: AsyncSession,
    signal_chain: SignalChain,
) -> dict[str, Path]:
    """Pre-resolve all gear file paths for a signal chain's blocks.

    Queries UserGear -> GearModel -> file_path for each block, returning
    a dict keyed by str(user_gear_id) -> absolute Path on disk.
    """
    paths: dict[str, Path] = {}

    for block in signal_chain.blocks:
        if block.user_gear_id is None:
            continue
        ug_id = str(block.user_gear_id)
        if ug_id in paths:
            continue

        stmt = (
            select(UserGear)
            .where(UserGear.id == block.user_gear_id)
            .options(joinedload(UserGear.gear_model))
        )
        result = await session.execute(stmt)
        user_gear = result.unique().scalar_one_or_none()

        if user_gear is None:
            raise ValueError(f"UserGear {ug_id} not found")

        gear_model = user_gear.gear_model
        if gear_model.file_path is None:
            raise ValueError(
                f"GearModel {gear_model.id} has no file_path "
                f"(download_status={gear_model.download_status})"
            )

        paths[ug_id] = STORAGE_ROOT / gear_model.file_path

    return paths


@broker.task(retry_on_error=True, max_retries=2)
async def handle_shootout_audio_job(job_id: UUID) -> None:
    """Handle SHOOTOUT_AUDIO job by processing a single signal chain.

    This job:
    1. Loads the job to get shootout chain ID
    2. Loads shootout chain, signal chain (with blocks), and DI track
    3. Reads DI audio from file
    4. Processes audio through signal chain
    5. Saves output as FLAC
    6. Measures loudness and creates AudioSegment record

    Args:
        job_id: The ID of the SHOOTOUT_AUDIO job

    Raises:
        RuntimeError: If job processing fails
    """
    database_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://gts:gts@db:5432/gts_core")
    parent_job_id: UUID | None = None

    try:
        async with get_session(database_url) as session:
            # Load job to get shootout chain ID
            stmt = select(Job).where(Job.id == job_id)
            result = await session.execute(stmt)
            job = result.unique().scalar_one_or_none()

            if job is None:
                raise ValueError(f"Job {job_id} not found")

            shootout_chain_id = job.entity_id
            if shootout_chain_id is None:
                raise ValueError(f"Job {job_id} has no entity_id set")
            parent_job_id = job.parent_job_id

            # Mark job as running before loading and processing assets.
            job.status = JobStatus.RUNNING
            job.started_at = datetime.now(UTC)
            job.last_heartbeat = datetime.now(UTC)
            await session.commit()

            # Load shootout chain with signal chain and blocks
            stmt = (
                select(ShootoutChain)
                .where(ShootoutChain.id == shootout_chain_id)
                .options(
                    joinedload(ShootoutChain.signal_chain).joinedload(SignalChain.blocks),
                    joinedload(ShootoutChain.shootout).joinedload(Shootout.di_track),
                )
            )
            result = await session.execute(stmt)
            shootout_chain = result.unique().scalar_one_or_none()

            if shootout_chain is None:
                raise ValueError(f"ShootoutChain {shootout_chain_id} not found")

            signal_chain = shootout_chain.signal_chain
            shootout = shootout_chain.shootout
            di_track = shootout.di_track

            if di_track is None:
                raise ValueError(f"Shootout {shootout.id} has no DI track")

            # Read DI audio file
            di_audio, sample_rate = sf.read(di_track.file_path)

            # Update job progress to 50 (loading complete)
            job.progress = 50
            job.last_heartbeat = datetime.now(UTC)
            await session.commit()

            # Pre-resolve all gear file paths, then process
            gear_paths = await _resolve_gear_paths(session, signal_chain)
            processed_audio = await execute_signal_chain(
                signal_chain,
                di_audio,
                sample_rate,
                lambda ug_id, _gt: gear_paths[ug_id],
            )

            # Update job progress to 90 (processing complete)
            job.progress = 90
            job.last_heartbeat = datetime.now(UTC)
            await session.commit()

            # Save output as FLAC under the canonical shootout artifact directory.
            output_dir = STORAGE_ROOT / "audio" / str(shootout.id) / "segments"
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / f"{shootout_chain.position:02d}_{shootout_chain_id}.flac"
            sf.write(str(output_path), processed_audio, sample_rate)

            # Measure loudness
            integrated_lufs, peak_dbfs = measure_loudness(output_path)

            # Calculate duration
            duration_seconds = len(processed_audio) / sample_rate

            # Idempotent upsert of AudioSegment per shootout_chain_id.
            segment_stmt = select(AudioSegment).where(
                AudioSegment.shootout_chain_id == shootout_chain_id
            )
            segment_result = await session.execute(segment_stmt)
            existing_segments = segment_result.scalars().all()
            if existing_segments:
                audio_segment = existing_segments[0]
                audio_segment.file_path = str(output_path)
                audio_segment.duration_seconds = duration_seconds
                audio_segment.integrated_lufs = integrated_lufs
                audio_segment.peak_dbfs = peak_dbfs
                for duplicate in existing_segments[1:]:
                    await session.delete(duplicate)
            else:
                audio_segment = AudioSegment(
                    shootout_chain_id=shootout_chain_id,
                    file_path=str(output_path),
                    duration_seconds=duration_seconds,
                    integrated_lufs=integrated_lufs,
                    peak_dbfs=peak_dbfs,
                )
                session.add(audio_segment)

            # Update job progress to 100 (complete)
            job.progress = 100
            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.now(UTC)
            job.last_heartbeat = datetime.now(UTC)

            await session.commit()

        if parent_job_id is not None:
            await _reconcile_parent(parent_job_id, database_url)

    except Exception as e:
        # Mark job as failed
        failed_parent_job_id: UUID | None = None
        async with get_session(database_url) as session:
            stmt = select(Job).where(Job.id == job_id)
            result = await session.execute(stmt)
            job = result.unique().scalar_one_or_none()

            if job is not None:
                job.status = JobStatus.FAILED
                job.error = str(e)
                failed_parent_job_id = job.parent_job_id
                await session.commit()

        if failed_parent_job_id is not None:
            await _reconcile_parent(failed_parent_job_id, database_url)

        raise RuntimeError(f"Audio job {job_id} failed: {e}") from e
