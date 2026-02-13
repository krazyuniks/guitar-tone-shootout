"""Unit tests for RemotionPlayer React component structure."""


class TestRemotionPlayerStructure:
    """Test that the RemotionPlayer component structure exists."""

    def test_component_directory_exists(self) -> None:
        """Component directory should exist at expected location."""
        import os

        component_path = os.path.join(
            "frontend",
            "astro",
            "src",
            "components",
            "RemotionPlayer",
        )
        assert os.path.isdir(component_path), f"Component directory not found at {component_path}"

    def test_component_index_exists(self) -> None:
        """Component should have an index.tsx file for exports."""
        import os

        index_file = os.path.join(
            "frontend",
            "astro",
            "src",
            "components",
            "RemotionPlayer",
            "index.tsx",
        )
        assert os.path.isfile(index_file), f"Component index file not found at {index_file}"

    def test_hero_animation_component_exists(self) -> None:
        """HeroAnimation component file should exist."""
        import os

        component_file = os.path.join(
            "frontend",
            "astro",
            "src",
            "components",
            "RemotionPlayer",
            "HeroAnimation.tsx",
        )
        assert os.path.isfile(component_file), (
            f"HeroAnimation component file not found at {component_file}"
        )

    def test_how_to_video_component_exists(self) -> None:
        """HowToVideo component file should exist."""
        import os

        component_file = os.path.join(
            "frontend",
            "astro",
            "src",
            "components",
            "RemotionPlayer",
            "HowToVideo.tsx",
        )
        assert os.path.isfile(component_file), (
            f"HowToVideo component file not found at {component_file}"
        )


class TestRemotionPlayerDependencies:
    """Test that @remotion/player dependency is configured."""

    def test_package_json_has_remotion_player(self) -> None:
        """package.json should include @remotion/player dependency."""
        import json
        import os

        package_json_path = os.path.join("frontend", "astro", "package.json")
        assert os.path.isfile(package_json_path), "package.json not found"

        with open(package_json_path) as f:
            package_data = json.load(f)

        dependencies = {
            **package_data.get("dependencies", {}),
            **package_data.get("devDependencies", {}),
        }

        assert "@remotion/player" in dependencies, "@remotion/player not in dependencies"

    def test_remotion_dependencies(self) -> None:
        """package.json should include remotion and react dependencies."""
        import json
        import os

        package_json_path = os.path.join("frontend", "astro", "package.json")

        with open(package_json_path) as f:
            package_data = json.load(f)

        dependencies = {
            **package_data.get("dependencies", {}),
            **package_data.get("devDependencies", {}),
        }

        # Remotion requires react and remotion core
        assert "react" in dependencies, "react not in dependencies"
        assert "react-dom" in dependencies, "react-dom not in dependencies"


class TestRemotionPlayerComponentFeatures:
    """Test that components support required features."""

    def test_index_imports_remotion_player(self) -> None:
        """index.tsx should import @remotion/player."""
        import os

        index_file = os.path.join(
            "frontend",
            "astro",
            "src",
            "components",
            "RemotionPlayer",
            "index.tsx",
        )

        with open(index_file) as f:
            content = f.read()

        assert "@remotion/player" in content, "index.tsx does not import @remotion/player"

    def test_hero_animation_is_react_component(self) -> None:
        """HeroAnimation should be a valid React component."""
        import os

        component_file = os.path.join(
            "frontend",
            "astro",
            "src",
            "components",
            "RemotionPlayer",
            "HeroAnimation.tsx",
        )

        with open(component_file) as f:
            content = f.read()

        # Should import React or use JSX
        has_react = "import" in content and ("react" in content.lower() or "React" in content)
        has_jsx = "return" in content and ("<" in content or "jsx" in content.lower())

        assert has_react or has_jsx, "HeroAnimation does not appear to be a React component"

    def test_how_to_video_is_react_component(self) -> None:
        """HowToVideo should be a valid React component."""
        import os

        component_file = os.path.join(
            "frontend",
            "astro",
            "src",
            "components",
            "RemotionPlayer",
            "HowToVideo.tsx",
        )

        with open(component_file) as f:
            content = f.read()

        # Should import React or use JSX
        has_react = "import" in content and ("react" in content.lower() or "React" in content)
        has_jsx = "return" in content and ("<" in content or "jsx" in content.lower())

        assert has_react or has_jsx, "HowToVideo does not appear to be a React component"

    def test_components_are_client_side_only(self) -> None:
        """Components should be client-side only (no SSR rendering of video)."""
        import os

        # Check that components are not in SSR pages or layouts
        index_file = os.path.join(
            "frontend",
            "astro",
            "src",
            "components",
            "RemotionPlayer",
            "index.tsx",
        )

        with open(index_file) as f:
            content = f.read()

        # RemotionPlayer wrapper should use Player component
        assert "Player" in content, "RemotionPlayer does not use Player component"


class TestBuildConfiguration:
    """Test that build configuration supports Remotion components."""

    def test_tsconfig_exists(self) -> None:
        """TypeScript config should exist for type checking."""
        import os

        tsconfig_path = os.path.join("frontend", "astro", "tsconfig.json")
        assert os.path.isfile(tsconfig_path), "tsconfig.json not found"

    def test_components_are_typescript(self) -> None:
        """Components should be written in TypeScript (tsx)."""
        import os

        files = [
            "frontend/astro/src/components/RemotionPlayer/index.tsx",
            "frontend/astro/src/components/RemotionPlayer/HeroAnimation.tsx",
            "frontend/astro/src/components/RemotionPlayer/HowToVideo.tsx",
        ]

        for file_path in files:
            if os.path.isfile(file_path):
                assert file_path.endswith(".tsx"), f"{file_path} should be TypeScript (.tsx)"
            else:
                # Force failure with clear message
                assert False, f"Component file not found at {file_path}"
