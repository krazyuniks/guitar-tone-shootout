"""Unit tests for GearMapperService end-to-end data flow.

Tests verify that sync records produce correct Gear, GearSource, and GearModel
rows in the gts_core database. Uses real PostgreSQL sessions -- no mocking.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import joinedload

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

from core.domain.value_objects.download_status import DownloadStatus
from core.records.gear_sync import GearSyncRecord, SyncOperation
from webapp.adapters.persistence.models.gear import Gear
from webapp.adapters.persistence.models.gear_model import GearModel
from webapp.adapters.persistence.models.gear_source import GearSource
from worker.services.gear_mapper import (
    GearMapperService,
    ParentGearNotReadyError,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mapper(session: AsyncSession) -> GearMapperService:
    return GearMapperService(session=session)


def _unique_id() -> str:
    """Generate a short unique suffix for test data."""
    return uuid4().hex[:8]


def _pack_record(
    source_record_id: str | None = None,
    name: str = "Test Amp",
    slug: str | None = None,
    gear_type: str = "amp",
    **extra_payload: object,
) -> GearSyncRecord:
    """Build a pack sync record with sensible defaults and unique slug."""
    suffix = _unique_id()
    if source_record_id is None:
        source_record_id = f"pack-{suffix}"
    if slug is None:
        slug = f"test-amp-{suffix}"
    payload = {
        "name": name,
        "slug": slug,
        "gear_type": gear_type,
        "platform": "nam",
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
    source_record_id: str | None = None,
    platform: str = "nam",
    size: str = "standard",
    **extra_payload: object,
) -> GearSyncRecord:
    """Build a model sync record with sensible defaults."""
    if source_record_id is None:
        source_record_id = f"model-{_unique_id()}"
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
# Pack sync -> Gear + GearSource creation
# ---------------------------------------------------------------------------


class TestPackSyncCreatesGear:
    """process_pack_sync must create Gear and GearSource rows."""

    async def test_creates_gear_row(self, mapper: GearMapperService, session: AsyncSession) -> None:
        """A pack sync record should create a Gear row in gts_core."""
        suffix = _unique_id()
        record = _pack_record(
            source_record_id=f"pack-{suffix}",
            name="Marshall JCM800",
            slug=f"marshall-jcm800-{suffix}",
            gear_type="amp",
        )
        await mapper.process_pack_sync(record)
        await session.flush()

        result = await session.execute(select(Gear).where(Gear.slug == f"marshall-jcm800-{suffix}"))
        gear = result.scalar_one()
        assert gear.name == "Marshall JCM800"
        assert gear.gear_type.value == "amp"

    async def test_creates_gear_source_row(
        self, mapper: GearMapperService, session: AsyncSession
    ) -> None:
        """A pack sync should create a GearSource linking gear to its source."""
        record = _pack_record()
        await mapper.process_pack_sync(record)
        await session.flush()

        result = await session.execute(
            select(GearSource).where(GearSource.source_record_id == record.source_record_id)
        )
        source = result.scalar_one()
        assert source.source_name == "t3k"

    async def test_gear_source_linked_to_gear(
        self, mapper: GearMapperService, session: AsyncSession
    ) -> None:
        """GearSource must be linked to the created Gear (via relationship or FK)."""
        record = _pack_record()
        await mapper.process_pack_sync(record)
        await session.flush()

        result = await session.execute(
            select(Gear).options(joinedload(Gear.source)).where(Gear.slug == record.payload["slug"])
        )
        gear = result.unique().scalar_one()
        assert gear.source is not None
        assert gear.source.source_name == "t3k"
        assert gear.source.source_record_id == record.source_record_id


# ---------------------------------------------------------------------------
# Pack sync -> Gear update (idempotency)
# ---------------------------------------------------------------------------


class TestPackSyncUpdatesGear:
    """process_pack_sync must update existing Gear when re-syncing."""

    async def test_updates_existing_gear_name(
        self, mapper: GearMapperService, session: AsyncSession
    ) -> None:
        """Re-syncing a pack with a newer timestamp updates the Gear name."""
        suffix = _unique_id()
        source_id = f"pack-{suffix}"

        # Create initial
        record_v1 = _pack_record(
            source_record_id=source_id,
            name="Old Name",
            slug=f"old-name-{suffix}",
        )
        await mapper.process_pack_sync(record_v1)
        await session.flush()

        # Update with newer timestamp
        record_v2 = GearSyncRecord(
            source_name="t3k",
            source_record_id=source_id,
            source_updated_at=datetime(2026, 2, 1, tzinfo=UTC),
            operation=SyncOperation.UPDATE,
            payload={"name": "New Name"},
        )
        await mapper.process_pack_sync(record_v2)
        await session.flush()

        result = await session.execute(select(Gear).where(Gear.slug == f"old-name-{suffix}"))
        gear = result.scalar_one()
        assert gear.name == "New Name"

    async def test_skips_stale_update(
        self, mapper: GearMapperService, session: AsyncSession
    ) -> None:
        """Re-syncing with older timestamp does NOT update the Gear."""
        suffix = _unique_id()
        source_id = f"pack-{suffix}"

        record_v1 = GearSyncRecord(
            source_name="t3k",
            source_record_id=source_id,
            source_updated_at=datetime(2026, 2, 1, tzinfo=UTC),
            operation=SyncOperation.CREATE,
            payload={
                "name": "Current Name",
                "slug": f"current-name-{suffix}",
                "gear_type": "amp",
                "platform": "nam",
            },
        )
        await mapper.process_pack_sync(record_v1)
        await session.flush()

        # Stale update with OLDER timestamp
        record_stale = GearSyncRecord(
            source_name="t3k",
            source_record_id=source_id,
            source_updated_at=datetime(2026, 1, 1, tzinfo=UTC),
            operation=SyncOperation.UPDATE,
            payload={"name": "Stale Name"},
        )
        await mapper.process_pack_sync(record_stale)
        await session.flush()

        result = await session.execute(select(Gear).where(Gear.slug == f"current-name-{suffix}"))
        gear = result.scalar_one()
        assert gear.name == "Current Name", "Stale update should NOT overwrite current name"


# ---------------------------------------------------------------------------
# Model sync -> GearModel creation
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
        model_record = _model_record(
            pack_id=pack_record.source_record_id,
            platform="nam",
            size="standard",
        )
        await mapper.process_model_sync(model_record)
        await session.flush()

        result = await session.execute(
            select(GearModel).where(
                GearModel.gear_id
                == (
                    select(Gear.id).where(Gear.slug == pack_record.payload["slug"])
                ).scalar_subquery()
            )
        )
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

        model_record = _model_record(pack_id=pack_record.source_record_id)
        await mapper.process_model_sync(model_record)
        await session.flush()

        # Load gear with models
        result = await session.execute(
            select(Gear)
            .options(joinedload(Gear.models))
            .where(Gear.slug == pack_record.payload["slug"])
        )
        gear = result.unique().scalar_one()
        assert len(gear.models) == 1
        assert gear.models[0].platform.value == "nam"

    async def test_model_sync_without_parent_raises(
        self, mapper: GearMapperService, session: AsyncSession
    ) -> None:
        """Model sync for non-existent parent gear must raise retryable error."""
        model_record = _model_record(pack_id=f"nonexistent-pack-{_unique_id()}")

        with pytest.raises(ParentGearNotReadyError, match="Parent gear not found"):
            await mapper.process_model_sync(model_record)

    async def test_model_sync_without_pack_id_raises(
        self, mapper: GearMapperService, session: AsyncSession
    ) -> None:
        """Model sync missing pack_id in payload must raise ValueError."""
        record = GearSyncRecord(
            source_name="t3k",
            source_record_id=f"model-bad-{_unique_id()}",
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

        model_record = _model_record(pack_id=pack_record.source_record_id)
        await mapper.process_model_sync(model_record)
        await session.flush()

        result = await session.execute(
            select(GearModel).where(
                GearModel.gear_id
                == (
                    select(Gear.id).where(Gear.slug == pack_record.payload["slug"])
                ).scalar_subquery()
            )
        )
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
        suffix = _unique_id()
        source_id = f"pack-{suffix}"

        # Create pack
        pack_record = _pack_record(
            source_record_id=source_id,
            name="Mesa Boogie Dual Rectifier",
            slug=f"mesa-boogie-dual-rectifier-{suffix}",
            gear_type="amp",
            platform="nam",
            description="High-gain amp capture",
        )
        await mapper.process_pack_sync(pack_record)
        await session.flush()

        # Create two models
        model1 = _model_record(
            pack_id=source_id,
            platform="nam",
            size="standard",
            download_url="https://example.com/model1.nam",
        )
        model2 = _model_record(
            pack_id=source_id,
            platform="nam",
            size="standard",
            checksum="abc123def456",
        )
        await mapper.process_model_sync(model1)
        await mapper.process_model_sync(model2)
        await session.flush()

        # Verify the complete aggregate
        result = await session.execute(
            select(Gear)
            .options(
                joinedload(Gear.source),
                joinedload(Gear.models),
            )
            .where(Gear.slug == f"mesa-boogie-dual-rectifier-{suffix}")
        )
        gear = result.unique().scalar_one()

        # Gear row exists
        assert gear.name == "Mesa Boogie Dual Rectifier"
        assert gear.gear_type.value == "amp"

        # GearSource row links back to T3K
        assert gear.source is not None
        assert gear.source.source_name == "t3k"
        assert gear.source.source_record_id == source_id

        # Two GearModel rows linked to parent Gear
        assert len(gear.models) == 2


class TestAggregateSyncRecord:
    """Tests for aggregate pack+models sync record processing."""

    async def test_process_sync_record_creates_gear_and_models_atomically(
        self, mapper: GearMapperService, session: AsyncSession, tmp_path, monkeypatch
    ) -> None:
        """Aggregate sync payload should create parent Gear and child GearModel rows."""
        suffix = _unique_id()
        monkeypatch.setenv("GTS_STORAGE_ROOT", str(tmp_path))
        source_model_dir = tmp_path / "source_downloads" / "t3k" / f"model-{suffix}"
        source_model_dir.mkdir(parents=True, exist_ok=True)
        (source_model_dir / f"model-{suffix}.nam").write_bytes(b"dummy-nam")

        record = GearSyncRecord(
            source_name="t3k",
            source_record_id=f"pack-{suffix}",
            source_updated_at=datetime(2026, 2, 15, tzinfo=UTC),
            operation=SyncOperation.CREATE,
            payload={
                "name": "Aggregate Pack",
                "slug": f"aggregate-pack-{suffix}",
                "gear_type": "amp",
                "platform": "nam",
                "models": [
                    {
                        "source_record_id": f"model-{suffix}",
                        "filename": f"model-{suffix}.nam",
                        "download_url": f"https://example.com/model-{suffix}.nam",
                        "checksum": "abc123",
                        "platform": "nam",
                        "size": "standard",
                    }
                ],
            },
        )

        await mapper.process_sync_record(record)
        await session.flush()

        result = await session.execute(
            select(Gear)
            .options(joinedload(Gear.models))
            .where(Gear.slug == f"aggregate-pack-{suffix}")
        )
        gear = result.unique().scalar_one()
        assert gear.name == "Aggregate Pack"
        assert len(gear.models) == 1
        assert gear.models[0].file_path is not None

    async def test_migrated_model_has_completed_download_status(
        self, mapper: GearMapperService, session: AsyncSession, tmp_path, monkeypatch
    ) -> None:
        """Model with successfully migrated file should have COMPLETED download status."""
        from core.domain.value_objects.download_status import DownloadStatus

        suffix = _unique_id()
        monkeypatch.setenv("GTS_STORAGE_ROOT", str(tmp_path))
        source_model_dir = tmp_path / "source_downloads" / "t3k" / f"model-{suffix}"
        source_model_dir.mkdir(parents=True, exist_ok=True)
        (source_model_dir / f"model-{suffix}.nam").write_bytes(b"dummy-nam")

        record = GearSyncRecord(
            source_name="t3k",
            source_record_id=f"pack-{suffix}",
            source_updated_at=datetime(2026, 2, 15, tzinfo=UTC),
            operation=SyncOperation.CREATE,
            payload={
                "name": "Status Check Pack",
                "slug": f"status-check-pack-{suffix}",
                "gear_type": "amp",
                "platform": "nam",
                "models": [
                    {
                        "source_record_id": f"model-{suffix}",
                        "filename": f"model-{suffix}.nam",
                        "download_url": f"https://example.com/model-{suffix}.nam",
                        "checksum": "abc123",
                        "platform": "nam",
                        "size": "standard",
                    }
                ],
            },
        )

        await mapper.process_sync_record(record)
        await session.flush()

        result = await session.execute(
            select(GearModel).where(
                GearModel.gear_id
                == (
                    select(Gear.id).where(Gear.slug == f"status-check-pack-{suffix}")
                ).scalar_subquery()
            )
        )
        model = result.scalar_one()
        assert model.download_status == DownloadStatus.COMPLETED
        assert model.file_path is not None

    async def test_process_sync_record_creates_pending_model_when_file_missing(
        self,
        mapper: GearMapperService,
        session: AsyncSession,
        tmp_path,
        monkeypatch,
    ) -> None:
        """Missing model files create models with PENDING status (no error)."""
        suffix = _unique_id()
        monkeypatch.setenv("GTS_STORAGE_ROOT", str(tmp_path))

        record = GearSyncRecord(
            source_name="t3k",
            source_record_id=f"pack-{suffix}",
            source_updated_at=datetime(2026, 2, 15, tzinfo=UTC),
            operation=SyncOperation.CREATE,
            payload={
                "name": "Aggregate Pack",
                "slug": f"aggregate-pack-missing-{suffix}",
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

        await mapper.process_sync_record(record)

        result = await session.execute(
            select(GearModel).where(
                GearModel.gear_id
                == (
                    select(Gear.id).where(Gear.slug == f"aggregate-pack-missing-{suffix}")
                ).scalar_subquery()
            )
        )
        model = result.scalar_one()
        assert model.download_status == DownloadStatus.PENDING
        assert model.file_path is None

    async def test_process_sync_record_mixed_bundle_one_file_missing(
        self, mapper: GearMapperService, session: AsyncSession, tmp_path, monkeypatch
    ) -> None:
        """Mixed bundle: available file is COMPLETED, missing file stays PENDING."""
        suffix = _unique_id()
        model_ok_id = f"model-ok-{suffix}"

        monkeypatch.setenv("GTS_STORAGE_ROOT", str(tmp_path))
        source_model_dir = tmp_path / "source_downloads" / "t3k" / model_ok_id
        source_model_dir.mkdir(parents=True, exist_ok=True)
        (source_model_dir / f"{model_ok_id}.nam").write_bytes(b"dummy-nam")

        record = GearSyncRecord(
            source_name="t3k",
            source_record_id=f"pack-{suffix}",
            source_updated_at=datetime(2026, 2, 15, tzinfo=UTC),
            operation=SyncOperation.CREATE,
            payload={
                "name": "Mixed Bundle Pack",
                "slug": f"mixed-bundle-pack-{suffix}",
                "gear_type": "amp",
                "platform": "nam",
                "models": [
                    {
                        "source_record_id": model_ok_id,
                        "filename": f"{model_ok_id}.nam",
                        "download_url": f"https://example.com/{model_ok_id}.nam",
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

        await mapper.process_sync_record(record)

        result = await session.execute(
            select(GearModel)
            .where(
                GearModel.gear_id
                == (
                    select(Gear.id).where(Gear.slug == f"mixed-bundle-pack-{suffix}")
                ).scalar_subquery()
            )
            .order_by(GearModel.download_status)
        )
        models = result.scalars().all()
        assert len(models) == 2

        statuses = {m.download_status for m in models}
        assert DownloadStatus.COMPLETED in statuses
        assert DownloadStatus.PENDING in statuses
