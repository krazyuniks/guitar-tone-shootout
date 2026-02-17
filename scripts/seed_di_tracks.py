#!/usr/bin/env python3
"""Bulk import DI track audio files from a directory into the database.

This script recursively scans a directory for supported audio files (.wav, .flac,
.ogg, .mp3) and creates DITrack records via DITrackService. It handles deduplication
via checksums and copies files to the configured storage path.

Usage:
    python scripts/seed_di_tracks.py <directory> <user_id> [--storage-path PATH]

Example:
    python scripts/seed_di_tracks.py ~/audio/di-tracks 550e8400-e29b-41d4-a716-446655440000
"""

import argparse
import asyncio
import hashlib
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar
from uuid import UUID

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

# Import webapp modules (available in container Python path via uv workspaces)
try:
    from webapp.adapters.persistence.models.base import get_async_session
    from webapp.services.di_track_service import DITrackService
except ImportError:
    # Fallback: add apps to path for imports (for direct script execution)
    repo_root = Path(__file__).parent.parent
    sys.path.insert(0, str(repo_root / "apps" / "webapp" / "src"))
    from webapp.adapters.persistence.models.base import get_async_session
    from webapp.services.di_track_service import DITrackService


@dataclass
class SeedResult:
    """Result summary from seeding operation."""

    imported_count: int = 0
    skipped_count: int = 0
    error_count: int = 0


class SeedDITracks:
    """Bulk importer for DI track audio files."""

    # Supported audio formats (must match DITrackService)
    SUPPORTED_FORMATS: ClassVar[set[str]] = {".wav", ".flac", ".ogg", ".mp3"}

    def __init__(
        self,
        directory: Path,
        user_id: UUID,
        session: "AsyncSession",
        storage_path: Path | None = None,
    ) -> None:
        """Initialize the seeder.

        Args:
            directory: Directory to scan for audio files
            user_id: User ID to assign ownership to imported tracks
            session: Database session for persistence
            storage_path: Optional custom storage path (defaults to $GTS_STORAGE_ROOT/uploads/di_tracks/)

        Raises:
            ValueError: If user_id is not a valid UUID
            TypeError: If user_id is not a UUID type
        """
        # Validate user_id type
        if not isinstance(user_id, UUID):
            raise TypeError(f"user_id must be a UUID, got {type(user_id)}")

        self.directory = directory
        self.user_id = user_id
        self.session = session
        self.storage_path = (
            storage_path or Path(os.environ["GTS_STORAGE_ROOT"]) / "uploads" / "di_tracks"
        )
        self.service = DITrackService(session)

    def find_audio_files(self) -> list[Path]:
        """Recursively find all supported audio files in the directory.

        Returns:
            List of Path objects for audio files
        """
        audio_files = []
        for suffix in self.SUPPORTED_FORMATS:
            audio_files.extend(self.directory.rglob(f"*{suffix}"))
        return sorted(audio_files)

    async def run(self) -> SeedResult:
        """Execute the bulk import process.

        Returns:
            SeedResult with counts of imported, skipped, and errored files

        Raises:
            ValueError: If directory does not exist
        """
        # Validate directory exists
        if not self.directory.exists():
            raise ValueError(f"Directory does not exist: {self.directory}")

        result = SeedResult()
        audio_files = self.find_audio_files()

        # Ensure storage directory exists
        self.storage_path.mkdir(parents=True, exist_ok=True)

        # Deduplicate files by checksum within the batch — keep only the
        # first file for each unique checksum. Files with identical content
        # (e.g., same WAV copied to different directories) are silently
        # ignored rather than counted as skipped or errored.
        seen_checksums: set[str] = set()
        unique_files: list[Path] = []
        for file_path in audio_files:
            file_checksum = hashlib.sha256(file_path.read_bytes()).hexdigest()
            if file_checksum not in seen_checksums:
                seen_checksums.add(file_checksum)
                unique_files.append(file_path)

        for file_path in unique_files:
            try:
                # Generate name from filename (without extension)
                name = file_path.stem

                # Copy file to storage path
                dest_filename = f"{self.user_id}_{file_path.name}"
                dest_path = self.storage_path / dest_filename

                # Copy the file if not already there
                if not dest_path.exists():
                    shutil.copy2(file_path, dest_path)

                # Create DITrack record via service
                await self.service.upload(
                    user_id=self.user_id,
                    file_path=str(dest_path),
                    original_filename=file_path.name,
                    name=name,
                    description=f"Imported from {file_path.parent.name}",
                )

                result.imported_count += 1
                print(f"✓ Imported: {file_path.name}")

            except ValueError as e:
                # DITrackService raises ValueError for duplicates
                if "duplicate checksum" in str(e):
                    result.skipped_count += 1
                    print(f"⊘ Skipped (duplicate): {file_path.name}")
                else:
                    result.error_count += 1
                    print(f"✗ Error: {file_path.name} - {e}")

            except Exception as e:
                result.error_count += 1
                print(f"✗ Error: {file_path.name} - {e}")

        # Commit all changes at the end
        await self.session.commit()

        return result


async def _async_main(args: argparse.Namespace) -> int:
    """Async entry point for the script.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    # Get database URL from environment
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL environment variable not set", file=sys.stderr)
        return 1

    # Create session factory
    session_factory = get_async_session(database_url)

    # Parse user_id
    try:
        user_id = UUID(args.user_id)
    except ValueError as e:
        print(f"ERROR: Invalid user_id format: {e}", file=sys.stderr)
        return 1

    # Parse directory path
    directory = Path(args.directory).expanduser().resolve()

    # Parse optional storage path
    storage_path = None
    if args.storage_path:
        storage_path = Path(args.storage_path).expanduser().resolve()

    # Run the seeder
    async with session_factory() as session:
        seeder = SeedDITracks(
            directory=directory,
            user_id=user_id,
            session=session,
            storage_path=storage_path,
        )

        result = await seeder.run()

    # Print summary
    print("\n" + "=" * 60)
    print("SEED SUMMARY")
    print("=" * 60)
    print(f"  Imported: {result.imported_count}")
    print(f"  Skipped:  {result.skipped_count}")
    print(f"  Errors:   {result.error_count}")
    print("=" * 60)

    return 0 if result.error_count == 0 else 1


def main() -> int:
    """Command-line entry point.

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    parser = argparse.ArgumentParser(
        description="Bulk import DI track audio files into the database"
    )
    parser.add_argument(
        "directory",
        help="Directory containing audio files to import",
    )
    parser.add_argument(
        "user_id",
        help="User ID (UUID) to assign ownership to imported tracks",
    )
    parser.add_argument(
        "--storage-path",
        help="Custom storage path (defaults to $GTS_STORAGE_ROOT/uploads/di_tracks/)",
    )

    args = parser.parse_args()

    return asyncio.run(_async_main(args))


if __name__ == "__main__":
    sys.exit(main())
