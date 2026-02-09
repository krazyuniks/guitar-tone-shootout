"""Unit tests for CompositionSpec value object.

Tests the generic composition specification for video rendering.
"""

from dataclasses import FrozenInstanceError

import pytest

from core.domain.value_objects.composition_spec import CompositionSpec


class TestCompositionSpecCreation:
    """Test CompositionSpec creation and immutability."""

    def test_can_create_with_minimal_fields(self) -> None:
        """CompositionSpec requires composition_type and data."""
        spec = CompositionSpec(
            composition_type="shootout",
            data={"test": "value"},
        )

        assert spec.composition_type == "shootout"
        assert spec.data == {"test": "value"}

    def test_composition_type_is_required(self) -> None:
        """composition_type field must be provided."""
        with pytest.raises(TypeError, match="composition_type"):
            CompositionSpec(data={"test": "value"})  # type: ignore

    def test_data_is_required(self) -> None:
        """data field must be provided."""
        with pytest.raises(TypeError, match="data"):
            CompositionSpec(composition_type="shootout")  # type: ignore

    def test_is_frozen_dataclass(self) -> None:
        """CompositionSpec must be immutable (frozen dataclass)."""
        spec = CompositionSpec(
            composition_type="shootout",
            data={"test": "value"},
        )

        with pytest.raises(FrozenInstanceError):
            spec.composition_type = "other"  # type: ignore

    def test_data_can_be_empty_dict(self) -> None:
        """data field can be an empty dictionary."""
        spec = CompositionSpec(
            composition_type="test",
            data={},
        )

        assert spec.data == {}

    def test_data_can_contain_nested_structures(self) -> None:
        """data field should accept nested dictionaries and lists."""
        spec = CompositionSpec(
            composition_type="shootout",
            data={
                "segments": [
                    {"audio": "/path/1.wav", "label": "Amp A"},
                    {"audio": "/path/2.wav", "label": "Amp B"},
                ],
                "resolution": "1920x1080",
                "metadata": {"title": "Test Shootout"},
            },
        )

        assert len(spec.data["segments"]) == 2
        assert spec.data["resolution"] == "1920x1080"
        assert spec.data["metadata"]["title"] == "Test Shootout"


class TestCompositionSpecEquality:
    """Test CompositionSpec equality and hashing."""

    def test_equal_specs_are_equal(self) -> None:
        """Two CompositionSpecs with same values should be equal."""
        spec1 = CompositionSpec(
            composition_type="shootout",
            data={"key": "value"},
        )
        spec2 = CompositionSpec(
            composition_type="shootout",
            data={"key": "value"},
        )

        assert spec1 == spec2

    def test_different_composition_type_not_equal(self) -> None:
        """CompositionSpecs with different types should not be equal."""
        spec1 = CompositionSpec(
            composition_type="shootout",
            data={"key": "value"},
        )
        spec2 = CompositionSpec(
            composition_type="other",
            data={"key": "value"},
        )

        assert spec1 != spec2

    def test_different_data_not_equal(self) -> None:
        """CompositionSpecs with different data should not be equal."""
        spec1 = CompositionSpec(
            composition_type="shootout",
            data={"key": "value1"},
        )
        spec2 = CompositionSpec(
            composition_type="shootout",
            data={"key": "value2"},
        )

        assert spec1 != spec2


class TestCompositionSpecUseCases:
    """Test CompositionSpec for different composition types."""

    def test_shootout_composition_spec(self) -> None:
        """CompositionSpec should support shootout composition data."""
        spec = CompositionSpec(
            composition_type="shootout",
            data={
                "shootout_id": "uuid-123",
                "segments": [
                    {"chain_id": "chain-1", "audio_path": "/path/1.wav"},
                    {"chain_id": "chain-2", "audio_path": "/path/2.wav"},
                ],
                "output_path": "/output/video.mp4",
            },
        )

        assert spec.composition_type == "shootout"
        assert "shootout_id" in spec.data
        assert len(spec.data["segments"]) == 2

    def test_generic_composition_spec(self) -> None:
        """CompositionSpec should support arbitrary composition types."""
        spec = CompositionSpec(
            composition_type="custom_renderer",
            data={
                "renderer": "remotion",
                "template": "comparison",
                "params": {"theme": "dark"},
            },
        )

        assert spec.composition_type == "custom_renderer"
        assert spec.data["renderer"] == "remotion"
