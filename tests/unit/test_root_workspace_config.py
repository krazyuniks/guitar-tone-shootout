"""Unit tests for root workspace configuration.

Verifies that:
- Root pyproject.toml includes model/* in workspace members (covers model/video)
- Import-linter contracts enforce video dependency rules
"""

from pathlib import Path

import pytest


class TestRootWorkspaceConfig:
    """Test root pyproject.toml workspace configuration."""

    @pytest.fixture
    def root_pyproject(self) -> Path:
        """Path to root pyproject.toml."""
        return Path("pyproject.toml")

    def test_video_in_workspace_members(self, root_pyproject: Path) -> None:
        """model/* included in workspace members (covers model/video)."""
        content = root_pyproject.read_text()

        # Workspace members pattern should include model/*
        assert "[tool.uv.workspace]" in content, "must have [tool.uv.workspace] section"
        assert "members = [" in content, "must have workspace members list"

        # model/* pattern covers model/video
        assert '"model/*"' in content or "'model/*'" in content, (
            "workspace members must include model/* pattern"
        )

    def test_import_linter_has_video_package(self, root_pyproject: Path) -> None:
        """Import-linter root_packages includes video."""
        content = root_pyproject.read_text()

        assert "[tool.importlinter]" in content, "must have [tool.importlinter] section"
        assert "root_packages" in content, "must declare root_packages"

        # Video must be in root_packages list
        assert '"video"' in content or "'video'" in content, "root_packages must include video"

    def test_import_linter_video_isolation_contract(self, root_pyproject: Path) -> None:
        """Import-linter contract enforces video can only depend on gts."""
        content = root_pyproject.read_text()

        # Look for video-dependencies contract (similar to audio-dependencies)
        assert "[[tool.importlinter.contracts]]" in content, "must have contracts section"

        # Check for video-dependencies contract
        lines = content.splitlines()
        video_contract_found = False
        in_video_contract = False

        for i, line in enumerate(lines):
            if 'name = "video-dependencies"' in line or "name = 'video-dependencies'" in line:
                video_contract_found = True
                in_video_contract = True
                continue

            # If we found the video contract, check the next few lines
            if in_video_contract:
                # Look for type = forbidden
                if 'type = "forbidden"' in line or "type = 'forbidden'" in line:
                    continue

                # Look for source_modules = ["video"]
                if "source_modules" in line:
                    assert "video" in line, "source_modules must include video"
                    continue

                # Look for forbidden_modules
                if "forbidden_modules" in line:
                    # Should forbid: audio, source_t3k, webapp, worker, scheduler
                    # (video can only depend on gts)
                    next_line_idx = i + 1
                    # Collect the full forbidden_modules list (may span multiple lines)
                    forbidden_block = line
                    while next_line_idx < len(lines) and "]" not in forbidden_block:
                        forbidden_block += lines[next_line_idx]
                        next_line_idx += 1

                    # Verify forbidden modules
                    assert "audio" in forbidden_block, "video must not depend on audio"
                    assert "source_t3k" in forbidden_block, "video must not depend on source_t3k"
                    assert "webapp" in forbidden_block, "video must not depend on webapp"
                    assert "worker" in forbidden_block, "video must not depend on worker"

                    # Stop checking after finding forbidden_modules
                    break

                # If we hit another contract, stop looking
                if "[[tool.importlinter.contracts]]" in line:
                    break

        assert video_contract_found, "must have video-dependencies import-linter contract"
