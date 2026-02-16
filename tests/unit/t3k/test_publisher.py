"""Unit tests for GearSyncPublisher.

Tests the conversion logic from T3K staging models to GearSyncRecord format.
"""

from datetime import UTC, datetime

from core.records.gear_sync import GearSyncRecord, SyncOperation
from source_t3k.adapters.outbound.models import T3KModelStaging, T3KToneStaging
from source_t3k.adapters.outbound.publisher import GearSyncPublisher


def _make_tone(**overrides) -> T3KToneStaging:
    """Build a T3KToneStaging with sensible defaults."""
    defaults = {
        "id": 42,
        "title": "Mesa Boogie Dual Rectifier",
        "description": "High gain amp",
        "tags": ["high-gain"],
        "makes": ["Mesa"],
        "gear": "amp",
        "platform": "nam",
        "models_count": 3,
        "favorites_count": 10,
        "downloads_count": 100,
        "images": ["https://example.com/thumb.jpg"],
        "user_id": "user-456",
        "url": "https://t3k.com/tones/42",
        "created_at": datetime(2024, 1, 1, tzinfo=UTC),
        "updated_at": datetime(2024, 1, 15, tzinfo=UTC),
    }
    defaults.update(overrides)
    return T3KToneStaging(**defaults)


def _make_model(**overrides) -> T3KModelStaging:
    """Build a T3KModelStaging with sensible defaults."""
    defaults = {
        "id": 99,
        "tone_id": 42,
        "user_id": "user-456",
        "name": "Clean Channel",
        "model_url": "https://t3k.com/models/99/clean.nam",
        "size": "standard",
        "created_at": datetime(2024, 1, 1, tzinfo=UTC),
        "updated_at": datetime(2024, 1, 20, tzinfo=UTC),
    }
    defaults.update(overrides)
    return T3KModelStaging(**defaults)


class TestGearSyncPublisherToneConversion:
    """Tests for converting T3KToneStaging to GearSyncRecord."""

    def test_creates_gear_sync_record_from_tone(self) -> None:
        tone = _make_tone()
        publisher = GearSyncPublisher(session=None, queue_name="gear_sync")
        record = publisher.create_tone_sync_record(tone)

        assert isinstance(record, GearSyncRecord)
        assert record.source_name == "t3k"
        assert record.source_record_id == "42"
        assert record.source_updated_at == datetime(2024, 1, 15, tzinfo=UTC)
        assert record.operation == SyncOperation.CREATE

    def test_tone_payload_contains_required_fields(self) -> None:
        tone = _make_tone()
        publisher = GearSyncPublisher(session=None, queue_name="gear_sync")
        record = publisher.create_tone_sync_record(tone)
        payload = record.payload

        assert payload["name"] == "Mesa Boogie Dual Rectifier"
        assert payload["description"] == "High gain amp"
        assert payload["thumbnail_url"] == "https://example.com/thumb.jpg"
        assert payload["platform"] == "nam"
        assert payload["gear_type"] == "amp"
        assert payload["creator_id"] == "user-456"

    def test_maps_full_rig_to_full_rig_gear_type(self) -> None:
        tone = _make_tone(gear="full-rig")
        publisher = GearSyncPublisher(session=None)
        record = publisher.create_tone_sync_record(tone)

        assert record.payload["gear_type"] == "full_rig"

    def test_maps_ir_gear_kind(self) -> None:
        tone = _make_tone(gear="ir", platform="ir")
        publisher = GearSyncPublisher(session=None)
        record = publisher.create_tone_sync_record(tone)

        assert record.payload["gear_type"] == "ir"
        assert record.payload["platform"] == "ir"

    def test_empty_images_gives_empty_thumbnail(self) -> None:
        tone = _make_tone(images=[])
        publisher = GearSyncPublisher(session=None)
        record = publisher.create_tone_sync_record(tone)

        assert record.payload["thumbnail_url"] == ""


class TestGearSyncPublisherModelConversion:
    """Tests for including models in GearSyncRecord."""

    def test_tone_record_includes_model_payloads(self) -> None:
        tone = _make_tone()
        models = [_make_model()]

        publisher = GearSyncPublisher(session=None)
        record = publisher.create_tone_sync_record(tone, models=models)

        assert len(record.payload["models"]) == 1
        model_payload = record.payload["models"][0]
        assert model_payload["source_record_id"] == "99"
        assert model_payload["name"] == "Clean Channel"
        assert model_payload["filename"] == "clean.nam"
        assert model_payload["download_url"] == "https://t3k.com/models/99/clean.nam"
        assert model_payload["size"] == "standard"
        assert model_payload["platform"] == "nam"
        assert model_payload["tone_id"] == "42"

    def test_source_updated_at_uses_max_of_tone_and_models(self) -> None:
        tone_time = datetime(2024, 1, 10, tzinfo=UTC)
        model_time = datetime(2024, 1, 20, tzinfo=UTC)

        tone = _make_tone(updated_at=tone_time, created_at=tone_time)
        models = [_make_model(updated_at=model_time, created_at=model_time)]

        publisher = GearSyncPublisher(session=None)
        record = publisher.create_tone_sync_record(tone, models=models)

        assert record.source_updated_at == model_time


class TestGearSyncPublisherSerialization:
    """Tests for GearSyncRecord serialization."""

    def test_tone_record_can_serialize_to_dict(self) -> None:
        tone = _make_tone()
        publisher = GearSyncPublisher(session=None)
        record = publisher.create_tone_sync_record(tone)

        record_dict = record.to_dict()

        assert record_dict["source_name"] == "t3k"
        assert record_dict["source_record_id"] == "42"
        assert record_dict["operation"] == "create"
        assert isinstance(record_dict["payload"], dict)
