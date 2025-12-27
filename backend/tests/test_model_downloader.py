"""Tests for the model downloader service."""

import asyncio
import json
import os
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.schemas.tone3000 import Model, ModelSize
from app.services.model_downloader import (
    ModelDownloader,
    ModelDownloadError,
    get_model_downloader,
)


@pytest.fixture
def sample_model() -> Model:
    """Create a sample model for testing."""
    return Model(
        id=456,
        name="Test Model Standard",
        size=ModelSize.STANDARD,
        model_url="https://tone3000.com/models/456/download",
        tone_id=123,
    )


@pytest.fixture
def valid_nam_content() -> bytes:
    """Create valid NAM model content."""
    data = {
        "architecture": "LSTM",
        "config": {"hidden_size": 32},
        "weights": {"layer1": [0.1, 0.2, 0.3]},
    }
    return json.dumps(data).encode("utf-8")


@pytest.fixture
def invalid_nam_content() -> bytes:
    """Create invalid NAM model content (missing required fields)."""
    data = {"some_field": "some_value"}
    return json.dumps(data).encode("utf-8")


class TestModelDownloaderInit:
    """Tests for ModelDownloader initialization."""

    def test_init_creates_cache_dir(self, tmp_path: Path) -> None:
        """Test that initialization creates the cache directory."""
        cache_dir = tmp_path / "model_cache"
        assert not cache_dir.exists()

        downloader = ModelDownloader(cache_dir=cache_dir)

        assert cache_dir.exists()
        assert downloader.cache_dir == cache_dir

    def test_init_uses_existing_dir(self, tmp_path: Path) -> None:
        """Test that initialization works with existing directory."""
        cache_dir = tmp_path / "existing_cache"
        cache_dir.mkdir()

        downloader = ModelDownloader(cache_dir=cache_dir)

        assert downloader.cache_dir == cache_dir


class TestCachePath:
    """Tests for cache path generation."""

    def test_cache_path_format(self, tmp_path: Path, sample_model: Model) -> None:
        """Test that cache path follows expected format."""
        downloader = ModelDownloader(cache_dir=tmp_path)
        path = downloader._cache_path(sample_model)

        expected = tmp_path / "123_456_standard.nam"
        assert path == expected

    def test_cache_path_different_sizes(self, tmp_path: Path) -> None:
        """Test cache paths for different model sizes."""
        downloader = ModelDownloader(cache_dir=tmp_path)

        sizes = [ModelSize.STANDARD, ModelSize.LITE, ModelSize.FEATHER, ModelSize.NANO]
        for size in sizes:
            model = Model(
                id=1,
                name="Test",
                size=size,
                model_url="https://example.com/model",
                tone_id=100,
            )
            path = downloader._cache_path(model)
            assert path.suffix == ".nam"
            assert size.value in path.name


class TestIsCached:
    """Tests for cache checking."""

    def test_is_cached_returns_false_when_not_cached(
        self, tmp_path: Path, sample_model: Model
    ) -> None:
        """Test is_cached returns False for uncached model."""
        downloader = ModelDownloader(cache_dir=tmp_path)

        assert not downloader.is_cached(sample_model)

    def test_is_cached_returns_true_when_cached(
        self, tmp_path: Path, sample_model: Model
    ) -> None:
        """Test is_cached returns True for cached model."""
        downloader = ModelDownloader(cache_dir=tmp_path)

        # Create a cached file
        cache_path = downloader._cache_path(sample_model)
        cache_path.write_text("{}")

        assert downloader.is_cached(sample_model)


class TestGetCachedPath:
    """Tests for getting cached path."""

    def test_get_cached_path_returns_none_when_not_cached(
        self, tmp_path: Path, sample_model: Model
    ) -> None:
        """Test get_cached_path returns None for uncached model."""
        downloader = ModelDownloader(cache_dir=tmp_path)

        assert downloader.get_cached_path(sample_model) is None

    def test_get_cached_path_returns_path_when_cached(
        self, tmp_path: Path, sample_model: Model
    ) -> None:
        """Test get_cached_path returns path for cached model."""
        downloader = ModelDownloader(cache_dir=tmp_path)

        # Create a cached file
        cache_path = downloader._cache_path(sample_model)
        cache_path.write_text("{}")

        result = downloader.get_cached_path(sample_model)
        assert result == cache_path


class TestDownloadModel:
    """Tests for model downloading."""

    async def test_download_model_returns_cached_path(
        self, tmp_path: Path, sample_model: Model, valid_nam_content: bytes
    ) -> None:
        """Test that downloading uses cache when available."""
        downloader = ModelDownloader(cache_dir=tmp_path)

        # Pre-cache the model
        cache_path = downloader._cache_path(sample_model)
        cache_path.write_bytes(valid_nam_content)
        original_mtime = cache_path.stat().st_mtime

        # Small delay to ensure mtime would change if file is touched
        await asyncio.sleep(0.01)

        mock_client = MagicMock()
        result = await downloader.download_model(mock_client, sample_model)

        assert result == cache_path
        # File should be touched (mtime updated)
        assert cache_path.stat().st_mtime >= original_mtime

    async def test_download_model_downloads_when_not_cached(
        self, tmp_path: Path, sample_model: Model, valid_nam_content: bytes
    ) -> None:
        """Test that model is downloaded when not cached."""
        downloader = ModelDownloader(cache_dir=tmp_path)

        # Mock httpx response
        mock_response = MagicMock()
        mock_response.content = valid_nam_content
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_http_client = AsyncMock()
            mock_http_client.get = AsyncMock(return_value=mock_response)
            mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
            mock_http_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_http_client

            mock_client = MagicMock()
            result = await downloader.download_model(mock_client, sample_model)

            assert result.exists()
            assert result.read_bytes() == valid_nam_content

    async def test_download_model_force_redownloads(
        self, tmp_path: Path, sample_model: Model, valid_nam_content: bytes
    ) -> None:
        """Test that force=True re-downloads even when cached."""
        downloader = ModelDownloader(cache_dir=tmp_path)

        # Pre-cache the model with different content
        cache_path = downloader._cache_path(sample_model)
        cache_path.write_text('{"old": "content"}')

        # Mock httpx response with new content
        mock_response = MagicMock()
        mock_response.content = valid_nam_content
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_http_client = AsyncMock()
            mock_http_client.get = AsyncMock(return_value=mock_response)
            mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
            mock_http_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_http_client

            mock_client = MagicMock()
            result = await downloader.download_model(
                mock_client, sample_model, force=True
            )

            assert result.read_bytes() == valid_nam_content

    async def test_download_model_validates_content(
        self, tmp_path: Path, sample_model: Model, invalid_nam_content: bytes
    ) -> None:
        """Test that invalid model content is rejected."""
        downloader = ModelDownloader(cache_dir=tmp_path)

        mock_response = MagicMock()
        mock_response.content = invalid_nam_content
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_http_client = AsyncMock()
            mock_http_client.get = AsyncMock(return_value=mock_response)
            mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
            mock_http_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_http_client

            mock_client = MagicMock()

            with pytest.raises(ModelDownloadError, match="Invalid model file"):
                await downloader.download_model(mock_client, sample_model)

    async def test_download_model_handles_http_error(
        self, tmp_path: Path, sample_model: Model
    ) -> None:
        """Test that HTTP errors are handled properly."""
        downloader = ModelDownloader(cache_dir=tmp_path)

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Not Found",
            request=MagicMock(),
            response=mock_response,
        )

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_http_client = AsyncMock()
            mock_http_client.get = AsyncMock(return_value=mock_response)
            mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
            mock_http_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_http_client

            mock_client = MagicMock()

            with pytest.raises(ModelDownloadError, match="HTTP 404"):
                await downloader.download_model(mock_client, sample_model)

    async def test_download_model_handles_network_error(
        self, tmp_path: Path, sample_model: Model
    ) -> None:
        """Test that network errors are handled properly."""
        downloader = ModelDownloader(cache_dir=tmp_path)

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_http_client = AsyncMock()
            mock_http_client.get = AsyncMock(
                side_effect=httpx.RequestError("Connection failed")
            )
            mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
            mock_http_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_http_client

            mock_client = MagicMock()

            with pytest.raises(ModelDownloadError, match="Failed to download"):
                await downloader.download_model(mock_client, sample_model)


class TestValidateModel:
    """Tests for model validation."""

    async def test_validate_valid_model(
        self, tmp_path: Path, valid_nam_content: bytes
    ) -> None:
        """Test validation passes for valid NAM model."""
        downloader = ModelDownloader(cache_dir=tmp_path)
        model = Model(
            id=1,
            name="Test",
            size=ModelSize.STANDARD,
            model_url="https://example.com/model",
            tone_id=100,
        )

        file_path = tmp_path / "test.nam"
        file_path.write_bytes(valid_nam_content)

        result = await downloader._validate_model(file_path, model)
        assert result is True

    async def test_validate_missing_architecture(self, tmp_path: Path) -> None:
        """Test validation fails when architecture/config is missing."""
        downloader = ModelDownloader(cache_dir=tmp_path)
        model = Model(
            id=1,
            name="Test",
            size=ModelSize.STANDARD,
            model_url="https://example.com/model",
            tone_id=100,
        )

        file_path = tmp_path / "test.nam"
        # Has weights but no architecture/config
        file_path.write_text('{"weights": [1, 2, 3]}')

        result = await downloader._validate_model(file_path, model)
        assert result is False

    async def test_validate_missing_weights(self, tmp_path: Path) -> None:
        """Test validation fails when weights are missing."""
        downloader = ModelDownloader(cache_dir=tmp_path)
        model = Model(
            id=1,
            name="Test",
            size=ModelSize.STANDARD,
            model_url="https://example.com/model",
            tone_id=100,
        )

        file_path = tmp_path / "test.nam"
        # Has architecture but no weights
        file_path.write_text('{"architecture": "LSTM", "config": {}}')

        result = await downloader._validate_model(file_path, model)
        assert result is False

    async def test_validate_invalid_json(self, tmp_path: Path) -> None:
        """Test validation fails for invalid JSON."""
        downloader = ModelDownloader(cache_dir=tmp_path)
        model = Model(
            id=1,
            name="Test",
            size=ModelSize.STANDARD,
            model_url="https://example.com/model",
            tone_id=100,
        )

        file_path = tmp_path / "test.nam"
        file_path.write_text("not valid json")

        result = await downloader._validate_model(file_path, model)
        assert result is False

    async def test_validate_binary_content(self, tmp_path: Path) -> None:
        """Test validation fails for binary content."""
        downloader = ModelDownloader(cache_dir=tmp_path)
        model = Model(
            id=1,
            name="Test",
            size=ModelSize.STANDARD,
            model_url="https://example.com/model",
            tone_id=100,
        )

        file_path = tmp_path / "test.nam"
        file_path.write_bytes(b"\x00\x01\x02\x03")

        result = await downloader._validate_model(file_path, model)
        assert result is False


class TestCleanupCache:
    """Tests for cache cleanup."""

    async def test_cleanup_removes_old_files(self, tmp_path: Path) -> None:
        """Test that old files are removed."""
        downloader = ModelDownloader(cache_dir=tmp_path)

        # Create an "old" file (set mtime to 40 days ago)
        old_file = tmp_path / "old_model.nam"
        old_file.write_text("{}")
        old_mtime = time.time() - (40 * 86400)
        os.utime(old_file, (old_mtime, old_mtime))

        # Create a "new" file
        new_file = tmp_path / "new_model.nam"
        new_file.write_text("{}")

        removed = await downloader.cleanup_cache(max_age_days=30)

        assert removed == 1
        assert not old_file.exists()
        assert new_file.exists()

    async def test_cleanup_keeps_recent_files(self, tmp_path: Path) -> None:
        """Test that recent files are kept."""
        downloader = ModelDownloader(cache_dir=tmp_path)

        # Create a recent file
        recent_file = tmp_path / "recent_model.nam"
        recent_file.write_text("{}")

        removed = await downloader.cleanup_cache(max_age_days=30)

        assert removed == 0
        assert recent_file.exists()

    async def test_cleanup_ignores_non_nam_files(self, tmp_path: Path) -> None:
        """Test that non-.nam files are ignored."""
        downloader = ModelDownloader(cache_dir=tmp_path)

        # Create an old non-.nam file
        other_file = tmp_path / "other.txt"
        other_file.write_text("test")
        old_mtime = time.time() - (40 * 86400)
        os.utime(other_file, (old_mtime, old_mtime))

        removed = await downloader.cleanup_cache(max_age_days=30)

        assert removed == 0
        assert other_file.exists()


class TestCacheStats:
    """Tests for cache statistics."""

    def test_get_cache_stats_empty_cache(self, tmp_path: Path) -> None:
        """Test stats for empty cache."""
        downloader = ModelDownloader(cache_dir=tmp_path)

        stats = downloader.get_cache_stats()

        assert stats["total_files"] == 0
        assert stats["total_size_bytes"] == 0
        assert stats["oldest_file_age_days"] == 0.0

    def test_get_cache_stats_with_files(self, tmp_path: Path) -> None:
        """Test stats for cache with files."""
        downloader = ModelDownloader(cache_dir=tmp_path)

        # Create some cached files
        (tmp_path / "model1.nam").write_text('{"test": 1}')
        (tmp_path / "model2.nam").write_text('{"test": 2}')

        stats = downloader.get_cache_stats()

        assert stats["total_files"] == 2
        assert stats["total_size_bytes"] > 0
        assert isinstance(stats["oldest_file_age_days"], float)


class TestGetModelDownloader:
    """Tests for the convenience function."""

    def test_get_model_downloader_returns_instance(self) -> None:
        """Test that get_model_downloader returns a ModelDownloader."""
        with patch("app.services.model_downloader.settings") as mock_settings:
            mock_settings.model_cache_dir = "/tmp/test_cache"
            downloader = get_model_downloader()

        assert isinstance(downloader, ModelDownloader)
