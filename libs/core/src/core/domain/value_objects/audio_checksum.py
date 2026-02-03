"""AudioChecksum value object for domain layer.

SHA256 checksum wrapper for audio file integrity verification.
"""

import hashlib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class AudioChecksum:
    """Value object representing an audio file checksum.

    This is an immutable value object wrapping a SHA256 hash
    for audio file integrity verification.

    Attributes:
        value: The SHA256 hash as a hexadecimal string
    """

    value: str

    def __post_init__(self) -> None:
        """Validate the checksum format."""
        if len(self.value) != 64:
            raise ValueError(
                f"Invalid SHA256 checksum length: expected 64, got {len(self.value)}"
            )
        try:
            int(self.value, 16)
        except ValueError as e:
            raise ValueError(f"Invalid SHA256 checksum format: {self.value}") from e

    @classmethod
    def from_file(cls, file_path: Path, chunk_size: int = 8192) -> "AudioChecksum":
        """Create a checksum from an audio file.

        Args:
            file_path: Path to the audio file
            chunk_size: Size of chunks to read (default 8KB)

        Returns:
            AudioChecksum with the SHA256 hash of the file

        Raises:
            FileNotFoundError: If the file doesn't exist
            PermissionError: If the file can't be read
        """
        sha256_hash = hashlib.sha256()
        with file_path.open("rb") as f:
            for chunk in iter(lambda: f.read(chunk_size), b""):
                sha256_hash.update(chunk)
        return cls(value=sha256_hash.hexdigest())

    @classmethod
    def from_bytes(cls, data: bytes) -> "AudioChecksum":
        """Create a checksum from raw bytes.

        Args:
            data: The bytes to hash

        Returns:
            AudioChecksum with the SHA256 hash of the data
        """
        return cls(value=hashlib.sha256(data).hexdigest())

    def matches(self, other: "AudioChecksum") -> bool:
        """Check if this checksum matches another.

        Args:
            other: The checksum to compare against

        Returns:
            True if the checksums match, False otherwise
        """
        return self.value == other.value

    def __str__(self) -> str:
        """Return the checksum as a string."""
        return self.value

    @property
    def short(self) -> str:
        """Return a shortened version of the checksum (first 8 chars).

        Useful for display in logs and UI.
        """
        return self.value[:8]
