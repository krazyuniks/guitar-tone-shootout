"""Tests for Shootout and ToneSelection models and schemas."""

import json
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.models import Shootout, ToneSelection
from app.schemas import (
    EffectSchema,
    ShootoutCreate,
    ShootoutListResponse,
    ShootoutResponse,
    ShootoutUpdate,
    ToneSelectionCreate,
    ToneSelectionResponse,
)


class TestShootoutModel:
    """Tests for Shootout SQLAlchemy model."""

    def test_shootout_repr(self):
        """Test Shootout __repr__ method."""
        shootout = Shootout(
            id=uuid4(),
            user_id=uuid4(),
            name="Test Shootout",
            di_track_path="/path/to/di.wav",
            di_track_original_name="di.wav",
        )
        assert "Test Shootout" in repr(shootout)

    def test_shootout_nullable_fields(self):
        """Test Shootout model nullable fields."""
        shootout = Shootout(
            user_id=uuid4(),
            name="Test",
            di_track_path="/path/to/di.wav",
            di_track_original_name="di.wav",
            output_format="mp4",
            sample_rate=44100,
            is_processed=False,
        )
        # Nullable fields default to None when not provided
        assert shootout.output_path is None
        assert shootout.description is None
        assert shootout.guitar is None
        assert shootout.pickup is None
        # Non-nullable fields are set explicitly
        assert shootout.output_format == "mp4"
        assert shootout.sample_rate == 44100
        assert shootout.is_processed is False


class TestToneSelectionModel:
    """Tests for ToneSelection SQLAlchemy model."""

    def test_tone_selection_repr(self):
        """Test ToneSelection __repr__ method."""
        tone = ToneSelection(
            id=uuid4(),
            shootout_id=uuid4(),
            tone3000_tone_id=123,
            tone3000_model_id=456,
            tone_title="Test Tone",
            model_name="Standard Model",
            model_size="standard",
            gear_type="amp",
            position=0,
        )
        assert "Test Tone" in repr(tone)
        assert "pos=0" in repr(tone)

    def test_tone_selection_nullable_fields(self):
        """Test ToneSelection model nullable fields."""
        tone = ToneSelection(
            shootout_id=uuid4(),
            tone3000_tone_id=123,
            tone3000_model_id=456,
            tone_title="Test",
            model_name="Model",
            model_size="standard",
            gear_type="amp",
            highpass=True,
            position=0,
        )
        # Nullable fields default to None when not provided
        assert tone.display_name is None
        assert tone.ir_path is None
        assert tone.effects_json is None
        # Non-nullable fields are set explicitly
        assert tone.highpass is True
        assert tone.position == 0


class TestToneSelectionCreateSchema:
    """Tests for ToneSelectionCreate Pydantic schema."""

    def test_valid_tone_selection(self):
        """Test creating a valid tone selection."""
        data = {
            "tone3000_tone_id": 123,
            "tone3000_model_id": 456,
            "tone_title": "Plexi Crunch",
            "model_name": "Standard Model",
            "model_size": "standard",
            "gear_type": "amp",
        }
        tone = ToneSelectionCreate(**data)
        assert tone.tone3000_tone_id == 123
        assert tone.tone3000_model_id == 456
        assert tone.highpass is True  # default
        assert tone.position == 0  # default
        assert tone.effects == []  # default

    def test_tone_selection_with_optional_fields(self):
        """Test tone selection with all optional fields."""
        data = {
            "tone3000_tone_id": 123,
            "tone3000_model_id": 456,
            "tone_title": "Plexi Crunch",
            "model_name": "Standard Model",
            "model_size": "standard",
            "gear_type": "amp",
            "display_name": "My Custom Name",
            "ir_path": "/path/to/ir.wav",
            "highpass": False,
            "position": 2,
            "effects": [
                {"effect_type": "reverb", "value": "room"},
            ],
        }
        tone = ToneSelectionCreate(**data)
        assert tone.display_name == "My Custom Name"
        assert tone.ir_path == "/path/to/ir.wav"
        assert tone.highpass is False
        assert tone.position == 2
        assert len(tone.effects) == 1
        assert tone.effects[0].effect_type == "reverb"

    def test_tone_selection_missing_required_field(self):
        """Test tone selection fails without required field."""
        data = {
            "tone3000_tone_id": 123,
            # missing tone3000_model_id
            "tone_title": "Plexi",
            "model_name": "Standard",
            "model_size": "standard",
            "gear_type": "amp",
        }
        with pytest.raises(ValidationError):
            ToneSelectionCreate(**data)

    def test_tone_selection_position_must_be_non_negative(self):
        """Test that position must be >= 0."""
        data = {
            "tone3000_tone_id": 123,
            "tone3000_model_id": 456,
            "tone_title": "Plexi",
            "model_name": "Standard",
            "model_size": "standard",
            "gear_type": "amp",
            "position": -1,
        }
        with pytest.raises(ValidationError):
            ToneSelectionCreate(**data)


class TestShootoutCreateSchema:
    """Tests for ShootoutCreate Pydantic schema."""

    def test_valid_shootout_create(self):
        """Test creating a valid shootout."""
        data = {
            "name": "Marshall vs Mesa",
            "di_track_path": "/uploads/di-track-123.wav",
            "di_track_original_name": "my_di.wav",
            "tone_selections": [
                {
                    "tone3000_tone_id": 123,
                    "tone3000_model_id": 456,
                    "tone_title": "Plexi Crunch",
                    "model_name": "Standard Model",
                    "model_size": "standard",
                    "gear_type": "amp",
                },
            ],
        }
        shootout = ShootoutCreate(**data)
        assert shootout.name == "Marshall vs Mesa"
        assert shootout.output_format == "mp4"  # default
        assert shootout.sample_rate == 44100  # default
        assert len(shootout.tone_selections) == 1

    def test_shootout_with_all_optional_fields(self):
        """Test shootout with all optional fields."""
        data = {
            "name": "Marshall vs Mesa",
            "description": "Comparing two classic amps",
            "di_track_path": "/uploads/di-track-123.wav",
            "di_track_original_name": "my_di.wav",
            "output_format": "webm",
            "sample_rate": 48000,
            "guitar": "Gibson Les Paul",
            "pickup": "Bridge Humbucker",
            "tone_selections": [
                {
                    "tone3000_tone_id": 123,
                    "tone3000_model_id": 456,
                    "tone_title": "Plexi",
                    "model_name": "Standard",
                    "model_size": "standard",
                    "gear_type": "amp",
                },
            ],
        }
        shootout = ShootoutCreate(**data)
        assert shootout.description == "Comparing two classic amps"
        assert shootout.output_format == "webm"
        assert shootout.sample_rate == 48000
        assert shootout.guitar == "Gibson Les Paul"
        assert shootout.pickup == "Bridge Humbucker"

    def test_shootout_requires_at_least_one_tone(self):
        """Test shootout requires at least one tone selection."""
        data = {
            "name": "Empty Shootout",
            "di_track_path": "/uploads/di.wav",
            "di_track_original_name": "di.wav",
            "tone_selections": [],
        }
        with pytest.raises(ValidationError) as exc_info:
            ShootoutCreate(**data)
        assert "tone_selections" in str(exc_info.value)

    def test_shootout_max_10_tones(self):
        """Test shootout allows maximum 10 tones."""
        tone_data = {
            "tone3000_tone_id": 123,
            "tone3000_model_id": 456,
            "tone_title": "Tone",
            "model_name": "Model",
            "model_size": "standard",
            "gear_type": "amp",
        }
        data = {
            "name": "Too Many Tones",
            "di_track_path": "/uploads/di.wav",
            "di_track_original_name": "di.wav",
            "tone_selections": [tone_data for _ in range(11)],
        }
        with pytest.raises(ValidationError) as exc_info:
            ShootoutCreate(**data)
        assert "tone_selections" in str(exc_info.value)

    def test_shootout_sample_rate_validation(self):
        """Test sample rate must be in valid range."""
        data = {
            "name": "Bad Sample Rate",
            "di_track_path": "/uploads/di.wav",
            "di_track_original_name": "di.wav",
            "sample_rate": 100,  # Too low
            "tone_selections": [
                {
                    "tone3000_tone_id": 123,
                    "tone3000_model_id": 456,
                    "tone_title": "Tone",
                    "model_name": "Model",
                    "model_size": "standard",
                    "gear_type": "amp",
                },
            ],
        }
        with pytest.raises(ValidationError):
            ShootoutCreate(**data)

    def test_shootout_name_max_length(self):
        """Test name length validation."""
        data = {
            "name": "x" * 256,  # Too long
            "di_track_path": "/uploads/di.wav",
            "di_track_original_name": "di.wav",
            "tone_selections": [
                {
                    "tone3000_tone_id": 123,
                    "tone3000_model_id": 456,
                    "tone_title": "Tone",
                    "model_name": "Model",
                    "model_size": "standard",
                    "gear_type": "amp",
                },
            ],
        }
        with pytest.raises(ValidationError):
            ShootoutCreate(**data)


class TestShootoutUpdateSchema:
    """Tests for ShootoutUpdate Pydantic schema."""

    def test_update_with_partial_fields(self):
        """Test update with only some fields."""
        data = {"name": "New Name"}
        update = ShootoutUpdate(**data)
        assert update.name == "New Name"
        assert update.description is None
        assert update.guitar is None
        assert update.pickup is None

    def test_update_all_fields(self):
        """Test update with all fields."""
        data = {
            "name": "New Name",
            "description": "New description",
            "guitar": "Fender Strat",
            "pickup": "Neck Single",
        }
        update = ShootoutUpdate(**data)
        assert update.name == "New Name"
        assert update.description == "New description"
        assert update.guitar == "Fender Strat"
        assert update.pickup == "Neck Single"

    def test_update_empty(self):
        """Test update with no fields."""
        data = {}
        update = ShootoutUpdate(**data)
        assert update.name is None
        assert update.description is None


class TestToneSelectionResponseSchema:
    """Tests for ToneSelectionResponse Pydantic schema."""

    def test_from_orm(self):
        """Test creating response from ORM model."""
        tone = ToneSelection(
            id=uuid4(),
            shootout_id=uuid4(),
            tone3000_tone_id=123,
            tone3000_model_id=456,
            tone_title="Plexi",
            model_name="Standard",
            model_size="standard",
            gear_type="amp",
            display_name="My Plexi",
            ir_path="/path/to/ir.wav",
            highpass=False,
            effects_json='[{"effect_type": "reverb", "value": "room"}]',
            position=1,
        )
        # Simulate created_at being set
        from datetime import UTC, datetime

        tone.created_at = datetime.now(UTC)

        response = ToneSelectionResponse.model_validate(tone)
        assert response.tone3000_tone_id == 123
        assert response.model_size == "standard"
        assert response.effects_json == '[{"effect_type": "reverb", "value": "room"}]'


class TestShootoutResponseSchema:
    """Tests for ShootoutResponse Pydantic schema."""

    def test_response_includes_tone_selections(self):
        """Test response includes related tone selections."""
        from datetime import UTC, datetime

        now = datetime.now(UTC)
        shootout_id = uuid4()

        tone = ToneSelection(
            id=uuid4(),
            shootout_id=shootout_id,
            tone3000_tone_id=123,
            tone3000_model_id=456,
            tone_title="Plexi",
            model_name="Standard",
            model_size="standard",
            gear_type="amp",
            highpass=True,
            position=0,
            created_at=now,
        )

        shootout = Shootout(
            id=shootout_id,
            user_id=uuid4(),
            name="Test Shootout",
            description="A test",
            di_track_path="/path/to/di.wav",
            di_track_original_name="di.wav",
            output_format="mp4",
            sample_rate=44100,
            guitar="Les Paul",
            pickup="Bridge",
            is_processed=False,
            created_at=now,
            updated_at=now,
        )
        shootout.tone_selections = [tone]

        response = ShootoutResponse.model_validate(shootout)
        assert response.name == "Test Shootout"
        assert len(response.tone_selections) == 1
        assert response.tone_selections[0].tone_title == "Plexi"


class TestShootoutListResponseSchema:
    """Tests for ShootoutListResponse Pydantic schema."""

    def test_list_response_includes_tone_count(self):
        """Test list response includes tone count instead of full selections."""
        from datetime import UTC, datetime

        now = datetime.now(UTC)
        shootout_id = uuid4()

        # Create a minimal dict that matches the schema
        data = {
            "id": shootout_id,
            "name": "Test",
            "description": None,
            "is_processed": False,
            "output_path": None,
            "tone_count": 3,
            "created_at": now,
            "updated_at": now,
        }

        response = ShootoutListResponse(**data)
        assert response.name == "Test"
        assert response.tone_count == 3


class TestEffectSchema:
    """Tests for EffectSchema."""

    def test_valid_effect(self):
        """Test creating a valid effect."""
        data = {"effect_type": "reverb", "value": "room"}
        effect = EffectSchema(**data)
        assert effect.effect_type == "reverb"
        assert effect.value == "room"

    def test_effect_types(self):
        """Test various effect types."""
        effects = [
            {"effect_type": "eq", "value": "highpass_80hz"},
            {"effect_type": "reverb", "value": "hall"},
            {"effect_type": "delay", "value": "slapback"},
            {"effect_type": "gain", "value": "+3.0"},
        ]
        for effect_data in effects:
            effect = EffectSchema(**effect_data)
            assert effect.effect_type == effect_data["effect_type"]
            assert effect.value == effect_data["value"]


class TestEffectsJsonSerialization:
    """Tests for effects JSON serialization in ToneSelection."""

    def test_serialize_effects_to_json(self):
        """Test serializing effects list to JSON string."""
        effects = [
            EffectSchema(effect_type="eq", value="highpass_80hz"),
            EffectSchema(effect_type="reverb", value="room"),
        ]

        # Serialize to JSON for storage
        effects_json = json.dumps([e.model_dump() for e in effects])
        assert "eq" in effects_json
        assert "reverb" in effects_json

        # Deserialize back
        loaded = json.loads(effects_json)
        assert len(loaded) == 2
        assert loaded[0]["effect_type"] == "eq"

    def test_effects_json_in_tone_selection(self):
        """Test effects_json field in ToneSelection model."""
        tone = ToneSelection(
            shootout_id=uuid4(),
            tone3000_tone_id=123,
            tone3000_model_id=456,
            tone_title="Test",
            model_name="Model",
            model_size="standard",
            gear_type="amp",
        )

        # Store effects as JSON string
        effects = [{"effect_type": "reverb", "value": "room"}]
        tone.effects_json = json.dumps(effects)

        # Retrieve and parse
        loaded = json.loads(tone.effects_json)
        assert loaded[0]["effect_type"] == "reverb"
