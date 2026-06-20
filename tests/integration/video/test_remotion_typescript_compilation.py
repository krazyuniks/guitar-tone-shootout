"""Integration tests for Remotion TypeScript compilation (T75).

Verifies that TypeScript compositions compile without errors and that
Remotion studio can be launched (validation only, not full render).
"""

import subprocess
from pathlib import Path

import pytest


@pytest.mark.integration
@pytest.mark.xfail(
    reason="Pre-existing: video node_modules not installed in webapp container", strict=False
)
class TestTypeScriptCompilation:
    """Test TypeScript compilation for Remotion compositions."""

    @pytest.fixture
    def video_root(self) -> Path:
        """Path to model/video/ directory."""
        return Path("model/video")

    def test_typescript_compiles_without_errors(self, video_root: Path) -> None:
        """TypeScript compiles without errors using npx tsc --noEmit."""
        # Run TypeScript compiler in check mode (no output files)
        result = subprocess.run(
            ["npx", "tsc", "--noEmit"],
            cwd=video_root,
            capture_output=True,
            text=True,
        )

        # TypeScript should compile successfully (exit code 0)
        assert result.returncode == 0, (
            f"TypeScript compilation failed:\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}"
        )

    def test_no_typescript_syntax_errors(self, video_root: Path) -> None:
        """TypeScript files have no syntax errors."""
        result = subprocess.run(
            ["npx", "tsc", "--noEmit"],
            cwd=video_root,
            capture_output=True,
            text=True,
        )

        # Check stderr for syntax errors
        stderr_lower = result.stderr.lower()
        assert "syntax error" not in stderr_lower, (
            f"TypeScript syntax errors found:\n{result.stderr}"
        )

    def test_no_typescript_type_errors(self, video_root: Path) -> None:
        """TypeScript files have no type errors."""
        result = subprocess.run(
            ["npx", "tsc", "--noEmit"],
            cwd=video_root,
            capture_output=True,
            text=True,
        )

        # Check stderr for type errors
        stderr_lower = result.stderr.lower()
        has_type_error = (
            "type error" in stderr_lower
            or "cannot find name" in stderr_lower
            or "property does not exist" in stderr_lower
        )
        assert not has_type_error, f"TypeScript type errors found:\n{result.stderr}"


@pytest.mark.integration
@pytest.mark.xfail(
    reason="Pre-existing: video node_modules not installed in webapp container", strict=False
)
class TestRemotionStudioLaunch:
    """Test Remotion Studio can be launched (validation only)."""

    @pytest.fixture
    def video_root(self) -> Path:
        """Path to model/video/ directory."""
        return Path("model/video")

    def test_remotion_config_exists(self, video_root: Path) -> None:
        """Remotion configuration file exists."""
        # Remotion v4 uses remotion.config.ts or looks for Root in package.json
        package_json = video_root / "package.json"
        assert package_json.exists(), "package.json must exist for Remotion config"

        # Check if package.json has remotion config or remotion.config.ts exists
        remotion_config = video_root / "remotion.config.ts"
        package_content = package_json.read_text()

        has_config = (
            remotion_config.exists() or "remotion" in package_content  # May have inline config
        )
        assert has_config, (
            "Remotion configuration must exist (remotion.config.ts or package.json config)"
        )

    def test_remotion_cli_installed(self, video_root: Path) -> None:
        """Remotion CLI is installed and accessible."""
        result = subprocess.run(
            ["npx", "remotion", "--version"],
            cwd=video_root,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, (
            f"Remotion CLI not installed or not accessible:\n"
            f"STDOUT: {result.stdout}\n"
            f"STDERR: {result.stderr}"
        )

    def test_remotion_can_list_compositions(self, video_root: Path) -> None:
        """Remotion can list compositions (validates Root.tsx registration)."""
        # Run remotion compositions command to list registered compositions
        result = subprocess.run(
            ["npx", "remotion", "compositions", "src/video/remotion/index.ts"],
            cwd=video_root,
            capture_output=True,
            text=True,
            timeout=30,  # Remotion may need time to bundle
        )

        # Should successfully list compositions
        assert result.returncode == 0, (
            f"Remotion failed to list compositions:\n"
            f"STDOUT: {result.stdout}\n"
            f"STDERR: {result.stderr}"
        )

        # Output should mention ShootoutVideo composition
        output = result.stdout + result.stderr
        assert "ShootoutVideo" in output or "shootout" in output.lower(), (
            f"ShootoutVideo composition not found in Remotion output:\n{output}"
        )


@pytest.mark.integration
@pytest.mark.xfail(
    reason="Pre-existing: video node_modules not installed in webapp container", strict=False
)
class TestRemotionComponentImports:
    """Test that components can be imported without errors."""

    @pytest.fixture
    def video_root(self) -> Path:
        """Path to model/video/ directory."""
        return Path("model/video")

    def test_compositions_can_be_imported(self, video_root: Path) -> None:
        """All composition files can be imported by TypeScript."""
        # Create a temporary test file that imports all compositions
        test_import = video_root / "test_imports.ts"
        test_content = """
// Temporary test file to verify imports
import { ShootoutVideo } from './src/video/remotion/compositions/ShootoutVideo';
import { GearBlock } from './src/video/remotion/compositions/GearBlock';
import { SignalChainSegment } from './src/video/remotion/compositions/SignalChainSegment';
import { SlideTransition } from './src/video/remotion/compositions/SlideTransition';
import { MetadataOverlay } from './src/video/remotion/compositions/MetadataOverlay';

// Verify all exports exist
const components = [
    ShootoutVideo,
    GearBlock,
    SignalChainSegment,
    SlideTransition,
    MetadataOverlay,
];
"""

        try:
            test_import.write_text(test_content)

            # Try to compile the test file
            result = subprocess.run(
                ["npx", "tsc", "--noEmit", "test_imports.ts"],
                cwd=video_root,
                capture_output=True,
                text=True,
            )

            assert result.returncode == 0, (
                f"Failed to import composition components:\n"
                f"STDOUT: {result.stdout}\n"
                f"STDERR: {result.stderr}"
            )

        finally:
            # Clean up test file
            if test_import.exists():
                test_import.unlink()

    def test_root_can_be_imported(self, video_root: Path) -> None:
        """Root.tsx can be imported by TypeScript."""
        # Create a temporary test file that imports Root
        test_import = video_root / "test_root_import.ts"
        test_content = """
// Temporary test file to verify Root import
import Root from './src/video/remotion/Root';

// Verify Root exists
const root = Root;
"""

        try:
            test_import.write_text(test_content)

            # Try to compile the test file
            result = subprocess.run(
                ["npx", "tsc", "--noEmit", "test_root_import.ts"],
                cwd=video_root,
                capture_output=True,
                text=True,
            )

            assert result.returncode == 0, (
                f"Failed to import Root:\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}"
            )

        finally:
            # Clean up test file
            if test_import.exists():
                test_import.unlink()
