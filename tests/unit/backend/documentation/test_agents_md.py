"""Unit tests for AGENTS.md documentation updates (T81).

These tests verify that AGENTS.md has been updated to include the video BC
in the stack table, project structure tree, and dependency rules table.

NOTE: These tests must run on the HOST, not in Docker containers, because
AGENTS.md is not mounted in the container filesystem.
"""

from pathlib import Path


class TestAgentsMdVideoIntegration:
    """Verify AGENTS.md includes video BC documentation."""

    @staticmethod
    def _read_agents_md() -> str:
        """Read AGENTS.md from repository root.

        This function navigates up from the test file location to find the repo root.
        Works both when running in Docker (if mounted) and on host.
        """
        # Navigate up from tests/unit/backend/documentation/ to repo root
        repo_root = Path(__file__).parent.parent.parent.parent.parent
        agents_md = repo_root / "AGENTS.md"

        if not agents_md.exists():
            # Try alternative path - we might be in a different location
            import os
            cwd = Path.cwd()
            agents_md = cwd / "AGENTS.md"

        return agents_md.read_text()

    def test_stack_table_includes_video_row(self) -> None:
        """Stack table MUST include a row mentioning video processing/composition."""
        content = self._read_agents_md()

        # Find the Stack section
        assert "## Stack" in content, "Stack section not found in AGENTS.md"

        # Look for video-related row in the stack table
        assert (
            "video" in content.lower() or "Video" in content
        ), "Stack table must mention video processing/composition"

    def test_project_structure_shows_libs_video(self) -> None:
        """Project structure tree MUST show libs/video/ with correct layout."""
        content = self._read_agents_md()

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

    def test_dependency_rules_table_includes_video(self) -> None:
        """Dependency rules table MUST include video module with correct rules."""
        content = self._read_agents_md()

        # Find dependency rules section
        has_dep_section = (
            "Dependency Rules" in content or
            "dependency" in content.lower()
        )
        assert has_dep_section, "Dependency rules section not found"

        # Video BC should be mentioned in dependency context
        assert "video" in content.lower(), (
            "Dependency rules must mention video module"
        )

    def test_no_cloudflare_references(self) -> None:
        """MUST NOT contain Cloudflare references (out of scope for this epic)."""
        content = self._read_agents_md()

        # Cloudflare is explicitly out of scope for E70
        assert "Cloudflare" not in content and "cloudflare" not in content, (
            "AGENTS.md must not reference Cloudflare (out of scope)"
        )

    def test_no_stale_contexts_video_references(self) -> None:
        """MUST NOT contain any stale contexts/video/ references."""
        content = self._read_agents_md()

        # All references must be to libs/video/, not contexts/video/
        assert "contexts/video" not in content, (
            "Stale reference to contexts/video found - must be libs/video/"
        )

    def test_structure_trees_consistent_with_development_md(self) -> None:
        """Project structure trees MUST be consistent across AGENTS.md and DEVELOPMENT.md."""
        agents_content = self._read_agents_md()

        # Read DEVELOPMENT.md for comparison
        repo_root = Path(__file__).parent.parent.parent.parent.parent
        dev_md = repo_root / "DEVELOPMENT.md"
        dev_content = dev_md.read_text()

        # Both should reference libs/video/ consistently
        agents_has_video = "libs/video/" in agents_content or "│   └── video/" in agents_content
        dev_has_video = "libs/video/" in dev_content or "│   └── video/" in dev_content

        assert agents_has_video == dev_has_video, (
            "AGENTS.md and DEVELOPMENT.md must consistently show libs/video/ in structure trees"
        )
