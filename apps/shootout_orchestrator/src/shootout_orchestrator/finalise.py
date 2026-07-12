"""Publish a completed shootout render as an immutable manifest."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from sqlalchemy import and_, select
from sqlalchemy.orm import aliased

from gts.domain.value_objects.job_status import JobStatus, JobType
from gts.domain.value_objects.waveform_data import WaveformData
from messaging.db import get_session_no_tx as get_session
from webapp.adapters.persistence.models.gear import Gear
from webapp.adapters.persistence.models.gear_model import GearModel
from webapp.adapters.persistence.models.job import Job
from webapp.adapters.persistence.models.shootout import (
    AudioSegment,
    DITrack,
    Shootout,
    ShootoutChain,
    ShootoutManifest,
)
from webapp.adapters.persistence.models.signal_chain import SignalChainBlock
from webapp.adapters.persistence.models.user import User
from webapp.adapters.persistence.models.user_gear import UserGear
from webapp.services.job_dispatch import send_and_mark_queued
from webapp.services.job_transitions import complete_shootout_finalise, transition_job

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class FinaliseError(Exception):
    """The current render cannot be resolved into a complete manifest."""


def _waveform_payload(waveform: Any) -> Any:
    if not isinstance(waveform, WaveformData):
        return waveform
    return {
        "peaks": waveform.to_list(),
        "sample_rate": waveform.sample_rate,
        "duration_seconds": waveform.duration_seconds,
        "samples_per_peak": waveform.samples_per_peak,
    }


async def _publish_manifest(session: AsyncSession, job_id: UUID) -> UUID:
    """Write the manifest and complete the finalise, parent, and shootout rows."""
    finalise_job = aliased(Job, name="finalise_job")
    parent_job = aliased(Job, name="parent_job")
    stmt = (
        select(
            finalise_job,
            parent_job,
            Shootout,
            User,
            DITrack,
            ShootoutManifest,
            ShootoutChain,
            AudioSegment,
            SignalChainBlock,
            UserGear,
            GearModel,
            Gear,
        )
        .join(parent_job, finalise_job.parent_job_id == parent_job.id)
        .join(Shootout, finalise_job.entity_id == Shootout.id)
        .outerjoin(User, Shootout.user_id == User.id)
        .outerjoin(DITrack, Shootout.di_track_id == DITrack.id)
        .outerjoin(
            ShootoutManifest,
            and_(
                ShootoutManifest.shootout_id == Shootout.id,
                ShootoutManifest.version == Shootout.render_version,
            ),
        )
        .outerjoin(ShootoutChain, ShootoutChain.shootout_id == Shootout.id)
        .outerjoin(
            AudioSegment,
            and_(
                AudioSegment.shootout_chain_id == ShootoutChain.id,
                AudioSegment.version == Shootout.render_version,
            ),
        )
        .outerjoin(
            SignalChainBlock,
            SignalChainBlock.signal_chain_id == ShootoutChain.signal_chain_id,
        )
        .outerjoin(UserGear, UserGear.id == SignalChainBlock.user_gear_id)
        .outerjoin(GearModel, GearModel.id == UserGear.gear_model_id)
        .outerjoin(Gear, Gear.id == GearModel.gear_id)
        .where(finalise_job.id == job_id)
        .order_by(ShootoutChain.position, SignalChainBlock.position)
        .with_for_update(of=[finalise_job, parent_job, Shootout])
    )
    rows = (await session.execute(stmt)).all()
    if not rows:
        raise ValueError(f"Job {job_id} not found")

    first = rows[0]
    job, parent, shootout, creator, di_track, existing_manifest = first[:6]
    if parent is None or shootout is None:
        raise FinaliseError(f"Finalise job {job_id} has no resolvable parent shootout")
    if existing_manifest is not None:
        complete_shootout_finalise(session, job, parent, shootout, None)
        await session.commit()
        return parent.id
    if creator is None:
        raise FinaliseError(f"Shootout {shootout.id} has no resolvable creator")
    if di_track is None:
        raise FinaliseError(f"Shootout {shootout.id} has no resolvable DI track")

    chain_payloads: list[dict[str, Any]] = []
    rows_by_chain: dict[UUID, list[Any]] = {}
    for row in rows:
        chain = row[6]
        if chain is not None:
            rows_by_chain.setdefault(chain.id, []).append(row)
    if not rows_by_chain:
        raise FinaliseError(f"Shootout {shootout.id} has no chains")

    for chain_rows in rows_by_chain.values():
        chain = chain_rows[0][6]
        segment = chain_rows[0][7]
        if segment is None:
            raise FinaliseError(
                f"Chain {chain.id} has no audio segment for version {shootout.render_version}"
            )
        provenance: list[dict[str, Any]] = []
        for row in chain_rows:
            block, user_gear, gear_model, gear = row[8:12]
            if block is None:
                continue
            if user_gear is None or gear_model is None or gear is None:
                raise FinaliseError(
                    f"Chain {chain.id} has unresolvable provenance at block position "
                    f"{block.position}"
                )
            provenance.append(
                {
                    "position": block.position,
                    "gear_type": block.gear_type.value,
                    "display_name": user_gear.nickname or gear.name,
                    "platform": gear_model.platform.value,
                    "icon_asset_id": str(gear.id),
                }
            )
        chain_payloads.append(
            {
                "label": chain.label,
                "media_path": f"v{shootout.render_version}/{chain.id}.wav",
                "segment_id": str(segment.id),
                "duration_seconds": segment.duration_seconds,
                "waveform": _waveform_payload(segment.waveform),
                "integrated_lufs": segment.integrated_lufs,
                "peak_dbfs": segment.peak_dbfs,
                "provenance": provenance,
            }
        )

    payload = {
        "schema_version": 1,
        "shootout": {
            "id": str(shootout.id),
            "title": shootout.name,
            "description": shootout.description,
            "creator": {
                "username": creator.username,
                "avatar_url": creator.avatar_url,
            },
            "created_at": shootout.created_at.isoformat(),
        },
        "di": {
            "name": di_track.name,
            "guitar": di_track.guitar,
            "pickup": di_track.pickup,
            "tuning": di_track.tuning,
            "duration_seconds": di_track.duration_seconds,
        },
        "timeline": {
            "aligned": "start",
            "duration_seconds": max(chain["duration_seconds"] for chain in chain_payloads),
        },
        "chains": chain_payloads,
    }
    manifest = ShootoutManifest(
        shootout_id=shootout.id,
        version=shootout.render_version,
        schema_version=1,
        payload=payload,
    )
    complete_shootout_finalise(session, job, parent, shootout, manifest)
    await session.commit()
    return parent.id


async def _dispatch_master(parent_job_id: UUID, session: AsyncSession) -> None:
    """Find or create the non-gating montage job and enqueue it once."""
    parent_job = aliased(Job, name="parent_job")
    master_job = aliased(Job, name="master_job")
    stmt = (
        select(parent_job, master_job)
        .outerjoin(
            master_job,
            and_(
                master_job.parent_job_id == parent_job.id,
                master_job.job_type == JobType.SHOOTOUT_MASTER,
            ),
        )
        .where(parent_job.id == parent_job_id)
        .with_for_update(of=parent_job)
    )
    row = (await session.execute(stmt)).one()
    parent, master = row
    if master is None:
        master = Job(
            user_id=parent.user_id,
            job_type=JobType.SHOOTOUT_MASTER,
            parent_job_id=parent.id,
            entity_id=parent.entity_id,
            status=JobStatus.PENDING,
            progress=0,
        )
        session.add(master)
        await session.flush()
    if master.status == JobStatus.PENDING:
        await send_and_mark_queued(session, master, message="Queued for master audio creation")
    await session.commit()


async def process_finalise_job(job_id: UUID, database_url: str) -> None:
    """Publish one render, then dispatch montage as non-gating enrichment."""
    try:
        async with get_session(database_url) as session:
            parent_job_id = await _publish_manifest(session, job_id)
    except FinaliseError as exc:
        logger.error("Shootout finalise failed for job %s: %s", job_id, exc)
        async with get_session(database_url) as session:
            await transition_job(session, job_id, JobStatus.FAILED, error=str(exc))
        return

    async with get_session(database_url) as session:
        await _dispatch_master(parent_job_id, session)
