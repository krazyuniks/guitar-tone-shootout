"""Unit tests for GearType enum in dedicated module.

This test verifies that GearType enum exists in its own module at
model/gts/src/gts/domain/value_objects/gear_type.py as specified
in the task requirements.
"""


class TestGearTypeEnum:
    """Tests for GearType enum module."""

    def test_gear_type_module_exists(self) -> None:
        """Test that gear_type module exists at expected location."""
        # This import will fail if the module doesn't exist
        from gts.domain.value_objects.gear_type import GearType

        assert GearType is not None

    def test_gear_type_has_amp(self) -> None:
        """Test that GearType.AMP exists with correct value."""
        from gts.domain.value_objects.gear_type import GearType

        assert hasattr(GearType, "AMP")
        assert GearType.AMP.value == "amp"

    def test_gear_type_has_full_rig(self) -> None:
        """Test that GearType.FULL_RIG exists with correct value."""
        from gts.domain.value_objects.gear_type import GearType

        assert hasattr(GearType, "FULL_RIG")
        assert GearType.FULL_RIG.value == "full_rig"

    def test_gear_type_has_pedal(self) -> None:
        """Test that GearType.PEDAL exists with correct value."""
        from gts.domain.value_objects.gear_type import GearType

        assert hasattr(GearType, "PEDAL")
        assert GearType.PEDAL.value == "pedal"

    def test_gear_type_has_outboard(self) -> None:
        """Test that GearType.OUTBOARD exists with correct value."""
        from gts.domain.value_objects.gear_type import GearType

        assert hasattr(GearType, "OUTBOARD")
        assert GearType.OUTBOARD.value == "outboard"

    def test_gear_type_has_ir(self) -> None:
        """Test that GearType.IR exists with correct value."""
        from gts.domain.value_objects.gear_type import GearType

        assert hasattr(GearType, "IR")
        assert GearType.IR.value == "ir"

    def test_gear_type_all_required_values(self) -> None:
        """Test that GearType has all required values from acceptance criteria."""
        from gts.domain.value_objects.gear_type import GearType

        # Wiki:304-312 specifies: AMP, FULL_RIG, PEDAL, OUTBOARD, IR
        required_values = {"amp", "full_rig", "pedal", "outboard", "ir"}
        actual_values = {member.value for member in GearType}

        assert required_values.issubset(actual_values), (
            f"Missing required GearType values. "
            f"Expected at least {required_values}, got {actual_values}"
        )

    def test_gear_type_is_string_enum(self) -> None:
        """Test that GearType values are strings."""
        from gts.domain.value_objects.gear_type import GearType

        for member in GearType:
            assert isinstance(member.value, str), (
                f"GearType.{member.name} value should be str, got {type(member.value)}"
            )
