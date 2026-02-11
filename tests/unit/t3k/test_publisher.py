"""Unit tests for GearSyncPublisher.

Tests the conversion logic from T3K staging models to GearSyncRecord format.
"""

from datetime import UTC, datetime

from core.records.gear_sync import GearSyncRecord, SyncOperation
from source_t3k.adapters.outbound.models import T3KModelStaging, T3KPackStaging
from source_t3k.adapters.outbound.publisher import GearSyncPublisher
from source_t3k.domain.value_objects import T3KPackType, T3KPlatform


class TestGearSyncPublisherPackConversion:
    """Tests for converting T3KPackStaging to GearSyncRecord."""

    def test_creates_gear_sync_record_from_pack(self) -> None:
        """Test that publish_pack creates a GearSyncRecord with correct structure."""
        pack = T3KPackStaging(
            id="pack-123",
            name="Mesa Boogie Dual Rectifier",
            slug="mesa-boogie-dual-rectifier",
            creator_id="creator-456",
            description="High gain amp pack",
            thumbnail_url="https://example.com/thumb.jpg",
            platform=T3KPlatform.NAM,
            pack_type=T3KPackType.AMP,
            created_at=datetime(2024, 1, 1, tzinfo=UTC),
            updated_at=datetime(2024, 1, 15, tzinfo=UTC),
        )

        publisher = GearSyncPublisher(session=None, queue_name="gear_pack_sync")

        # This should fail because the method doesn't exist yet
        record = publisher.create_pack_sync_record(pack)

        assert isinstance(record, GearSyncRecord)
        assert record.source_name == "t3k"
        assert record.source_record_id == "pack-123"
        assert record.source_updated_at == datetime(2024, 1, 15, tzinfo=UTC)
        assert record.operation == SyncOperation.CREATE

    def test_pack_payload_contains_required_fields(self) -> None:
        """Test that pack payload includes all fields needed for Gear creation."""
        pack = T3KPackStaging(
            id="pack-123",
            name="Mesa Boogie Dual Rectifier",
            slug="mesa-boogie-dual-rectifier",
            creator_id="creator-456",
            description="High gain amp pack",
            thumbnail_url="https://example.com/thumb.jpg",
            platform=T3KPlatform.NAM,
            pack_type=T3KPackType.AMP,
            created_at=datetime(2024, 1, 1, tzinfo=UTC),
            updated_at=datetime(2024, 1, 15, tzinfo=UTC),
        )

        publisher = GearSyncPublisher(session=None, queue_name="gear_pack_sync")
        record = publisher.create_pack_sync_record(pack)

        payload = record.payload

        # Core Gear fields
        assert payload["name"] == "Mesa Boogie Dual Rectifier"
        assert payload["slug"] == "mesa-boogie-dual-rectifier"
        assert payload["description"] == "High gain amp pack"
        assert payload["thumbnail_url"] == "https://example.com/thumb.jpg"
        assert payload["platform"] == "nam"
        assert payload["gear_type"] == "amp"
        assert payload["creator_id"] == "creator-456"

    def test_pack_payload_maps_t3k_enums_to_core_enums(self) -> None:
        """Test that T3K enum values are mapped to core domain enum values."""
        pack = T3KPackStaging(
            id="pack-ir",
            name="IR Pack",
            slug="ir-pack",
            creator_id="creator-456",
            description="Impulse responses",
            thumbnail_url="https://example.com/ir.jpg",
            platform=T3KPlatform.IR,
            pack_type=T3KPackType.IR,
            created_at=datetime(2024, 1, 1, tzinfo=UTC),
            updated_at=datetime(2024, 1, 15, tzinfo=UTC),
        )

        publisher = GearSyncPublisher(session=None, queue_name="gear_pack_sync")
        record = publisher.create_pack_sync_record(pack)

        # T3KPlatform.IR -> "ir", T3KPackType.IR -> "ir"
        assert record.payload["platform"] == "ir"
        assert record.payload["gear_type"] == "ir"


class TestGearSyncPublisherModelConversion:
    """Tests for converting T3KModelStaging to GearSyncRecord."""

    def test_creates_gear_sync_record_from_model(self) -> None:
        """Test that publish_model creates a GearSyncRecord with correct structure."""
        model = T3KModelStaging(
            id="model-789",
            pack_id="pack-123",
            name="Channel 1 Vintage",
            filename="channel1_vintage.nam",
            file_size=1024000,
            download_url="https://example.com/model.nam",
            checksum="abc123",
            created_at=datetime(2024, 1, 1, tzinfo=UTC),
            updated_at=datetime(2024, 1, 20, tzinfo=UTC),
        )

        publisher = GearSyncPublisher(session=None, queue_name="gear_model_sync")

        # This should fail because the method doesn't exist yet
        record = publisher.create_model_sync_record(model)

        assert isinstance(record, GearSyncRecord)
        assert record.source_name == "t3k"
        assert record.source_record_id == "model-789"
        assert record.source_updated_at == datetime(2024, 1, 20, tzinfo=UTC)
        assert record.operation == SyncOperation.CREATE

    def test_model_payload_contains_required_fields(self) -> None:
        """Test that model payload includes all fields needed for GearModel creation."""
        model = T3KModelStaging(
            id="model-789",
            pack_id="pack-123",
            name="Channel 1 Vintage",
            filename="channel1_vintage.nam",
            file_size=1024000,
            download_url="https://example.com/model.nam",
            checksum="abc123",
            created_at=datetime(2024, 1, 1, tzinfo=UTC),
            updated_at=datetime(2024, 1, 20, tzinfo=UTC),
        )

        publisher = GearSyncPublisher(session=None, queue_name="gear_model_sync")
        record = publisher.create_model_sync_record(model)

        payload = record.payload

        # Core GearModel fields
        assert payload["name"] == "Channel 1 Vintage"
        assert payload["filename"] == "channel1_vintage.nam"
        assert payload["file_size"] == 1024000
        assert payload["download_url"] == "https://example.com/model.nam"
        assert payload["checksum"] == "abc123"
        assert payload["pack_id"] == "pack-123"


class TestGearSyncPublisherSerialization:
    """Tests for GearSyncRecord serialization."""

    def test_pack_record_can_serialize_to_dict(self) -> None:
        """Test that GearSyncRecord from pack can be serialized to dict for pgmq."""
        pack = T3KPackStaging(
            id="pack-123",
            name="Mesa Boogie",
            slug="mesa-boogie",
            creator_id="creator-456",
            description="Amp",
            thumbnail_url="https://example.com/thumb.jpg",
            platform=T3KPlatform.NAM,
            pack_type=T3KPackType.AMP,
            created_at=datetime(2024, 1, 1, tzinfo=UTC),
            updated_at=datetime(2024, 1, 15, tzinfo=UTC),
        )

        publisher = GearSyncPublisher(session=None, queue_name="gear_pack_sync")
        record = publisher.create_pack_sync_record(pack)

        # Should be able to serialize to dict for JSON
        record_dict = record.to_dict()

        assert record_dict["source_name"] == "t3k"
        assert record_dict["source_record_id"] == "pack-123"
        assert record_dict["operation"] == "create"
        assert isinstance(record_dict["payload"], dict)

    def test_model_record_can_serialize_to_dict(self) -> None:
        """Test that GearSyncRecord from model can be serialized to dict for pgmq."""
        model = T3KModelStaging(
            id="model-789",
            pack_id="pack-123",
            name="Channel 1",
            filename="channel1.nam",
            file_size=1024000,
            download_url="https://example.com/model.nam",
            checksum="abc123",
            created_at=datetime(2024, 1, 1, tzinfo=UTC),
            updated_at=datetime(2024, 1, 20, tzinfo=UTC),
        )

        publisher = GearSyncPublisher(session=None, queue_name="gear_model_sync")
        record = publisher.create_model_sync_record(model)

        record_dict = record.to_dict()

        assert record_dict["source_name"] == "t3k"
        assert record_dict["source_record_id"] == "model-789"
        assert record_dict["operation"] == "create"
        assert isinstance(record_dict["payload"], dict)
