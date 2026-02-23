"""Master Audio Creation Job.

This module creates a master audio file for a shootout by:
1. Loading all audio segments for the shootout
2. Normalising each segment to -14.0 LUFS
3. Updating AudioSegment records with post-normalisation loudness values
4. Concatenating segments in chain position order
5. Creating chapter markers
6. Saving the master audio as FLAC
7. Updating the shootout's output_path field
"""

import os
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import numpy as np
import soundfile as sf
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from audio.processing.loudness import normalize_loudness
from gts.domain.value_objects.job_status import JobStatus
from webapp.adapters.persistence.models.job import Job
from webapp.adapters.persistence.models.shootout import ShootoutStatus
from worker.db import get_session, get_session_no_tx
from worker.main import broker

STORAGE_ROOT = Path(os.environ["GTS_STORAGE_ROOT"])


async def create_master_audio(
    shootout_id: UUID,
    database_url: str | None = None,
    job_id: UUID | None = None,
) -> None:
    """Create master audio file for a shootout.

    Args:
        shootout_id: UUID of the shootout to process
        database_url: Database connection string (or None to use DATABASE_URL env var)
        job_id: Optional job ID for heartbeat updates during processing

    Raises:
        ValueError: If shootout is not found
    """
    if database_url is None:
        database_url = os.environ.get("DATABASE_URL", "")

    async with get_session(database_url) as session:
        from webapp.adapters.persistence.models.shootout import Shootout, ShootoutChain

        stmt = (
            select(Shootout)
            .where(Shootout.id == shootout_id)
            .options(joinedload(Shootout.chains).joinedload(ShootoutChain.segments))
        )
        result = await session.execute(stmt)
        shootout = result.unique().scalar_one_or_none()

        if shootout is None:
            raise ValueError(f"Shootout {shootout_id} not found")

        # Handle empty shootout (no chains)
        if not shootout.chains:
            return

        chains = sorted(shootout.chains, key=lambda c: c.position)

        total_segments = sum(len(chain.segments) for chain in chains)
        if total_segments == 0:
            return

        # Create output directory for shootout artifacts.
        output_dir = STORAGE_ROOT / "audio" / str(shootout_id)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Process each segment: normalize and update loudness values
        normalized_files = []
        for chain_idx, chain in enumerate(chains, 1):
            for segment in chain.segments:
                input_path = Path(segment.file_path)
                normalized_path = output_dir / f"normalized_{input_path.name}"

                # Normalize loudness to -14.0 LUFS
                result_lufs, result_peak_dbfs = normalize_loudness(
                    input_path, normalized_path, target_lufs=-14.0
                )

                segment.integrated_lufs = result_lufs
                segment.peak_dbfs = result_peak_dbfs
                normalized_files.append(normalized_path)

            # Update heartbeat after each chain to avoid stale heartbeat detection
            if job_id is not None:
                async with get_session_no_tx(database_url) as hb_session:
                    hb_stmt = select(Job).where(Job.id == job_id)
                    hb_result = await hb_session.execute(hb_stmt)
                    hb_job = hb_result.scalar_one_or_none()
                    if hb_job is not None:
                        hb_job.last_heartbeat = datetime.now(UTC)
                        hb_job.progress = 10 + int(70 * chain_idx / len(chains))
                        await hb_session.commit()

        audio_arrays = []
        sample_rate = None
        for norm_file in normalized_files:
            audio_data, sr = sf.read(norm_file)
            audio_arrays.append(audio_data)
            if sample_rate is None:
                sample_rate = sr

        master_audio = np.concatenate(audio_arrays)

        chapters = []
        current_time = 0.0
        for chain in chains:
            for segment in chain.segments:
                duration = segment.duration_seconds or 0.0
                chapters.append(
                    {
                        "label": chain.label,
                        "start_time": current_time,
                        "end_time": current_time + duration,
                    }
                )
                current_time += duration

        # Save master audio as FLAC
        master_path = output_dir / "master.flac"
        sf.write(master_path, master_audio, sample_rate)

        shootout.output_path = str(master_path)

        await session.commit()


@broker.task(retry_on_error=True, max_retries=2)
async def handle_shootout_master_job(job_id: UUID) -> None:
    """Handle SHOOTOUT_MASTER job by creating the master audio artifact."""
    database_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://gts:gts@db:5432/gts_core")
    shootout_id: UUID | None = None

    try:
        async with get_session_no_tx(database_url) as session:
            stmt = select(Job).where(Job.id == job_id)
            result = await session.execute(stmt)
            job = result.scalar_one_or_none()
            if job is None:
                raise ValueError(f"Job {job_id} not found")
            if job.entity_id is None:
                raise ValueError(f"Job {job_id} has no entity_id set")

            shootout_id = job.entity_id
            job.status = JobStatus.RUNNING
            if job.started_at is None:
                job.started_at = datetime.now(UTC)
            job.last_heartbeat = datetime.now(UTC)
            job.progress = 10
            job.message = "Creating master audio"
            await session.commit()

        await create_master_audio(shootout_id, database_url, job_id=job_id)

        async with get_session_no_tx(database_url) as session:
            stmt = select(Job).where(Job.id == job_id)
            result = await session.execute(stmt)
            job = result.scalar_one_or_none()
            if job is None:
                return

            job.status = JobStatus.COMPLETED
            job.progress = 100
            job.completed_at = datetime.now(UTC)
            job.last_heartbeat = datetime.now(UTC)
            job.message = "Master audio created"

            if job.parent_job_id is not None:
                parent_stmt = select(Job).where(Job.id == job.parent_job_id)
                parent_result = await session.execute(parent_stmt)
                parent_job = parent_result.scalar_one_or_none()
                if parent_job is not None and parent_job.status != JobStatus.FAILED:
                    parent_job.status = JobStatus.COMPLETED
                    parent_job.progress = 100
                    parent_job.completed_at = datetime.now(UTC)
                    parent_job.message = "Audio processing complete"

            from webapp.adapters.persistence.models.shootout import Shootout

            shootout_stmt = select(Shootout).where(Shootout.id == shootout_id)
            shootout_result = await session.execute(shootout_stmt)
            shootout = shootout_result.scalar_one_or_none()
            if shootout is not None:
                shootout.status = ShootoutStatus.COMPLETED

            await session.commit()

    except Exception as e:
        async with get_session_no_tx(database_url) as session:
            stmt = select(Job).where(Job.id == job_id)
            result = await session.execute(stmt)
            job = result.scalar_one_or_none()

            if job is not None:
                job.status = JobStatus.FAILED
                job.error = str(e)
                job.completed_at = datetime.now(UTC)

                if job.parent_job_id is not None:
                    parent_stmt = select(Job).where(Job.id == job.parent_job_id)
                    parent_result = await session.execute(parent_stmt)
                    parent_job = parent_result.scalar_one_or_none()
                    if parent_job is not None:
                        parent_job.status = JobStatus.FAILED
                        parent_job.error = f"Master audio stage failed: {e}"
                        parent_job.completed_at = datetime.now(UTC)

            if shootout_id is not None:
                from webapp.adapters.persistence.models.shootout import Shootout

                shootout_stmt = select(Shootout).where(Shootout.id == shootout_id)
                shootout_result = await session.execute(shootout_stmt)
                shootout = shootout_result.scalar_one_or_none()
                if shootout is not None:
                    shootout.status = ShootoutStatus.FAILED

            await session.commit()

        raise RuntimeError(f"Master audio job {job_id} failed: {e}") from e
