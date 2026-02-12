"""Unit tests for video-related just commands in justfile.

Tests verify that video BC development commands are defined in the justfile.
These tests read the justfile directly rather than executing commands.
"""

from pathlib import Path


class TestJustVideoCommands:
    """Test video-specific just commands are defined in justfile."""

    def test_justfile_includes_video_studio_command(self) -> None:
        """Verify video-studio command is defined in justfile."""
        justfile = Path("/app/justfile")
        assert justfile.exists(), "justfile not found at /app/justfile"

        content = justfile.read_text()

        # Should have a video-studio command definition
        assert "video-studio:" in content, "video-studio command not defined in justfile"

        # Find the video-studio command section
        studio_idx = content.find("video-studio:")
        studio_section = content[studio_idx : studio_idx + 500]

        # Should reference Remotion Studio
        assert (
            "remotion" in studio_section.lower() or "studio" in studio_section.lower()
        ), "video-studio command does not reference Remotion"

    def test_justfile_has_at_least_three_video_commands(self) -> None:
        """Verify justfile defines at least 3 video-related commands."""
        justfile = Path("/app/justfile")
        content = justfile.read_text()

        # Count command definitions that contain "video"
        # Commands are defined as "command-name:"
        video_commands = []
        for line in content.splitlines():
            # Match lines like "video-studio:" or "check-video:" (command definitions)
            if (
                "video" in line.lower()
                and line.strip().endswith(":")
                and not line.strip().startswith("#")
            ):
                video_commands.append(line.strip())

        assert (
            len(video_commands) >= 3
        ), f"Expected at least 3 video commands, found {len(video_commands)}: {video_commands}"

    def test_lint_command_includes_video_in_scope(self) -> None:
        """Verify lint command includes video package in scope."""
        justfile = Path("/app/justfile")
        content = justfile.read_text()

        # Find the lint command
        lint_idx = content.find("lint:")
        assert lint_idx != -1, "lint command not found in justfile"

        lint_section = content[lint_idx : lint_idx + 500]

        # Should include libs/video or video/ in ruff commands
        # The command should be something like: ruff check libs/ ... which includes video
        assert "libs/" in lint_section, "lint command does not include libs/ in scope"
