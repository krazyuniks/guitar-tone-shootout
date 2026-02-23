"""Unit tests for model/video/ package structure.

Verifies that the video package scaffold exists with correct structure:
- Python package (pyproject.toml, __init__.py)
- Node.js package (package.json, tsconfig.json)
- Remotion scaffold
"""

from pathlib import Path

import pytest


class TestVideoPackageStructure:
    """Test model/video/ package structure."""

    @pytest.fixture
    def video_root(self) -> Path:
        """Path to model/video/ directory."""
        return Path("model/video")

    @pytest.fixture
    def video_src(self, video_root: Path) -> Path:
        """Path to model/video/src/video/ directory."""
        return video_root / "src" / "video"

    def test_video_directory_exists(self, video_root: Path) -> None:
        """model/video/ directory exists."""
        assert video_root.exists(), "model/video/ directory must exist"
        assert video_root.is_dir(), "model/video/ must be a directory"

    def test_pyproject_toml_exists(self, video_root: Path) -> None:
        """model/video/pyproject.toml exists."""
        pyproject = video_root / "pyproject.toml"
        assert pyproject.exists(), "model/video/pyproject.toml must exist"
        assert pyproject.is_file(), "pyproject.toml must be a file"

    def test_pyproject_toml_has_correct_config(self, video_root: Path) -> None:
        """model/video/pyproject.toml has correct uv workspace config."""
        pyproject = video_root / "pyproject.toml"
        content = pyproject.read_text()

        # Must have project name
        assert "[project]" in content, "pyproject.toml must have [project] section"
        assert 'name = "gts-video"' in content, "project name must be gts-video"

        # Must depend on a gts workspace package
        assert "gts-domain" in content or "gts-core" in content, (
            "gts-video must depend on a gts workspace package (gts-domain or gts-core)"
        )

        # Must have workspace source config
        assert "[tool.uv.sources]" in content, "must have [tool.uv.sources] section"

        # Must have build-system config
        assert "[build-system]" in content, "must have [build-system] section"
        assert "hatchling" in content, "must use hatchling build backend"

    def test_python_package_init_exists(self, video_src: Path) -> None:
        """model/video/src/video/__init__.py exists."""
        init_file = video_src / "__init__.py"
        assert init_file.exists(), "src/video/__init__.py must exist"
        assert init_file.is_file(), "__init__.py must be a file"

    def test_remotion_package_exists(self, video_src: Path) -> None:
        """model/video/src/video/remotion/ package exists."""
        remotion_dir = video_src / "remotion"
        assert remotion_dir.exists(), "src/video/remotion/ directory must exist"
        assert remotion_dir.is_dir(), "remotion must be a directory"

    def test_package_json_exists(self, video_root: Path) -> None:
        """model/video/package.json exists."""
        package_json = video_root / "package.json"
        assert package_json.exists(), "package.json must exist"
        assert package_json.is_file(), "package.json must be a file"

    def test_package_json_has_remotion_dependencies(self, video_root: Path) -> None:
        """model/video/package.json declares remotion dependencies."""
        import json

        package_json = video_root / "package.json"
        data = json.loads(package_json.read_text())

        assert "dependencies" in data or "devDependencies" in data, (
            "package.json must have dependencies or devDependencies"
        )

        # Check for remotion in either dependencies or devDependencies
        all_deps = {}
        if "dependencies" in data:
            all_deps.update(data["dependencies"])
        if "devDependencies" in data:
            all_deps.update(data["devDependencies"])

        assert "remotion" in all_deps, "must declare remotion dependency"
        assert "@remotion/cli" in all_deps, "must declare @remotion/cli dependency"

    def test_tsconfig_json_exists(self, video_root: Path) -> None:
        """model/video/tsconfig.json exists."""
        tsconfig = video_root / "tsconfig.json"
        assert tsconfig.exists(), "tsconfig.json must exist"
        assert tsconfig.is_file(), "tsconfig.json must be a file"

    def test_tsconfig_json_configured_for_react_typescript(self, video_root: Path) -> None:
        """model/video/tsconfig.json configured for React/TypeScript."""
        import json

        tsconfig = video_root / "tsconfig.json"
        data = json.loads(tsconfig.read_text())

        assert "compilerOptions" in data, "tsconfig.json must have compilerOptions"
        compiler_opts = data["compilerOptions"]

        # Must have JSX configured for React
        assert "jsx" in compiler_opts, "must configure jsx"
        # Common values: "react", "react-jsx", "react-jsxdev"
        assert "react" in compiler_opts["jsx"].lower(), "jsx must be configured for React"

        # Must have module resolution
        assert "moduleResolution" in compiler_opts, "must configure moduleResolution"
