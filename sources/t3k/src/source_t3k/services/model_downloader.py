"""Model file downloader for T3K NAM models.

Downloads NAM model files from T3K to local storage with retry logic.
Filenames are derived from the model_url path.
"""

import logging
from collections.abc import Callable, Coroutine
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from source_t3k.adapters.inbound.rate_limiter import RateLimiter
from source_t3k.adapters.outbound.models import T3KModelStaging

logger = logging.getLogger(__name__)


class ModelDownloader:
    """Downloads T3K model files with retry logic."""

    def __init__(
        self,
        base_path: Path,
        session: AsyncSession,
        http_client: AsyncClient | None = None,
        get_auth_headers: Callable[[], Coroutine[Any, Any, dict[str, str]]] | None = None,
        rate_limiter: RateLimiter | None = None,
    ):
        self._base_path = base_path
        self._session = session
        self._http_client = http_client
        self._get_auth_headers = get_auth_headers
        self._rate_limiter = rate_limiter

    def _get_model_path(self, model: T3KModelStaging) -> Path:
        """Get local storage path for a model.

        Derives filename from the model_url path component.
        """
        filename = PurePosixPath(model.model_url).name or f"{model.id}.nam"
        return self._base_path / str(model.id) / filename

    async def download_model(self, model: T3KModelStaging) -> Path | None:
        """Download a single model file.

        Skips download if file already exists.
        Retries up to 3 times on transient failure.
        Raises T3KAPIError immediately on Vercel challenge or rate limit.
        """
        from source_t3k.adapters.inbound.exceptions import T3KAPIError
        from source_t3k.adapters.inbound.vercel_solver import is_vercel_challenge

        path = self._get_model_path(model)

        if path.exists():
            logger.info("Model %s: file exists, skipping download (%s)", model.id, path)
            if model.file_synced_at is None:
                model.file_synced_at = datetime.now(UTC)
            return None

        if self._http_client is None:
            logger.warning("No HTTP client configured — skipping download for model %s", model.id)
            return None

        headers = {}
        if self._get_auth_headers is not None:
            headers = await self._get_auth_headers()

        for attempt in range(3):
            if self._rate_limiter is not None:
                await self._rate_limiter.acquire()

            try:
                response = await self._http_client.get(
                    model.model_url, headers=headers, follow_redirects=True
                )
                if response.status_code == 429:
                    raise T3KAPIError("Rate limit exceeded during model download")
                if response.status_code >= 400:
                    body = response.text
                    if is_vercel_challenge(response.status_code, body):
                        raise T3KAPIError("Vercel challenge during model download")
                response.raise_for_status()
                content = response.content

                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
                model.file_synced_at = datetime.now(UTC)
                logger.info("Model %s: downloaded %d bytes → %s", model.id, len(content), path)
                return path

            except T3KAPIError:
                raise
            except Exception:
                if path.exists():
                    path.unlink()
                if attempt < 2:
                    logger.debug("Download attempt %d failed for model %s", attempt + 1, model.id)
                else:
                    logger.warning("All download attempts exhausted for model %s", model.id)

        return None

    async def download_models_for_tone(self, tone_id: int) -> list[Path]:
        """Download all models for a tone.

        Returns list of successfully downloaded file paths.
        """
        stmt = select(T3KModelStaging).where(T3KModelStaging.tone_id == tone_id)
        result = await self._session.execute(stmt)
        models = result.scalars().all()

        downloaded_paths = []
        for model in models:
            path = await self.download_model(model)
            if path is not None:
                downloaded_paths.append(path)

        return downloaded_paths
