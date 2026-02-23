"""Unit tests for video props serializer."""

from gts.domain.value_objects.composition_spec import CompositionSpec
from video.props import (
    serialize_composition_props,
    validate_remotion_props,
)


class TestSerializeCompositionProps:
    """Tests for CompositionSpec to Remotion props serialization."""

    def test_converts_composition_spec_to_json_dict(self) -> None:
        """Serialize returns JSON-serializable dict."""
        spec = CompositionSpec(
            composition_type="shootout",
            data={
                "shootout_id": "s-123",
                "title": "My Shootout",
                "gear_ids": ["g1", "g2", "g3"],
            },
        )

        props = serialize_composition_props(spec)

        assert isinstance(props, dict)
        assert props["compositionType"] == "shootout"
        assert props["data"]["shootout_id"] == "s-123"

    def test_converts_snake_case_to_camel_case(self) -> None:
        """Serialize converts Python snake_case to JS camelCase."""
        spec = CompositionSpec(
            composition_type="test_comp",
            data={"test_field": "value", "another_field": 123},
        )

        props = serialize_composition_props(spec)

        # Top-level keys should be camelCase
        assert "compositionType" in props
        # Data can remain as-is (or be converted depending on impl)
        assert props["data"]["test_field"] == "value"

    def test_handles_nested_data_structures(self) -> None:
        """Serialize handles nested dicts and lists in data."""
        spec = CompositionSpec(
            composition_type="complex",
            data={
                "nested": {"level2": {"level3": "value"}},
                "list_data": [{"id": "1"}, {"id": "2"}],
            },
        )

        props = serialize_composition_props(spec)

        assert props["data"]["nested"]["level2"]["level3"] == "value"
        assert len(props["data"]["list_data"]) == 2

    def test_handles_empty_data(self) -> None:
        """Serialize handles composition with empty data dict."""
        spec = CompositionSpec(composition_type="minimal", data={})

        props = serialize_composition_props(spec)

        assert props["compositionType"] == "minimal"
        assert props["data"] == {}

    def test_preserves_numeric_types(self) -> None:
        """Serialize preserves int, float, bool types."""
        spec = CompositionSpec(
            composition_type="typed",
            data={
                "count": 42,
                "ratio": 0.75,
                "enabled": True,
                "disabled": False,
            },
        )

        props = serialize_composition_props(spec)

        assert props["data"]["count"] == 42
        assert props["data"]["ratio"] == 0.75
        assert props["data"]["enabled"] is True
        assert props["data"]["disabled"] is False


class TestValidateRemotionProps:
    """Tests for Remotion props validation."""

    def test_accepts_valid_props_structure(self) -> None:
        """Validate returns True for valid Remotion props."""
        props = {
            "compositionType": "shootout",
            "data": {"shootout_id": "s-123"},
        }

        assert validate_remotion_props(props) is True

    def test_rejects_missing_composition_type(self) -> None:
        """Validate rejects props without compositionType."""
        props = {"data": {"test": "value"}}

        assert validate_remotion_props(props) is False

    def test_rejects_missing_data(self) -> None:
        """Validate rejects props without data field."""
        props = {"compositionType": "test"}

        assert validate_remotion_props(props) is False

    def test_rejects_non_dict_data(self) -> None:
        """Validate rejects props where data is not a dict."""
        props = {"compositionType": "test", "data": "not a dict"}

        assert validate_remotion_props(props) is False

    def test_accepts_extra_fields(self) -> None:
        """Validate allows additional fields for extensibility."""
        props = {
            "compositionType": "test",
            "data": {},
            "metadata": {"version": "1.0"},
        }

        # Should still be valid (extra fields allowed)
        assert validate_remotion_props(props) is True
