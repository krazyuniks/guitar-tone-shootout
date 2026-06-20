"""Unit tests for Platform enum in dedicated module.

This test verifies that Platform enum exists in its own module at
model/gts/src/gts/domain/value_objects/platform.py as specified
in the task requirements.
"""


class TestPlatformEnum:
    """Tests for Platform enum module."""

    def test_platform_module_exists(self) -> None:
        """Test that platform module exists at expected location."""
        # This import will fail if the module doesn't exist
        from gts.domain.value_objects.platform import Platform

        assert Platform is not None

    def test_platform_has_nam(self) -> None:
        """Test that Platform.NAM exists with correct value."""
        from gts.domain.value_objects.platform import Platform

        assert hasattr(Platform, "NAM")
        assert Platform.NAM.value == "nam"

    def test_platform_has_ir(self) -> None:
        """Test that Platform.IR exists with correct value."""
        from gts.domain.value_objects.platform import Platform

        assert hasattr(Platform, "IR")
        assert Platform.IR.value == "ir"

    def test_platform_has_aida_x(self) -> None:
        """Test that Platform.AIDA_X exists with correct value."""
        from gts.domain.value_objects.platform import Platform

        assert hasattr(Platform, "AIDA_X")
        assert Platform.AIDA_X.value == "aida_x"

    def test_platform_all_required_values(self) -> None:
        """Test that Platform has required values from acceptance criteria."""
        from gts.domain.value_objects.platform import Platform

        # Wiki:314-322 specifies platforms including NAM, IR, AIDA_X
        required_values = {"nam", "ir", "aida_x"}
        actual_values = {member.value for member in Platform}

        assert required_values.issubset(actual_values), (
            f"Missing required Platform values. "
            f"Expected at least {required_values}, got {actual_values}"
        )

    def test_platform_is_string_enum(self) -> None:
        """Test that Platform values are strings."""
        from gts.domain.value_objects.platform import Platform

        for member in Platform:
            assert isinstance(member.value, str), (
                f"Platform.{member.name} value should be str, got {type(member.value)}"
            )

    def test_platform_supports_aa_snapshot(self) -> None:
        """Test that Platform includes AA_SNAPSHOT for Axe-FX/Helix snapshots."""
        from gts.domain.value_objects.platform import Platform

        # Platform should support various modelling platforms
        assert hasattr(Platform, "AA_SNAPSHOT")
        assert Platform.AA_SNAPSHOT.value == "aa_snapshot"

    def test_platform_supports_proteus(self) -> None:
        """Test that Platform includes PROTEUS for Proteus Tone Capture."""
        from gts.domain.value_objects.platform import Platform

        assert hasattr(Platform, "PROTEUS")
        assert Platform.PROTEUS.value == "proteus"
