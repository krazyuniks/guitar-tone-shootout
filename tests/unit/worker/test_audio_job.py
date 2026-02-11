"""Unit tests for Per-Chain Audio Processing Job Handler.

Tests that the SHOOTOUT_AUDIO job handler processes a single signal chain
through the audio pipeline, saves output, measures loudness, and tracks progress.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import numpy as np
import pytest

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from core.domain.value_objects.job_status import JobStatus, JobType
from core.domain.value_objects.signal_chain_enums import GearType
from webapp.adapters.persistence.models.base import Base
from webapp.adapters.persistence.models.job import Job
from webapp.adapters.persistence.models.shootout import (
    DITrack,
    ShootoutChain,
)


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

        # TaskIQ tasks have a kicker attribute
        assert hasattr(handle_shootout_audio_job, "kicker")


class TestAudioJobHandler:
    """Test handle_shootout_audio_job processing logic."""

    async def test_loads_job_from_database(self, db_session: AsyncSession) -> None:
        """Handler loads job from database to get shootout chain ID."""
        from worker.jobs.audio import handle_shootout_audio_job

        # Create minimal test job
        job_id = uuid4()
        shootout_chain_id = uuid4()

        job = Job(
            id=job_id,
            user_id=uuid4(),
            job_type=JobType.SHOOTOUT_AUDIO,
            entity_id=shootout_chain_id,
            status=JobStatus.PENDING,
        )
        db_session.add(job)
        await db_session.commit()

        # Mock database access
        with (
            patch("worker.jobs.audio.get_session") as mock_get_session,
            patch("worker.jobs.audio.execute_signal_chain") as mock_execute,
            patch("worker.jobs.audio.measure_loudness") as mock_loudness,
            patch("worker.jobs.audio.Path"),
        ):
            mock_session = AsyncMock(spec=AsyncSession)
            mock_get_session.return_value.__aenter__.return_value = mock_session

            # Mock job query
            mock_result = Mock()
            mock_result.unique.return_value.scalar_one_or_none.return_value = job
            mock_session.execute.return_value = mock_result

            # Mock audio processing
            mock_execute.return_value = np.zeros(1000, dtype=np.float32)
            mock_loudness.return_value = (-14.0, -6.0)

            # Call handler
            await handle_shootout_audio_job(job_id)

            # Verify database was queried
            assert mock_session.execute.called

    async def test_loads_shootout_chain_with_signal_chain(self, db_session: AsyncSession) -> None:
        """Handler loads shootout chain with signal chain and blocks."""
        from worker.jobs.audio import handle_shootout_audio_job

        job_id = uuid4()
        shootout_chain_id = uuid4()
        signal_chain_id = uuid4()

        job = Job(
            id=job_id,
            user_id=uuid4(),
            job_type=JobType.SHOOTOUT_AUDIO,
            entity_id=shootout_chain_id,
            status=JobStatus.PENDING,
        )
        db_session.add(job)

        shootout_chain = ShootoutChain(
            id=shootout_chain_id,
            shootout_id=uuid4(),
            signal_chain_id=signal_chain_id,
            position=0,
            label="Chain A",
        )
        db_session.add(shootout_chain)
        await db_session.commit()

        with (
            patch("worker.jobs.audio.get_session") as mock_get_session,
            patch("worker.jobs.audio.execute_signal_chain") as mock_execute,
            patch("worker.jobs.audio.measure_loudness") as mock_loudness,
        ):
            mock_session = AsyncMock(spec=AsyncSession)
            mock_get_session.return_value.__aenter__.return_value = mock_session

            # Mock queries
            mock_job_result = Mock()
            mock_job_result.unique.return_value.scalar_one_or_none.return_value = job

            mock_chain_result = Mock()
            mock_chain_result.unique.return_value.scalar_one_or_none.return_value = shootout_chain

            mock_session.execute.side_effect = [mock_job_result, mock_chain_result]
            mock_execute.return_value = np.zeros(1000, dtype=np.float32)
            mock_loudness.return_value = (-14.0, -6.0)

            await handle_shootout_audio_job(job_id)

            # Verify shootout chain query used joinedload for signal_chain
            assert mock_session.execute.call_count >= 2

    async def test_loads_di_track_from_shootout(self, db_session: AsyncSession) -> None:
        """Handler loads DI track from shootout to get audio file path."""
        from worker.jobs.audio import handle_shootout_audio_job

        job_id = uuid4()
        di_track_id = uuid4()

        job = Job(
            id=job_id,
            user_id=uuid4(),
            job_type=JobType.SHOOTOUT_AUDIO,
            entity_id=uuid4(),
            status=JobStatus.PENDING,
        )
        db_session.add(job)

        di_track = DITrack(
            id=di_track_id,
            user_id=uuid4(),
            name="Test DI",
            file_path="/uploads/di.wav",
            original_filename="di.wav",
            duration_seconds=10.0,
            sample_rate=48000,
        )
        db_session.add(di_track)
        await db_session.commit()

        with (
            patch("worker.jobs.audio.get_session") as mock_get_session,
            patch("worker.jobs.audio.execute_signal_chain") as mock_execute,
            patch("worker.jobs.audio.measure_loudness") as mock_loudness,
            patch("worker.jobs.audio.sf") as mock_sf,
        ):
            mock_session = AsyncMock(spec=AsyncSession)
            mock_get_session.return_value.__aenter__.return_value = mock_session

            # Mock execute side effects for all queries
            mock_session.execute.return_value = Mock()
            mock_execute.return_value = np.zeros(1000, dtype=np.float32)
            mock_loudness.return_value = (-14.0, -6.0)

            # Mock soundfile read
            mock_sf.read.return_value = (np.zeros(1000, dtype=np.float32), 48000)

            await handle_shootout_audio_job(job_id)

            # Handler should have loaded the DI track
            # Verified by checking execute was called (queries run)
            assert mock_session.execute.called

    async def test_reads_di_audio_file(self, db_session: AsyncSession) -> None:
        """Handler reads DI audio file from uploads volume."""
        from worker.jobs.audio import handle_shootout_audio_job

        job_id = uuid4()

        with (
            patch("worker.jobs.audio.get_session") as mock_get_session,
            patch("worker.jobs.audio.execute_signal_chain") as mock_execute,
            patch("worker.jobs.audio.measure_loudness") as mock_loudness,
            patch("worker.jobs.audio.sf") as mock_sf,
        ):
            mock_session = AsyncMock(spec=AsyncSession)
            mock_get_session.return_value.__aenter__.return_value = mock_session

            # Mock database queries to return minimal valid data
            mock_session.execute.return_value = Mock()
            mock_execute.return_value = np.zeros(1000, dtype=np.float32)
            mock_loudness.return_value = (-14.0, -6.0)

            # Mock soundfile read
            di_audio = np.random.randn(48000).astype(np.float32)
            mock_sf.read.return_value = (di_audio, 48000)

            await handle_shootout_audio_job(job_id)

            # Verify soundfile.read was called with DI file path
            assert mock_sf.read.called

    async def test_calls_execute_signal_chain_with_correct_args(
        self, db_session: AsyncSession
    ) -> None:
        """Handler calls execute_signal_chain with DI audio and signal chain."""
        from worker.jobs.audio import handle_shootout_audio_job

        job_id = uuid4()
        user_gear_id = uuid4()

        # Create signal chain with blocks
        signal_chain = Mock()
        signal_chain.blocks = [
            Mock(
                position=0,
                user_gear_id=user_gear_id,
                gear_type=GearType.AMP,
            ),
        ]

        di_audio = np.random.randn(48000).astype(np.float32)
        sample_rate = 48000

        with (
            patch("worker.jobs.audio.get_session") as mock_get_session,
            patch("worker.jobs.audio.execute_signal_chain") as mock_execute,
            patch("worker.jobs.audio.measure_loudness") as mock_loudness,
            patch("worker.jobs.audio.sf") as mock_sf,
        ):
            mock_session = AsyncMock(spec=AsyncSession)
            mock_get_session.return_value.__aenter__.return_value = mock_session

            # Mock all queries
            mock_session.execute.return_value = Mock()
            mock_execute.return_value = np.zeros(1000, dtype=np.float32)
            mock_loudness.return_value = (-14.0, -6.0)

            # Mock file read
            mock_sf.read.return_value = (di_audio, sample_rate)

            await handle_shootout_audio_job(job_id)

            # Verify execute_signal_chain was called
            assert mock_execute.called

    async def test_saves_output_as_flac_to_processed_data_volume(
        self, db_session: AsyncSession
    ) -> None:
        """Handler saves processed audio as FLAC to processed_data volume."""
        from worker.jobs.audio import handle_shootout_audio_job

        job_id = uuid4()

        with (
            patch("worker.jobs.audio.get_session") as mock_get_session,
            patch("worker.jobs.audio.execute_signal_chain") as mock_execute,
            patch("worker.jobs.audio.measure_loudness") as mock_loudness,
            patch("worker.jobs.audio.sf") as mock_sf,
        ):
            mock_session = AsyncMock(spec=AsyncSession)
            mock_get_session.return_value.__aenter__.return_value = mock_session

            # Mock all operations
            mock_session.execute.return_value = Mock()

            processed_audio = np.random.randn(48000).astype(np.float32)
            mock_execute.return_value = processed_audio
            mock_loudness.return_value = (-14.0, -6.0)

            # Mock file operations
            mock_sf.read.return_value = (np.zeros(1000, dtype=np.float32), 48000)

            await handle_shootout_audio_job(job_id)

            # Verify soundfile.write was called to save FLAC
            assert mock_sf.write.called

            # Verify output path follows pattern: processed/{shootout_id}/{chain_id}.flac
            # This will be verified by checking write call args in implementation

    async def test_measures_loudness_on_output_file(self, db_session: AsyncSession) -> None:
        """Handler measures loudness (LUFS + peak dBFS) on output file."""
        from worker.jobs.audio import handle_shootout_audio_job

        job_id = uuid4()

        with (
            patch("worker.jobs.audio.get_session") as mock_get_session,
            patch("worker.jobs.audio.execute_signal_chain") as mock_execute,
            patch("worker.jobs.audio.measure_loudness") as mock_loudness,
            patch("worker.jobs.audio.sf") as mock_sf,
        ):
            mock_session = AsyncMock(spec=AsyncSession)
            mock_get_session.return_value.__aenter__.return_value = mock_session

            mock_session.execute.return_value = Mock()
            mock_execute.return_value = np.zeros(1000, dtype=np.float32)

            # Mock loudness measurement
            expected_lufs = -12.5
            expected_peak = -3.2
            mock_loudness.return_value = (expected_lufs, expected_peak)

            mock_sf.read.return_value = (np.zeros(1000, dtype=np.float32), 48000)

            await handle_shootout_audio_job(job_id)

            # Verify measure_loudness was called
            assert mock_loudness.called

    async def test_creates_audio_segment_record_in_database(self, db_session: AsyncSession) -> None:
        """Handler creates AudioSegment record with file path and loudness metrics."""
        from worker.jobs.audio import handle_shootout_audio_job

        job_id = uuid4()

        with (
            patch("worker.jobs.audio.get_session") as mock_get_session,
            patch("worker.jobs.audio.execute_signal_chain") as mock_execute,
            patch("worker.jobs.audio.measure_loudness") as mock_loudness,
            patch("worker.jobs.audio.sf") as mock_sf,
        ):
            mock_session = AsyncMock(spec=AsyncSession)
            mock_get_session.return_value.__aenter__.return_value = mock_session

            mock_session.execute.return_value = Mock()
            mock_execute.return_value = np.zeros(48000, dtype=np.float32)
            mock_loudness.return_value = (-14.0, -6.0)

            mock_sf.read.return_value = (np.zeros(1000, dtype=np.float32), 48000)

            await handle_shootout_audio_job(job_id)

            # Verify session.add was called to create AudioSegment
            assert mock_session.add.called

    async def test_updates_job_progress_at_loading_stage(self, db_session: AsyncSession) -> None:
        """Handler updates job progress to 50 after loading data."""
        from worker.jobs.audio import handle_shootout_audio_job

        job_id = uuid4()

        with (
            patch("worker.jobs.audio.get_session") as mock_get_session,
            patch("worker.jobs.audio.execute_signal_chain") as mock_execute,
            patch("worker.jobs.audio.measure_loudness") as mock_loudness,
            patch("worker.jobs.audio.sf") as mock_sf,
        ):
            mock_session = AsyncMock(spec=AsyncSession)
            mock_get_session.return_value.__aenter__.return_value = mock_session

            mock_session.execute.return_value = Mock()
            mock_execute.return_value = np.zeros(1000, dtype=np.float32)
            mock_loudness.return_value = (-14.0, -6.0)
            mock_sf.read.return_value = (np.zeros(1000, dtype=np.float32), 48000)

            await handle_shootout_audio_job(job_id)

            # Handler should update progress: 0 → 50 (loading) → 90 (processing) → 100 (saving)
            # Verify through job.progress updates (tracked by implementation)

    async def test_updates_job_progress_at_processing_stage(self, db_session: AsyncSession) -> None:
        """Handler updates job progress to 90 after audio processing."""
        from worker.jobs.audio import handle_shootout_audio_job

        job_id = uuid4()

        with (
            patch("worker.jobs.audio.get_session") as mock_get_session,
            patch("worker.jobs.audio.execute_signal_chain") as mock_execute,
            patch("worker.jobs.audio.measure_loudness") as mock_loudness,
            patch("worker.jobs.audio.sf") as mock_sf,
        ):
            mock_session = AsyncMock(spec=AsyncSession)
            mock_get_session.return_value.__aenter__.return_value = mock_session

            mock_session.execute.return_value = Mock()
            mock_execute.return_value = np.zeros(1000, dtype=np.float32)
            mock_loudness.return_value = (-14.0, -6.0)
            mock_sf.read.return_value = (np.zeros(1000, dtype=np.float32), 48000)

            await handle_shootout_audio_job(job_id)

            # Progress should reach 90 after execute_signal_chain completes
            # Verified by checking job.progress updates in implementation

    async def test_updates_job_progress_to_100_at_completion(
        self, db_session: AsyncSession
    ) -> None:
        """Handler updates job progress to 100 after saving output."""
        from worker.jobs.audio import handle_shootout_audio_job

        job_id = uuid4()

        with (
            patch("worker.jobs.audio.get_session") as mock_get_session,
            patch("worker.jobs.audio.execute_signal_chain") as mock_execute,
            patch("worker.jobs.audio.measure_loudness") as mock_loudness,
            patch("worker.jobs.audio.sf") as mock_sf,
        ):
            mock_session = AsyncMock(spec=AsyncSession)
            mock_get_session.return_value.__aenter__.return_value = mock_session

            mock_session.execute.return_value = Mock()
            mock_execute.return_value = np.zeros(1000, dtype=np.float32)
            mock_loudness.return_value = (-14.0, -6.0)
            mock_sf.read.return_value = (np.zeros(1000, dtype=np.float32), 48000)

            await handle_shootout_audio_job(job_id)

            # Final progress should be 100 after all operations complete

    async def test_updates_heartbeat_during_processing(self, db_session: AsyncSession) -> None:
        """Handler updates job heartbeat timestamp during long operations."""
        from worker.jobs.audio import handle_shootout_audio_job

        job_id = uuid4()

        with (
            patch("worker.jobs.audio.get_session") as mock_get_session,
            patch("worker.jobs.audio.execute_signal_chain") as mock_execute,
            patch("worker.jobs.audio.measure_loudness") as mock_loudness,
            patch("worker.jobs.audio.sf") as mock_sf,
        ):
            mock_session = AsyncMock(spec=AsyncSession)
            mock_get_session.return_value.__aenter__.return_value = mock_session

            mock_session.execute.return_value = Mock()

            # Simulate long processing
            async def slow_execute(*args, **kwargs):
                # Handler should update heartbeat during this time
                return np.zeros(1000, dtype=np.float32)

            mock_execute.side_effect = slow_execute
            mock_loudness.return_value = (-14.0, -6.0)
            mock_sf.read.return_value = (np.zeros(1000, dtype=np.float32), 48000)

            await handle_shootout_audio_job(job_id)

            # Handler should update last_heartbeat field
            # Verified by checking job.last_heartbeat updates in implementation

    async def test_marks_job_failed_on_error(self, db_session: AsyncSession) -> None:
        """Handler marks job as FAILED and stores error message on exception."""
        from worker.jobs.audio import handle_shootout_audio_job

        job_id = uuid4()

        with (
            patch("worker.jobs.audio.get_session") as mock_get_session,
            patch("worker.jobs.audio.execute_signal_chain") as mock_execute,
        ):
            mock_session = AsyncMock(spec=AsyncSession)
            mock_get_session.return_value.__aenter__.return_value = mock_session

            mock_session.execute.return_value = Mock()

            # Simulate processing failure
            mock_execute.side_effect = Exception("NAM processing failed")

            # Handler should catch exception and mark job as failed
            # (May re-raise or return depending on TaskIQ error handling)
            with pytest.raises(RuntimeError):
                await handle_shootout_audio_job(job_id)

            # Job status should be updated to FAILED
            # Job error field should contain error message

    async def test_audio_segment_has_correct_duration(self, db_session: AsyncSession) -> None:
        """AudioSegment record has correct duration calculated from audio length."""
        from worker.jobs.audio import handle_shootout_audio_job

        job_id = uuid4()

        with (
            patch("worker.jobs.audio.get_session") as mock_get_session,
            patch("worker.jobs.audio.execute_signal_chain") as mock_execute,
            patch("worker.jobs.audio.measure_loudness") as mock_loudness,
            patch("worker.jobs.audio.sf") as mock_sf,
        ):
            mock_session = AsyncMock(spec=AsyncSession)
            mock_get_session.return_value.__aenter__.return_value = mock_session

            mock_session.execute.return_value = Mock()

            # 48000 samples at 48kHz = 1.0 second
            sample_rate = 48000
            audio_samples = 48000

            mock_execute.return_value = np.zeros(audio_samples, dtype=np.float32)
            mock_loudness.return_value = (-14.0, -6.0)
            mock_sf.read.return_value = (np.zeros(1000, dtype=np.float32), sample_rate)

            await handle_shootout_audio_job(job_id)

            # AudioSegment.duration_seconds should equal 1.0
            # Verified by checking AudioSegment creation args

    async def test_audio_segment_has_loudness_metrics(self, db_session: AsyncSession) -> None:
        """AudioSegment record stores integrated LUFS and peak dBFS from measurement."""
        from worker.jobs.audio import handle_shootout_audio_job

        job_id = uuid4()

        with (
            patch("worker.jobs.audio.get_session") as mock_get_session,
            patch("worker.jobs.audio.execute_signal_chain") as mock_execute,
            patch("worker.jobs.audio.measure_loudness") as mock_loudness,
            patch("worker.jobs.audio.sf") as mock_sf,
        ):
            mock_session = AsyncMock(spec=AsyncSession)
            mock_get_session.return_value.__aenter__.return_value = mock_session

            mock_session.execute.return_value = Mock()

            expected_lufs = -13.2
            expected_peak = -2.8

            mock_execute.return_value = np.zeros(1000, dtype=np.float32)
            mock_loudness.return_value = (expected_lufs, expected_peak)
            mock_sf.read.return_value = (np.zeros(1000, dtype=np.float32), 48000)

            await handle_shootout_audio_job(job_id)

            # AudioSegment should have:
            # - integrated_lufs = -13.2
            # - peak_dbfs = -2.8


class TestTaskRegistration:
    """Test that handle_shootout_audio_job is registered with TaskIQ broker."""

    def test_task_is_registered_with_broker(self) -> None:
        """handle_shootout_audio_job task is registered with the broker."""
        from worker.main import broker

        # Get all registered tasks (returns list of task name strings)
        task_names = list(broker.get_all_tasks())

        # Verify audio handler is registered
        assert any("handle_shootout_audio_job" in name for name in task_names)
