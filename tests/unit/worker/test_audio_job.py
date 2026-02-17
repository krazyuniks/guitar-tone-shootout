"""Unit tests for Per-Chain Audio Processing Job Handler.

Tests that the SHOOTOUT_AUDIO job handler processes a single signal chain
through the audio pipeline, saves output, measures loudness, and tracks progress.
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING
from uuid import uuid4

import numpy as np
import pytest

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from core.domain.value_objects.job_status import JobStatus, JobType
from webapp.adapters.persistence.models.base import Base
from webapp.adapters.persistence.models.job import Job
from webapp.adapters.persistence.models.shootout import (
    DITrack,
    Shootout,
    ShootoutChain,
)
from webapp.adapters.persistence.models.signal_chain import SignalChain


@pytest.fixture
async def db_engine() -> AsyncGenerator[AsyncEngine, None]:
    """Create a test database engine (SQLite for testing)."""
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(db_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session."""
    async_session = async_sessionmaker(db_engine, expire_on_commit=False)
    async with async_session() as session:
        yield session


def _make_fake_get_session(session: AsyncSession):
    """Create a fake get_session context manager that yields the test session."""

    @contextlib.asynccontextmanager
    async def fake_get_session(url=None):
        yield session

    return fake_get_session


async def _fake_execute_signal_chain(signal_chain, di_audio, sample_rate, resolver):
    """Test double for execute_signal_chain — returns processed audio."""
    return np.zeros(len(di_audio), dtype=np.float32)


def _fake_measure_loudness(path):
    """Test double for measure_loudness — returns (LUFS, peak_dBFS)."""
    return (-14.0, -6.0)


def _fake_sf_read(path):
    """Test double for soundfile.read — returns (audio, sample_rate)."""
    return (np.zeros(1000, dtype=np.float32), 48000)


_sf_write_calls: list[tuple] = []


def _fake_sf_write(path, data, samplerate):
    """Test double for soundfile.write — records calls."""
    _sf_write_calls.append((path, data, samplerate))


@pytest.fixture(autouse=True)
def _reset_sf_write_calls():
    _sf_write_calls.clear()


async def _create_full_job_fixture(session: AsyncSession):
    """Create a complete set of related DB objects for audio job tests.

    Returns (job_id, shootout_chain_id).
    """
    user_id = uuid4()
    di_track = DITrack(
        id=uuid4(),
        user_id=user_id,
        name="Test DI",
        file_path="/uploads/di.wav",
        original_filename="di.wav",
        duration_seconds=10.0,
        sample_rate=48000,
    )
    session.add(di_track)

    signal_chain = SignalChain(
        id=uuid4(),
        user_id=user_id,
        name="Test Chain",
    )
    session.add(signal_chain)

    shootout = Shootout(
        id=uuid4(),
        user_id=user_id,
        name="Test Shootout",
        di_track_id=di_track.id,
    )
    session.add(shootout)

    shootout_chain = ShootoutChain(
        id=uuid4(),
        shootout_id=shootout.id,
        signal_chain_id=signal_chain.id,
        position=0,
        label="Chain A",
    )
    session.add(shootout_chain)

    job = Job(
        id=uuid4(),
        user_id=user_id,
        job_type=JobType.SHOOTOUT_AUDIO,
        entity_id=shootout_chain.id,
        status=JobStatus.PENDING,
    )
    session.add(job)
    await session.commit()

    return job.id, shootout_chain.id


def _apply_audio_monkeypatches(monkeypatch, session, **overrides):
    """Apply standard monkeypatches for audio job tests."""
    monkeypatch.setattr(
        "worker.jobs.audio.get_session",
        overrides.get("get_session", _make_fake_get_session(session)),
    )
    monkeypatch.setattr(
        "worker.jobs.audio.execute_signal_chain",
        overrides.get("execute_signal_chain", _fake_execute_signal_chain),
    )
    monkeypatch.setattr(
        "worker.jobs.audio.measure_loudness",
        overrides.get("measure_loudness", _fake_measure_loudness),
    )
    monkeypatch.setattr("worker.jobs.audio.sf.read", overrides.get("sf_read", _fake_sf_read))
    monkeypatch.setattr("worker.jobs.audio.sf.write", overrides.get("sf_write", _fake_sf_write))


class TestAudioJobHandlerModule:
    """Test audio job handler module exists and provides required functions."""

    def test_audio_job_module_exists(self) -> None:
        """audio module exists in worker.jobs package."""
        from worker.jobs import audio  # noqa: F401

    def test_handle_shootout_audio_job_function_exists(self) -> None:
        """handle_shootout_audio_job function exists."""
        from worker.jobs.audio import handle_shootout_audio_job

        assert callable(handle_shootout_audio_job)

    def test_handle_shootout_audio_job_is_taskiq_task(self) -> None:
        """handle_shootout_audio_job is a TaskIQ task."""
        from worker.jobs.audio import handle_shootout_audio_job

        assert hasattr(handle_shootout_audio_job, "kicker")


class TestAudioJobHandler:
    """Test handle_shootout_audio_job processing logic."""

    async def test_loads_job_from_database(
        self, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Handler loads job from database to get shootout chain ID."""
        from worker.jobs.audio import handle_shootout_audio_job

        job_id, _ = await _create_full_job_fixture(db_session)
        _apply_audio_monkeypatches(monkeypatch, db_session)

        await handle_shootout_audio_job(job_id)

        # Verify job was loaded and status updated
        await db_session.refresh(await db_session.get(Job, job_id))
        job = await db_session.get(Job, job_id)
        assert job is not None
        assert job.status == JobStatus.COMPLETED

    async def test_loads_shootout_chain_with_signal_chain(
        self, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Handler loads shootout chain with signal chain and blocks."""
        from worker.jobs.audio import handle_shootout_audio_job

        job_id, _ = await _create_full_job_fixture(db_session)
        _apply_audio_monkeypatches(monkeypatch, db_session)

        await handle_shootout_audio_job(job_id)

        job = await db_session.get(Job, job_id)
        assert job is not None
        assert job.status == JobStatus.COMPLETED

    async def test_loads_di_track_from_shootout(
        self, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Handler loads DI track from shootout to get audio file path."""
        from worker.jobs.audio import handle_shootout_audio_job

        job_id, _ = await _create_full_job_fixture(db_session)

        sf_read_calls = []

        def tracking_sf_read(path):
            sf_read_calls.append(path)
            return (np.zeros(1000, dtype=np.float32), 48000)

        _apply_audio_monkeypatches(monkeypatch, db_session, sf_read=tracking_sf_read)

        await handle_shootout_audio_job(job_id)

        # DI track file_path should have been read
        assert len(sf_read_calls) == 1
        assert "di.wav" in sf_read_calls[0]

    async def test_reads_di_audio_file(
        self, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Handler reads DI audio file from uploads volume."""
        from worker.jobs.audio import handle_shootout_audio_job

        job_id, _ = await _create_full_job_fixture(db_session)

        sf_read_calls = []

        def tracking_sf_read(path):
            sf_read_calls.append(path)
            return (np.random.randn(48000).astype(np.float32), 48000)

        _apply_audio_monkeypatches(monkeypatch, db_session, sf_read=tracking_sf_read)

        await handle_shootout_audio_job(job_id)

        assert len(sf_read_calls) == 1

    async def test_calls_execute_signal_chain_with_correct_args(
        self, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Handler calls execute_signal_chain with DI audio and signal chain."""
        from worker.jobs.audio import handle_shootout_audio_job

        job_id, _ = await _create_full_job_fixture(db_session)

        execute_calls = []

        async def tracking_execute(signal_chain, di_audio, sample_rate, resolver):
            execute_calls.append((signal_chain, di_audio, sample_rate, resolver))
            return np.zeros(len(di_audio), dtype=np.float32)

        _apply_audio_monkeypatches(monkeypatch, db_session, execute_signal_chain=tracking_execute)

        await handle_shootout_audio_job(job_id)

        assert len(execute_calls) == 1
        _, di_audio, sample_rate, _ = execute_calls[0]
        assert isinstance(di_audio, np.ndarray)
        assert sample_rate == 48000

    async def test_saves_output_as_flac_to_processed_data_volume(
        self, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Handler saves processed audio as FLAC to processed_data volume."""
        from worker.jobs.audio import handle_shootout_audio_job

        job_id, _ = await _create_full_job_fixture(db_session)
        _apply_audio_monkeypatches(monkeypatch, db_session)

        await handle_shootout_audio_job(job_id)

        assert len(_sf_write_calls) == 1
        output_path, _, _ = _sf_write_calls[0]
        assert output_path.endswith(".flac")

    async def test_measures_loudness_on_output_file(
        self, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Handler measures loudness (LUFS + peak dBFS) on output file."""
        from worker.jobs.audio import handle_shootout_audio_job

        job_id, _ = await _create_full_job_fixture(db_session)

        loudness_calls = []

        def tracking_measure_loudness(path):
            loudness_calls.append(path)
            return (-12.5, -3.2)

        _apply_audio_monkeypatches(
            monkeypatch, db_session, measure_loudness=tracking_measure_loudness
        )

        await handle_shootout_audio_job(job_id)

        assert len(loudness_calls) == 1

    async def test_creates_audio_segment_record_in_database(
        self, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Handler creates AudioSegment record with file path and loudness metrics."""
        from webapp.adapters.persistence.models.shootout import AudioSegment
        from worker.jobs.audio import handle_shootout_audio_job

        job_id, shootout_chain_id = await _create_full_job_fixture(db_session)
        _apply_audio_monkeypatches(monkeypatch, db_session)

        await handle_shootout_audio_job(job_id)

        # Verify AudioSegment was created in DB
        from sqlalchemy import select

        result = await db_session.execute(
            select(AudioSegment).where(AudioSegment.shootout_chain_id == shootout_chain_id)
        )
        segment = result.scalar_one_or_none()
        assert segment is not None
        assert segment.file_path is not None

    async def test_updates_job_progress_at_loading_stage(
        self, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Handler updates job progress to 50 after loading data."""
        from worker.jobs.audio import handle_shootout_audio_job

        job_id, _ = await _create_full_job_fixture(db_session)

        progress_values = []

        original_commit = db_session.commit

        async def tracking_commit():
            job = await db_session.get(Job, job_id)
            if job:
                progress_values.append(job.progress)
            await original_commit()

        monkeypatch.setattr(db_session, "commit", tracking_commit)
        _apply_audio_monkeypatches(monkeypatch, db_session)

        await handle_shootout_audio_job(job_id)

        # Progress should go through 50 (loading) → 90 (processing) → 100 (complete)
        assert 50 in progress_values

    async def test_updates_job_progress_at_processing_stage(
        self, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Handler updates job progress to 90 after audio processing."""
        from worker.jobs.audio import handle_shootout_audio_job

        job_id, _ = await _create_full_job_fixture(db_session)

        progress_values = []

        original_commit = db_session.commit

        async def tracking_commit():
            job = await db_session.get(Job, job_id)
            if job:
                progress_values.append(job.progress)
            await original_commit()

        monkeypatch.setattr(db_session, "commit", tracking_commit)
        _apply_audio_monkeypatches(monkeypatch, db_session)

        await handle_shootout_audio_job(job_id)

        assert 90 in progress_values

    async def test_updates_job_progress_to_100_at_completion(
        self, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Handler updates job progress to 100 after saving output."""
        from worker.jobs.audio import handle_shootout_audio_job

        job_id, _ = await _create_full_job_fixture(db_session)
        _apply_audio_monkeypatches(monkeypatch, db_session)

        await handle_shootout_audio_job(job_id)

        job = await db_session.get(Job, job_id)
        assert job is not None
        assert job.progress == 100

    async def test_updates_heartbeat_during_processing(
        self, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Handler updates job heartbeat timestamp during long operations."""
        from worker.jobs.audio import handle_shootout_audio_job

        job_id, _ = await _create_full_job_fixture(db_session)
        _apply_audio_monkeypatches(monkeypatch, db_session)

        await handle_shootout_audio_job(job_id)

        job = await db_session.get(Job, job_id)
        assert job is not None
        assert job.last_heartbeat is not None

    async def test_marks_job_failed_on_error(
        self, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Handler marks job as FAILED and stores error message on exception."""
        from worker.jobs.audio import handle_shootout_audio_job

        job_id, _ = await _create_full_job_fixture(db_session)

        async def failing_execute(signal_chain, di_audio, sample_rate, resolver):
            raise Exception("NAM processing failed")

        _apply_audio_monkeypatches(monkeypatch, db_session, execute_signal_chain=failing_execute)

        with pytest.raises(RuntimeError):
            await handle_shootout_audio_job(job_id)

        job = await db_session.get(Job, job_id)
        assert job is not None
        assert job.status == JobStatus.FAILED
        assert "NAM processing failed" in job.error

    async def test_audio_segment_has_correct_duration(
        self, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """AudioSegment record has correct duration calculated from audio length."""
        from webapp.adapters.persistence.models.shootout import AudioSegment
        from worker.jobs.audio import handle_shootout_audio_job

        job_id, shootout_chain_id = await _create_full_job_fixture(db_session)

        # 48000 samples at 48kHz = 1.0 second
        async def execute_returning_1s(signal_chain, di_audio, sample_rate, resolver):
            return np.zeros(48000, dtype=np.float32)

        _apply_audio_monkeypatches(
            monkeypatch,
            db_session,
            execute_signal_chain=execute_returning_1s,
            sf_read=lambda _path: (np.zeros(48000, dtype=np.float32), 48000),
        )

        await handle_shootout_audio_job(job_id)

        from sqlalchemy import select

        result = await db_session.execute(
            select(AudioSegment).where(AudioSegment.shootout_chain_id == shootout_chain_id)
        )
        segment = result.scalar_one_or_none()
        assert segment is not None
        assert segment.duration_seconds == pytest.approx(1.0)

    async def test_audio_segment_has_loudness_metrics(
        self, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """AudioSegment record stores integrated LUFS and peak dBFS from measurement."""
        from webapp.adapters.persistence.models.shootout import AudioSegment
        from worker.jobs.audio import handle_shootout_audio_job

        job_id, shootout_chain_id = await _create_full_job_fixture(db_session)

        expected_lufs = -13.2
        expected_peak = -2.8

        _apply_audio_monkeypatches(
            monkeypatch,
            db_session,
            measure_loudness=lambda _path: (expected_lufs, expected_peak),
        )

        await handle_shootout_audio_job(job_id)

        from sqlalchemy import select

        result = await db_session.execute(
            select(AudioSegment).where(AudioSegment.shootout_chain_id == shootout_chain_id)
        )
        segment = result.scalar_one_or_none()
        assert segment is not None
        assert segment.integrated_lufs == pytest.approx(expected_lufs)
        assert segment.peak_dbfs == pytest.approx(expected_peak)


class TestTaskRegistration:
    """Test that handle_shootout_audio_job is registered with TaskIQ broker."""

    def test_task_is_registered_with_broker(self) -> None:
        """handle_shootout_audio_job task is registered with the broker."""
        from worker.main import broker

        task_names = list(broker.get_all_tasks())
        assert any("handle_shootout_audio_job" in name for name in task_names)
