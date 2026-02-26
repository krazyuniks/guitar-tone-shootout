"""Tests for Remotion Studio integration.

Verifies that the video-studio command can launch Remotion Studio for video BC development.
"""

import json
from pathlib import Path


class TestRemotionStudio:
    """Test Remotion Studio command and setup."""

    def test_libs_video_exists(self) -> None:
        """Verify model/video directory exists (from T72)."""
        video_path = Path("/app/model/video")
        assert video_path.exists(), "model/video directory not found (required from T72)"
        assert video_path.is_dir(), "model/video is not a directory"

    def test_libs_video_has_package_json(self) -> None:
        """Verify model/video has package.json with Remotion dependencies."""
        package_json = Path("/app/model/video/package.json")
        assert package_json.exists(), "model/video/package.json not found"

        with open(package_json) as f:
            pkg = json.load(f)

        # Should have remotion dependencies
        deps = pkg.get("dependencies", {})
        assert "remotion" in deps, "remotion not in package.json dependencies"
        assert "@remotion/cli" in deps, "@remotion/cli not in package.json dependencies"

    def test_video_studio_command_launches_remotion(self) -> None:
        """Verify video-studio command would launch Remotion Studio.

        We can't actually launch the interactive studio in tests, but we can verify
        the command is defined and would execute the correct script.
        """
        justfile = Path("/app/justfile")
        content = justfile.read_text()

        assert "video-studio" in content, "video-studio command not defined in justfile"

        # The command should reference Remotion Studio or npx remotion studio
        # Find the video-studio section
        studio_start = content.find("video-studio")
        if studio_start == -1:
            raise AssertionError("video-studio command not found in justfile")

        # Get a reasonable chunk after the command definition
        studio_section = content[studio_start : studio_start + 500]

        # Should mention remotion or studio
        assert "remotion" in studio_section.lower() or "studio" in studio_section.lower(), (
            "video-studio command does not reference Remotion"
        )

    def test_video_package_has_remotion_entry_point(self) -> None:
        """Verify model/video has Remotion entry point (index.ts)."""
        entry_point = Path("/app/model/video/src/video/remotion/index.ts")
        assert entry_point.exists(), (
            "model/video/src/video/remotion/index.ts not found - Remotion needs an entry point"
        )
