"""Port interfaces for hexagonal architecture."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path  # noqa: TC003 - used in abstract method signatures
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from guitar_tone_shootout.domain.models import NAMCapture, NAMTonePack


class ModelRepositoryPort(ABC):
    """
    Port for fetching model metadata from external sources.

    Implementations handle scraping/API calls to sources like Tone3000.
    """

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Unique identifier for this source (e.g., 'tone3000')."""
        ...

    @abstractmethod
    def fetch_tone_pack(self, page_url: str) -> NAMTonePack:
        """
        Fetch metadata for a tone pack from its page URL.

        Args:
            page_url: Full URL to the tone pack page

        Returns:
            NAMTonePack with all available metadata and captures

        Raises:
            ValueError: If URL is invalid or not supported
            ConnectionError: If unable to fetch page
        """
        ...

    @abstractmethod
    def get_capture_by_name(
        self, page_url: str, capture_name: str
    ) -> tuple[NAMTonePack, NAMCapture]:
        """
        Fetch a specific capture from a tone pack.

        Args:
            page_url: Full URL to the tone pack page
            capture_name: Name of the specific capture (partial match supported)

        Returns:
            Tuple of (NAMTonePack, NAMCapture)

        Raises:
            ValueError: If capture not found
        """
        ...


class ModelDownloaderPort(ABC):
    """
    Port for downloading model files.

    Handles actual file downloads and local storage.
    """

    @abstractmethod
    def download_capture(self, capture: NAMCapture, target_dir: Path) -> Path:
        """
        Download a NAM capture file.

        Args:
            capture: NAMCapture with download URL
            target_dir: Directory to save the file

        Returns:
            Path to downloaded file

        Raises:
            ConnectionError: If download fails
            IOError: If unable to write file
        """
        ...

    @abstractmethod
    def download_ir(self, url: str, target_path: Path) -> Path:
        """
        Download an impulse response file.

        Args:
            url: Direct download URL
            target_path: Full path for the downloaded file

        Returns:
            Path to downloaded file
        """
        ...

    def is_cached(self, capture: NAMCapture, target_dir: Path) -> bool:
        """
        Check if a capture is already downloaded.

        Args:
            capture: NAMCapture to check
            target_dir: Directory where file would be stored

        Returns:
            True if file exists locally
        """
        target_path = target_dir / capture.filename
        return target_path.exists()
