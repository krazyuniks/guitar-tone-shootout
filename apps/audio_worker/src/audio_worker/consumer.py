"""Audio command consumer for the audio-worker container."""

from __future__ import annotations

import asyncio
import logging
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import UUID

import numpy as np
import soundfile as sf
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import joinedload

from audio.analysis.waveform import extract_waveform
from audio.processing import (
    ChainExecutionError,
    LoudnessError,
    ProcessingError,
    execute_signal_chain,
    normalize_loudness,
)
from audio_worker.lease import MessageLease
from gts.domain.value_objects.job_status import JobStatus, JobType
from messaging.commands import ProcessAudioCommand
from messaging.consumer_base import BaseConsumer, SkipMessage
from messaging.db import get_session_no_tx as get_session
from messaging.pgmq_client import PgmqClient
from webapp.adapters.persistence.models.job import Job
from webapp.adapters.persistence.models.shootout import (
    AudioSegment,
    Shootout,
    ShootoutChain,
    ShootoutStatus,
)
from webapp.adapters.persistence.models.signal_chain import SignalChain
from webapp.adapters.persistence.models.user_gear import UserGear
from webapp.services.job_transitions import (
    ClaimOutcome,
    claim_job,
    job_lease_is_live,
    mark_job_dead_lettered,
    transition_job,
)

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from gts.domain.value_objects.signal_chain_enums import GearType
    from messaging.envelope import MessageEnvelope

STORAGE_BASE = Path("/app/storage/audio")
TARGET_LUFS = -14.0

# One CPU-bound render at a time per worker; the event loop stays free for
# /health and the lease heartbeat throughout.
_render_gate = asyncio.Semaphore(1)


async def _process_shootout_audio(job_id: UUID, database_url: str) -> None:
    """Process a single SHOOTOUT_AUDIO job (one signal chain against the DI track).

    The consumer claimed the job (RUNNING) before dispatching here; this
    function only does the work and reports the terminal state through the
    transition service.
    """
    try:
        async with get_session(database_url) as session:
            # Load job again for entity_id
            job_stmt = select(Job).where(Job.id == job_id)
            job_result = await session.execute(job_stmt)
            job = job_result.scalar_one_or_none()
            if job is None:
                raise ValueError(f"Job {job_id} not found after start")

            shootout_chain_id = job.entity_id
            if shootout_chain_id is None:
                raise ValueError(f"Job {job_id} has no entity_id (shootout_chain_id)")

            # Load shootout chain with signal chain and blocks
            sc_stmt = (
                select(ShootoutChain)
                .where(ShootoutChain.id == shootout_chain_id)
                .options(
                    joinedload(ShootoutChain.shootout).joinedload(Shootout.di_track),
                    joinedload(ShootoutChain.signal_chain).joinedload(SignalChain.blocks),
                )
            )
            sc_result = await session.execute(sc_stmt)
            shootout_chain = sc_result.unique().scalar_one_or_none()
            if shootout_chain is None:
                raise ValueError(f"ShootoutChain {shootout_chain_id} not found")

            shootout = shootout_chain.shootout
            signal_chain = shootout_chain.signal_chain
            di_track = shootout.di_track
            if di_track is None:
                raise ValueError(f"Shootout {shootout.id} has no DI track")

            shootout_id = shootout.id
            render_version = shootout.render_version

            # Pre-load gear paths for chain blocks
            user_gear_ids = [
                b.user_gear_id for b in signal_chain.blocks if b.user_gear_id is not None
            ]
            gear_map: dict[str, Path] = {}
            if user_gear_ids:
                ug_stmt = (
                    select(UserGear)
                    .where(UserGear.id.in_(user_gear_ids))
                    .options(joinedload(UserGear.gear_model))
                )
                ug_result = await session.execute(ug_stmt)
                for ug in ug_result.unique().scalars().all():
                    if ug.gear_model.file_path:
                        gear_map[str(ug.id)] = Path(ug.gear_model.file_path)

        # Load DI audio
        di_path = Path(di_track.file_path)
        if not di_path.exists():
            raise ProcessingError(f"DI track file not found: {di_path}")

        di_audio, sample_rate = sf.read(str(di_path))
        # Convert stereo to mono if needed
        if di_audio.ndim == 2:
            di_audio = np.mean(di_audio, axis=1)

        # Build gear path resolver
        def gear_path_resolver(user_gear_id: str, gear_type: GearType) -> Path:
            path = gear_map.get(user_gear_id)
            if path is None:
                raise ChainExecutionError(f"No file for user_gear {user_gear_id}")
            return path

        # Execute signal chain
        logger.info(
            "Processing chain %s for shootout %s (%d blocks)",
            shootout_chain_id,
            shootout_id,
            len(signal_chain.blocks),
        )
        async with _render_gate:
            processed_audio = await asyncio.to_thread(
                execute_signal_chain, signal_chain, di_audio, sample_rate, gear_path_resolver
            )

        # Write processed audio to temp file, then normalise into the
        # per-version directory (ADR-0004): a render only ever writes inside
        # its own version and never touches files an existing manifest pins.
        output_dir = STORAGE_BASE / str(shootout_id) / f"v{render_version}"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{shootout_chain_id}.wav"

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            sf.write(str(tmp_path), processed_audio, sample_rate)
            result_lufs, result_peak = normalize_loudness(tmp_path, output_path, TARGET_LUFS)
        finally:
            tmp_path.unlink(missing_ok=True)

        # Extract waveform data
        waveform = extract_waveform(output_path)

        # Measure duration from output
        info = sf.info(str(output_path))
        duration_seconds = info.duration

        # Upsert the segment on its idempotency key and complete the job in
        # ONE transaction: a redelivered message that re-renders can never
        # duplicate a segment row, and the segment write commits with the
        # COMPLETED transition (which also reconciles the parent).
        async with get_session(database_url) as session:
            upsert = (
                pg_insert(AudioSegment)
                .values(
                    shootout_chain_id=shootout_chain_id,
                    file_path=str(output_path),
                    duration_seconds=duration_seconds,
                    integrated_lufs=result_lufs,
                    peak_dbfs=result_peak,
                    waveform=waveform,
                    version=render_version,
                )
                .on_conflict_do_update(
                    constraint="uq_audio_segments_chain_version",
                    set_={
                        "file_path": str(output_path),
                        "duration_seconds": duration_seconds,
                        "integrated_lufs": result_lufs,
                        "peak_dbfs": result_peak,
                        "waveform": waveform,
                    },
                )
            )
            await session.execute(upsert)
            await transition_job(
                session,
                job_id,
                JobStatus.COMPLETED,
                progress=100,
                result_path=str(output_path),
            )

        logger.info(
            "Completed chain %s: lufs=%.1f peak=%.1f duration=%.1fs",
            shootout_chain_id,
            result_lufs,
            result_peak,
            duration_seconds,
        )

    except (ChainExecutionError, ProcessingError, LoudnessError) as exc:
        logger.error("Chain processing failed for job %s: %s", job_id, exc)
        async with get_session(database_url) as session:
            # FAILED applies retry bookkeeping and reconciles the parent.
            await transition_job(session, job_id, JobStatus.FAILED, error=str(exc))


async def _process_shootout_master(job_id: UUID, database_url: str) -> None:
    """Process a SHOOTOUT_MASTER job (concatenate all chain segments into master).

    Claimed by the consumer before dispatch; terminal states route through the
    transition service. The direct shootout/parent COMPLETED projection below
    is the legacy publish path DOM-shootout-finalise replaces with the
    SHOOTOUT_FINALISE manifest write.
    """
    try:
        async with get_session(database_url) as session:
            job_stmt = select(Job).where(Job.id == job_id)
            job_result = await session.execute(job_stmt)
            job = job_result.scalar_one_or_none()
            if job is None:
                raise ValueError(f"Job {job_id} not found after start")

            shootout_id = job.entity_id
            if shootout_id is None:
                raise ValueError(f"Job {job_id} has no entity_id (shootout_id)")

            # Load shootout with chains and their segments
            s_stmt = (
                select(Shootout)
                .where(Shootout.id == shootout_id)
                .options(
                    joinedload(Shootout.chains).joinedload(ShootoutChain.segments),
                )
            )
            s_result = await session.execute(s_stmt)
            shootout = s_result.unique().scalar_one_or_none()
            if shootout is None:
                raise ValueError(f"Shootout {shootout_id} not found")

        # Collect and concatenate audio from all chain segments (ordered by
        # chain position). Segments are pinned to this run's render version -
        # never segments[0], which is undefined after a redelivery or rerun.
        render_version = shootout.render_version
        sorted_chains = sorted(shootout.chains, key=lambda c: c.position)
        all_audio: list[np.ndarray] = []
        sample_rate: int | None = None

        for chain in sorted_chains:
            versioned = [seg for seg in chain.segments if seg.version == render_version]
            if not versioned:
                raise ProcessingError(
                    f"Chain {chain.id} has no audio segment for version {render_version}"
                )
            segment = versioned[0]
            seg_path = Path(segment.file_path)
            if not seg_path.exists():
                raise ProcessingError(f"Segment file not found: {seg_path}")

            audio, sr = sf.read(str(seg_path))
            if audio.ndim == 2:
                audio = np.mean(audio, axis=1)
            if sample_rate is None:
                sample_rate = sr
            all_audio.append(audio)

        if not all_audio or sample_rate is None:
            raise ProcessingError("No audio segments to concatenate")

        # Concatenate all chain audio
        master_audio = np.concatenate(all_audio)

        # Write to temp, normalise to master FLAC in this run's version dir
        output_dir = STORAGE_BASE / str(shootout_id) / f"v{render_version}"
        output_dir.mkdir(parents=True, exist_ok=True)
        master_path = output_dir / "master.wav"

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            sf.write(str(tmp_path), master_audio, sample_rate)
            normalize_loudness(tmp_path, master_path, TARGET_LUFS)
        finally:
            tmp_path.unlink(missing_ok=True)

        # Update shootout and jobs in the service lock order (own job ->
        # parent job -> shootout) so this cannot deadlock against a concurrent
        # reconcile. The shootout/parent COMPLETED projection is the legacy
        # publish gate, replaced by DOM-shootout-finalise; the master job's
        # own terminal write goes through the service.
        async with get_session(database_url) as session:
            job_stmt = select(Job).where(Job.id == job_id).with_for_update()
            job_result = await session.execute(job_stmt)
            job = job_result.scalar_one_or_none()

            parent_job = None
            if job is not None and job.parent_job_id is not None:
                parent_stmt = select(Job).where(Job.id == job.parent_job_id).with_for_update()
                parent_result = await session.execute(parent_stmt)
                parent_job = parent_result.scalar_one_or_none()

            s_stmt = select(Shootout).where(Shootout.id == shootout_id).with_for_update()
            s_result = await session.execute(s_stmt)
            shootout = s_result.scalar_one_or_none()
            if shootout is not None:
                shootout.output_path = str(master_path)
                shootout.status = ShootoutStatus.COMPLETED

            if parent_job is not None:
                parent_job.status = JobStatus.COMPLETED
                parent_job.progress = 100
                parent_job.completed_at = datetime.now(UTC)
                parent_job.result_path = str(master_path)

            await transition_job(
                session,
                job_id,
                JobStatus.COMPLETED,
                progress=100,
                result_path=str(master_path),
            )

        logger.info("Master audio created for shootout %s: %s", shootout_id, master_path)

    except (ProcessingError, LoudnessError) as exc:
        logger.error("Master processing failed for job %s: %s", job_id, exc)
        async with get_session(database_url) as session:
            await transition_job(session, job_id, JobStatus.FAILED, error=str(exc))


async def process_audio_job(job_id: UUID) -> None:
    """Process an audio job (SHOOTOUT_AUDIO or SHOOTOUT_MASTER).

    Routes to the appropriate handler based on job type.
    """
    database_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://gts:gts@db:5432/gts_core")

    # Determine job type
    async with get_session(database_url) as session:
        stmt = select(Job.job_type).where(Job.id == job_id)
        result = await session.execute(stmt)
        job_type = result.scalar_one_or_none()

    if job_type is None:
        logger.error("Job %s not found", job_id)
        return

    if job_type == JobType.SHOOTOUT_AUDIO:
        await _process_shootout_audio(job_id, database_url)
    elif job_type == JobType.SHOOTOUT_MASTER:
        await _process_shootout_master(job_id, database_url)
    else:
        logger.warning("Unsupported job type %s for job %s", job_type, job_id)


class ProcessAudioConsumer(BaseConsumer):
    """Consume process_audio queue commands."""

    def __init__(self, session) -> None:
        super().__init__(
            message_bus=PgmqClient(session),
            queue_name="audio_commands",
            dead_letter_queue="dead_letter",
        )
        self._session = session

    async def handle_message(self, envelope: MessageEnvelope) -> None:
        """Claim, then work the job under a renewed lease (idempotent consumption)."""
        command = ProcessAudioCommand.model_validate(envelope.model_dump(mode="python"))
        job_id = UUID(command.payload["job_id"])
        database_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://gts:gts@db:5432/gts_core")

        async with get_session(database_url) as session:
            outcome = await claim_job(session, job_id, message="Processing")
        if outcome == ClaimOutcome.ALREADY_TERMINAL:
            # Redelivered message for finished work: archive as a no-op.
            logger.info("Job %s already terminal; archiving redelivered message", job_id)
            return
        if outcome == ClaimOutcome.LIVE_LEASE:
            # Another consumer is live on this job: release without ack.
            raise SkipMessage(str(job_id))

        message = self.current_message
        if message is None:
            await process_audio_job(job_id)
            return
        async with MessageLease(database_url, self.queue_name, message.msg_id, job_id):
            await process_audio_job(job_id)

    async def should_dead_letter(self, queued_message) -> bool:
        """Never dead-letter a job whose lease is live (skips grew read_ct)."""
        raw_job_id = (queued_message.message.get("payload") or {}).get("job_id")
        if not raw_job_id:
            return True
        database_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://gts:gts@db:5432/gts_core")
        async with get_session(database_url) as session:
            return not await job_lease_is_live(session, UUID(str(raw_job_id)))

    async def on_dead_letter(self, message: dict[str, object], reason: str) -> None:
        """Couple the job row to the queue-level DLQ in the same commit."""
        await mark_job_dead_lettered(self._session, message, reason)

    async def commit_message(self) -> None:
        """Commit domain writes and queue archive in one transaction."""
        await self._session.commit()

    async def rollback_message(self) -> None:
        """Rollback failed message attempts before retry/DLQ decisions."""
        await self._session.rollback()

    async def reset_message_context(self) -> None:
        """Clear session identity state between long-lived message iterations."""
        self._session.expunge_all()
