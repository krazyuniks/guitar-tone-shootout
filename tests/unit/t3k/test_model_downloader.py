"""Unit tests for T3K model downloader service.

ModelDownloader downloads NAM model files from T3K to local storage.
It retries on failure and skips existing files.
Filenames are derived from model_url (no checksums).
"""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from httpx import AsyncClient, MockTransport, Request, Response
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from source_t3k.adapters.outbound.models import T3KModelStaging
from source_t3k.services.model_downloader import ModelDownloader


@pytest.fixture
async def db_engine() -> AsyncEngine:
    """Create an in-memory SQLite engine with only the models staging table."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(T3KModelStaging.__table__.create)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(db_engine: AsyncEngine) -> AsyncSession:
    """Create a database session."""
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with factory() as session:
        yield session


def _make_model(
    model_id: int = 99,
    tone_id: int = 42,
    model_url: str = "https://t3k.com/download/test_model.nam",
) -> T3KModelStaging:
    """Build a T3KModelStaging with sensible defaults."""
    now = datetime(2024, 1, 1, tzinfo=UTC)
    return T3KModelStaging(
        id=model_id,
        tone_id=tone_id,
        user_id="user-1",
        name="Test Model",
        model_url=model_url,
        size="standard",
        created_at=now,
        updated_at=now,
    )


def _make_http_client(content: bytes = b"model-data", status: int = 200) -> AsyncClient:
    """Build an AsyncClient backed by MockTransport."""

    def handler(request: Request) -> Response:
        return Response(status, content=content)

    return AsyncClient(transport=MockTransport(handler))


def _make_transport(handler) -> AsyncClient:
    """Create an AsyncClient wired to a MockTransport handler."""
    return AsyncClient(transport=MockTransport(handler))


class TestModelDownloaderInit:
    """Test ModelDownloader initialization."""

    def test_init_with_default_http_client(self, tmp_path: Path, db_session: AsyncSession) -> None:
        downloader = ModelDownloader(base_path=tmp_path, session=db_session)
        assert downloader._base_path == tmp_path
        assert downloader._session is db_session
        assert downloader._http_client is None

    def test_init_with_custom_http_client(self, tmp_path: Path, db_session: AsyncSession) -> None:
        client = _make_http_client()
        downloader = ModelDownloader(base_path=tmp_path, session=db_session, http_client=client)
        assert downloader._http_client is client


class TestGetModelPath:
    """Test ModelDownloader._get_model_path() method."""

    def test_derives_filename_from_model_url(
        self, tmp_path: Path, db_session: AsyncSession
    ) -> None:
        model = _make_model(model_url="https://t3k.com/download/clean_channel.nam")
        downloader = ModelDownloader(base_path=tmp_path, session=db_session)
        path = downloader._get_model_path(model)
        assert path == tmp_path / "99" / "clean_channel.nam"

    def test_uses_model_id_as_directory(self, tmp_path: Path, db_session: AsyncSession) -> None:
        model = _make_model(model_id=123, model_url="https://t3k.com/test.nam")
        downloader = ModelDownloader(base_path=tmp_path, session=db_session)
        path = downloader._get_model_path(model)
        assert path.parent.name == "123"


class TestDownloadModel:
    """Test ModelDownloader.download_model() method."""

    @pytest.mark.asyncio
    async def test_downloads_file_to_correct_location(
        self, tmp_path: Path, db_session: AsyncSession
    ) -> None:
        model = _make_model()
        client = _make_http_client(content=b"nam-content")
        downloader = ModelDownloader(base_path=tmp_path, session=db_session, http_client=client)

        result = await downloader.download_model(model)

        expected = tmp_path / "99" / "test_model.nam"
        assert result == expected
        assert expected.exists()
        assert expected.read_bytes() == b"nam-content"

    @pytest.mark.asyncio
    async def test_creates_parent_directory(self, tmp_path: Path, db_session: AsyncSession) -> None:
        model = _make_model()
        client = _make_http_client()
        downloader = ModelDownloader(base_path=tmp_path, session=db_session, http_client=client)

        result = await downloader.download_model(model)

        assert result is not None
        assert result.parent.exists()

    @pytest.mark.asyncio
    async def test_skips_existing_file(self, tmp_path: Path, db_session: AsyncSession) -> None:
        model = _make_model()
        model_path = tmp_path / "99" / "test_model.nam"
        model_path.parent.mkdir(parents=True)
        model_path.write_bytes(b"existing")

        client = _make_http_client()
        downloader = ModelDownloader(base_path=tmp_path, session=db_session, http_client=client)

        result = await downloader.download_model(model)

        assert result is None


class TestRetryBehaviour:
    """Test ModelDownloader retry behaviour on failures."""

    @pytest.mark.asyncio
    async def test_retries_on_network_error(self, tmp_path: Path, db_session: AsyncSession) -> None:
        model = _make_model()
        call_count = 0

        def handler(request: Request) -> Response:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Network error")
            return Response(200, content=b"success")

        client = AsyncClient(transport=MockTransport(handler))
        downloader = ModelDownloader(base_path=tmp_path, session=db_session, http_client=client)

        result = await downloader.download_model(model)

        assert result is not None
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_fails_after_max_retries(self, tmp_path: Path, db_session: AsyncSession) -> None:
        model = _make_model()

        def handler(request: Request) -> Response:
            raise Exception("Network error")

        client = AsyncClient(transport=MockTransport(handler))
        downloader = ModelDownloader(base_path=tmp_path, session=db_session, http_client=client)

        result = await downloader.download_model(model)

        assert result is None

    @pytest.mark.asyncio
    async def test_removes_partial_file_after_failure(
        self, tmp_path: Path, db_session: AsyncSession
    ) -> None:
        model = _make_model()

        def handler(request: Request) -> Response:
            raise Exception("Network error")

        client = AsyncClient(transport=MockTransport(handler))
        downloader = ModelDownloader(base_path=tmp_path, session=db_session, http_client=client)

        result = await downloader.download_model(model)

        expected_path = tmp_path / "99" / "test_model.nam"
        assert result is None
        assert not expected_path.exists()


class TestDownloadModelsForTone:
    """Test ModelDownloader.download_models_for_tone() method."""

    @pytest.mark.asyncio
    async def test_downloads_all_models_for_tone(
        self, tmp_path: Path, db_session: AsyncSession
    ) -> None:
        for i in range(3):
            model = T3KModelStaging(
                id=i + 1,
                tone_id=42,
                user_id="u",
                name=f"Model {i}",
                model_url=f"https://t3k.com/model_{i}.nam",
                size="standard",
                created_at=datetime(2024, 1, 1, tzinfo=UTC),
                updated_at=datetime(2024, 1, 1, tzinfo=UTC),
            )
            db_session.add(model)
        await db_session.commit()

        client = _make_http_client()
        downloader = ModelDownloader(base_path=tmp_path, session=db_session, http_client=client)

        result = await downloader.download_models_for_tone(42)

        assert len(result) == 3
        assert all(isinstance(p, Path) for p in result)

    @pytest.mark.asyncio
    async def test_returns_empty_for_nonexistent_tone(
        self, tmp_path: Path, db_session: AsyncSession
    ) -> None:
        client = _make_http_client()
        downloader = ModelDownloader(base_path=tmp_path, session=db_session, http_client=client)

        result = await downloader.download_models_for_tone(999)

        assert result == []

    @pytest.mark.asyncio
    async def test_filters_by_tone_id(self, tmp_path: Path, db_session: AsyncSession) -> None:
        model_a = T3KModelStaging(
            id=1,
            tone_id=10,
            user_id="u",
            name="A",
            model_url="https://t3k.com/a.nam",
            size="standard",
            created_at=datetime(2024, 1, 1, tzinfo=UTC),
            updated_at=datetime(2024, 1, 1, tzinfo=UTC),
        )
        model_b = T3KModelStaging(
            id=2,
            tone_id=20,
            user_id="u",
            name="B",
            model_url="https://t3k.com/b.nam",
            size="standard",
            created_at=datetime(2024, 1, 1, tzinfo=UTC),
            updated_at=datetime(2024, 1, 1, tzinfo=UTC),
        )
        db_session.add(model_a)
        db_session.add(model_b)
        await db_session.commit()

        client = _make_http_client()
        downloader = ModelDownloader(base_path=tmp_path, session=db_session, http_client=client)

        result = await downloader.download_models_for_tone(10)

        assert len(result) == 1
