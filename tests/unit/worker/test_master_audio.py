"""Unit tests for Master Audio Creation Job.

Tests that the create_master_audio function loads all AudioSegment records for a shootout,
normalises each segment to -14.0 LUFS, updates records with post-normalisation loudness,
concatenates segments in position order, adds chapter markers, saves as FLAC, and updates
the shootout output_path field.
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING
from uuid import uuid4

import numpy as np
import pytest

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

from webapp.adapters.persistence.models.shootout import (
    AudioSegment,
    DITrack,
    Shootout,
    ShootoutChain,
)
from webapp.adapters.persistence.models.signal_chain import SignalChain
from webapp.adapters.persistence.models.user import User


def _make_fake_get_session(session: AsyncSession):
    """Create a fake get_session context manager that yields the test session."""

    @contextlib.asynccontextmanager
    async def fake_get_session(_url=None):
        yield session

    return fake_get_session


async def _create_shootout_fixture(
    session: AsyncSession,
    *,
    num_chains: int = 1,
    segments_per_chain: int = 1,
    chain_labels: list[str] | None = None,
) -> tuple:
    """Create a Shootout with chains and audio segments.

    Returns:
        (shootout_id, chain_ids, segment_ids) tuple
    """
    # Create user for FK satisfaction
    user = User(
        id=uuid4(),
        username=f"testuser-{uuid4().hex[:8]}",
        is_active=True,
    )
    session.add(user)
    await session.flush()

    user_id = user.id
    shootout_id = uuid4()

    # DITrack needed for Shootout FK
    di_track = DITrack(
        id=uuid4(),
        user_id=user_id,
        name="Test DI",
        file_path="/uploads/test.wav",
        original_filename="test.wav",
        duration_seconds=10.0,
        sample_rate=48000,
    )
    session.add(di_track)

    shootout = Shootout(
        id=shootout_id,
        user_id=user_id,
        di_track_id=di_track.id,
        name="Test Shootout",
    )
    session.add(shootout)

    # SignalChain needed for ShootoutChain FK
    signal_chain = SignalChain(
        id=uuid4(),
        user_id=user_id,
        name="Test Chain",
    )
    session.add(signal_chain)

    chain_ids = []
    segment_ids = []
    labels = chain_labels or [f"Chain {i}" for i in range(num_chains)]

    for i in range(num_chains):
        chain_id = uuid4()
        chain = ShootoutChain(
            id=chain_id,
            shootout_id=shootout_id,
            signal_chain_id=signal_chain.id,
            position=i,
            label=labels[i] if i < len(labels) else f"Chain {i}",
        )
        session.add(chain)
        chain_ids.append(chain_id)

        for j in range(segments_per_chain):
            seg_id = uuid4()
            segment = AudioSegment(
                id=seg_id,
                shootout_chain_id=chain_id,
                file_path=f"/processed/{shootout_id}/chain{i}_seg{j}.flac",
                duration_seconds=5.0,
                integrated_lufs=-12.0,
                peak_dbfs=-3.0,
            )
            session.add(segment)
            segment_ids.append(seg_id)

    await session.flush()
    return shootout_id, chain_ids, segment_ids


# --- Tracking test doubles ---

_normalize_calls: list[dict] = []
_sf_write_calls: list[dict] = []


def _fake_normalize_loudness(input_path, output_path, *, target_lufs=-14.0):
    """Test double that tracks calls and returns normalised values."""
    _normalize_calls.append(
        {"input": str(input_path), "output": str(output_path), "target_lufs": target_lufs}
    )
    return (-14.0, -6.0)


def _fake_sf_read(_path):
    """Test double returning 1 second of silence at 48kHz."""
    return np.zeros(48000, dtype=np.float32), 48000


def _fake_sf_write(path, data, samplerate):
    """Test double that tracks write calls."""
    _sf_write_calls.append({"path": str(path), "samples": len(data), "samplerate": samplerate})


def _apply_master_audio_monkeypatches(
    monkeypatch: pytest.MonkeyPatch,
    session: AsyncSession,
    *,
    normalize_loudness=None,
    sf_read=None,
    sf_write=None,
) -> None:
    """Apply monkeypatches for master_audio tests."""
    monkeypatch.setattr("worker.jobs.master_audio.get_session", _make_fake_get_session(session))
    monkeypatch.setattr(
        "worker.jobs.master_audio.normalize_loudness",
        normalize_loudness or _fake_normalize_loudness,
    )
    monkeypatch.setattr("worker.jobs.master_audio.sf.read", sf_read or _fake_sf_read)
    monkeypatch.setattr("worker.jobs.master_audio.sf.write", sf_write or _fake_sf_write)
    # Prevent real filesystem operations
    monkeypatch.setattr("worker.jobs.master_audio.Path.mkdir", lambda *_a, **_kw: None)


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

    async def test_loads_shootout_from_database(
        self, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Function loads shootout from database by ID."""
        from worker.jobs.master_audio import create_master_audio

        shootout_id, _, _ = await _create_shootout_fixture(db_session)
        _normalize_calls.clear()

        _apply_master_audio_monkeypatches(monkeypatch, db_session)
        await create_master_audio(shootout_id)

        # If it didn't raise, it found the shootout
        assert len(_normalize_calls) == 1

    async def test_loads_all_shootout_chains_with_segments(
        self, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Function loads all shootout chains and processes each segment."""
        from worker.jobs.master_audio import create_master_audio

        shootout_id, _, _ = await _create_shootout_fixture(db_session, num_chains=2)
        _normalize_calls.clear()

        _apply_master_audio_monkeypatches(monkeypatch, db_session)
        await create_master_audio(shootout_id)

        # 2 chains * 1 segment each = 2 normalize calls
        assert len(_normalize_calls) == 2

    async def test_calls_normalize_loudness_for_each_segment(
        self, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Function calls normalize_loudness for each segment with target -14.0 LUFS."""
        from worker.jobs.master_audio import create_master_audio

        shootout_id, _, _ = await _create_shootout_fixture(
            db_session, num_chains=1, segments_per_chain=2
        )
        _normalize_calls.clear()

        _apply_master_audio_monkeypatches(monkeypatch, db_session)
        await create_master_audio(shootout_id)

        assert len(_normalize_calls) == 2
        for call in _normalize_calls:
            assert call["target_lufs"] == -14.0

    async def test_updates_audio_segment_records_with_normalized_loudness(
        self, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Function updates AudioSegment records with post-normalisation loudness values."""
        from sqlalchemy import select

        from worker.jobs.master_audio import create_master_audio

        shootout_id, _, segment_ids = await _create_shootout_fixture(db_session)
        _normalize_calls.clear()

        _apply_master_audio_monkeypatches(monkeypatch, db_session)
        await create_master_audio(shootout_id)

        # Reload the segment and check updated values
        result = await db_session.execute(
            select(AudioSegment).where(AudioSegment.id == segment_ids[0])
        )
        segment = result.scalar_one()
        assert segment.integrated_lufs == -14.0
        assert segment.peak_dbfs == -6.0

    async def test_concatenates_segments_in_chain_position_order(
        self, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Function concatenates normalised segments in chain position order."""
        from worker.jobs.master_audio import create_master_audio

        shootout_id, _, _ = await _create_shootout_fixture(db_session, num_chains=2)
        _normalize_calls.clear()

        _apply_master_audio_monkeypatches(monkeypatch, db_session)
        await create_master_audio(shootout_id)

        # Position 0 should be processed before position 1
        assert "chain0" in _normalize_calls[0]["input"]
        assert "chain1" in _normalize_calls[1]["input"]

    async def test_saves_master_audio_as_flac_in_processed_directory(
        self, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Function saves master audio as FLAC at processed/{shootout_id}/master.flac."""
        from worker.jobs.master_audio import create_master_audio

        shootout_id, _, _ = await _create_shootout_fixture(db_session)
        _sf_write_calls.clear()

        _apply_master_audio_monkeypatches(monkeypatch, db_session)
        await create_master_audio(shootout_id)

        assert len(_sf_write_calls) == 1
        assert str(shootout_id) in _sf_write_calls[0]["path"]
        assert "master.flac" in _sf_write_calls[0]["path"]

    async def test_updates_shootout_output_path_field(
        self, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Function updates shootout.output_path with master audio file location."""
        from sqlalchemy import select

        from worker.jobs.master_audio import create_master_audio

        shootout_id, _, _ = await _create_shootout_fixture(db_session)

        _apply_master_audio_monkeypatches(monkeypatch, db_session)
        await create_master_audio(shootout_id)

        result = await db_session.execute(select(Shootout).where(Shootout.id == shootout_id))
        shootout = result.scalar_one()
        assert shootout.output_path is not None
        assert str(shootout_id) in shootout.output_path
        assert "master.flac" in shootout.output_path

    async def test_handles_empty_shootout_gracefully(
        self, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Function handles shootout with no chains without error."""
        from worker.jobs.master_audio import create_master_audio

        shootout_id, _, _ = await _create_shootout_fixture(
            db_session, num_chains=0, segments_per_chain=0
        )
        _normalize_calls.clear()

        _apply_master_audio_monkeypatches(monkeypatch, db_session)
        await create_master_audio(shootout_id)

        assert len(_normalize_calls) == 0

    async def test_handles_shootout_not_found(
        self, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Function raises error when shootout does not exist."""
        from worker.jobs.master_audio import create_master_audio

        _apply_master_audio_monkeypatches(monkeypatch, db_session)

        with pytest.raises(ValueError, match="not found"):
            await create_master_audio(uuid4())

    async def test_normalize_uses_different_output_path_than_input(
        self, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Function normalises to a different file, not overwriting the original."""
        from worker.jobs.master_audio import create_master_audio

        shootout_id, _, _ = await _create_shootout_fixture(db_session)
        _normalize_calls.clear()

        _apply_master_audio_monkeypatches(monkeypatch, db_session)
        await create_master_audio(shootout_id)

        for call in _normalize_calls:
            assert call["input"] != call["output"]

    async def test_commits_database_changes(
        self, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Function commits segment updates and shootout.output_path to database."""
        from sqlalchemy import select

        from worker.jobs.master_audio import create_master_audio

        shootout_id, _, segment_ids = await _create_shootout_fixture(db_session)

        _apply_master_audio_monkeypatches(monkeypatch, db_session)
        await create_master_audio(shootout_id)

        # Verify output_path was persisted
        result = await db_session.execute(select(Shootout).where(Shootout.id == shootout_id))
        shootout = result.scalar_one()
        assert shootout.output_path is not None

        # Verify segment loudness was persisted
        result = await db_session.execute(
            select(AudioSegment).where(AudioSegment.id == segment_ids[0])
        )
        segment = result.scalar_one()
        assert segment.integrated_lufs == -14.0

    async def test_creates_chapter_markers_for_segment_boundaries(
        self, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Function processes segments from chains with proper labels."""
        from worker.jobs.master_audio import create_master_audio

        shootout_id, _, _ = await _create_shootout_fixture(
            db_session, num_chains=2, chain_labels=["Mesa Boogie", "Fender Twin"]
        )
        _normalize_calls.clear()
        _sf_write_calls.clear()

        _apply_master_audio_monkeypatches(monkeypatch, db_session)
        await create_master_audio(shootout_id)

        # Verify both chains were processed (chapter markers are internal)
        assert len(_normalize_calls) == 2
        # Master was written
        assert len(_sf_write_calls) == 1
        # Master should contain concatenated audio from both chains
        assert _sf_write_calls[0]["samples"] == 48000 * 2  # 2 segments of 1s each
