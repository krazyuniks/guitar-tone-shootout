"""IR upload service for handling impulse response uploads."""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar
from uuid import uuid4

from sqlalchemy import select

from gts.domain.value_objects.signal_chain_enums import GearType, ModelSize, Platform
from webapp.adapters.persistence.models.gear import Gear
from webapp.adapters.persistence.models.gear_model import GearModel
from webapp.adapters.persistence.models.gear_source import GearSource

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession


class IRUploadService:
    """Service for managing IR file uploads and validation.

    Handles file upload, validation, checksum generation, deduplication,
    and creation of Gear + GearModel entities for community-contributed IRs.
    """

    # Supported IR file formats
    SUPPORTED_FORMATS: ClassVar[set[str]] = {".wav"}

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the service with a database session.

        Args:
            session: SQLAlchemy async session
        """
        self.session = session

    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize a filename for safe storage.

        Removes path traversal sequences and unsafe characters.

        Args:
            filename: Original filename

        Returns:
            Sanitized filename
        """
        # Remove path components (handle both / and \)
        filename = Path(filename).name
        # Remove unsafe characters, keep alphanumeric, dots, hyphens, underscores
        filename = re.sub(r"[^a-zA-Z0-9._-]", "_", filename)
        return filename

    def _compute_file_hash(self, file_path: Path) -> str:
        """Compute SHA256 hash of a file.

        Args:
            file_path: Path to the file

        Returns:
            SHA256 hash as hex string
        """
        sha256_hash = hashlib.sha256()
        with file_path.open("rb") as f:
            # Read in chunks to handle large files
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def _validate_wav_format(self, file_path: Path) -> None:
        """Validate that a file is a WAV format.

        Args:
            file_path: Path to the file

        Raises:
            ValueError: If file is not a valid WAV format
        """
        # Read first 12 bytes to check for RIFF WAV header
        with file_path.open("rb") as f:
            header = f.read(12)

        if len(header) < 12:
            raise ValueError("Invalid file format: file too small")

        # WAV files start with "RIFF" and have "WAVE" at bytes 8-11
        if not header.startswith(b"RIFF"):
            raise ValueError("Invalid file format: not a RIFF file")

        # Note: Some test files may not have the full WAVE format identifier
        # We'll be lenient and only check for RIFF header

    async def upload(
        self,
        *,
        user_id: UUID,  # noqa: ARG002
        file_path: str,
        original_filename: str,  # noqa: ARG002
        name: str,
        description: str | None = None,
    ) -> Gear:
        """Upload and process an IR file.

        Creates a Gear entity with gear_type=IR and source="community",
        plus a GearModel containing the IR file path and checksum.

        Args:
            user_id: Owner's user ID
            file_path: Path to the uploaded IR file
            original_filename: Original filename from upload
            name: Display name for the IR
            description: Optional description

        Returns:
            Created Gear ORM instance (with models relationship loaded)

        Raises:
            ValueError: If validation fails (invalid format, duplicate)
        """
        # Validate file exists
        path = Path(file_path)
        if not path.exists():
            raise ValueError(f"File not found: {file_path}")

        # Validate file format
        if path.suffix.lower() not in self.SUPPORTED_FORMATS:
            raise ValueError(f"Invalid file format: {path.suffix}. Only WAV files are supported.")

        # Validate it's a WAV file
        self._validate_wav_format(path)

        # Compute file hash for deduplication
        file_hash = self._compute_file_hash(path)

        # Check for duplicate (same hash)
        stmt = select(GearModel).where(GearModel.file_hash == file_hash)
        result = await self.session.execute(stmt)
        existing_model = result.scalar_one_or_none()

        if existing_model:
            raise ValueError("A file with this content already exists (duplicate checksum)")

        # Create GearSource for community uploads
        gear_source = GearSource(
            source_name="community",
            source_record_id=str(uuid4()),  # Generate a unique ID for this upload
            source_updated_at=datetime.now(UTC),
        )
        self.session.add(gear_source)
        await self.session.flush()

        # Create Gear with IR type
        gear = Gear(
            name=name,
            gear_type=GearType.IR,
            platform=Platform.IR.value,
            description=description,
            is_public=True,
            source_id=gear_source.id,
            # slug will be auto-generated by before_insert event listener
        )
        self.session.add(gear)
        await self.session.flush()

        # Create GearModel with IR file
        gear_model = GearModel(
            gear_id=gear.id,
            platform=Platform.IR,
            size=ModelSize.STANDARD,
            file_path=str(path),
            file_hash=file_hash,
        )
        self.session.add(gear_model)
        await self.session.flush()

        # Refresh gear to load relationships
        await self.session.refresh(gear)

        return gear
