"""Unit tests for T3K model downloader service.

ModelDownloader downloads NAM model files from T3K to local storage.
It validates checksums, retries on failure, and skips existing files.
"""

import hashlib
from datetime import datetime
from pathlib import Path

import pytest
from httpx import AsyncClient, MockTransport, Request, Response
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from source_t3k.adapters.outbound.models import Base, T3KModelStaging
from source_t3k.services.model_downloader import ModelDownloader


@pytest.fixture
async def db_engine() -> AsyncEngine:
    """Create an in-memory SQLite engine for testing."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(db_engine: AsyncEngine) -> AsyncSession:
    """Create a database session with transaction rollback."""
    async_session = async_sessionmaker(db_engine, expire_on_commit=False)
    async with async_session() as session:
        yield session


@pytest.fixture
async def sample_model(db_session: AsyncSession) -> T3KModelStaging:
    """Create a sample T3KModelStaging record."""
    model = T3KModelStaging(
        id="model-123",
        pack_id="pack-456",
        name="Test Model",
        filename="test_model.nam",
        file_size=1024000,
        download_url="https://t3k.com/download/test_model.nam",
        checksum="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",  # SHA-256 of empty string
        created_at=datetime(2024, 1, 1, 0, 0, 0),
        updated_at=datetime(2024, 1, 2, 0, 0, 0),
    )
    db_session.add(model)
    await db_session.commit()
    await db_session.refresh(model)
    return model


def _make_transport(handler) -> AsyncClient:
    """Create an AsyncClient wired to a MockTransport handler."""
    return AsyncClient(transport=MockTransport(handler))


class TestModelDownloaderInit:
    """Test ModelDownloader initialization."""

    def test_init_with_default_http_client(self, tmp_path: Path, db_session: AsyncSession) -> None:
        """ModelDownloader should initialize with default httpx client."""
        downloader = ModelDownloader(base_path=tmp_path, session=db_session)

        assert downloader._base_path == tmp_path
        assert downloader._session is db_session
        assert downloader._http_client is None

    def test_init_with_custom_http_client(self, tmp_path: Path, db_session: AsyncSession) -> None:
        """ModelDownloader should accept custom httpx client."""
        client = _make_transport(lambda _r: Response(200))
        downloader = ModelDownloader(base_path=tmp_path, session=db_session, http_client=client)

        assert downloader._base_path == tmp_path
        assert downloader._session is db_session
        assert downloader._http_client is client

    def test_init_creates_base_path_if_missing(
        self, tmp_path: Path, db_session: AsyncSession
    ) -> None:
        """ModelDownloader should create base_path directory if it doesn't exist."""
        non_existent = tmp_path / "downloads" / "t3k"
        assert not non_existent.exists()

        downloader = ModelDownloader(base_path=non_existent, session=db_session)

        assert downloader._base_path == non_existent


class TestGetModelPath:
    """Test ModelDownloader._get_model_path() method."""

    def test_get_model_path_constructs_correct_path(
        self, tmp_path: Path, db_session: AsyncSession, sample_model: T3KModelStaging
    ) -> None:
        """_get_model_path should construct path as base_path/source_record_id/filename."""
        downloader = ModelDownloader(base_path=tmp_path, session=db_session)

        path = downloader._get_model_path(sample_model)

        expected = tmp_path / "model-123" / "test_model.nam"
        assert path == expected

    def test_get_model_path_uses_model_id_as_directory(
        self, tmp_path: Path, db_session: AsyncSession, sample_model: T3KModelStaging
    ) -> None:
        """_get_model_path should use model.id as the subdirectory name."""
        downloader = ModelDownloader(base_path=tmp_path, session=db_session)

        path = downloader._get_model_path(sample_model)

        assert path.parent.name == "model-123"


class TestVerifyChecksum:
    """Test ModelDownloader._verify_checksum() method."""

    def test_verify_checksum_returns_true_for_matching_checksum(
        self, tmp_path: Path, db_session: AsyncSession
    ) -> None:
        """_verify_checksum should return True when file checksum matches."""
        test_file = tmp_path / "test.nam"
        content = b"test content"
        test_file.write_bytes(content)

        expected_checksum = hashlib.sha256(content).hexdigest()
        downloader = ModelDownloader(base_path=tmp_path, session=db_session)

        result = downloader._verify_checksum(test_file, expected_checksum)

        assert result is True

    def test_verify_checksum_returns_false_for_mismatched_checksum(
        self, tmp_path: Path, db_session: AsyncSession
    ) -> None:
        """_verify_checksum should return False when file checksum doesn't match."""
        test_file = tmp_path / "test.nam"
        test_file.write_bytes(b"test content")

        wrong_checksum = "0" * 64  # Invalid checksum
        downloader = ModelDownloader(base_path=tmp_path, session=db_session)

        result = downloader._verify_checksum(test_file, wrong_checksum)

        assert result is False

    def test_verify_checksum_returns_false_for_nonexistent_file(
        self, tmp_path: Path, db_session: AsyncSession
    ) -> None:
        """_verify_checksum should return False when file doesn't exist."""
        nonexistent_file = tmp_path / "missing.nam"
        downloader = ModelDownloader(base_path=tmp_path, session=db_session)

        result = downloader._verify_checksum(nonexistent_file, "abc123")

        assert result is False


class TestDownloadModel:
    """Test ModelDownloader.download_model() method."""

    @pytest.mark.asyncio
    async def test_download_model_downloads_file_to_correct_location(
        self, tmp_path: Path, db_session: AsyncSession, sample_model: T3KModelStaging
    ) -> None:
        """download_model should download file to base_path/source_record_id/filename."""
        file_content = b""  # Empty content matches sample_model checksum

        def handler(request: Request) -> Response:
            return Response(200, content=file_content)

        client = _make_transport(handler)
        downloader = ModelDownloader(base_path=tmp_path, session=db_session, http_client=client)
        result_path = await downloader.download_model(sample_model)

        expected_path = tmp_path / "model-123" / "test_model.nam"
        assert result_path == expected_path
        assert expected_path.exists()
        assert expected_path.read_bytes() == file_content

    @pytest.mark.asyncio
    async def test_download_model_creates_parent_directory(
        self, tmp_path: Path, db_session: AsyncSession, sample_model: T3KModelStaging
    ) -> None:
        """download_model should create parent directory if it doesn't exist."""

        def handler(request: Request) -> Response:
            return Response(200, content=b"")

        client = _make_transport(handler)
        downloader = ModelDownloader(base_path=tmp_path, session=db_session, http_client=client)
        result_path = await downloader.download_model(sample_model)

        assert result_path.parent.exists()

    @pytest.mark.asyncio
    async def test_download_model_validates_checksum(
        self, tmp_path: Path, db_session: AsyncSession, sample_model: T3KModelStaging
    ) -> None:
        """download_model should validate downloaded file checksum."""

        def handler(request: Request) -> Response:
            return Response(200, content=b"wrong content")  # Won't match checksum

        client = _make_transport(handler)
        downloader = ModelDownloader(base_path=tmp_path, session=db_session, http_client=client)

        # Should raise exception or return None on checksum mismatch
        result = await downloader.download_model(sample_model)

        assert result is None

    @pytest.mark.asyncio
    async def test_download_model_sends_correct_request(
        self, tmp_path: Path, db_session: AsyncSession, sample_model: T3KModelStaging
    ) -> None:
        """download_model should send GET request to model.download_url."""
        captured_requests: list[Request] = []

        def handler(request: Request) -> Response:
            captured_requests.append(request)
            return Response(200, content=b"")

        client = _make_transport(handler)
        downloader = ModelDownloader(base_path=tmp_path, session=db_session, http_client=client)
        await downloader.download_model(sample_model)

        assert len(captured_requests) == 1
        assert str(captured_requests[0].url) == sample_model.download_url


class TestSkipExisting:
    """Test ModelDownloader skips existing files with correct checksum."""

    @pytest.mark.asyncio
    async def test_download_model_skips_existing_file_with_matching_checksum(
        self, tmp_path: Path, db_session: AsyncSession, sample_model: T3KModelStaging
    ) -> None:
        """download_model should skip download if file exists with correct checksum."""
        # Create existing file with correct checksum
        model_path = tmp_path / "model-123" / "test_model.nam"
        model_path.parent.mkdir(parents=True)
        model_path.write_bytes(b"")  # Empty content matches sample_model checksum

        request_count = 0

        def handler(request: Request) -> Response:
            nonlocal request_count
            request_count += 1
            return Response(200, content=b"")

        client = _make_transport(handler)
        downloader = ModelDownloader(base_path=tmp_path, session=db_session, http_client=client)

        result_path = await downloader.download_model(sample_model)

        # Should return None to indicate skip
        assert result_path is None
        # Should not have called HTTP client
        assert request_count == 0

    @pytest.mark.asyncio
    async def test_download_model_redownloads_existing_file_with_wrong_checksum(
        self, tmp_path: Path, db_session: AsyncSession, sample_model: T3KModelStaging
    ) -> None:
        """download_model should re-download if file exists with wrong checksum."""
        # Create existing file with WRONG checksum
        model_path = tmp_path / "model-123" / "test_model.nam"
        model_path.parent.mkdir(parents=True)
        model_path.write_bytes(b"wrong content")

        request_count = 0

        def handler(request: Request) -> Response:
            nonlocal request_count
            request_count += 1
            return Response(200, content=b"")  # Correct content

        client = _make_transport(handler)
        downloader = ModelDownloader(base_path=tmp_path, session=db_session, http_client=client)
        result_path = await downloader.download_model(sample_model)

        # Should have downloaded
        assert result_path == model_path
        assert request_count == 1


class TestRetryBehaviour:
    """Test ModelDownloader retry behaviour on failures."""

    @pytest.mark.asyncio
    async def test_download_model_retries_on_network_error(
        self, tmp_path: Path, db_session: AsyncSession, sample_model: T3KModelStaging
    ) -> None:
        """download_model should retry up to 3 times on network errors."""
        call_count = 0

        def handler(request: Request) -> Response:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Network error")
            return Response(200, content=b"")

        client = _make_transport(handler)
        downloader = ModelDownloader(base_path=tmp_path, session=db_session, http_client=client)
        result_path = await downloader.download_model(sample_model)

        assert result_path is not None
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_download_model_fails_after_max_retries(
        self, tmp_path: Path, db_session: AsyncSession, sample_model: T3KModelStaging
    ) -> None:
        """download_model should fail after 3 unsuccessful retries."""
        call_count = 0

        def handler(request: Request) -> Response:
            nonlocal call_count
            call_count += 1
            raise Exception("Network error")

        client = _make_transport(handler)
        downloader = ModelDownloader(base_path=tmp_path, session=db_session, http_client=client)
        result = await downloader.download_model(sample_model)

        assert result is None
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_download_model_removes_corrupt_file_after_all_retries_fail(
        self, tmp_path: Path, db_session: AsyncSession, sample_model: T3KModelStaging
    ) -> None:
        """download_model should remove partial/corrupt file after all retries fail."""

        def handler(request: Request) -> Response:
            return Response(200, content=b"corrupt content")

        client = _make_transport(handler)
        downloader = ModelDownloader(base_path=tmp_path, session=db_session, http_client=client)
        result = await downloader.download_model(sample_model)

        expected_path = tmp_path / "model-123" / "test_model.nam"
        assert result is None
        # Corrupt file should be removed
        assert not expected_path.exists()


class TestDownloadModelsForPack:
    """Test ModelDownloader.download_models_for_pack() method."""

    @pytest.mark.asyncio
    async def test_download_models_for_pack_downloads_all_models(
        self, tmp_path: Path, db_session: AsyncSession
    ) -> None:
        """download_models_for_pack should download all models for a pack."""
        # Create multiple models for the same pack
        models = [
            T3KModelStaging(
                id=f"model-{i}",
                pack_id="pack-999",
                name=f"Model {i}",
                filename=f"model_{i}.nam",
                file_size=1024000,
                download_url=f"https://t3k.com/download/model_{i}.nam",
                checksum="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                created_at=datetime(2024, 1, 1, 0, 0, 0),
                updated_at=datetime(2024, 1, 2, 0, 0, 0),
            )
            for i in range(3)
        ]
        for model in models:
            db_session.add(model)
        await db_session.commit()

        request_count = 0

        def handler(request: Request) -> Response:
            nonlocal request_count
            request_count += 1
            return Response(200, content=b"")

        client = _make_transport(handler)
        downloader = ModelDownloader(base_path=tmp_path, session=db_session, http_client=client)
        result_paths = await downloader.download_models_for_pack("pack-999")

        assert len(result_paths) == 3
        assert all(isinstance(p, Path) for p in result_paths)
        assert request_count == 3

    @pytest.mark.asyncio
    async def test_download_models_for_pack_returns_empty_list_for_nonexistent_pack(
        self, tmp_path: Path, db_session: AsyncSession
    ) -> None:
        """download_models_for_pack should return empty list for pack with no models."""
        request_count = 0

        def handler(request: Request) -> Response:
            nonlocal request_count
            request_count += 1
            return Response(200, content=b"")

        client = _make_transport(handler)
        downloader = ModelDownloader(base_path=tmp_path, session=db_session, http_client=client)

        result_paths = await downloader.download_models_for_pack("nonexistent-pack")

        assert result_paths == []
        assert request_count == 0

    @pytest.mark.asyncio
    async def test_download_models_for_pack_queries_by_pack_id(
        self, tmp_path: Path, db_session: AsyncSession
    ) -> None:
        """download_models_for_pack should query models filtered by pack_id."""
        # Create models for different packs
        pack_a_model = T3KModelStaging(
            id="model-a",
            pack_id="pack-aaa",
            name="Model A",
            filename="model_a.nam",
            file_size=1024000,
            download_url="https://t3k.com/download/model_a.nam",
            checksum="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            created_at=datetime(2024, 1, 1, 0, 0, 0),
            updated_at=datetime(2024, 1, 2, 0, 0, 0),
        )
        pack_b_model = T3KModelStaging(
            id="model-b",
            pack_id="pack-bbb",
            name="Model B",
            filename="model_b.nam",
            file_size=2048000,
            download_url="https://t3k.com/download/model_b.nam",
            checksum="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            created_at=datetime(2024, 1, 1, 0, 0, 0),
            updated_at=datetime(2024, 1, 2, 0, 0, 0),
        )
        db_session.add(pack_a_model)
        db_session.add(pack_b_model)
        await db_session.commit()

        request_count = 0

        def handler(request: Request) -> Response:
            nonlocal request_count
            request_count += 1
            return Response(200, content=b"")

        client = _make_transport(handler)
        downloader = ModelDownloader(base_path=tmp_path, session=db_session, http_client=client)
        result_paths = await downloader.download_models_for_pack("pack-aaa")

        # Should only download pack-aaa model, not pack-bbb
        assert len(result_paths) == 1
        assert request_count == 1

    @pytest.mark.asyncio
    async def test_download_models_for_pack_excludes_skipped_models(
        self, tmp_path: Path, db_session: AsyncSession
    ) -> None:
        """download_models_for_pack should exclude models that were skipped from results."""
        # Create one model that already exists (will be skipped)
        existing_model = T3KModelStaging(
            id="model-existing",
            pack_id="pack-skip",
            name="Existing Model",
            filename="existing.nam",
            file_size=1024000,
            download_url="https://t3k.com/download/existing.nam",
            checksum="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            created_at=datetime(2024, 1, 1, 0, 0, 0),
            updated_at=datetime(2024, 1, 2, 0, 0, 0),
        )
        # Create one model that will be downloaded
        new_model = T3KModelStaging(
            id="model-new",
            pack_id="pack-skip",
            name="New Model",
            filename="new.nam",
            file_size=2048000,
            download_url="https://t3k.com/download/new.nam",
            checksum="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            created_at=datetime(2024, 1, 1, 0, 0, 0),
            updated_at=datetime(2024, 1, 2, 0, 0, 0),
        )
        db_session.add(existing_model)
        db_session.add(new_model)
        await db_session.commit()

        # Pre-create existing file with correct checksum
        existing_path = tmp_path / "model-existing" / "existing.nam"
        existing_path.parent.mkdir(parents=True)
        existing_path.write_bytes(b"")

        request_count = 0

        def handler(request: Request) -> Response:
            nonlocal request_count
            request_count += 1
            return Response(200, content=b"")

        client = _make_transport(handler)
        downloader = ModelDownloader(base_path=tmp_path, session=db_session, http_client=client)
        result_paths = await downloader.download_models_for_pack("pack-skip")

        # Should only include the newly downloaded model
        assert len(result_paths) == 1
        assert result_paths[0].name == "new.nam"
        # Should only have called HTTP client once (for new model)
        assert request_count == 1
