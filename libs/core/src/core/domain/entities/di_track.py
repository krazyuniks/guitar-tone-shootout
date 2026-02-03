"""DITrack entity for domain layer.

Represents user-uploaded DI (direct input) recordings.
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from uuid import UUID

from core.domain.entities.base import Entity, new_id, utcnow
from core.domain.value_objects.audio_checksum import AudioChecksum
from core.domain.value_objects.waveform_data import WaveformData


@dataclass(eq=False, slots=True)
class DITrack(Entity):
    """Entity representing a user-uploaded DI recording.

    A DI track is a clean guitar recording that can be processed
    through various signal chains for comparison.

    Attributes:
        id: Unique identifier
        user_id: Owner's user ID
        name: Display name for the track
        file_path: Path to the audio file
        original_filename: Original uploaded filename
        duration_seconds: Track duration
        sample_rate: Audio sample rate in Hz
        description: Optional description
        guitar: Guitar used for recording
        pickup: Pickup position/type
        checksum: Audio file checksum for integrity
        waveform: Waveform visualization data
        created_at: When uploaded
        updated_at: When last updated
    """

    user_id: UUID = field(default_factory=new_id)
    name: str = ""
    file_path: str = ""
    original_filename: str = ""
    duration_seconds: float = 0.0
    sample_rate: int = 44100
    description: str | None = None
    guitar: str | None = None
    pickup: str | None = None
    checksum: AudioChecksum | None = None
    waveform: WaveformData | None = None
    id: UUID = field(default_factory=new_id)
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)

    @property
    def path(self) -> Path:
        """Get the file path as a Path object."""
        return Path(self.file_path)

    @property
    def extension(self) -> str:
        """Get the file extension (without dot)."""
        return self.path.suffix.lstrip(".")

    def update_metadata(
        self,
        name: str | None = None,
        description: str | None = None,
        guitar: str | None = None,
        pickup: str | None = None,
    ) -> None:
        """Update track metadata.

        Args:
            name: New name (if provided)
            description: New description (if provided)
            guitar: Guitar info (if provided)
            pickup: Pickup info (if provided)
        """
        if name is not None:
            self.name = name
        if description is not None:
            self.description = description
        if guitar is not None:
            self.guitar = guitar
        if pickup is not None:
            self.pickup = pickup
        self.updated_at = utcnow()

    def set_waveform(self, waveform: WaveformData) -> None:
        """Set the waveform visualization data.

        Args:
            waveform: The waveform data
        """
        self.waveform = waveform
        self.updated_at = utcnow()

    def set_checksum(self, checksum: AudioChecksum) -> None:
        """Set the audio file checksum.

        Args:
            checksum: The checksum
        """
        self.checksum = checksum
        self.updated_at = utcnow()

    def verify_checksum(self) -> bool:
        """Verify the file checksum matches.

        Returns:
            True if checksum matches, False if not set or mismatch
        """
        if self.checksum is None:
            return False
        current = AudioChecksum.from_file(self.path)
        return self.checksum.matches(current)
