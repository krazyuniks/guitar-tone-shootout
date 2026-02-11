"""GearMapperService for mapping source sync records to core domain entities."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from core.domain.value_objects.download_status import DownloadStatus
from core.domain.value_objects.signal_chain_enums import GearType, ModelSize, Platform
from webapp.adapters.persistence.models.gear import Gear
from webapp.adapters.persistence.models.gear_model import GearModel
from webapp.adapters.persistence.models.gear_source import GearSource

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession

    from core.records.gear_sync import GearSyncRecord


class GearMapperService:
    """Maps GearSyncRecords to Gear/GearModel entities in gts_core."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def process_pack_sync(self, record: GearSyncRecord) -> None:
        """Process a gear pack sync record."""
        existing_gear = await self._lookup_gear_by_source(
            record.source_name,
            record.source_record_id,
        )

        if existing_gear:
            if (
                existing_gear.source
                and record.source_updated_at <= existing_gear.source.source_updated_at
            ):
                return
            await self._update_gear(existing_gear, record)
        else:
            await self._create_gear(record)

    async def process_model_sync(self, record: GearSyncRecord) -> None:
        """Process a gear model sync record."""
        pack_id = record.payload.get("pack_id")
        if not pack_id:
            raise ValueError("Model sync record missing pack_id in payload")

        parent_gear = await self._lookup_gear_by_source(
            record.source_name,
            pack_id,
        )

        if not parent_gear:
            raise ValueError(f"Parent gear not found for pack_id={pack_id}")

        existing_model = await self._lookup_model_by_source(
            parent_gear.id,
            record.source_name,
            record.source_record_id,
        )

        if existing_model:
            await self._update_model(existing_model, record)
        else:
            await self._create_model(parent_gear.id, record)

    async def _lookup_gear_by_source(
        self,
        source_name: str,
        source_record_id: str,
    ) -> Gear | None:
        """Look up gear by source tracking information."""
        stmt = (
            select(Gear)
            .join(GearSource)
            .where(GearSource.source_name == source_name)
            .where(GearSource.source_record_id == source_record_id)
            .options(joinedload(Gear.source))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def _lookup_model_by_source(
        self,
        gear_id: UUID,
        _source_name: str,
        _source_record_id: str,
    ) -> GearModel | None:
        """Look up gear model by gear_id and source tracking."""
        stmt = select(GearModel).where(GearModel.gear_id == gear_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def _create_gear(self, record: GearSyncRecord) -> None:
        """Create new Gear and GearSource from sync record."""
        name = record.payload.get("name", "")
        slug = record.payload.get("slug", "")
        gear_type_str = record.payload.get("gear_type", "")
        platform = record.payload.get("platform")
        description = record.payload.get("description")
        thumbnail_url = record.payload.get("thumbnail_url")

        gear = Gear(
            name=name,
            slug=slug,
            gear_type=GearType(gear_type_str),
            platform=platform,
            description=description,
            thumbnail_url=thumbnail_url,
        )
        self.session.add(gear)

        gear_source = GearSource(
            source_name=record.source_name,
            source_record_id=record.source_record_id,
            source_updated_at=record.source_updated_at,
        )
        gear_source.gear = gear
        self.session.add(gear_source)

    async def _update_gear(self, gear: Gear, record: GearSyncRecord) -> None:
        """Update existing Gear with data from sync record."""
        if "name" in record.payload:
            gear.name = record.payload["name"]
        if "description" in record.payload:
            gear.description = record.payload["description"]
        if "thumbnail_url" in record.payload:
            gear.thumbnail_url = record.payload["thumbnail_url"]

        if gear.source:
            gear.source.source_updated_at = record.source_updated_at

    async def _create_model(self, gear_id: UUID, record: GearSyncRecord) -> None:
        """Create new GearModel from sync record."""
        platform_str = record.payload.get("platform", "nam")
        size_str = record.payload.get("size", "standard")
        download_url = record.payload.get("download_url")
        checksum = record.payload.get("checksum")
        filename = record.payload.get("filename")

        model = GearModel(
            gear_id=gear_id,
            platform=Platform(platform_str),
            size=ModelSize(size_str),
            download_url=download_url,
            file_hash=checksum,
            download_status=DownloadStatus.PENDING,
        )

        if filename:
            file_path = await self._migrate_model_file(
                record.source_name,
                record.source_record_id,
                model.id,
                filename,
            )
            if file_path:
                model.file_path = file_path

        self.session.add(model)

    async def _update_model(self, model: GearModel, record: GearSyncRecord) -> None:
        """Update existing GearModel with data from sync record."""
        if "download_url" in record.payload:
            model.download_url = record.payload["download_url"]
        if "checksum" in record.payload:
            model.file_hash = record.payload["checksum"]

    async def _migrate_model_file(
        self,
        source_name: str,
        source_record_id: str,
        model_id: UUID,
        filename: str,
    ) -> str | None:
        """Migrate model file from source_downloads to models directory.

        Returns relative file path if migration succeeded, None otherwise.
        """
        source_path = Path(
            f"/app/data/source_downloads/{source_name}/{source_record_id}/{filename}"
        )
        dest_path = Path(f"/app/data/models/{model_id}.nam")

        dest_path.parent.mkdir(parents=True, exist_ok=True)

        if source_path.exists():
            source_path.rename(dest_path)
            return f"models/{model_id}.nam"
        return None
