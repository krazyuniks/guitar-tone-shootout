"""Model file downloader for T3K NAM models.

Downloads NAM model files from T3K to local storage with checksum
verification and retry logic.
"""

import hashlib
from pathlib import Path

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from source_t3k.adapters.outbound.models import T3KModelStaging


class ModelDownloader:
    """Downloads T3K model files with checksum verification and retry logic."""

    def __init__(
        self, base_path: Path, session: AsyncSession, http_client: AsyncClient | None = None
    ):
        """Initialize model downloader.

        Args:
            base_path: Root directory for downloaded models
            session: Database session for querying models
            http_client: Optional HTTP client (creates default if None)
        """
        self._base_path = base_path
        self._session = session
        self._http_client = http_client

    def _get_model_path(self, model: T3KModelStaging) -> Path:
        """Get local storage path for a model.

        Args:
            model: Model staging record

        Returns:
            Path to local file: base_path/model.id/model.filename
        """
        return self._base_path / model.id / model.filename

    def _verify_checksum(self, path: Path, expected_checksum: str) -> bool:
        """Verify file checksum matches expected SHA-256.

        Args:
            path: Path to file to verify
            expected_checksum: Expected SHA-256 hex digest

        Returns:
            True if checksum matches, False otherwise
        """
        if not path.exists():
            return False

        try:
            sha256 = hashlib.sha256()
            with path.open("rb") as f:
                while chunk := f.read(8192):
                    sha256.update(chunk)
            return sha256.hexdigest() == expected_checksum
        except Exception:
            return False

    async def download_model(self, model: T3KModelStaging) -> Path | None:
        """Download a single model file.

        Skips download if file already exists with correct checksum.
        Retries up to 3 times on failure. Removes corrupt files after all retries fail.

        Args:
            model: Model staging record with download URL and checksum

        Returns:
            Path to downloaded file if successful, None if skipped or failed
        """
        path = self._get_model_path(model)

        # Skip if already exists with correct checksum
        if path.exists() and self._verify_checksum(path, model.checksum):
            return None

        # Create HTTP client if not provided
        client = self._http_client if self._http_client is not None else AsyncClient()

        # Retry up to 3 times
        for _attempt in range(3):
            try:
                # Download file
                response = await client.get(model.download_url)
                content = response.content

                # Create parent directory
                path.parent.mkdir(parents=True, exist_ok=True)

                # Write file
                path.write_bytes(content)

                # Verify checksum
                if self._verify_checksum(path, model.checksum):
                    return path

                # Checksum failed - remove file and retry
                if path.exists():
                    path.unlink()

            except Exception:
                # Network error - retry
                if path.exists():
                    path.unlink()
                continue

        # All retries exhausted - clean up any partial file
        if path.exists():
            path.unlink()

        return None

    async def download_models_for_pack(self, pack_id: str) -> list[Path]:
        """Download all models for a pack.

        Args:
            pack_id: Pack ID to query models for

        Returns:
            List of successfully downloaded file paths (excludes skipped models)
        """
        # Query models for pack
        stmt = select(T3KModelStaging).where(T3KModelStaging.pack_id == pack_id)
        result = await self._session.execute(stmt)
        models = result.scalars().all()

        # Download each model
        downloaded_paths = []
        for model in models:
            path = await self.download_model(model)
            if path is not None:
                downloaded_paths.append(path)

        return downloaded_paths
