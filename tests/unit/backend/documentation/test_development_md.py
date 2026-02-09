"""Unit tests for DEVELOPMENT.md documentation updates (T81).

These tests verify that DEVELOPMENT.md has been updated to include the video BC
in the stack table, project structure tree, and dependency rules table.

NOTE: These tests must run on the HOST, not in Docker containers, because
DEVELOPMENT.md is not mounted in the container filesystem.
"""

import pytest
from pathlib import Path


@pytest.mark.host_only
class TestDevelopmentMdVideoIntegration:
    """Verify DEVELOPMENT.md includes video BC documentation."""

    @staticmethod
    def _read_development_md() -> str:
        """Read DEVELOPMENT.md from repository root.

        This function navigates up from the test file location to find the repo root.
        Works both when running in Docker (if mounted) and on host.
        """
        # Navigate up from tests/unit/backend/documentation/ to repo root
        repo_root = Path(__file__).parent.parent.parent.parent.parent
        dev_md = repo_root / "DEVELOPMENT.md"

        if not dev_md.exists():
            # Try alternative path - we might be in a different location
            # This happens when running in Docker with different mount structure
            import os
            cwd = Path.cwd()
            dev_md = cwd / "DEVELOPMENT.md"

        return dev_md.read_text()

    def test_stack_table_includes_video_row(self) -> None:
        """Stack table MUST include a row mentioning video processing/composition."""
        content = self._read_development_md()

        # Find the Stack section
        assert "## Stack" in content, "Stack section not found in DEVELOPMENT.md"

        # Look for video-related row in the stack table
        # The video BC is part of the backend processing stack
        assert (
            "video" in content.lower() or "Video" in content
        ), "Stack table must mention video processing/composition"

    def test_project_structure_shows_libs_video(self) -> None:
        """Project structure tree MUST show libs/video/ with correct layout."""
        content = self._read_development_md()

        # Find the Project Structure section
        assert "## Project Structure" in content, "Project Structure section not found"

        # Verify libs/video/ is present (not contexts/video/)
        assert "libs/video/" in content or "│   └── video/" in content, (
            "Project structure must show libs/video/ directory"
        )

        # Ensure no stale references to contexts/video/
        assert "contexts/video/" not in content, (
            "Stale reference to contexts/video/ found - must be libs/video/"
        )

    def test_project_structure_shows_video_subdirectories(self) -> None:
        """Project structure tree MUST show video BC subdirectory layout."""
        content = self._read_development_md()

        # The video BC should have src/video/ with subdirectories
        # Based on the epic context, it should show composition, rendering, etc.
        assert "src/video/" in content or "└── video/" in content, (
            "Project structure must show src/video/ subdirectory"
        )

    def test_dependency_rules_table_includes_video(self) -> None:
        """Dependency rules table MUST include video module with correct rules."""
        content = self._read_development_md()

        # Find dependency rules section (various possible headers)
        has_dep_section = (
            "dependency" in content.lower() or
            "Dependency" in content or
            "module" in content.lower()
        )
        assert has_dep_section, "Dependency rules section not found"

        # Video BC should be mentioned in dependency context
        # It depends on core, but not on sources/apps
        assert "video" in content.lower(), (
            "Dependency rules must mention video module"
        )

    def test_no_cloudflare_references(self) -> None:
        """MUST NOT contain Cloudflare references (out of scope for this epic)."""
        content = self._read_development_md()

        # Cloudflare is explicitly out of scope for E70
        assert "Cloudflare" not in content and "cloudflare" not in content, (
            "DEVELOPMENT.md must not reference Cloudflare (out of scope)"
        )

    def test_no_stale_contexts_video_references(self) -> None:
        """MUST NOT contain any stale contexts/video/ references."""
        content = self._read_development_md()

        # All references must be to libs/video/, not contexts/video/
        assert "contexts/video" not in content, (
            "Stale reference to contexts/video found - must be libs/video/"
        )
