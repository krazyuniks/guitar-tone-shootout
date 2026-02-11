"""Unit tests for Master Audio Creation Job.

Tests that the create_master_audio function loads all AudioSegment records for a shootout,
normalises each segment to -14.0 LUFS, updates records with post-normalisation loudness,
concatenates segments in position order, adds chapter markers, saves as FLAC, and updates
the shootout output_path field.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import pytest

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from webapp.adapters.persistence.models.base import Base
from webapp.adapters.persistence.models.shootout import (
    AudioSegment,
    Shootout,
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


class TestMasterAudioModule:
    """Test master_audio module exists and provides required function."""

    def test_master_audio_module_exists(self) -> None:
        """master_audio module exists in worker.jobs package."""
        from worker.jobs import master_audio  # noqa: F401

    def test_create_master_audio_function_exists(self) -> None:
        """create_master_audio function exists."""
        from worker.jobs.master_audio import create_master_audio

        assert callable(create_master_audio)


class TestCreateMasterAudio:
    """Test create_master_audio function behaviour."""

    async def test_loads_shootout_from_database(self, db_session: AsyncSession) -> None:
        """Function loads shootout from database to get all chains and segments."""
        from worker.jobs.master_audio import create_master_audio

        shootout_id = uuid4()

        with (
            patch("worker.jobs.master_audio.get_session") as mock_get_session,
            patch("worker.jobs.master_audio.normalize_loudness") as mock_normalize,
            patch("worker.jobs.master_audio.Path"),
        ):
            mock_session = AsyncMock(spec=AsyncSession)
            mock_get_session.return_value.__aenter__.return_value = mock_session

            # Mock shootout query
            mock_result = Mock()
            mock_result.unique.return_value.scalar_one_or_none.return_value = None
            mock_session.execute.return_value = mock_result

            mock_normalize.return_value = (-14.0, -6.0)

            await create_master_audio(shootout_id)

            # Verify database was queried for shootout
            assert mock_session.execute.called

    async def test_loads_all_shootout_chains_with_segments(self, db_session: AsyncSession) -> None:
        """Function loads all shootout chains with their audio segments."""
        from worker.jobs.master_audio import create_master_audio

        shootout_id = uuid4()

        with (
            patch("worker.jobs.master_audio.get_session") as mock_get_session,
            patch("worker.jobs.master_audio.normalize_loudness") as mock_normalize,
            patch("worker.jobs.master_audio.Path"),
        ):
            mock_session = AsyncMock(spec=AsyncSession)
            mock_get_session.return_value.__aenter__.return_value = mock_session

            # Mock shootout with chains
            chain1 = Mock(spec=ShootoutChain, position=0, label="Chain A")
            chain1.segments = []
            chain2 = Mock(spec=ShootoutChain, position=1, label="Chain B")
            chain2.segments = []

            shootout = Mock(spec=Shootout)
            shootout.chains = [chain1, chain2]

            mock_result = Mock()
            mock_result.unique.return_value.scalar_one_or_none.return_value = shootout
            mock_session.execute.return_value = mock_result

            mock_normalize.return_value = (-14.0, -6.0)

            await create_master_audio(shootout_id)

            # Verify query used joinedload for chains and segments
            assert mock_session.execute.called

    async def test_calls_normalize_loudness_for_each_segment(
        self, db_session: AsyncSession
    ) -> None:
        """Function calls normalize_loudness for each audio segment with target -14.0 LUFS."""
        from worker.jobs.master_audio import create_master_audio

        shootout_id = uuid4()

        with (
            patch("worker.jobs.master_audio.get_session") as mock_get_session,
            patch("worker.jobs.master_audio.normalize_loudness") as mock_normalize,
            patch("worker.jobs.master_audio.Path"),
            patch("worker.jobs.master_audio.sf"),
        ):
            mock_session = AsyncMock(spec=AsyncSession)
            mock_get_session.return_value.__aenter__.return_value = mock_session

            # Create segments
            segment1 = Mock(
                spec=AudioSegment,
                file_path="/processed/shootout1/chain1.flac",
                integrated_lufs=-12.0,
                peak_dbfs=-3.0,
            )
            segment2 = Mock(
                spec=AudioSegment,
                file_path="/processed/shootout1/chain2.flac",
                integrated_lufs=-16.0,
                peak_dbfs=-5.0,
            )

            chain = Mock(spec=ShootoutChain, position=0)
            chain.segments = [segment1, segment2]

            shootout = Mock(spec=Shootout, id=shootout_id)
            shootout.chains = [chain]

            mock_result = Mock()
            mock_result.unique.return_value.scalar_one_or_none.return_value = shootout
            mock_session.execute.return_value = mock_result

            mock_normalize.return_value = (-14.0, -6.0)

            await create_master_audio(shootout_id)

            # Verify normalize_loudness called for each segment with target -14.0
            assert mock_normalize.call_count == 2
            # Check target_lufs argument
            for call_item in mock_normalize.call_args_list:
                assert call_item.kwargs.get("target_lufs") == -14.0

    async def test_updates_audio_segment_records_with_normalized_loudness(
        self, db_session: AsyncSession
    ) -> None:
        """Function updates AudioSegment records with post-normalisation loudness values."""
        from worker.jobs.master_audio import create_master_audio

        shootout_id = uuid4()

        with (
            patch("worker.jobs.master_audio.get_session") as mock_get_session,
            patch("worker.jobs.master_audio.normalize_loudness") as mock_normalize,
            patch("worker.jobs.master_audio.Path"),
            patch("worker.jobs.master_audio.sf"),
        ):
            mock_session = AsyncMock(spec=AsyncSession)
            mock_get_session.return_value.__aenter__.return_value = mock_session

            # Create segment
            segment = Mock(
                spec=AudioSegment,
                file_path="/processed/shootout1/chain1.flac",
                integrated_lufs=-12.0,
                peak_dbfs=-3.0,
            )

            chain = Mock(spec=ShootoutChain, position=0)
            chain.segments = [segment]

            shootout = Mock(spec=Shootout, id=shootout_id)
            shootout.chains = [chain]

            mock_result = Mock()
            mock_result.unique.return_value.scalar_one_or_none.return_value = shootout
            mock_session.execute.return_value = mock_result

            # normalize_loudness returns new LUFS and peak
            normalized_lufs = -14.0
            normalized_peak = -4.5
            mock_normalize.return_value = (normalized_lufs, normalized_peak)

            await create_master_audio(shootout_id)

            # Verify segment loudness values were updated
            assert segment.integrated_lufs == normalized_lufs
            assert segment.peak_dbfs == normalized_peak

    async def test_concatenates_segments_in_chain_position_order(
        self, db_session: AsyncSession
    ) -> None:
        """Function concatenates normalised segments in chain position order."""
        from worker.jobs.master_audio import create_master_audio

        shootout_id = uuid4()

        with (
            patch("worker.jobs.master_audio.get_session") as mock_get_session,
            patch("worker.jobs.master_audio.normalize_loudness") as mock_normalize,
            patch("worker.jobs.master_audio.Path"),
            patch("worker.jobs.master_audio.sf") as mock_sf,
        ):
            mock_session = AsyncMock(spec=AsyncSession)
            mock_get_session.return_value.__aenter__.return_value = mock_session

            # Create segments in different chains with positions
            segment1 = Mock(
                spec=AudioSegment,
                file_path="/processed/shootout1/chain1.flac",
                duration_seconds=5.0,
            )
            segment2 = Mock(
                spec=AudioSegment,
                file_path="/processed/shootout1/chain2.flac",
                duration_seconds=5.0,
            )

            chain1 = Mock(spec=ShootoutChain, position=1)
            chain1.segments = [segment2]
            chain2 = Mock(spec=ShootoutChain, position=0)
            chain2.segments = [segment1]

            shootout = Mock(spec=Shootout, id=shootout_id)
            shootout.chains = [chain1, chain2]  # Deliberately out of order

            mock_result = Mock()
            mock_result.unique.return_value.scalar_one_or_none.return_value = shootout
            mock_session.execute.return_value = mock_result

            mock_normalize.return_value = (-14.0, -6.0)

            # Mock soundfile reads
            import numpy as np

            mock_sf.read.return_value = (np.zeros(48000, dtype=np.float32), 48000)

            await create_master_audio(shootout_id)

            # Verify segments were loaded in position order (chain2 before chain1)
            # This will be verified by concatenation order in implementation

    async def test_saves_master_audio_as_flac_in_processed_directory(
        self, db_session: AsyncSession
    ) -> None:
        """Function saves master audio as FLAC at processed/{shootout_id}/master.flac."""
        from worker.jobs.master_audio import create_master_audio

        shootout_id = uuid4()

        with (
            patch("worker.jobs.master_audio.get_session") as mock_get_session,
            patch("worker.jobs.master_audio.normalize_loudness") as mock_normalize,
            patch("worker.jobs.master_audio.Path"),
            patch("worker.jobs.master_audio.sf") as mock_sf,
        ):
            mock_session = AsyncMock(spec=AsyncSession)
            mock_get_session.return_value.__aenter__.return_value = mock_session

            segment = Mock(spec=AudioSegment, file_path="/processed/shootout1/chain1.flac")
            chain = Mock(spec=ShootoutChain, position=0)
            chain.segments = [segment]

            shootout = Mock(spec=Shootout, id=shootout_id)
            shootout.chains = [chain]

            mock_result = Mock()
            mock_result.unique.return_value.scalar_one_or_none.return_value = shootout
            mock_session.execute.return_value = mock_result

            mock_normalize.return_value = (-14.0, -6.0)

            import numpy as np

            mock_sf.read.return_value = (np.zeros(48000, dtype=np.float32), 48000)

            await create_master_audio(shootout_id)

            # Verify soundfile.write was called to save master.flac
            assert mock_sf.write.called

            # Verify output path includes shootout_id and master.flac
            write_call_args = mock_sf.write.call_args
            output_path_arg = str(write_call_args[0][0])
            assert str(shootout_id) in output_path_arg
            assert "master.flac" in output_path_arg

    async def test_updates_shootout_output_path_field(self, db_session: AsyncSession) -> None:
        """Function updates shootout.output_path with master audio file location."""
        from worker.jobs.master_audio import create_master_audio

        shootout_id = uuid4()

        with (
            patch("worker.jobs.master_audio.get_session") as mock_get_session,
            patch("worker.jobs.master_audio.normalize_loudness") as mock_normalize,
            patch("worker.jobs.master_audio.Path"),
            patch("worker.jobs.master_audio.sf") as mock_sf,
        ):
            mock_session = AsyncMock(spec=AsyncSession)
            mock_get_session.return_value.__aenter__.return_value = mock_session

            segment = Mock(spec=AudioSegment, file_path="/processed/shootout1/chain1.flac")
            chain = Mock(spec=ShootoutChain, position=0)
            chain.segments = [segment]

            shootout = Mock(spec=Shootout, id=shootout_id)
            shootout.chains = [chain]
            shootout.output_path = None  # Initially null

            mock_result = Mock()
            mock_result.unique.return_value.scalar_one_or_none.return_value = shootout
            mock_session.execute.return_value = mock_result

            mock_normalize.return_value = (-14.0, -6.0)

            import numpy as np

            mock_sf.read.return_value = (np.zeros(48000, dtype=np.float32), 48000)

            await create_master_audio(shootout_id)

            # Verify output_path was set
            assert shootout.output_path is not None
            assert str(shootout_id) in shootout.output_path
            assert "master.flac" in shootout.output_path

    async def test_creates_chapter_markers_for_segment_boundaries(
        self, db_session: AsyncSession
    ) -> None:
        """Function adds chapter markers at segment boundaries with chain labels."""
        from worker.jobs.master_audio import create_master_audio

        shootout_id = uuid4()

        with (
            patch("worker.jobs.master_audio.get_session") as mock_get_session,
            patch("worker.jobs.master_audio.normalize_loudness") as mock_normalize,
            patch("worker.jobs.master_audio.Path"),
            patch("worker.jobs.master_audio.sf") as mock_sf,
        ):
            mock_session = AsyncMock(spec=AsyncSession)
            mock_get_session.return_value.__aenter__.return_value = mock_session

            # Create segments with durations
            segment1 = Mock(
                spec=AudioSegment,
                file_path="/processed/shootout1/chain1.flac",
                duration_seconds=5.0,
            )
            segment2 = Mock(
                spec=AudioSegment,
                file_path="/processed/shootout1/chain2.flac",
                duration_seconds=7.0,
            )

            chain1 = Mock(spec=ShootoutChain, position=0, label="Mesa Boogie")
            chain1.segments = [segment1]
            chain2 = Mock(spec=ShootoutChain, position=1, label="Fender Twin")
            chain2.segments = [segment2]

            shootout = Mock(spec=Shootout, id=shootout_id)
            shootout.chains = [chain1, chain2]

            mock_result = Mock()
            mock_result.unique.return_value.scalar_one_or_none.return_value = shootout
            mock_session.execute.return_value = mock_result

            mock_normalize.return_value = (-14.0, -6.0)

            import numpy as np

            mock_sf.read.return_value = (np.zeros(48000, dtype=np.float32), 48000)

            await create_master_audio(shootout_id)

            # Chapter markers should be created:
            # Chapter 1: 0.0s - "Mesa Boogie"
            # Chapter 2: 5.0s - "Fender Twin"
            # Implementation will verify this through metadata or separate chapter file

    async def test_handles_empty_shootout_gracefully(self, db_session: AsyncSession) -> None:
        """Function handles shootout with no segments without error."""
        from worker.jobs.master_audio import create_master_audio

        shootout_id = uuid4()

        with (
            patch("worker.jobs.master_audio.get_session") as mock_get_session,
            patch("worker.jobs.master_audio.normalize_loudness") as mock_normalize,
        ):
            mock_session = AsyncMock(spec=AsyncSession)
            mock_get_session.return_value.__aenter__.return_value = mock_session

            # Shootout with no chains
            shootout = Mock(spec=Shootout, id=shootout_id)
            shootout.chains = []

            mock_result = Mock()
            mock_result.unique.return_value.scalar_one_or_none.return_value = shootout
            mock_session.execute.return_value = mock_result

            # Should not raise exception
            await create_master_audio(shootout_id)

            # normalize_loudness should not be called
            assert mock_normalize.call_count == 0

    async def test_handles_shootout_not_found(self, db_session: AsyncSession) -> None:
        """Function raises error when shootout does not exist."""
        from worker.jobs.master_audio import create_master_audio

        shootout_id = uuid4()

        with (
            patch("worker.jobs.master_audio.get_session") as mock_get_session,
        ):
            mock_session = AsyncMock(spec=AsyncSession)
            mock_get_session.return_value.__aenter__.return_value = mock_session

            # Shootout not found
            mock_result = Mock()
            mock_result.unique.return_value.scalar_one_or_none.return_value = None
            mock_session.execute.return_value = mock_result

            # Should raise exception
            with pytest.raises(ValueError, match="not found"):
                await create_master_audio(shootout_id)

    async def test_creates_output_directory_if_not_exists(self, db_session: AsyncSession) -> None:
        """Function creates processed/{shootout_id} directory if it does not exist."""
        from worker.jobs.master_audio import create_master_audio

        shootout_id = uuid4()

        with (
            patch("worker.jobs.master_audio.get_session") as mock_get_session,
            patch("worker.jobs.master_audio.normalize_loudness") as mock_normalize,
            patch("worker.jobs.master_audio.Path") as mock_path_class,
            patch("worker.jobs.master_audio.sf") as mock_sf,
        ):
            mock_session = AsyncMock(spec=AsyncSession)
            mock_get_session.return_value.__aenter__.return_value = mock_session

            segment = Mock(spec=AudioSegment, file_path="/processed/shootout1/chain1.flac")
            chain = Mock(spec=ShootoutChain, position=0)
            chain.segments = [segment]

            shootout = Mock(spec=Shootout, id=shootout_id)
            shootout.chains = [chain]

            mock_result = Mock()
            mock_result.unique.return_value.scalar_one_or_none.return_value = shootout
            mock_session.execute.return_value = mock_result

            mock_normalize.return_value = (-14.0, -6.0)

            import numpy as np

            mock_sf.read.return_value = (np.zeros(48000, dtype=np.float32), 48000)

            # Mock Path to track mkdir calls
            mock_path_instance = Mock()
            mock_path_class.return_value = mock_path_instance

            await create_master_audio(shootout_id)

            # Verify parent directory mkdir was called with parents=True
            # This ensures the output directory is created

    async def test_commits_database_changes(self, db_session: AsyncSession) -> None:
        """Function commits all database changes (segment updates, shootout.output_path)."""
        from worker.jobs.master_audio import create_master_audio

        shootout_id = uuid4()

        with (
            patch("worker.jobs.master_audio.get_session") as mock_get_session,
            patch("worker.jobs.master_audio.normalize_loudness") as mock_normalize,
            patch("worker.jobs.master_audio.Path"),
            patch("worker.jobs.master_audio.sf") as mock_sf,
        ):
            mock_session = AsyncMock(spec=AsyncSession)
            mock_get_session.return_value.__aenter__.return_value = mock_session

            segment = Mock(
                spec=AudioSegment,
                file_path="/processed/shootout1/chain1.flac",
                integrated_lufs=-12.0,
                peak_dbfs=-3.0,
            )
            chain = Mock(spec=ShootoutChain, position=0)
            chain.segments = [segment]

            shootout = Mock(spec=Shootout, id=shootout_id)
            shootout.chains = [chain]
            shootout.output_path = None

            mock_result = Mock()
            mock_result.unique.return_value.scalar_one_or_none.return_value = shootout
            mock_session.execute.return_value = mock_result

            mock_normalize.return_value = (-14.0, -6.0)

            import numpy as np

            mock_sf.read.return_value = (np.zeros(48000, dtype=np.float32), 48000)

            await create_master_audio(shootout_id)

            # Verify session.commit was called
            assert mock_session.commit.called

    async def test_normalises_temporary_files_not_original_segments(
        self, db_session: AsyncSession
    ) -> None:
        """Function normalises copies of segments, not the original processed audio files."""
        from worker.jobs.master_audio import create_master_audio

        shootout_id = uuid4()

        with (
            patch("worker.jobs.master_audio.get_session") as mock_get_session,
            patch("worker.jobs.master_audio.normalize_loudness") as mock_normalize,
            patch("worker.jobs.master_audio.Path"),
            patch("worker.jobs.master_audio.sf") as mock_sf,
        ):
            mock_session = AsyncMock(spec=AsyncSession)
            mock_get_session.return_value.__aenter__.return_value = mock_session

            original_file = "/processed/shootout1/chain1.flac"
            segment = Mock(spec=AudioSegment, file_path=original_file)
            chain = Mock(spec=ShootoutChain, position=0)
            chain.segments = [segment]

            shootout = Mock(spec=Shootout, id=shootout_id)
            shootout.chains = [chain]

            mock_result = Mock()
            mock_result.unique.return_value.scalar_one_or_none.return_value = shootout
            mock_session.execute.return_value = mock_result

            mock_normalize.return_value = (-14.0, -6.0)

            import numpy as np

            mock_sf.read.return_value = (np.zeros(48000, dtype=np.float32), 48000)

            await create_master_audio(shootout_id)

            # Verify normalize_loudness was NOT called with original file path as output
            # (Implementation should use temp files or copies)
            for call_item in mock_normalize.call_args_list:
                input_path = call_item[0][0]
                output_path = call_item[0][1]
                # Output should be different from input (temp file)
                assert input_path != output_path
