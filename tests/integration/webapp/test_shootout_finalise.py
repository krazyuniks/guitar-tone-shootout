"""SHOOTOUT_FINALISE manifest publication and failure boundaries."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from sqlalchemy import func, select, text

from gts.domain.value_objects.download_status import DownloadStatus
from gts.domain.value_objects.job_status import JobStatus, JobType
from gts.domain.value_objects.signal_chain_enums import GearType, ModelSize, Platform
from gts.domain.value_objects.waveform_data import WaveformData
from messaging.pgmq_client import PgmqClient
from shootout_orchestrator.finalise import process_finalise_job
from webapp.adapters.persistence.models.gear import Gear
from webapp.adapters.persistence.models.gear_model import GearModel
from webapp.adapters.persistence.models.job import Job
from webapp.adapters.persistence.models.shootout import (
    AudioSegment,
    DITrack,
    Shootout,
    ShootoutChain,
    ShootoutManifest,
    ShootoutStatus,
)
from webapp.adapters.persistence.models.signal_chain import SignalChain, SignalChainBlock
from webapp.adapters.persistence.models.user import User
from webapp.adapters.persistence.models.user_gear import UserGear

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from sqlalchemy.ext.asyncio import AsyncSession


def _session_factory(session: AsyncSession):
    @asynccontextmanager
    async def factory(_url: str) -> AsyncGenerator[AsyncSession, None]:
        yield session

    return factory


async def _setup_finalise(
    db_session: AsyncSession,
    test_user: User,
    *,
    missing_segment: bool = False,
    unresolved_provenance: bool = False,
) -> dict[str, object]:
    test_user.avatar_url = "https://example.test/avatar.png"
    di_track = DITrack(
        user_id=test_user.id,
        name="Dry guitar",
        file_path="/audio/dry.wav",
        original_filename="dry.wav",
        duration_seconds=2.5,
        sample_rate=48000,
        guitar="Telecaster",
        pickup="bridge",
        tuning="E standard",
    )
    db_session.add(di_track)

    gear = Gear(
        name=f"Finalise Amp {uuid4().hex[:8]}",
        slug=f"finalise-amp-{uuid4().hex[:8]}",
        gear_type=GearType.AMP,
        platform=Platform.NAM.value,
    )
    db_session.add(gear)
    await db_session.flush()
    gear_model = GearModel(
        gear_id=gear.id,
        platform=Platform.NAM,
        size=ModelSize.STANDARD,
        download_status=DownloadStatus.COMPLETED,
    )
    db_session.add(gear_model)
    await db_session.flush()
    user_gear = UserGear(
        user_id=test_user.id,
        gear_model_id=gear_model.id,
        nickname="My finalise amp",
    )
    db_session.add(user_gear)
    await db_session.flush()

    shootout = Shootout(
        user_id=test_user.id,
        di_track_id=di_track.id,
        name="Finalise contract",
        description="A manifest snapshot",
        status=ShootoutStatus.PROCESSING,
        render_version=2,
    )
    db_session.add(shootout)
    await db_session.flush()

    chains: list[ShootoutChain] = []
    segments: list[AudioSegment] = []
    for position, duration in enumerate((1.25, 2.0)):
        signal_chain = SignalChain(
            user_id=test_user.id,
            name=f"Signal chain {position}",
            platform=Platform.NAM,
        )
        db_session.add(signal_chain)
        await db_session.flush()
        block = SignalChainBlock(
            signal_chain_id=signal_chain.id,
            position=0,
            user_gear_id=uuid4() if unresolved_provenance else user_gear.id,
            gear_type=GearType.AMP,
        )
        db_session.add(block)
        chain = ShootoutChain(
            shootout_id=shootout.id,
            signal_chain_id=signal_chain.id,
            position=position,
            label=f"Chain {position + 1}",
        )
        db_session.add(chain)
        await db_session.flush()
        chains.append(chain)
        if not (missing_segment and position == 1):
            segment = AudioSegment(
                shootout_chain_id=chain.id,
                file_path=f"/app/storage/audio/{shootout.id}/v2/{chain.id}.wav",
                duration_seconds=duration,
                integrated_lufs=-14.0,
                peak_dbfs=-1.5,
                waveform=WaveformData(
                    peaks=(0.1, 0.5),
                    sample_rate=48000,
                    duration_seconds=duration,
                    samples_per_peak=24000,
                ),
                version=2,
            )
            db_session.add(segment)
            segments.append(segment)

    parent = Job(
        user_id=test_user.id,
        job_type=JobType.SHOOTOUT,
        entity_id=shootout.id,
        status=JobStatus.RUNNING,
        progress=100,
    )
    db_session.add(parent)
    await db_session.flush()
    finalise = Job(
        user_id=test_user.id,
        job_type=JobType.SHOOTOUT_FINALISE,
        parent_job_id=parent.id,
        entity_id=shootout.id,
        status=JobStatus.RUNNING,
    )
    db_session.add(finalise)
    await PgmqClient(db_session).create_queue("audio_commands")
    await db_session.commit()
    return {
        "shootout": shootout,
        "parent": parent,
        "finalise": finalise,
        "chains": chains,
        "segments": segments,
        "gear": gear,
    }


@pytest.mark.asyncio
@pytest.mark.integration
class TestShootoutFinalise:
    async def test_writes_manifest_completes_publication_and_dispatches_master_once(
        self,
        db_session: AsyncSession,
        test_user: User,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        setup = await _setup_finalise(db_session, test_user)
        import shootout_orchestrator.finalise as finalise_module

        monkeypatch.setattr(finalise_module, "get_session", _session_factory(db_session))
        finalise_id = setup["finalise"].id
        await process_finalise_job(finalise_id, "test")
        await process_finalise_job(finalise_id, "test")

        manifest = (
            await db_session.execute(
                select(ShootoutManifest).where(ShootoutManifest.shootout_id == setup["shootout"].id)
            )
        ).scalar_one()
        payload = manifest.payload
        assert manifest.version == 2
        assert payload["schema_version"] == 1
        assert payload["shootout"] == {
            "id": str(setup["shootout"].id),
            "title": "Finalise contract",
            "description": "A manifest snapshot",
            "creator": {
                "username": test_user.username,
                "avatar_url": "https://example.test/avatar.png",
            },
            "created_at": setup["shootout"].created_at.isoformat(),
        }
        assert payload["di"] == {
            "name": "Dry guitar",
            "guitar": "Telecaster",
            "pickup": "bridge",
            "tuning": "E standard",
            "duration_seconds": 2.5,
        }
        assert payload["timeline"] == {"aligned": "start", "duration_seconds": 2.0}
        assert [chain["label"] for chain in payload["chains"]] == ["Chain 1", "Chain 2"]
        first_chain = payload["chains"][0]
        assert first_chain["media_path"] == f"v2/{setup['chains'][0].id}.wav"
        assert first_chain["segment_id"] == str(setup["segments"][0].id)
        assert first_chain["waveform"]["peaks"] == [0.1, 0.5]
        assert first_chain["provenance"] == [
            {
                "position": 0,
                "gear_type": "amp",
                "display_name": "My finalise amp",
                "platform": "nam",
                "icon_asset_id": str(setup["gear"].id),
            }
        ]
        assert "parameters" not in first_chain["provenance"][0]
        assert "montage" not in payload
        assert "video" not in payload

        await db_session.refresh(setup["shootout"])
        await db_session.refresh(setup["parent"])
        await db_session.refresh(setup["finalise"])
        assert setup["shootout"].status == ShootoutStatus.COMPLETED
        assert setup["parent"].status == JobStatus.COMPLETED
        assert setup["finalise"].status == JobStatus.COMPLETED

        masters = (
            (
                await db_session.execute(
                    select(Job).where(
                        Job.parent_job_id == setup["parent"].id,
                        Job.job_type == JobType.SHOOTOUT_MASTER,
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(masters) == 1
        assert masters[0].status == JobStatus.QUEUED
        message_count = await db_session.scalar(
            text(
                "SELECT count(*) FROM pgmq.q_audio_commands "
                "WHERE message->'payload'->>'job_id' = :job_id"
            ),
            {"job_id": str(masters[0].id)},
        )
        assert message_count == 1

    @pytest.mark.parametrize("failure", ["segment", "provenance"])
    async def test_unresolvable_snapshot_fails_without_manifest(
        self,
        db_session: AsyncSession,
        test_user: User,
        monkeypatch: pytest.MonkeyPatch,
        failure: str,
    ) -> None:
        setup = await _setup_finalise(
            db_session,
            test_user,
            missing_segment=failure == "segment",
            unresolved_provenance=failure == "provenance",
        )
        import shootout_orchestrator.finalise as finalise_module

        monkeypatch.setattr(finalise_module, "get_session", _session_factory(db_session))
        await process_finalise_job(setup["finalise"].id, "test")

        await db_session.refresh(setup["finalise"])
        await db_session.refresh(setup["parent"])
        await db_session.refresh(setup["shootout"])
        assert setup["finalise"].status == JobStatus.FAILED
        assert setup["parent"].status == JobStatus.RUNNING
        assert setup["shootout"].status == ShootoutStatus.PROCESSING
        assert await db_session.scalar(select(func.count()).select_from(ShootoutManifest)) == 0
        if failure == "segment":
            assert "no audio segment for version 2" in (setup["finalise"].error or "")
        else:
            assert str(setup["chains"][0].id) in (setup["finalise"].error or "")
            assert "block position 0" in (setup["finalise"].error or "")
