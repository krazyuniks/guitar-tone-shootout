"""Unit tests for GearMapperService end-to-end data flow.

Tests verify that sync records produce correct Gear, GearSource, and GearModel
rows in the gts_core database. Uses real SQLite sessions — no mocking.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import joinedload

from core.records.gear_sync import GearSyncRecord, SyncOperation
from webapp.adapters.persistence.models.base import Base
from webapp.adapters.persistence.models.gear import Gear
from webapp.adapters.persistence.models.gear_model import GearModel
from webapp.adapters.persistence.models.gear_source import GearSource
from worker.services.gear_mapper import (
    GearMapperService,
    ModelFileNotReadyError,
    ParentGearNotReadyError,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def db_engine() -> AsyncGenerator[AsyncEngine, None]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def session(db_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with factory() as session:
        yield session


@pytest.fixture
def mapper(session: AsyncSession) -> GearMapperService:
    return GearMapperService(session=session)


def _pack_record(
    source_record_id: str = "pack-001",
    name: str = "Test Amp",
    slug: str = "test-amp",
    gear_type: str = "amp",
    **extra_payload: object,
) -> GearSyncRecord:
    """Build a pack sync record with sensible defaults."""
    payload = {
        "name": name,
        "slug": slug,
        "gear_type": gear_type,
        **extra_payload,
    }
    return GearSyncRecord(
        source_name="t3k",
        source_record_id=source_record_id,
        source_updated_at=datetime(2026, 1, 15, tzinfo=UTC),
        operation=SyncOperation.CREATE,
        payload=payload,
    )


def _model_record(
    pack_id: str = "pack-001",
    source_record_id: str = "model-001",
    platform: str = "nam",
    size: str = "standard",
    **extra_payload: object,
) -> GearSyncRecord:
    """Build a model sync record with sensible defaults."""
    payload = {
        "pack_id": pack_id,
        "platform": platform,
        "size": size,
        **extra_payload,
    }
    return GearSyncRecord(
        source_name="t3k",
        source_record_id=source_record_id,
        source_updated_at=datetime(2026, 1, 15, tzinfo=UTC),
        operation=SyncOperation.CREATE,
        payload=payload,
    )


# ---------------------------------------------------------------------------
# Pack sync → Gear + GearSource creation
# ---------------------------------------------------------------------------


class TestPackSyncCreatesGear:
    """process_pack_sync must create Gear and GearSource rows."""

    async def test_creates_gear_row(self, mapper: GearMapperService, session: AsyncSession) -> None:
        """A pack sync record should create a Gear row in gts_core."""
        record = _pack_record(name="Marshall JCM800", slug="marshall-jcm800", gear_type="amp")
        await mapper.process_pack_sync(record)
        await session.flush()

        result = await session.execute(select(Gear))
        gear = result.scalar_one()
        assert gear.name == "Marshall JCM800"
        assert gear.slug == "marshall-jcm800"
        assert gear.gear_type.value == "amp"

    async def test_creates_gear_source_row(
        self, mapper: GearMapperService, session: AsyncSession
    ) -> None:
        """A pack sync should create a GearSource linking gear to its source."""
        record = _pack_record()
        await mapper.process_pack_sync(record)
        await session.flush()

        result = await session.execute(select(GearSource))
        source = result.scalar_one()
        assert source.source_name == "t3k"
        assert source.source_record_id == "pack-001"

    async def test_gear_source_linked_to_gear(
        self, mapper: GearMapperService, session: AsyncSession
    ) -> None:
        """GearSource must be linked to the created Gear (via relationship or FK)."""
        record = _pack_record()
        await mapper.process_pack_sync(record)
        await session.flush()

        result = await session.execute(select(Gear).options(joinedload(Gear.source)))
        gear = result.unique().scalar_one()
        assert gear.source is not None
        assert gear.source.source_name == "t3k"
        assert gear.source.source_record_id == "pack-001"


# ---------------------------------------------------------------------------
# Pack sync → Gear update (idempotency)
# ---------------------------------------------------------------------------


class TestPackSyncUpdatesGear:
    """process_pack_sync must update existing Gear when re-syncing."""

    async def test_updates_existing_gear_name(
        self, mapper: GearMapperService, session: AsyncSession
    ) -> None:
        """Re-syncing a pack with a newer timestamp updates the Gear name."""
        # Create initial
        record_v1 = _pack_record(name="Old Name", slug="old-name")
        await mapper.process_pack_sync(record_v1)
        await session.flush()

        # Update with newer timestamp
        record_v2 = GearSyncRecord(
            source_name="t3k",
            source_record_id="pack-001",
            source_updated_at=datetime(2026, 2, 1, tzinfo=UTC),
            operation=SyncOperation.UPDATE,
            payload={"name": "New Name"},
        )
        await mapper.process_pack_sync(record_v2)
        await session.flush()

        result = await session.execute(select(Gear))
        gear = result.scalar_one()
        assert gear.name == "New Name"

    async def test_skips_stale_update(
        self, mapper: GearMapperService, session: AsyncSession
    ) -> None:
        """Re-syncing with older timestamp does NOT update the Gear."""
        record_v1 = GearSyncRecord(
            source_name="t3k",
            source_record_id="pack-001",
            source_updated_at=datetime(2026, 2, 1, tzinfo=UTC),
            operation=SyncOperation.CREATE,
            payload={"name": "Current Name", "slug": "current-name", "gear_type": "amp"},
        )
        await mapper.process_pack_sync(record_v1)
        await session.flush()

        # Stale update with OLDER timestamp
        record_stale = GearSyncRecord(
            source_name="t3k",
            source_record_id="pack-001",
            source_updated_at=datetime(2026, 1, 1, tzinfo=UTC),
            operation=SyncOperation.UPDATE,
            payload={"name": "Stale Name"},
        )
        await mapper.process_pack_sync(record_stale)
        await session.flush()

        result = await session.execute(select(Gear))
        gear = result.scalar_one()
        assert gear.name == "Current Name", "Stale update should NOT overwrite current name"


# ---------------------------------------------------------------------------
# Model sync → GearModel creation
# ---------------------------------------------------------------------------


class TestModelSyncCreatesGearModel:
    """process_model_sync must create GearModel rows linked to parent Gear."""

    async def test_creates_gear_model_row(
        self, mapper: GearMapperService, session: AsyncSession
    ) -> None:
        """A model sync record should create a GearModel in gts_core."""
        # First create the parent gear
        pack_record = _pack_record()
        await mapper.process_pack_sync(pack_record)
        await session.flush()

        # Then create a model for that gear
        model_record = _model_record(platform="nam", size="standard")
        await mapper.process_model_sync(model_record)
        await session.flush()

        result = await session.execute(select(GearModel))
        model = result.scalar_one()
        assert model.platform.value == "nam"
        assert model.size.value == "standard"

    async def test_gear_model_linked_to_parent_gear(
        self, mapper: GearMapperService, session: AsyncSession
    ) -> None:
        """GearModel must reference the correct parent Gear via gear_id."""
        pack_record = _pack_record()
        await mapper.process_pack_sync(pack_record)
        await session.flush()

        model_record = _model_record()
        await mapper.process_model_sync(model_record)
        await session.flush()

        # Load gear with models
        result = await session.execute(select(Gear).options(joinedload(Gear.models)))
        gear = result.unique().scalar_one()
        assert len(gear.models) == 1
        assert gear.models[0].platform.value == "nam"

    async def test_model_sync_without_parent_raises(
        self, mapper: GearMapperService, session: AsyncSession
    ) -> None:
        """Model sync for non-existent parent gear must raise retryable error."""
        model_record = _model_record(pack_id="nonexistent-pack")

        with pytest.raises(ParentGearNotReadyError, match="Parent gear not found"):
            await mapper.process_model_sync(model_record)

    async def test_model_sync_without_pack_id_raises(
        self, mapper: GearMapperService, session: AsyncSession
    ) -> None:
        """Model sync missing pack_id in payload must raise ValueError."""
        record = GearSyncRecord(
            source_name="t3k",
            source_record_id="model-bad",
            source_updated_at=datetime(2026, 1, 15, tzinfo=UTC),
            operation=SyncOperation.CREATE,
            payload={"platform": "nam", "size": "standard"},  # no pack_id
        )

        with pytest.raises(ValueError, match="missing pack_id"):
            await mapper.process_model_sync(record)

    async def test_gear_model_has_pending_download_status(
        self, mapper: GearMapperService, session: AsyncSession
    ) -> None:
        """Newly created GearModel should start with PENDING download status."""
        from core.domain.value_objects.download_status import DownloadStatus

        pack_record = _pack_record()
        await mapper.process_pack_sync(pack_record)
        await session.flush()

        model_record = _model_record()
        await mapper.process_model_sync(model_record)
        await session.flush()

        result = await session.execute(select(GearModel))
        model = result.scalar_one()
        assert model.download_status == DownloadStatus.PENDING


# ---------------------------------------------------------------------------
# Full data flow: pack + models in one sequence
# ---------------------------------------------------------------------------


class TestFullDataFlow:
    """End-to-end: sync produces Gear + GearSource + multiple GearModels."""

    async def test_full_sync_creates_complete_aggregate(
        self, mapper: GearMapperService, session: AsyncSession
    ) -> None:
        """Syncing a pack then two models produces a complete gear aggregate."""
        # Create pack
        pack_record = _pack_record(
            name="Mesa Boogie Dual Rectifier",
            slug="mesa-boogie-dual-rectifier",
            gear_type="amp",
            platform="nam",
            description="High-gain amp capture",
        )
        await mapper.process_pack_sync(pack_record)
        await session.flush()

        # Create two models
        model1 = _model_record(
            source_record_id="model-001",
            platform="nam",
            size="standard",
            download_url="https://example.com/model1.nam",
        )
        model2 = _model_record(
            source_record_id="model-002",
            platform="nam",
            size="standard",
            checksum="abc123def456",
        )
        await mapper.process_model_sync(model1)
        await mapper.process_model_sync(model2)
        await session.flush()

        # Verify the complete aggregate
        result = await session.execute(
            select(Gear).options(
                joinedload(Gear.source),
                joinedload(Gear.models),
            )
        )
        gear = result.unique().scalar_one()

        # Gear row exists
        assert gear.name == "Mesa Boogie Dual Rectifier"
        assert gear.gear_type.value == "amp"

        # GearSource row links back to T3K
        assert gear.source is not None
        assert gear.source.source_name == "t3k"
        assert gear.source.source_record_id == "pack-001"

        # Two GearModel rows linked to parent Gear
        assert len(gear.models) == 2


class TestAggregateSyncRecord:
    """Tests for aggregate pack+models sync record processing."""

    async def test_process_sync_record_creates_gear_and_models_atomically(
        self, mapper: GearMapperService, session: AsyncSession, tmp_path, monkeypatch
    ) -> None:
        """Aggregate sync payload should create parent Gear and child GearModel rows."""
        monkeypatch.setenv("GTS_STORAGE_ROOT", str(tmp_path))
        source_model_dir = tmp_path / "source_downloads" / "t3k" / "model-001"
        source_model_dir.mkdir(parents=True, exist_ok=True)
        (source_model_dir / "model-001.nam").write_bytes(b"dummy-nam")

        record = GearSyncRecord(
            source_name="t3k",
            source_record_id="pack-001",
            source_updated_at=datetime(2026, 2, 15, tzinfo=UTC),
            operation=SyncOperation.CREATE,
            payload={
                "name": "Aggregate Pack",
                "slug": "aggregate-pack",
                "gear_type": "amp",
                "platform": "nam",
                "models": [
                    {
                        "source_record_id": "model-001",
                        "filename": "model-001.nam",
                        "download_url": "https://example.com/model-001.nam",
                        "checksum": "abc123",
                        "platform": "nam",
                        "size": "standard",
                    }
                ],
            },
        )

        await mapper.process_sync_record(record)
        await session.flush()

        result = await session.execute(select(Gear).options(joinedload(Gear.models)))
        gear = result.unique().scalar_one()
        assert gear.name == "Aggregate Pack"
        assert len(gear.models) == 1
        assert gear.models[0].file_path is not None

    async def test_migrated_model_has_completed_download_status(
        self, mapper: GearMapperService, session: AsyncSession, tmp_path, monkeypatch
    ) -> None:
        """Model with successfully migrated file should have COMPLETED download status."""
        from core.domain.value_objects.download_status import DownloadStatus

        monkeypatch.setenv("GTS_STORAGE_ROOT", str(tmp_path))
        source_model_dir = tmp_path / "source_downloads" / "t3k" / "model-001"
        source_model_dir.mkdir(parents=True, exist_ok=True)
        (source_model_dir / "model-001.nam").write_bytes(b"dummy-nam")

        record = GearSyncRecord(
            source_name="t3k",
            source_record_id="pack-001",
            source_updated_at=datetime(2026, 2, 15, tzinfo=UTC),
            operation=SyncOperation.CREATE,
            payload={
                "name": "Status Check Pack",
                "slug": "status-check-pack",
                "gear_type": "amp",
                "platform": "nam",
                "models": [
                    {
                        "source_record_id": "model-001",
                        "filename": "model-001.nam",
                        "download_url": "https://example.com/model-001.nam",
                        "checksum": "abc123",
                        "platform": "nam",
                        "size": "standard",
                    }
                ],
            },
        )

        await mapper.process_sync_record(record)
        await session.flush()

        result = await session.execute(select(GearModel))
        model = result.scalar_one()
        assert model.download_status == DownloadStatus.COMPLETED
        assert model.file_path is not None

    async def test_process_sync_record_raises_retryable_error_when_model_file_missing(
        self,
        mapper: GearMapperService,
        session: AsyncSession,
        tmp_path,
        monkeypatch,
    ) -> None:
        """Missing model files should fail atomically and be retried by consumer."""
        monkeypatch.setenv("GTS_STORAGE_ROOT", str(tmp_path))

        record = GearSyncRecord(
            source_name="t3k",
            source_record_id="pack-001",
            source_updated_at=datetime(2026, 2, 15, tzinfo=UTC),
            operation=SyncOperation.CREATE,
            payload={
                "name": "Aggregate Pack",
                "slug": "aggregate-pack",
                "gear_type": "amp",
                "platform": "nam",
                "models": [
                    {
                        "source_record_id": "model-404",
                        "filename": "missing.nam",
                        "download_url": "https://example.com/missing.nam",
                        "checksum": "abc123",
                        "platform": "nam",
                        "size": "standard",
                    }
                ],
            },
        )

        with pytest.raises(ModelFileNotReadyError, match="Model file not ready"):
            await mapper.process_sync_record(record)

        # Consumer rolls back on retryable errors; emulate that to verify
        # aggregate creation is atomic and idempotent.
        await session.rollback()

        gear_count = (await session.execute(select(Gear))).scalars().all()
        model_count = (await session.execute(select(GearModel))).scalars().all()
        assert len(gear_count) == 0
        assert len(model_count) == 0

    async def test_process_sync_record_rolls_back_bundle_when_one_file_missing(
        self, mapper: GearMapperService, session: AsyncSession, tmp_path, monkeypatch
    ) -> None:
        """A mixed bundle retries as a unit; no partial models should persist."""

        monkeypatch.setenv("GTS_STORAGE_ROOT", str(tmp_path))
        source_model_dir = tmp_path / "source_downloads" / "t3k" / "model-001"
        source_model_dir.mkdir(parents=True, exist_ok=True)
        (source_model_dir / "model-001.nam").write_bytes(b"dummy-nam")

        record = GearSyncRecord(
            source_name="t3k",
            source_record_id="pack-001",
            source_updated_at=datetime(2026, 2, 15, tzinfo=UTC),
            operation=SyncOperation.CREATE,
            payload={
                "name": "Mixed Bundle Pack",
                "slug": "mixed-bundle-pack",
                "gear_type": "amp",
                "platform": "nam",
                "models": [
                    {
                        "source_record_id": "model-001",
                        "filename": "model-001.nam",
                        "download_url": "https://example.com/model-001.nam",
                        "checksum": "abc123",
                        "platform": "nam",
                        "size": "standard",
                    },
                    {
                        "source_record_id": "model-404",
                        "filename": "missing.nam",
                        "download_url": "https://example.com/missing.nam",
                        "checksum": "def456",
                        "platform": "nam",
                        "size": "standard",
                    },
                ],
            },
        )

        with pytest.raises(ModelFileNotReadyError, match="Model file not ready"):
            await mapper.process_sync_record(record)

        await session.rollback()

        gear_count = (await session.execute(select(Gear))).scalars().all()
        model_count = (await session.execute(select(GearModel))).scalars().all()
        assert len(gear_count) == 0
        assert len(model_count) == 0
