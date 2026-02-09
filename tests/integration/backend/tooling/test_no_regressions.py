"""Tests to verify no regressions in existing just commands.

Ensures that adding video commands didn't break existing commands.
"""

from pathlib import Path


class TestNoRegressions:
    """Test that existing commands still work after adding video support."""

    def test_existing_quality_commands_still_exist(self) -> None:
        """Verify existing quality gate commands are still available."""
        justfile = Path("/app/justfile")
        content = justfile.read_text()

        # Core quality commands should still exist
        required_commands = [
            "check:",
            "lint:",
            "check-types:",
            "check-tests:",
            "check-imports:",
        ]

        for cmd in required_commands:
            assert cmd in content, f"Command '{cmd}' not found in justfile"

    def test_existing_test_commands_still_exist(self) -> None:
        """Verify existing test commands are still available."""
        justfile = Path("/app/justfile")
        content = justfile.read_text()

        required_commands = [
            "test-unit:",
            "test-integration:",
            "test:",
            "test-regression:",
            "test-golden-path:",
            "tdd ",  # tdd has a parameter, so no colon
        ]

        for cmd in required_commands:
            assert cmd in content, f"Command '{cmd}' not found in justfile"

    def test_existing_frontend_commands_still_exist(self) -> None:
        """Verify existing frontend commands are still available."""
        justfile = Path("/app/justfile")
        content = justfile.read_text()

        required_commands = [
            "build-astro:",
            "watch-astro:",
            "check-astro:",
        ]

        for cmd in required_commands:
            assert cmd in content, f"Command '{cmd}' not found in justfile"

    def test_lint_command_still_includes_existing_packages(self) -> None:
        """Verify lint command still includes existing packages (libs/, apps/, sources/)."""
        justfile = Path("/app/justfile")
        content = justfile.read_text()

        # Find lint command
        lint_idx = content.find("lint:")
        assert lint_idx != -1, "lint command not found"

        lint_section = content[lint_idx : lint_idx + 500]

        # Should still include existing package paths
        assert "libs/" in lint_section, "lint command no longer includes libs/"
        assert "apps/" in lint_section, "lint command no longer includes apps/"
        assert "sources/" in lint_section, "lint command no longer includes sources/"

    def test_check_imports_still_validates_core_isolation(self) -> None:
        """Verify import linter still enforces core isolation."""
        # Read pyproject.toml to verify core-isolation contract still exists
        pyproject = Path("/app/pyproject.toml")
        content = pyproject.read_text()

        assert "core-isolation" in content, "core-isolation contract removed from pyproject.toml"
        assert "video" in content, "video not in import linter root_packages"

    def test_check_command_structure_unchanged(self) -> None:
        """Verify check command still calls all expected quality gates."""
        justfile = Path("/app/justfile")
        content = justfile.read_text()

        # Find check command
        check_idx = content.find("check:")
        assert check_idx != -1, "check command not found"

        check_section = content[check_idx : check_idx + 200]

        # Should still call all quality gates
        assert "lint" in check_section, "check command no longer calls lint"
        assert "check-types" in check_section, "check command no longer calls check-types"
        assert "check-tests" in check_section, "check command no longer calls check-tests"
        assert "check-imports" in check_section, "check command no longer calls check-imports"
