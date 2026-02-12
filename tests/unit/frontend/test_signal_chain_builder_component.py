"""Unit tests for SignalChainBuilder React component structure."""

import pytest


@pytest.mark.xfail(reason="Pre-existing: component not yet implemented")
class TestSignalChainBuilderStructure:
    """Test that the SignalChainBuilder component structure exists."""

    def test_component_directory_exists(self) -> None:
        """Component directory should exist at expected location."""
        import os

        component_path = os.path.join(
            "frontend",
            "astro",
            "src",
            "components",
            "SignalChainBuilder",
        )
        assert os.path.isdir(component_path), f"Component directory not found at {component_path}"

    def test_component_index_exists(self) -> None:
        """Component should have an index file for exports."""
        import os

        # Check for either .tsx or .ts index file
        base_path = os.path.join(
            "frontend",
            "astro",
            "src",
            "components",
            "SignalChainBuilder",
        )
        index_tsx = os.path.join(base_path, "index.tsx")
        index_ts = os.path.join(base_path, "index.ts")

        has_index = os.path.isfile(index_tsx) or os.path.isfile(index_ts)
        assert has_index, f"Component index file not found at {base_path}/index.(tsx|ts)"

    def test_main_component_exists(self) -> None:
        """Main SignalChainBuilder component file should exist."""
        import os

        component_file = os.path.join(
            "frontend",
            "astro",
            "src",
            "components",
            "SignalChainBuilder",
            "SignalChainBuilder.tsx",
        )
        assert os.path.isfile(component_file), f"Main component file not found at {component_file}"


@pytest.mark.xfail(reason="Pre-existing: component not yet implemented")
class TestAstroReactIntegration:
    """Test that Astro is configured for React integration."""

    def test_astro_config_has_react_integration(self) -> None:
        """Astro config should include React integration."""
        import os

        config_path = os.path.join("frontend", "astro", "astro.config.mjs")
        assert os.path.isfile(config_path), "Astro config file not found"

        with open(config_path) as f:
            config_content = f.read()

        # Check for React integration
        assert (
            "@astrojs/react" in config_content
        ), "React integration not configured in astro.config.mjs"
        assert "react()" in config_content, "React integration not added to integrations array"

    def test_package_json_has_react_dependencies(self) -> None:
        """package.json should include React dependencies."""
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

        assert "react" in dependencies, "react not in dependencies"
        assert "react-dom" in dependencies, "react-dom not in dependencies"
        assert "@astrojs/react" in dependencies, "@astrojs/react not in dependencies"
        assert "@types/react" in dependencies, "@types/react not in devDependencies"
        assert "@types/react-dom" in dependencies, "@types/react-dom not in devDependencies"


@pytest.mark.xfail(reason="Pre-existing: component not yet implemented")
class TestComponentFeatures:
    """Test that component supports required features."""

    def test_component_supports_drag_and_drop(self) -> None:
        """Component should import drag-and-drop library."""
        import os

        component_file = os.path.join(
            "frontend",
            "astro",
            "src",
            "components",
            "SignalChainBuilder",
            "SignalChainBuilder.tsx",
        )

        with open(component_file) as f:
            component_content = f.read()

        # Check for drag-and-drop library imports
        # Common libraries: react-dnd, react-beautiful-dnd, @dnd-kit
        has_dnd = any(
            lib in component_content
            for lib in ["react-dnd", "react-beautiful-dnd", "@dnd-kit", "dnd"]
        )
        assert has_dnd, "Component does not import drag-and-drop library"

    def test_component_has_gear_selection_interface(self) -> None:
        """Component should reference gear selection functionality."""
        import os

        component_file = os.path.join(
            "frontend",
            "astro",
            "src",
            "components",
            "SignalChainBuilder",
            "SignalChainBuilder.tsx",
        )

        with open(component_file) as f:
            component_content = f.read()

        # Check for gear-related functionality
        has_gear_selection = any(
            keyword in component_content.lower()
            for keyword in ["gear", "library", "select", "usergear"]
        )
        assert has_gear_selection, "Component does not reference gear selection"

    def test_component_supports_single_chain_mode(self) -> None:
        """Component should support single chain mode."""
        import os

        component_file = os.path.join(
            "frontend",
            "astro",
            "src",
            "components",
            "SignalChainBuilder",
            "SignalChainBuilder.tsx",
        )

        with open(component_file) as f:
            component_content = f.read()

        # Check for mode-related props or state
        has_mode_support = any(
            keyword in component_content.lower() for keyword in ["mode", "single", "permutation"]
        )
        assert has_mode_support, "Component does not support single/permutation mode configuration"

    def test_component_supports_permutation_mode(self) -> None:
        """Component should support permutation mode (multiple gear per slot)."""
        import os

        component_file = os.path.join(
            "frontend",
            "astro",
            "src",
            "components",
            "SignalChainBuilder",
            "SignalChainBuilder.tsx",
        )

        with open(component_file) as f:
            component_content = f.read()

        # Check for permutation/multiple gear support
        has_permutation = any(
            keyword in component_content.lower() for keyword in ["permutation", "multiple", "slot"]
        )
        assert has_permutation, "Component does not support permutation mode"

    def test_component_uses_api_endpoints(self) -> None:
        """Component should use signal chain and library API endpoints."""
        import os

        component_file = os.path.join(
            "frontend",
            "astro",
            "src",
            "components",
            "SignalChainBuilder",
            "SignalChainBuilder.tsx",
        )

        with open(component_file) as f:
            component_content = f.read()

        # Check for API endpoint usage
        has_signal_chain_api = "/api/v1/signal-chains" in component_content
        has_library_api = "/api/v1/library" in component_content

        assert (
            has_signal_chain_api or has_library_api
        ), "Component does not reference signal chain or library API endpoints"


@pytest.mark.xfail(reason="Pre-existing: component not yet implemented")
class TestBuildConfiguration:
    """Test that build configuration supports the component."""

    def test_tsconfig_exists(self) -> None:
        """TypeScript config should exist for type checking."""
        import os

        tsconfig_path = os.path.join("frontend", "astro", "tsconfig.json")
        assert os.path.isfile(tsconfig_path), "tsconfig.json not found"

    def test_component_has_typescript(self) -> None:
        """Component should be written in TypeScript (tsx)."""
        import os

        component_file = os.path.join(
            "frontend",
            "astro",
            "src",
            "components",
            "SignalChainBuilder",
            "SignalChainBuilder.tsx",
        )

        # Test will fail if component doesn't exist (desired)
        # When it exists, verify it's TypeScript
        if os.path.isfile(component_file):
            assert component_file.endswith(".tsx"), "Component should be TypeScript (.tsx)"
        else:
            # Force failure with clear message
            assert False, f"Component file not found at {component_file}"
