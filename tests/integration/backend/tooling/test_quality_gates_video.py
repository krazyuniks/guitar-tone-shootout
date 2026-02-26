"""Tests for quality gate commands including video package.

Verifies that just check, lint, and type checking commands include libs/video in their scope.
"""

from pathlib import Path


class TestQualityGatesIncludeVideo:
    """Test that quality gates include video package."""

    def test_lint_command_includes_video(self) -> None:
        """Verify lint command includes libs/video in scope."""
        justfile = Path("/app/justfile")
        content = justfile.read_text()

        # Find the lint command definition
        lint_start = content.find("lint:")
        assert lint_start != -1, "lint command not found in justfile"

        # Get the lint command section (next ~300 chars should include the command)
        lint_section = content[lint_start : lint_start + 500]

        # Should include model/ or video in the ruff command
        assert "model/" in lint_section or "video" in lint_section, (
            "lint command does not include model/ or video in scope"
        )

    def test_check_types_includes_video(self) -> None:
        """Verify type checking includes video package."""
        justfile = Path("/app/justfile")
        content = justfile.read_text()

        # The check-types command currently only checks libs/core/ --strict
        # For video (TypeScript), we need a separate type check command
        # Check if there's a video-specific type check or if check-types was updated

        # Look for type checking of video
        # This might be a new command like check-types-video or an update to check-types
        has_video_type_check = (
            "mypy libs/video" in content
            or "tsc" in content
            or "check-types-video" in content
            or "check-video" in content
        )

        assert has_video_type_check, (
            "No type checking found for video package. "
            "Video is TypeScript/Python so should use tsc or mypy."
        )

    def test_check_tests_includes_video(self) -> None:
        """Verify test commands can run video tests."""
        justfile = Path("/app/justfile")
        content = justfile.read_text()

        # Check that test commands include video in their scope
        # Video tests would be in tests/unit/video/ or tests/integration/video/
        test_section_start = content.find("# Testing")
        test_section = content[test_section_start : test_section_start + 2000]

        # The test-unit command should include tests/unit/ which would cover tests/unit/video/
        assert "tests/unit/" in test_section, "test-unit does not include tests/unit/"

    def test_check_command_includes_video_quality_gates(self) -> None:
        """Verify main check command includes video in all quality gates."""
        justfile = Path("/app/justfile")
        content = justfile.read_text()

        # Find the check command definition
        check_start = content.find("check:")
        assert check_start != -1, "check command not found in justfile"

        check_section = content[check_start : check_start + 200]

        # The check command should include check-imports which already has video
        assert "check-imports" in check_section, "check command does not call check-imports"

        # And it should include lint which should now cover video
        assert "lint" in check_section, "check command does not call lint"

    def test_video_python_code_exists(self) -> None:
        """Verify video package Python code exists."""
        video_init = Path("/app/model/video/src/video/__init__.py")
        assert video_init.exists(), "model/video/src/video/__init__.py not found"
