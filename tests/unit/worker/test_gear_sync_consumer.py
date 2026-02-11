"""Unit tests for gear sync consumer and GearMapperService.

Tests the pgmq consumer polling loop that reads from gear_pack_sync and
gear_model_sync queues in gts_t3k_source, validates messages against
GearSyncRecord schema, and upserts to gts_core via GearMapperService.
"""

import contextlib
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from core.domain.value_objects.download_status import DownloadStatus
from core.domain.value_objects.signal_chain_enums import GearType, ModelSize, Platform
from core.records.gear_sync import GearSyncRecord, SyncOperation
from webapp.adapters.persistence.models.gear import Gear
from webapp.adapters.persistence.models.gear_model import GearModel
from webapp.adapters.persistence.models.gear_source import GearSource
from worker.consumers.gear_sync import GearSyncConsumer
from worker.services.gear_mapper import GearMapperService


class TestGearSyncConsumerInit:
    """Tests for GearSyncConsumer construction and configuration."""

    def test_consumer_class_exists(self) -> None:
        """GearSyncConsumer class exists in worker.consumers.gear_sync module."""
        assert GearSyncConsumer is not None

    def test_consumer_initializes_with_required_params(self) -> None:
        """GearSyncConsumer initializes with database sessions and queue names."""
        core_session = Mock(spec=AsyncSession)
        t3k_session = Mock(spec=AsyncSession)

        consumer = GearSyncConsumer(
            core_session=core_session,
            t3k_session=t3k_session,
            pack_queue_name="gear_pack_sync",
            model_queue_name="gear_model_sync",
            dead_letter_queue="sync_dead_letter",
        )

        assert consumer.core_session == core_session
        assert consumer.t3k_session == t3k_session
        assert consumer.pack_queue_name == "gear_pack_sync"
        assert consumer.model_queue_name == "gear_model_sync"
        assert consumer.dead_letter_queue == "sync_dead_letter"

    def test_consumer_has_mapper_service(self) -> None:
        """GearSyncConsumer has a GearMapperService instance."""
        core_session = Mock(spec=AsyncSession)
        t3k_session = Mock(spec=AsyncSession)

        consumer = GearSyncConsumer(
            core_session=core_session,
            t3k_session=t3k_session,
            pack_queue_name="gear_pack_sync",
            model_queue_name="gear_model_sync",
            dead_letter_queue="sync_dead_letter",
        )

        assert hasattr(consumer, "mapper")
        assert isinstance(consumer.mapper, GearMapperService)


class TestGearSyncConsumerPolling:
    """Tests for pgmq polling loop mechanics."""

    @pytest.mark.asyncio
    async def test_polls_pack_queue_with_correct_params(self) -> None:
        """Consumer polls gear_pack_sync queue with vt=60, qty=10."""
        core_session = AsyncMock(spec=AsyncSession)
        t3k_session = AsyncMock(spec=AsyncSession)

        # Mock pgmq.read_with_poll to return empty result
        t3k_session.execute = AsyncMock(return_value=AsyncMock(fetchall=Mock(return_value=[])))

        consumer = GearSyncConsumer(
            core_session=core_session,
            t3k_session=t3k_session,
            pack_queue_name="gear_pack_sync",
            model_queue_name="gear_model_sync",
            dead_letter_queue="sync_dead_letter",
        )

        await consumer.poll_pack_queue()

        # Verify SQL call with correct parameters
        t3k_session.execute.assert_called_once()
        call_args = t3k_session.execute.call_args
        sql_text = str(call_args[0][0])

        assert "pgmq.read_with_poll" in sql_text
        assert "gear_pack_sync" in str(call_args[1])
        assert call_args[1]["vt"] == 60
        assert call_args[1]["qty"] == 10

    @pytest.mark.asyncio
    async def test_polls_model_queue_with_correct_params(self) -> None:
        """Consumer polls gear_model_sync queue with vt=60, qty=10."""
        core_session = AsyncMock(spec=AsyncSession)
        t3k_session = AsyncMock(spec=AsyncSession)

        # Mock pgmq.read_with_poll to return empty result
        t3k_session.execute = AsyncMock(return_value=AsyncMock(fetchall=Mock(return_value=[])))

        consumer = GearSyncConsumer(
            core_session=core_session,
            t3k_session=t3k_session,
            pack_queue_name="gear_pack_sync",
            model_queue_name="gear_model_sync",
            dead_letter_queue="sync_dead_letter",
        )

        await consumer.poll_model_queue()

        # Verify SQL call with correct parameters
        t3k_session.execute.assert_called_once()
        call_args = t3k_session.execute.call_args
        sql_text = str(call_args[0][0])

        assert "pgmq.read_with_poll" in sql_text
        assert "gear_model_sync" in str(call_args[1])
        assert call_args[1]["vt"] == 60
        assert call_args[1]["qty"] == 10

    @pytest.mark.asyncio
    async def test_deserializes_messages_via_gear_sync_record(self) -> None:
        """Consumer deserializes message payload via GearSyncRecord.from_dict()."""
        core_session = AsyncMock(spec=AsyncSession)
        t3k_session = AsyncMock(spec=AsyncSession)

        # Mock pgmq message row
        message_data = {
            "source_name": "t3k",
            "source_record_id": "pack-123",
            "source_updated_at": "2024-01-15T10:00:00Z",
            "operation": "create",
            "payload": {"name": "Mesa Boogie", "gear_type": "amp", "platform": "nam"},
        }
        mock_row = Mock(msg_id=1, message=message_data, read_ct=1)
        t3k_session.execute = AsyncMock(
            return_value=AsyncMock(fetchall=Mock(return_value=[mock_row]))
        )

        consumer = GearSyncConsumer(
            core_session=core_session,
            t3k_session=t3k_session,
            pack_queue_name="gear_pack_sync",
            model_queue_name="gear_model_sync",
            dead_letter_queue="sync_dead_letter",
        )

        with patch.object(consumer.mapper, "process_pack_sync") as mock_process:
            mock_process.return_value = None
            await consumer.poll_pack_queue()

            # Verify GearSyncRecord was passed to mapper
            mock_process.assert_called_once()
            record = mock_process.call_args[0][0]
            assert isinstance(record, GearSyncRecord)
            assert record.source_name == "t3k"
            assert record.source_record_id == "pack-123"
            assert record.operation == SyncOperation.CREATE


class TestGearSyncConsumerDeadLetter:
    """Tests for dead letter handling of invalid messages."""

    @pytest.mark.asyncio
    async def test_invalid_message_moved_to_dead_letter_queue(self) -> None:
        """Messages with schema validation failure are moved to sync_dead_letter queue."""
        core_session = AsyncMock(spec=AsyncSession)
        t3k_session = AsyncMock(spec=AsyncSession)

        # Mock invalid message (missing required field)
        invalid_message_data = {
            "source_name": "t3k",
            # Missing source_record_id
            "source_updated_at": "2024-01-15T10:00:00Z",
            "operation": "create",
            "payload": {},
        }
        mock_row = Mock(msg_id=1, message=invalid_message_data, read_ct=1)

        # First call returns invalid message, second call for dead letter send
        t3k_session.execute = AsyncMock(
            side_effect=[
                AsyncMock(fetchall=Mock(return_value=[mock_row])),
                AsyncMock(),  # Dead letter send
                AsyncMock(),  # Archive original message
            ]
        )

        consumer = GearSyncConsumer(
            core_session=core_session,
            t3k_session=t3k_session,
            pack_queue_name="gear_pack_sync",
            model_queue_name="gear_model_sync",
            dead_letter_queue="sync_dead_letter",
        )

        await consumer.poll_pack_queue()

        # Verify dead letter queue was called
        assert t3k_session.execute.call_count >= 2
        calls = [str(call[0][0]) for call in t3k_session.execute.call_args_list]
        assert any("sync_dead_letter" in call for call in calls)

    @pytest.mark.asyncio
    async def test_messages_with_high_read_count_moved_to_dead_letter(self) -> None:
        """Messages with read_ct > 5 are moved to sync_dead_letter queue."""
        core_session = AsyncMock(spec=AsyncSession)
        t3k_session = AsyncMock(spec=AsyncSession)

        # Mock message with high read count
        message_data = {
            "source_name": "t3k",
            "source_record_id": "pack-123",
            "source_updated_at": "2024-01-15T10:00:00Z",
            "operation": "create",
            "payload": {"name": "Mesa Boogie", "gear_type": "amp", "platform": "nam"},
        }
        mock_row = Mock(msg_id=1, message=message_data, read_ct=6)  # read_ct > 5

        t3k_session.execute = AsyncMock(
            side_effect=[
                AsyncMock(fetchall=Mock(return_value=[mock_row])),
                AsyncMock(),  # Dead letter send
                AsyncMock(),  # Archive original message
            ]
        )

        consumer = GearSyncConsumer(
            core_session=core_session,
            t3k_session=t3k_session,
            pack_queue_name="gear_pack_sync",
            model_queue_name="gear_model_sync",
            dead_letter_queue="sync_dead_letter",
        )

        await consumer.poll_pack_queue()

        # Verify dead letter queue was called
        assert t3k_session.execute.call_count >= 2
        calls = [str(call[0][0]) for call in t3k_session.execute.call_args_list]
        assert any("sync_dead_letter" in call for call in calls)


class TestGearSyncConsumerArchive:
    """Tests for pgmq.archive() on successful processing."""

    @pytest.mark.asyncio
    async def test_archives_message_after_successful_processing(self) -> None:
        """Consumer calls pgmq.archive(queue_name, msg_id) after successful processing."""
        core_session = AsyncMock(spec=AsyncSession)
        t3k_session = AsyncMock(spec=AsyncSession)

        # Mock valid message
        message_data = {
            "source_name": "t3k",
            "source_record_id": "pack-123",
            "source_updated_at": "2024-01-15T10:00:00Z",
            "operation": "create",
            "payload": {"name": "Mesa Boogie", "gear_type": "amp", "platform": "nam"},
        }
        mock_row = Mock(msg_id=42, message=message_data, read_ct=1)

        t3k_session.execute = AsyncMock(
            side_effect=[
                AsyncMock(fetchall=Mock(return_value=[mock_row])),
                AsyncMock(),  # Archive call
            ]
        )

        consumer = GearSyncConsumer(
            core_session=core_session,
            t3k_session=t3k_session,
            pack_queue_name="gear_pack_sync",
            model_queue_name="gear_model_sync",
            dead_letter_queue="sync_dead_letter",
        )

        with patch.object(consumer.mapper, "process_pack_sync") as mock_process:
            mock_process.return_value = None
            await consumer.poll_pack_queue()

            # Verify archive was called with correct msg_id
            assert t3k_session.execute.call_count == 2
            archive_call = str(t3k_session.execute.call_args_list[1][0][0])
            assert "pgmq.archive" in archive_call
            assert t3k_session.execute.call_args_list[1][1]["msg_id"] == 42


class TestGearMapperServiceCreate:
    """Tests for GearMapperService creating new gear from sync records."""

    @pytest.mark.asyncio
    async def test_mapper_service_class_exists(self) -> None:
        """GearMapperService class exists in worker.services.gear_mapper module."""
        assert GearMapperService is not None

    @pytest.mark.asyncio
    async def test_creates_gear_from_pack_sync_record(self) -> None:
        """GearMapperService creates new Gear entity from pack sync record."""
        core_session = AsyncMock(spec=AsyncSession)

        # Mock no existing gear
        core_session.execute = AsyncMock(
            return_value=AsyncMock(scalar_one_or_none=Mock(return_value=None))
        )

        mapper = GearMapperService(session=core_session)

        record = GearSyncRecord(
            source_name="t3k",
            source_record_id="pack-123",
            source_updated_at=datetime(2024, 1, 15, tzinfo=UTC),
            operation=SyncOperation.CREATE,
            payload={
                "name": "Mesa Boogie Dual Rectifier",
                "slug": "mesa-boogie-dual-rectifier",
                "gear_type": "amp",
                "platform": "nam",
                "description": "High gain amp",
                "thumbnail_url": "https://example.com/thumb.jpg",
            },
        )

        await mapper.process_pack_sync(record)

        # Verify Gear entity was added to session
        core_session.add.assert_called()
        gear = core_session.add.call_args_list[0][0][0]
        assert isinstance(gear, Gear)
        assert gear.name == "Mesa Boogie Dual Rectifier"
        assert gear.slug == "mesa-boogie-dual-rectifier"
        assert gear.gear_type == GearType.AMP
        assert gear.platform == "nam"

    @pytest.mark.asyncio
    async def test_creates_gear_source_record(self) -> None:
        """GearMapperService creates GearSource record with source tracking data."""
        core_session = AsyncMock(spec=AsyncSession)

        # Mock no existing gear
        core_session.execute = AsyncMock(
            return_value=AsyncMock(scalar_one_or_none=Mock(return_value=None))
        )

        mapper = GearMapperService(session=core_session)

        record = GearSyncRecord(
            source_name="t3k",
            source_record_id="pack-123",
            source_updated_at=datetime(2024, 1, 15, 10, 30, tzinfo=UTC),
            operation=SyncOperation.CREATE,
            payload={
                "name": "Mesa Boogie",
                "slug": "mesa-boogie",
                "gear_type": "amp",
                "platform": "nam",
            },
        )

        await mapper.process_pack_sync(record)

        # Verify GearSource was added
        assert core_session.add.call_count == 2  # Gear + GearSource
        gear_source = next(
            call[0][0]
            for call in core_session.add.call_args_list
            if isinstance(call[0][0], GearSource)
        )
        assert gear_source.source_name == "t3k"
        assert gear_source.source_record_id == "pack-123"
        assert gear_source.source_updated_at == datetime(2024, 1, 15, 10, 30, tzinfo=UTC)

    @pytest.mark.asyncio
    async def test_looks_up_existing_gear_by_source(self) -> None:
        """GearMapperService looks up existing gear using (source_name, source_record_id)."""
        core_session = AsyncMock(spec=AsyncSession)

        # Mock existing gear source
        existing_gear = Gear(
            id=uuid4(),
            name="Old Name",
            slug="old-name",
            gear_type=GearType.AMP,
        )
        existing_source = GearSource(
            id=uuid4(),
            source_name="t3k",
            source_record_id="pack-123",
            source_updated_at=datetime(2024, 1, 1, tzinfo=UTC),
        )
        existing_gear.source = existing_source

        core_session.execute = AsyncMock(
            return_value=AsyncMock(scalar_one_or_none=Mock(return_value=existing_gear))
        )

        mapper = GearMapperService(session=core_session)

        record = GearSyncRecord(
            source_name="t3k",
            source_record_id="pack-123",
            source_updated_at=datetime(2024, 1, 20, tzinfo=UTC),
            operation=SyncOperation.UPDATE,
            payload={"name": "New Name", "slug": "new-name", "gear_type": "amp"},
        )

        await mapper.process_pack_sync(record)

        # Verify query used source lookup
        call_args = core_session.execute.call_args
        query_text = str(call_args[0][0])
        assert "gear_sources" in query_text.lower()
        assert "source_name" in query_text.lower() or "t3k" in str(call_args)


class TestGearMapperServiceUpdate:
    """Tests for GearMapperService updating existing gear."""

    @pytest.mark.asyncio
    async def test_updates_existing_gear_fields(self) -> None:
        """GearMapperService updates existing gear when source_updated_at is newer."""
        core_session = AsyncMock(spec=AsyncSession)

        # Mock existing gear with old data
        existing_gear = Gear(
            id=uuid4(),
            name="Old Name",
            slug="old-name",
            gear_type=GearType.AMP,
            description="Old description",
        )
        existing_source = GearSource(
            id=uuid4(),
            source_name="t3k",
            source_record_id="pack-123",
            source_updated_at=datetime(2024, 1, 1, tzinfo=UTC),
        )
        existing_gear.source = existing_source

        core_session.execute = AsyncMock(
            return_value=AsyncMock(scalar_one_or_none=Mock(return_value=existing_gear))
        )

        mapper = GearMapperService(session=core_session)

        record = GearSyncRecord(
            source_name="t3k",
            source_record_id="pack-123",
            source_updated_at=datetime(2024, 1, 20, tzinfo=UTC),  # Newer
            operation=SyncOperation.UPDATE,
            payload={
                "name": "New Name",
                "slug": "new-name",
                "gear_type": "amp",
                "description": "New description",
            },
        )

        await mapper.process_pack_sync(record)

        # Verify gear fields were updated
        assert existing_gear.name == "New Name"
        assert existing_gear.description == "New description"
        assert existing_source.source_updated_at == datetime(2024, 1, 20, tzinfo=UTC)

    @pytest.mark.asyncio
    async def test_skips_update_when_source_updated_at_is_older(self) -> None:
        """GearMapperService skips update when source_updated_at <= existing (last-write-wins)."""
        core_session = AsyncMock(spec=AsyncSession)

        # Mock existing gear with newer data
        existing_gear = Gear(
            id=uuid4(),
            name="Current Name",
            slug="current-name",
            gear_type=GearType.AMP,
        )
        existing_source = GearSource(
            id=uuid4(),
            source_name="t3k",
            source_record_id="pack-123",
            source_updated_at=datetime(2024, 1, 20, tzinfo=UTC),
        )
        existing_gear.source = existing_source

        core_session.execute = AsyncMock(
            return_value=AsyncMock(scalar_one_or_none=Mock(return_value=existing_gear))
        )

        mapper = GearMapperService(session=core_session)

        record = GearSyncRecord(
            source_name="t3k",
            source_record_id="pack-123",
            source_updated_at=datetime(2024, 1, 15, tzinfo=UTC),  # Older
            operation=SyncOperation.UPDATE,
            payload={"name": "Old Name", "slug": "old-name", "gear_type": "amp"},
        )

        await mapper.process_pack_sync(record)

        # Verify gear was NOT updated
        assert existing_gear.name == "Current Name"
        assert existing_source.source_updated_at == datetime(2024, 1, 20, tzinfo=UTC)

    @pytest.mark.asyncio
    async def test_skips_update_when_source_updated_at_is_equal(self) -> None:
        """GearMapperService skips update when source_updated_at == existing."""
        core_session = AsyncMock(spec=AsyncSession)

        existing_gear = Gear(
            id=uuid4(),
            name="Current Name",
            slug="current-name",
            gear_type=GearType.AMP,
        )
        existing_source = GearSource(
            id=uuid4(),
            source_name="t3k",
            source_record_id="pack-123",
            source_updated_at=datetime(2024, 1, 15, tzinfo=UTC),
        )
        existing_gear.source = existing_source

        core_session.execute = AsyncMock(
            return_value=AsyncMock(scalar_one_or_none=Mock(return_value=existing_gear))
        )

        mapper = GearMapperService(session=core_session)

        record = GearSyncRecord(
            source_name="t3k",
            source_record_id="pack-123",
            source_updated_at=datetime(2024, 1, 15, tzinfo=UTC),  # Same
            operation=SyncOperation.UPDATE,
            payload={"name": "Updated Name", "slug": "updated-name", "gear_type": "amp"},
        )

        await mapper.process_pack_sync(record)

        # Verify gear was NOT updated
        assert existing_gear.name == "Current Name"


class TestGearMapperServiceModel:
    """Tests for GearMapperService creating/updating GearModel records."""

    @pytest.mark.asyncio
    async def test_creates_gear_model_from_model_sync_record(self) -> None:
        """GearMapperService creates GearModel entity from model sync record."""
        core_session = AsyncMock(spec=AsyncSession)

        # Mock existing gear (found by pack_id lookup)
        existing_gear = Gear(
            id=uuid4(),
            name="Mesa Boogie",
            slug="mesa-boogie",
            gear_type=GearType.AMP,
        )

        # Mock no existing model
        core_session.execute = AsyncMock(
            side_effect=[
                AsyncMock(scalar_one_or_none=Mock(return_value=existing_gear)),  # Gear lookup
                AsyncMock(scalar_one_or_none=Mock(return_value=None)),  # Model lookup
            ]
        )

        mapper = GearMapperService(session=core_session)

        record = GearSyncRecord(
            source_name="t3k",
            source_record_id="model-789",
            source_updated_at=datetime(2024, 1, 20, tzinfo=UTC),
            operation=SyncOperation.CREATE,
            payload={
                "pack_id": "pack-123",
                "name": "Channel 1 Vintage",
                "filename": "channel1_vintage.nam",
                "download_url": "https://example.com/model.nam",
                "checksum": "abc123",
                "platform": "nam",
                "size": "standard",
            },
        )

        await mapper.process_model_sync(record)

        # Verify GearModel entity was added
        core_session.add.assert_called_once()
        model = core_session.add.call_args[0][0]
        assert isinstance(model, GearModel)
        assert model.gear_id == existing_gear.id
        assert model.platform == Platform.NAM
        assert model.size == ModelSize.STANDARD
        assert model.download_url == "https://example.com/model.nam"
        assert model.file_hash == "abc123"

    @pytest.mark.asyncio
    async def test_updates_existing_gear_model(self) -> None:
        """GearMapperService updates existing GearModel when source is newer."""
        core_session = AsyncMock(spec=AsyncSession)

        gear_id = uuid4()
        existing_gear = Gear(
            id=gear_id,
            name="Mesa Boogie",
            slug="mesa-boogie",
            gear_type=GearType.AMP,
        )

        existing_model = GearModel(
            id=uuid4(),
            gear_id=gear_id,
            platform=Platform.NAM,
            size=ModelSize.STANDARD,
            download_url="https://old-url.com/model.nam",
            download_status=DownloadStatus.PENDING,
        )

        core_session.execute = AsyncMock(
            side_effect=[
                AsyncMock(scalar_one_or_none=Mock(return_value=existing_gear)),
                AsyncMock(scalar_one_or_none=Mock(return_value=existing_model)),
            ]
        )

        mapper = GearMapperService(session=core_session)

        record = GearSyncRecord(
            source_name="t3k",
            source_record_id="model-789",
            source_updated_at=datetime(2024, 1, 20, tzinfo=UTC),
            operation=SyncOperation.UPDATE,
            payload={
                "pack_id": "pack-123",
                "download_url": "https://new-url.com/model.nam",
                "checksum": "newchecksum",
                "platform": "nam",
                "size": "standard",
            },
        )

        await mapper.process_model_sync(record)

        # Verify model was updated
        assert existing_model.download_url == "https://new-url.com/model.nam"
        assert existing_model.file_hash == "newchecksum"


class TestGearMapperServiceFileMigration:
    """Tests for model file migration from source_downloads to models/."""

    @pytest.mark.asyncio
    async def test_moves_model_file_on_successful_upsert(self) -> None:
        """GearMapperService moves file from source_downloads/{source}/{source_record_id}/ to models/{gear_model_uuid}.nam."""
        core_session = AsyncMock(spec=AsyncSession)

        gear_id = uuid4()
        existing_gear = Gear(
            id=gear_id,
            name="Mesa Boogie",
            slug="mesa-boogie",
            gear_type=GearType.AMP,
        )

        core_session.execute = AsyncMock(
            side_effect=[
                AsyncMock(scalar_one_or_none=Mock(return_value=existing_gear)),
                AsyncMock(scalar_one_or_none=Mock(return_value=None)),
            ]
        )

        mapper = GearMapperService(session=core_session)

        record = GearSyncRecord(
            source_name="t3k",
            source_record_id="model-789",
            source_updated_at=datetime(2024, 1, 20, tzinfo=UTC),
            operation=SyncOperation.CREATE,
            payload={
                "pack_id": "pack-123",
                "filename": "channel1.nam",
                "download_url": "https://example.com/model.nam",
                "platform": "nam",
                "size": "standard",
            },
        )

        with patch("worker.services.gear_mapper.Path") as mock_path:
            mock_source_file = MagicMock(spec=Path)
            mock_source_file.exists.return_value = True
            mock_dest_file = MagicMock(spec=Path)
            mock_path.return_value = mock_source_file
            mock_path.side_effect = [mock_source_file, mock_dest_file]

            await mapper.process_model_sync(record)

            # Verify file move was attempted
            mock_source_file.rename.assert_called_once()

    @pytest.mark.asyncio
    async def test_sets_file_path_on_gear_model_after_migration(self) -> None:
        """GearMapperService updates GearModel.file_path after successful file migration."""
        core_session = AsyncMock(spec=AsyncSession)

        gear_id = uuid4()

        existing_gear = Gear(
            id=gear_id,
            name="Mesa Boogie",
            slug="mesa-boogie",
            gear_type=GearType.AMP,
        )

        core_session.execute = AsyncMock(
            side_effect=[
                AsyncMock(scalar_one_or_none=Mock(return_value=existing_gear)),
                AsyncMock(scalar_one_or_none=Mock(return_value=None)),
            ]
        )

        mapper = GearMapperService(session=core_session)

        record = GearSyncRecord(
            source_name="t3k",
            source_record_id="model-789",
            source_updated_at=datetime(2024, 1, 20, tzinfo=UTC),
            operation=SyncOperation.CREATE,
            payload={
                "pack_id": "pack-123",
                "filename": "channel1.nam",
                "download_url": "https://example.com/model.nam",
                "platform": "nam",
                "size": "standard",
            },
        )

        with patch("worker.services.gear_mapper.Path") as mock_path:
            mock_source_file = MagicMock(spec=Path)
            mock_source_file.exists.return_value = True
            mock_path.return_value = mock_source_file

            await mapper.process_model_sync(record)

            # Verify GearModel was added with file_path
            core_session.add.assert_called_once()
            model = core_session.add.call_args[0][0]
            assert isinstance(model, GearModel)
            assert model.file_path is not None
            assert "models/" in model.file_path
            assert model.file_path.endswith(".nam")


class TestGearSyncConsumerErrorHandling:
    """Tests for error handling and resilience."""

    @pytest.mark.asyncio
    async def test_handles_database_connection_errors(self) -> None:
        """Consumer handles database connection errors gracefully."""
        core_session = AsyncMock(spec=AsyncSession)
        t3k_session = AsyncMock(spec=AsyncSession)

        # Mock connection error
        t3k_session.execute = AsyncMock(side_effect=ConnectionError("Database unavailable"))

        consumer = GearSyncConsumer(
            core_session=core_session,
            t3k_session=t3k_session,
            pack_queue_name="gear_pack_sync",
            model_queue_name="gear_model_sync",
            dead_letter_queue="sync_dead_letter",
        )

        # Should not raise, should handle gracefully
        try:
            await consumer.poll_pack_queue()
        except ConnectionError:
            pytest.fail("Consumer should handle database connection errors gracefully")

    @pytest.mark.asyncio
    async def test_consumer_has_run_loop_method(self) -> None:
        """Consumer has a run() method for the main polling loop."""
        core_session = AsyncMock(spec=AsyncSession)
        t3k_session = AsyncMock(spec=AsyncSession)

        consumer = GearSyncConsumer(
            core_session=core_session,
            t3k_session=t3k_session,
            pack_queue_name="gear_pack_sync",
            model_queue_name="gear_model_sync",
            dead_letter_queue="sync_dead_letter",
        )

        assert hasattr(consumer, "run")
        assert callable(consumer.run)

    @pytest.mark.asyncio
    async def test_run_loop_polls_both_queues(self) -> None:
        """Consumer run() loop polls both pack and model queues."""
        core_session = AsyncMock(spec=AsyncSession)
        t3k_session = AsyncMock(spec=AsyncSession)

        # Mock empty results
        t3k_session.execute = AsyncMock(return_value=AsyncMock(fetchall=Mock(return_value=[])))

        consumer = GearSyncConsumer(
            core_session=core_session,
            t3k_session=t3k_session,
            pack_queue_name="gear_pack_sync",
            model_queue_name="gear_model_sync",
            dead_letter_queue="sync_dead_letter",
        )

        # Mock asyncio.sleep to prevent infinite loop
        with (
            patch("asyncio.sleep", side_effect=KeyboardInterrupt),
            contextlib.suppress(KeyboardInterrupt),
        ):
            await consumer.run()

        # Verify both queues were polled
        assert t3k_session.execute.call_count >= 2
