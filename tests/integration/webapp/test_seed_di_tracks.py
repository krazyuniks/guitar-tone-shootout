"""Integration tests for DI track seed import command.

Tests the bulk import functionality that will be used by scripts/seed_di_tracks.py,
verifying it correctly processes audio files and creates database records.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

from webapp.adapters.persistence.models.shootout import DITrack
from webapp.adapters.persistence.models.user import User

# Import the script module — scripts/ is not mounted in Docker containers,
# so skip the entire module if the import fails.
scripts_dir = Path(__file__).parent.parent.parent.parent / "scripts"
if str(scripts_dir) not in sys.path:
    sys.path.insert(0, str(scripts_dir))

try:
    from seed_di_tracks import SeedDITracks
except ModuleNotFoundError:
    pytest.skip("seed_di_tracks not available (scripts/ not mounted)", allow_module_level=True)


@pytest.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create a test user for seeding."""
    user = User(username="seeduser", email="seed@example.com")
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest.fixture
def temp_audio_dir(tmp_path: Path) -> Path:
    """Create a temporary directory with mock audio files."""
    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()

    # Create mock audio files (minimal valid WAVE headers)
    # RIFF header for a minimal 1-second 44.1kHz mono 16-bit WAV
    wav_header = (
        b"RIFF"
        + (36 + 44100 * 2).to_bytes(4, "little")  # File size - 8
        + b"WAVE"
        + b"fmt "
        + (16).to_bytes(4, "little")  # fmt chunk size
        + (1).to_bytes(2, "little")  # Audio format (PCM)
        + (1).to_bytes(2, "little")  # Channels
        + (44100).to_bytes(4, "little")  # Sample rate
        + (44100 * 2).to_bytes(4, "little")  # Byte rate
        + (2).to_bytes(2, "little")  # Block align
        + (16).to_bytes(2, "little")  # Bits per sample
        + b"data"
        + (44100 * 2).to_bytes(4, "little")  # Data chunk size
        + b"\x00" * (44100 * 2)  # Silence
    )

    # Create test files
    (audio_dir / "track1.wav").write_bytes(wav_header)
    (audio_dir / "track2.flac").write_bytes(b"fLaC\x00\x00\x00\x22")  # Minimal FLAC header
    (audio_dir / "track3.ogg").write_bytes(b"OggS")  # Minimal OGG header
    (audio_dir / "track4.mp3").write_bytes(b"\xff\xfb")  # Minimal MP3 header

    # Create nested directory
    nested = audio_dir / "subdir"
    nested.mkdir()
    (nested / "track5.wav").write_bytes(wav_header)

    # Create non-audio files (should be ignored)
    (audio_dir / "readme.txt").write_text("Not an audio file")
    (audio_dir / "metadata.json").write_text("{}")

    return audio_dir


class TestSeedDITracks:
    """Test suite for DI track seeding functionality."""

    async def test_script_module_exists(self):
        """Verify the seed_di_tracks module can be imported."""
        from scripts import seed_di_tracks

        assert hasattr(seed_di_tracks, "SeedDITracks")

    async def test_finds_supported_audio_files(self, temp_audio_dir: Path):
        """Verify script finds all supported audio formats recursively."""
        seeder = SeedDITracks(
            directory=temp_audio_dir,
            user_id=uuid4(),
            session=None,  # type: ignore
        )

        files = seeder.find_audio_files()

        # Should find 5 audio files (.wav, .flac, .ogg, .mp3) across root and subdir
        assert len(files) == 5
        suffixes = {f.suffix for f in files}
        assert suffixes == {".wav", ".flac", ".ogg", ".mp3"}

    async def test_skips_non_audio_files(self, temp_audio_dir: Path):
        """Verify script ignores non-audio files."""
        seeder = SeedDITracks(
            directory=temp_audio_dir,
            user_id=uuid4(),
            session=None,  # type: ignore
        )

        files = seeder.find_audio_files()

        # Should not include .txt or .json files
        assert not any(f.suffix == ".txt" for f in files)
        assert not any(f.suffix == ".json" for f in files)

    async def test_creates_di_track_records(
        self, db_session: AsyncSession, test_user: User, temp_audio_dir: Path
    ):
        """Verify script creates DITrack records via DITrackService."""
        seeder = SeedDITracks(directory=temp_audio_dir, user_id=test_user.id, session=db_session)

        result = await seeder.run()

        # Verify tracks were created
        from sqlalchemy import select

        stmt = select(DITrack).where(DITrack.user_id == test_user.id)
        tracks_result = await db_session.execute(stmt)
        tracks = tracks_result.scalars().all()

        assert len(tracks) > 0
        assert result.imported_count > 0

    async def test_skips_duplicates_by_checksum(
        self, db_session: AsyncSession, test_user: User, temp_audio_dir: Path
    ):
        """Verify script skips files with duplicate checksums without error."""
        seeder = SeedDITracks(directory=temp_audio_dir, user_id=test_user.id, session=db_session)

        # First run
        result1 = await seeder.run()
        imported_first = result1.imported_count

        # Second run with same files
        result2 = await seeder.run()

        # All files should be skipped as duplicates
        assert result2.skipped_count == imported_first
        assert result2.imported_count == 0

    async def test_copies_files_to_storage(
        self, db_session: AsyncSession, test_user: User, temp_audio_dir: Path, tmp_path: Path
    ):
        """Verify script copies audio files to storage path."""
        storage_path = tmp_path / "storage"
        storage_path.mkdir()

        seeder = SeedDITracks(
            directory=temp_audio_dir,
            user_id=test_user.id,
            session=db_session,
            storage_path=storage_path,
        )

        await seeder.run()

        # Verify files were copied to storage
        stored_files = list(storage_path.rglob("*"))
        assert len(stored_files) > 0

    async def test_reports_summary(
        self, db_session: AsyncSession, test_user: User, temp_audio_dir: Path
    ):
        """Verify script returns summary with counts."""
        seeder = SeedDITracks(directory=temp_audio_dir, user_id=test_user.id, session=db_session)

        result = await seeder.run()

        # Verify summary structure
        assert hasattr(result, "imported_count")
        assert hasattr(result, "skipped_count")
        assert hasattr(result, "error_count")
        assert isinstance(result.imported_count, int)
        assert isinstance(result.skipped_count, int)
        assert isinstance(result.error_count, int)

    async def test_handles_invalid_audio_files(
        self, db_session: AsyncSession, test_user: User, tmp_path: Path
    ):
        """Verify script handles corrupted/invalid audio files gracefully."""
        audio_dir = tmp_path / "audio"
        audio_dir.mkdir()

        # Create invalid audio file (wrong extension)
        (audio_dir / "corrupted.wav").write_bytes(b"NOT A VALID WAV FILE")

        seeder = SeedDITracks(directory=audio_dir, user_id=test_user.id, session=db_session)

        result = await seeder.run()

        # Should count as error, not crash
        assert result.error_count >= 1

    async def test_command_line_interface_exists(self):
        """Verify script has CLI entry point with main() function."""
        from scripts import seed_di_tracks

        assert hasattr(seed_di_tracks, "main")
        assert callable(seed_di_tracks.main)

    async def test_validates_directory_exists(self, db_session: AsyncSession, test_user: User):
        """Verify script validates directory path exists."""
        seeder = SeedDITracks(
            directory=Path("/nonexistent/path"),
            user_id=test_user.id,
            session=db_session,
        )

        with pytest.raises(ValueError, match="[Dd]irectory"):
            await seeder.run()

    async def test_validates_user_id(self, db_session: AsyncSession, temp_audio_dir: Path):
        """Verify script validates user_id format."""
        # Invalid user_id should raise ValueError
        with pytest.raises((ValueError, TypeError)):
            SeedDITracks(
                directory=temp_audio_dir,
                user_id="not-a-uuid",  # type: ignore
                session=db_session,
            )
