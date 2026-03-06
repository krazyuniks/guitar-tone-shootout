"""Integration tests for audio-worker process_audio_job().

Tests the full SHOOTOUT_AUDIO and SHOOTOUT_MASTER job processing pipeline
using real PostgreSQL with SAVEPOINT isolation, and synthetic audio/model files.

The consumer functions create their own DB sessions via get_session(). For
SAVEPOINT isolation, we monkeypatch get_session to yield the test session.
"""

from __future__ import annotations

import json
import sys
import types
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

import numpy as np
import pytest
import soundfile as sf
from sqlalchemy import select

from audio.processing.nam_loader import clear_model_cache
from gts.domain.value_objects.download_status import DownloadStatus
from gts.domain.value_objects.job_status import JobStatus, JobType
from gts.domain.value_objects.signal_chain_enums import GearType, ModelSize, Platform
from webapp.adapters.persistence.models.gear import Gear
from webapp.adapters.persistence.models.gear_model import GearModel
from webapp.adapters.persistence.models.job import Job
from webapp.adapters.persistence.models.shootout import (
    AudioSegment,
    DITrack,
    Shootout,
    ShootoutChain,
    ShootoutStatus,
)
from webapp.adapters.persistence.models.signal_chain import SignalChain, SignalChainBlock
from webapp.adapters.persistence.models.user import User
from webapp.adapters.persistence.models.user_gear import UserGear

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from sqlalchemy.ext.asyncio import AsyncSession


def _create_minimal_nam_file(path: Path) -> None:
    """Create a minimal valid .nam file (WaveNet architecture)."""
    for mod_name in ("nam.train", "nam.train.colab"):
        if mod_name not in sys.modules:
            sys.modules[mod_name] = types.ModuleType(mod_name)

    from nam.models.wavenet import WaveNet

    layer_config = {
        "input_size": 1,
        "condition_size": 1,
        "head_size": 1,
        "channels": 1,
        "kernel_size": 2,
        "dilations": [1],
        "activation": "Tanh",
        "gated": False,
        "head_bias": False,
    }
    wavenet_config = {
        "layers": [layer_config],
        "head": None,
        "head_scale": 0.02,
    }
    model = WaveNet(
        layers_configs=wavenet_config["layers"],
        head_config=wavenet_config["head"],
        head_scale=wavenet_config["head_scale"],
        sample_rate=48000,
    )
    weights = []
    for p in model.parameters():
        weights.extend(p.detach().cpu().numpy().flatten().tolist())
    config = {
        "version": "0.5.4",
        "architecture": "WaveNet",
        "config": wavenet_config,
        "weights": weights,
        "sample_rate": 48000,
        "metadata": {},
    }
    with open(path, "w") as f:
        json.dump(config, f)


def _create_ir_file(path: Path) -> None:
    """Create a synthetic IR file."""
    sample_rate = 48000
    t = np.linspace(0, 0.1, int(sample_rate * 0.1))
    rng = np.random.default_rng(42)
    ir = np.exp(-20 * t) * rng.standard_normal(len(t)) * 0.1
    sf.write(str(path), ir, sample_rate)


def _create_di_file(path: Path) -> None:
    """Create a synthetic DI track (440Hz sine, 3 seconds, realistic amplitude)."""
    sample_rate = 48000
    duration = 3.0
    t = np.linspace(0, duration, int(sample_rate * duration))
    audio = np.sin(2 * np.pi * 440.0 * t) * 0.3
    sf.write(str(path), audio.astype(np.float32), sample_rate)


def _make_session_factory(session: AsyncSession):
    """Create a get_session replacement that yields the test session."""

    @asynccontextmanager
    async def _factory(_url: str) -> AsyncGenerator[AsyncSession, None]:
        yield session

    return _factory


@pytest.fixture(autouse=True)
def _clear_nam_cache() -> None:
    clear_model_cache()


@pytest.fixture
def audio_dir(tmp_path: Path) -> Path:
    d = tmp_path / "audio"
    d.mkdir()
    return d


@pytest.fixture
def nam_model_path(audio_dir: Path) -> Path:
    p = audio_dir / "test_model.nam"
    _create_minimal_nam_file(p)
    return p


@pytest.fixture
def ir_file_path(audio_dir: Path) -> Path:
    p = audio_dir / "test_ir.wav"
    _create_ir_file(p)
    return p


@pytest.fixture
def di_file_path(audio_dir: Path) -> Path:
    p = audio_dir / "test_di.wav"
    _create_di_file(p)
    return p


@pytest.fixture
async def test_user(db_session: AsyncSession) -> User:
    suffix = uuid4().hex[:8]
    user = User(username=f"audiotest_{suffix}", email=f"audiotest_{suffix}@test.com")
    db_session.add(user)
    await db_session.flush()
    return user


@pytest.fixture
def patch_sessions(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch) -> None:
    """Monkeypatch get_session in consumer and reconciliation modules."""
    import audio_worker.consumer as consumer_mod
    import webapp.services.shootout_reconciliation as reconcile_mod

    factory = _make_session_factory(db_session)
    monkeypatch.setattr(consumer_mod, "get_session", factory)
    monkeypatch.setattr(reconcile_mod, "get_session", factory)


@pytest.fixture
async def shootout_audio_setup(
    db_session: AsyncSession,
    test_user: User,
    di_file_path: Path,
    nam_model_path: Path,
    ir_file_path: Path,
    tmp_path: Path,
) -> dict:
    """Create full set of DB records for a SHOOTOUT_AUDIO job test."""
    # DITrack
    di_track = DITrack(
        user_id=test_user.id,
        name="Test DI",
        file_path=str(di_file_path),
        original_filename="test_di.wav",
        duration_seconds=1.0,
        sample_rate=48000,
    )
    db_session.add(di_track)
    await db_session.flush()

    # Shootout
    shootout = Shootout(
        user_id=test_user.id,
        di_track_id=di_track.id,
        name="Test Shootout",
        status=ShootoutStatus.PROCESSING,
    )
    db_session.add(shootout)
    await db_session.flush()

    # Gear + GearModel for AMP (NAM model)
    amp_gear = Gear(
        name=f"Test Amp {uuid4().hex[:6]}",
        slug=f"test-amp-{uuid4().hex[:6]}",
        gear_type="amp",
        platform="nam",
    )
    db_session.add(amp_gear)
    await db_session.flush()

    amp_model = GearModel(
        gear_id=amp_gear.id,
        platform=Platform.NAM,
        size=ModelSize.STANDARD,
        file_path=str(nam_model_path),
        download_status=DownloadStatus.COMPLETED,
    )
    db_session.add(amp_model)
    await db_session.flush()

    amp_user_gear = UserGear(
        user_id=test_user.id,
        gear_model_id=amp_model.id,
    )
    db_session.add(amp_user_gear)
    await db_session.flush()

    # Gear + GearModel for IR
    ir_gear = Gear(
        name=f"Test IR {uuid4().hex[:6]}",
        slug=f"test-ir-{uuid4().hex[:6]}",
        gear_type="ir",
        platform="ir",
    )
    db_session.add(ir_gear)
    await db_session.flush()

    ir_model = GearModel(
        gear_id=ir_gear.id,
        platform=Platform.IR,
        size=ModelSize.STANDARD,
        file_path=str(ir_file_path),
        download_status=DownloadStatus.COMPLETED,
    )
    db_session.add(ir_model)
    await db_session.flush()

    ir_user_gear = UserGear(
        user_id=test_user.id,
        gear_model_id=ir_model.id,
    )
    db_session.add(ir_user_gear)
    await db_session.flush()

    # SignalChain with AMP + IR blocks
    chain = SignalChain(
        user_id=test_user.id,
        name="Test Chain",
        platform=Platform.NAM,
    )
    db_session.add(chain)
    await db_session.flush()

    amp_block = SignalChainBlock(
        signal_chain_id=chain.id,
        position=0,
        user_gear_id=amp_user_gear.id,
        gear_type=GearType.AMP,
    )
    ir_block = SignalChainBlock(
        signal_chain_id=chain.id,
        position=1,
        user_gear_id=ir_user_gear.id,
        gear_type=GearType.IR,
    )
    db_session.add_all([amp_block, ir_block])
    await db_session.flush()

    # ShootoutChain linking shootout to signal chain
    shootout_chain = ShootoutChain(
        shootout_id=shootout.id,
        signal_chain_id=chain.id,
        position=0,
        label="Chain A",
    )
    db_session.add(shootout_chain)
    await db_session.flush()

    # Parent SHOOTOUT job
    parent_job = Job(
        user_id=test_user.id,
        job_type=JobType.SHOOTOUT,
        entity_id=shootout.id,
        status=JobStatus.RUNNING,
    )
    db_session.add(parent_job)
    await db_session.flush()

    # SHOOTOUT_AUDIO child job
    audio_job = Job(
        user_id=test_user.id,
        job_type=JobType.SHOOTOUT_AUDIO,
        parent_job_id=parent_job.id,
        entity_id=shootout_chain.id,
        status=JobStatus.QUEUED,
    )
    db_session.add(audio_job)
    await db_session.flush()

    await db_session.commit()

    output_dir = tmp_path / "storage" / "audio"
    output_dir.mkdir(parents=True)

    return {
        "audio_job_id": audio_job.id,
        "parent_job_id": parent_job.id,
        "shootout_id": shootout.id,
        "shootout_chain_id": shootout_chain.id,
        "output_dir": output_dir,
    }


@pytest.mark.asyncio
async def test_process_shootout_audio_job(
    db_session: AsyncSession,
    shootout_audio_setup: dict,
    patch_sessions: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Full SHOOTOUT_AUDIO processing: chain execution, normalisation, segment creation."""
    import audio_worker.consumer as consumer_mod

    setup = shootout_audio_setup
    monkeypatch.setattr(consumer_mod, "STORAGE_BASE", setup["output_dir"])

    await consumer_mod.process_audio_job(setup["audio_job_id"])

    # Verify job completed
    db_session.expire_all()
    stmt = select(Job).where(Job.id == setup["audio_job_id"])
    result = await db_session.execute(stmt)
    job = result.scalar_one()
    assert job.status == JobStatus.COMPLETED
    assert job.progress == 100
    assert job.result_path is not None

    # Verify AudioSegment created
    seg_stmt = select(AudioSegment).where(
        AudioSegment.shootout_chain_id == setup["shootout_chain_id"]
    )
    seg_result = await db_session.execute(seg_stmt)
    segment = seg_result.scalar_one()
    assert segment.file_path is not None
    assert segment.duration_seconds > 0
    assert segment.integrated_lufs < 0
    assert segment.peak_dbfs < 0
    assert segment.waveform is not None

    # Verify FLAC file exists
    assert Path(segment.file_path).exists()


@pytest.mark.asyncio
async def test_process_shootout_master_job(
    db_session: AsyncSession,
    shootout_audio_setup: dict,
    patch_sessions: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SHOOTOUT_MASTER processing: concatenation and normalisation of chain segments."""
    import audio_worker.consumer as consumer_mod

    setup = shootout_audio_setup
    monkeypatch.setattr(consumer_mod, "STORAGE_BASE", setup["output_dir"])

    # First, process the audio job to create segments
    database_url = "unused-patched"
    await consumer_mod._process_shootout_audio(setup["audio_job_id"], database_url)

    # Create SHOOTOUT_MASTER job
    db_session.expire_all()
    user_id_result = await db_session.execute(
        select(Job.user_id).where(Job.id == setup["audio_job_id"])
    )
    user_id = user_id_result.scalar_one()

    master_job = Job(
        user_id=user_id,
        job_type=JobType.SHOOTOUT_MASTER,
        parent_job_id=setup["parent_job_id"],
        entity_id=setup["shootout_id"],
        status=JobStatus.QUEUED,
    )
    db_session.add(master_job)
    await db_session.flush()
    master_job_id = master_job.id
    await db_session.commit()

    await consumer_mod._process_shootout_master(master_job_id, database_url)

    # Verify master job completed
    db_session.expire_all()
    stmt = select(Job).where(Job.id == master_job_id)
    result = await db_session.execute(stmt)
    job = result.scalar_one()
    assert job.status == JobStatus.COMPLETED
    assert job.result_path is not None

    # Verify shootout updated
    s_stmt = select(Shootout).where(Shootout.id == setup["shootout_id"])
    s_result = await db_session.execute(s_stmt)
    shootout = s_result.scalar_one()
    assert shootout.status == ShootoutStatus.COMPLETED
    assert shootout.output_path is not None

    # Verify master FLAC exists
    assert Path(job.result_path).exists()


@pytest.mark.asyncio
async def test_process_audio_job_missing_gear_file(
    db_session: AsyncSession,
    test_user: User,
    di_file_path: Path,
    tmp_path: Path,
    patch_sessions: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Chain block references non-existent gear file — job should fail."""
    import audio_worker.consumer as consumer_mod

    output_dir = tmp_path / "storage" / "audio"
    output_dir.mkdir(parents=True)
    monkeypatch.setattr(consumer_mod, "STORAGE_BASE", output_dir)

    # DITrack
    di_track = DITrack(
        user_id=test_user.id,
        name="Test DI Missing",
        file_path=str(di_file_path),
        original_filename="test_di.wav",
        duration_seconds=1.0,
        sample_rate=48000,
    )
    db_session.add(di_track)
    await db_session.flush()

    # Shootout
    shootout = Shootout(
        user_id=test_user.id,
        di_track_id=di_track.id,
        name="Test Shootout Missing",
        status=ShootoutStatus.PROCESSING,
    )
    db_session.add(shootout)
    await db_session.flush()

    # Gear with MISSING file_path
    gear = Gear(
        name=f"Missing Gear {uuid4().hex[:6]}",
        slug=f"missing-gear-{uuid4().hex[:6]}",
        gear_type="amp",
        platform="nam",
    )
    db_session.add(gear)
    await db_session.flush()

    gear_model = GearModel(
        gear_id=gear.id,
        platform=Platform.NAM,
        size=ModelSize.STANDARD,
        file_path=None,
        download_status=DownloadStatus.PENDING,
    )
    db_session.add(gear_model)
    await db_session.flush()

    user_gear = UserGear(user_id=test_user.id, gear_model_id=gear_model.id)
    db_session.add(user_gear)
    await db_session.flush()

    chain = SignalChain(
        user_id=test_user.id,
        name="Chain Missing File",
        platform=Platform.NAM,
    )
    db_session.add(chain)
    await db_session.flush()

    block = SignalChainBlock(
        signal_chain_id=chain.id,
        position=0,
        user_gear_id=user_gear.id,
        gear_type=GearType.FULL_RIG,
    )
    db_session.add(block)
    await db_session.flush()

    shootout_chain = ShootoutChain(
        shootout_id=shootout.id,
        signal_chain_id=chain.id,
        position=0,
        label="Missing Chain",
    )
    db_session.add(shootout_chain)
    await db_session.flush()

    parent_job = Job(
        user_id=test_user.id,
        job_type=JobType.SHOOTOUT,
        entity_id=shootout.id,
        status=JobStatus.RUNNING,
    )
    db_session.add(parent_job)
    await db_session.flush()

    audio_job = Job(
        user_id=test_user.id,
        job_type=JobType.SHOOTOUT_AUDIO,
        parent_job_id=parent_job.id,
        entity_id=shootout_chain.id,
        status=JobStatus.QUEUED,
    )
    db_session.add(audio_job)
    await db_session.flush()
    audio_job_id = audio_job.id
    await db_session.commit()

    await consumer_mod.process_audio_job(audio_job_id)

    # Verify job failed
    db_session.expire_all()
    stmt = select(Job).where(Job.id == audio_job_id)
    result = await db_session.execute(stmt)
    job = result.scalar_one()
    assert job.status == JobStatus.FAILED
    assert job.error is not None
    assert "No file" in job.error or "user_gear" in job.error


@pytest.mark.asyncio
async def test_reconcile_creates_master_after_all_complete(
    db_session: AsyncSession,
    test_user: User,
    patch_sessions: None,
) -> None:
    """When all SHOOTOUT_AUDIO children complete, reconciliation creates a SHOOTOUT_MASTER job."""
    from webapp.services.shootout_reconciliation import reconcile_parent_after_audio

    shootout = Shootout(
        user_id=test_user.id,
        name="Reconcile Test",
        status=ShootoutStatus.PROCESSING,
    )
    db_session.add(shootout)
    await db_session.flush()

    parent_job = Job(
        user_id=test_user.id,
        job_type=JobType.SHOOTOUT,
        entity_id=shootout.id,
        status=JobStatus.RUNNING,
    )
    db_session.add(parent_job)
    await db_session.flush()

    child1 = Job(
        user_id=test_user.id,
        job_type=JobType.SHOOTOUT_AUDIO,
        parent_job_id=parent_job.id,
        entity_id=uuid4(),
        status=JobStatus.COMPLETED,
    )
    child2 = Job(
        user_id=test_user.id,
        job_type=JobType.SHOOTOUT_AUDIO,
        parent_job_id=parent_job.id,
        entity_id=uuid4(),
        status=JobStatus.COMPLETED,
    )
    db_session.add_all([child1, child2])
    await db_session.flush()
    await db_session.commit()

    # Capture IDs before expire_all (lazy load would fail in sync context)
    parent_job_id = parent_job.id
    shootout_id = shootout.id

    await reconcile_parent_after_audio(parent_job_id, "unused-patched")

    # Verify SHOOTOUT_MASTER job was created
    db_session.expire_all()
    master_stmt = select(Job).where(
        Job.parent_job_id == parent_job_id,
        Job.job_type == JobType.SHOOTOUT_MASTER,
    )
    master_result = await db_session.execute(master_stmt)
    master_job = master_result.scalar_one_or_none()
    assert master_job is not None
    assert master_job.status in {JobStatus.PENDING, JobStatus.QUEUED}
    assert master_job.entity_id == shootout_id

    # Verify parent progress = 100%
    parent_stmt = select(Job).where(Job.id == parent_job_id)
    parent_result = await db_session.execute(parent_stmt)
    parent = parent_result.scalar_one()
    assert parent.progress == 100
