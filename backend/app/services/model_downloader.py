"""Model downloader service with caching.

This service downloads NAM models from Tone 3000 and caches them locally
to avoid redundant downloads.
"""

import json
import time
from pathlib import Path
from typing import TYPE_CHECKING

import aiofiles
import httpx

from app.core.config import settings
from app.core.logging import get_logger
from app.schemas.tone3000 import Model, ModelSize

if TYPE_CHECKING:
    from app.services.tone3000 import Tone3000Client

logger = get_logger(__name__)


class ModelDownloadError(Exception):
    """Error during model download or validation."""


class ModelDownloader:
    """Service to download and cache Tone 3000 models.

    Downloads NAM/IR models from Tone 3000 using pre-signed URLs and caches
    them locally. Supports validation of downloaded files and automatic
    cleanup of old cached models.

    Usage:
        downloader = ModelDownloader()
        model_path = await downloader.download_model(client, model)
    """

    def __init__(self, cache_dir: Path | None = None) -> None:
        """Initialize the model downloader.

        Args:
            cache_dir: Directory for caching models. Defaults to settings value.
        """
        self.cache_dir = cache_dir or Path(settings.model_cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _cache_path(self, model: Model) -> Path:
        """Generate cache file path for a model.

        Args:
            model: The model to generate a path for.

        Returns:
            Path to the cached model file.
        """
        # Use tone_id, model_id, and size to create unique filename
        extension = self._get_extension(model.size)
        filename = f"{model.tone_id}_{model.id}_{model.size.value}{extension}"
        return self.cache_dir / filename

    def _get_extension(self, size: ModelSize) -> str:
        """Get file extension based on model size.

        Args:
            size: The model size/type.

        Returns:
            File extension including the dot.
        """
        # NAM models are .nam files (JSON format)
        # All NAM sizes (standard, lite, feather, nano) use .nam
        return ".nam"

    def is_cached(self, model: Model) -> bool:
        """Check if a model is already cached.

        Args:
            model: The model to check.

        Returns:
            True if the model is cached, False otherwise.
        """
        return self._cache_path(model).exists()

    def get_cached_path(self, model: Model) -> Path | None:
        """Get the cached path for a model if it exists.

        Args:
            model: The model to look up.

        Returns:
            Path to the cached model if it exists, None otherwise.
        """
        path = self._cache_path(model)
        if path.exists():
            return path
        return None

    async def download_model(
        self,
        client: "Tone3000Client",
        model: Model,
        force: bool = False,
    ) -> Path:
        """Download a model, using cache if available.

        Args:
            client: Tone 3000 API client for downloading.
            model: The model to download.
            force: Force re-download even if cached.

        Returns:
            Path to the local model file.

        Raises:
            ModelDownloadError: If download or validation fails.
        """
        cache_path = self._cache_path(model)

        # Check cache first
        if not force and cache_path.exists():
            logger.debug("Using cached model: %s", cache_path)
            # Touch to update mtime for LRU-style cache management
            cache_path.touch()
            return cache_path

        logger.info(
            "Downloading model %d for tone %d (%s)",
            model.id,
            model.tone_id,
            model.size.value,
        )

        try:
            # Download from pre-signed URL
            async with httpx.AsyncClient(timeout=120.0) as http:
                response = await http.get(model.model_url, follow_redirects=True)
                response.raise_for_status()
                content = response.content

            # Write to temp file first, then rename for atomicity
            temp_path = cache_path.with_suffix(".tmp")
            async with aiofiles.open(temp_path, "wb") as f:
                await f.write(content)

            # Validate the downloaded file
            if not await self._validate_model(temp_path, model):
                temp_path.unlink(missing_ok=True)
                raise ModelDownloadError(f"Invalid model file for model {model.id}")

            # Atomic rename
            temp_path.rename(cache_path)

            logger.info("Model downloaded and cached: %s", cache_path)
            return cache_path

        except httpx.HTTPStatusError as e:
            logger.error(
                "HTTP error downloading model %d: %s",
                model.id,
                e.response.status_code,
            )
            raise ModelDownloadError(
                f"Failed to download model {model.id}: HTTP {e.response.status_code}"
            ) from e
        except httpx.RequestError as e:
            logger.error("Network error downloading model %d: %s", model.id, e)
            raise ModelDownloadError(f"Failed to download model {model.id}: {e}") from e

    async def _validate_model(self, path: Path, model: Model) -> bool:
        """Validate a downloaded model file.

        Args:
            path: Path to the downloaded file.
            model: The model metadata for context.

        Returns:
            True if the file is valid, False otherwise.
        """
        try:
            async with aiofiles.open(path, encoding="utf-8") as f:
                content = await f.read()

            # NAM models are JSON files
            data = json.loads(content)

            # Check for expected NAM model structure
            # NAM files typically have "architecture" or "config" fields
            has_architecture = "architecture" in data
            has_config = "config" in data
            has_weights = "weights" in data or "state_dict" in data

            if not (has_architecture or has_config):
                logger.warning(
                    "Model %d missing expected fields (architecture/config)",
                    model.id,
                )
                return False

            if not has_weights:
                logger.warning(
                    "Model %d missing weights/state_dict",
                    model.id,
                )
                return False

            logger.debug("Model %d validation passed", model.id)
            return True

        except json.JSONDecodeError as e:
            logger.warning("Model %d is not valid JSON: %s", model.id, e)
            return False
        except UnicodeDecodeError as e:
            logger.warning("Model %d is not valid UTF-8: %s", model.id, e)
            return False
        except Exception as e:
            logger.warning("Model %d validation error: %s", model.id, e)
            return False

    async def download_models_for_tone(
        self,
        client: "Tone3000Client",
        tone_id: int,
        size: ModelSize | None = None,
    ) -> list[Path]:
        """Download all models for a tone.

        Args:
            client: Tone 3000 API client.
            tone_id: ID of the tone to download models for.
            size: Optional size filter. If None, downloads all sizes.

        Returns:
            List of paths to downloaded model files.

        Raises:
            ModelDownloadError: If any download fails.
        """
        # Get available models from Tone 3000
        async with client:
            models = await client.get_models(tone_id)

        if not models:
            logger.warning("No models found for tone %d", tone_id)
            return []

        # Filter by size if specified
        if size is not None:
            models = [m for m in models if m.size == size]

        # Download each model
        paths: list[Path] = []
        for model in models:
            try:
                async with client:
                    path = await self.download_model(client, model)
                paths.append(path)
            except ModelDownloadError as e:
                logger.error("Failed to download model %d: %s", model.id, e)
                raise

        return paths

    async def cleanup_cache(self, max_age_days: int | None = None) -> int:
        """Remove cached models older than max_age_days.

        Args:
            max_age_days: Maximum age in days. Defaults to settings value.

        Returns:
            Number of files removed.
        """
        max_age = max_age_days or settings.model_cache_max_age_days
        cutoff = time.time() - (max_age * 86400)

        removed = 0
        for path in self.cache_dir.glob("*.nam"):
            try:
                if path.stat().st_mtime < cutoff:
                    path.unlink()
                    removed += 1
                    logger.info("Removed old cached model: %s", path)
            except OSError as e:
                logger.warning("Failed to remove %s: %s", path, e)

        logger.info("Cache cleanup complete: removed %d files", removed)
        return removed

    def get_cache_stats(self) -> dict[str, object]:
        """Get cache statistics.

        Returns:
            Dict with cache statistics:
                - total_files: Number of cached files
                - total_size_bytes: Total size of cached files
                - oldest_file_age_days: Age of oldest file in days
        """
        files = list(self.cache_dir.glob("*.nam"))
        total_size = sum(f.stat().st_size for f in files)

        if files:
            oldest_mtime = min(f.stat().st_mtime for f in files)
            oldest_age_days = (time.time() - oldest_mtime) / 86400
        else:
            oldest_age_days = 0.0

        return {
            "total_files": len(files),
            "total_size_bytes": total_size,
            "oldest_file_age_days": round(oldest_age_days, 1),
        }


# Convenience function for getting a configured downloader
def get_model_downloader() -> ModelDownloader:
    """Get a ModelDownloader instance with default settings.

    Returns:
        Configured ModelDownloader instance.
    """
    return ModelDownloader()
