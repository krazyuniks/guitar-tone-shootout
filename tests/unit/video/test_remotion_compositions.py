"""Unit tests for Remotion compositions (T75).

Verifies that the Remotion (React/TypeScript) composition files exist and have
correct structure for server-side video rendering.
"""

from pathlib import Path

import pytest


class TestRemotionCompositions:
    """Test Remotion composition file structure."""

    @pytest.fixture
    def remotion_dir(self) -> Path:
        """Path to model/video/src/video/remotion/ directory."""
        return Path("model/video/src/video/remotion")

    @pytest.fixture
    def compositions_dir(self, remotion_dir: Path) -> Path:
        """Path to compositions directory."""
        return remotion_dir / "compositions"

    def test_compositions_directory_exists(self, compositions_dir: Path) -> None:
        """model/video/src/video/remotion/compositions/ directory exists."""
        assert compositions_dir.exists(), "compositions/ directory must exist"
        assert compositions_dir.is_dir(), "compositions must be a directory"

    def test_shootout_video_composition_exists(self, compositions_dir: Path) -> None:
        """ShootoutVideo.tsx composition file exists."""
        shootout_video = compositions_dir / "ShootoutVideo.tsx"
        assert shootout_video.exists(), "ShootoutVideo.tsx must exist"
        assert shootout_video.is_file(), "ShootoutVideo.tsx must be a file"

    def test_gear_block_component_exists(self, compositions_dir: Path) -> None:
        """GearBlock.tsx component file exists."""
        gear_block = compositions_dir / "GearBlock.tsx"
        assert gear_block.exists(), "GearBlock.tsx must exist"
        assert gear_block.is_file(), "GearBlock.tsx must be a file"

    def test_signal_chain_segment_component_exists(self, compositions_dir: Path) -> None:
        """SignalChainSegment.tsx component file exists."""
        signal_chain = compositions_dir / "SignalChainSegment.tsx"
        assert signal_chain.exists(), "SignalChainSegment.tsx must exist"
        assert signal_chain.is_file(), "SignalChainSegment.tsx must be a file"

    def test_slide_transition_component_exists(self, compositions_dir: Path) -> None:
        """SlideTransition.tsx component file exists."""
        slide_transition = compositions_dir / "SlideTransition.tsx"
        assert slide_transition.exists(), "SlideTransition.tsx must exist"
        assert slide_transition.is_file(), "SlideTransition.tsx must be a file"

    def test_metadata_overlay_component_exists(self, compositions_dir: Path) -> None:
        """MetadataOverlay.tsx component file exists."""
        metadata_overlay = compositions_dir / "MetadataOverlay.tsx"
        assert metadata_overlay.exists(), "MetadataOverlay.tsx must exist"
        assert metadata_overlay.is_file(), "MetadataOverlay.tsx must be a file"

    def test_remotion_root_exists(self, remotion_dir: Path) -> None:
        """Root.tsx file exists at remotion root."""
        root_file = remotion_dir / "Root.tsx"
        assert root_file.exists(), "Root.tsx must exist"
        assert root_file.is_file(), "Root.tsx must be a file"

    def test_remotion_index_exists(self, remotion_dir: Path) -> None:
        """index.ts file exists at remotion root."""
        index_file = remotion_dir / "index.ts"
        assert index_file.exists(), "index.ts must exist"
        assert index_file.is_file(), "index.ts must be a file"


class TestShootoutVideoComposition:
    """Test ShootoutVideo composition content."""

    @pytest.fixture
    def shootout_video_file(self) -> Path:
        """Path to ShootoutVideo.tsx file."""
        return Path("model/video/src/video/remotion/compositions/ShootoutVideo.tsx")

    def test_shootout_video_imports_react(self, shootout_video_file: Path) -> None:
        """ShootoutVideo.tsx imports React."""
        content = shootout_video_file.read_text()
        assert "import" in content, "ShootoutVideo.tsx must have imports"
        assert "react" in content.lower(), "ShootoutVideo.tsx must import React"

    def test_shootout_video_exports_component(self, shootout_video_file: Path) -> None:
        """ShootoutVideo.tsx exports a component."""
        content = shootout_video_file.read_text()
        assert "export" in content, "ShootoutVideo.tsx must export a component"
        # Must have either named or default export
        has_export = (
            "export default" in content
            or "export const ShootoutVideo" in content
            or "export function ShootoutVideo" in content
        )
        assert has_export, "ShootoutVideo.tsx must export ShootoutVideo component"


class TestGearBlockComponent:
    """Test GearBlock component content."""

    @pytest.fixture
    def gear_block_file(self) -> Path:
        """Path to GearBlock.tsx file."""
        return Path("model/video/src/video/remotion/compositions/GearBlock.tsx")

    def test_gear_block_imports_react(self, gear_block_file: Path) -> None:
        """GearBlock.tsx imports React."""
        content = gear_block_file.read_text()
        assert "import" in content, "GearBlock.tsx must have imports"
        assert "react" in content.lower(), "GearBlock.tsx must import React"

    def test_gear_block_exports_component(self, gear_block_file: Path) -> None:
        """GearBlock.tsx exports a component."""
        content = gear_block_file.read_text()
        assert "export" in content, "GearBlock.tsx must export a component"
        # Must have either named or default export
        has_export = (
            "export default" in content
            or "export const GearBlock" in content
            or "export function GearBlock" in content
        )
        assert has_export, "GearBlock.tsx must export GearBlock component"

    def test_gear_block_has_props_interface(self, gear_block_file: Path) -> None:
        """GearBlock.tsx defines props interface."""
        content = gear_block_file.read_text()
        # Must have interface or type definition for props
        has_props = (
            "interface" in content or "type GearBlockProps" in content or ": React.FC<" in content
        )
        assert has_props, "GearBlock.tsx must define props interface or type"


class TestSignalChainSegmentComponent:
    """Test SignalChainSegment component content."""

    @pytest.fixture
    def signal_chain_file(self) -> Path:
        """Path to SignalChainSegment.tsx file."""
        return Path("model/video/src/video/remotion/compositions/SignalChainSegment.tsx")

    def test_signal_chain_imports_react(self, signal_chain_file: Path) -> None:
        """SignalChainSegment.tsx imports React."""
        content = signal_chain_file.read_text()
        assert "import" in content, "SignalChainSegment.tsx must have imports"
        assert "react" in content.lower(), "SignalChainSegment.tsx must import React"

    def test_signal_chain_exports_component(self, signal_chain_file: Path) -> None:
        """SignalChainSegment.tsx exports a component."""
        content = signal_chain_file.read_text()
        assert "export" in content, "SignalChainSegment.tsx must export a component"
        # Must have either named or default export
        has_export = (
            "export default" in content
            or "export const SignalChainSegment" in content
            or "export function SignalChainSegment" in content
        )
        assert has_export, "SignalChainSegment.tsx must export SignalChainSegment component"


class TestSlideTransitionComponent:
    """Test SlideTransition component content."""

    @pytest.fixture
    def slide_transition_file(self) -> Path:
        """Path to SlideTransition.tsx file."""
        return Path("model/video/src/video/remotion/compositions/SlideTransition.tsx")

    def test_slide_transition_imports_react(self, slide_transition_file: Path) -> None:
        """SlideTransition.tsx imports React."""
        content = slide_transition_file.read_text()
        assert "import" in content, "SlideTransition.tsx must have imports"
        assert "react" in content.lower(), "SlideTransition.tsx must import React"

    def test_slide_transition_exports_component(self, slide_transition_file: Path) -> None:
        """SlideTransition.tsx exports a component."""
        content = slide_transition_file.read_text()
        assert "export" in content, "SlideTransition.tsx must export a component"
        # Must have either named or default export
        has_export = (
            "export default" in content
            or "export const SlideTransition" in content
            or "export function SlideTransition" in content
        )
        assert has_export, "SlideTransition.tsx must export SlideTransition component"


class TestMetadataOverlayComponent:
    """Test MetadataOverlay component content."""

    @pytest.fixture
    def metadata_overlay_file(self) -> Path:
        """Path to MetadataOverlay.tsx file."""
        return Path("model/video/src/video/remotion/compositions/MetadataOverlay.tsx")

    def test_metadata_overlay_imports_react(self, metadata_overlay_file: Path) -> None:
        """MetadataOverlay.tsx imports React."""
        content = metadata_overlay_file.read_text()
        assert "import" in content, "MetadataOverlay.tsx must have imports"
        assert "react" in content.lower(), "MetadataOverlay.tsx must import React"

    def test_metadata_overlay_exports_component(self, metadata_overlay_file: Path) -> None:
        """MetadataOverlay.tsx exports a component."""
        content = metadata_overlay_file.read_text()
        assert "export" in content, "MetadataOverlay.tsx must export a component"
        # Must have either named or default export
        has_export = (
            "export default" in content
            or "export const MetadataOverlay" in content
            or "export function MetadataOverlay" in content
        )
        assert has_export, "MetadataOverlay.tsx must export MetadataOverlay component"


class TestRemotionRootRegistration:
    """Test Remotion Root.tsx composition registration."""

    @pytest.fixture
    def root_file(self) -> Path:
        """Path to Root.tsx file."""
        return Path("model/video/src/video/remotion/Root.tsx")

    def test_root_imports_remotion(self, root_file: Path) -> None:
        """Root.tsx imports Remotion."""
        content = root_file.read_text()
        assert "import" in content, "Root.tsx must have imports"
        assert "remotion" in content.lower(), "Root.tsx must import from remotion"

    def test_root_imports_shootout_video(self, root_file: Path) -> None:
        """Root.tsx imports ShootoutVideo composition."""
        content = root_file.read_text()
        assert "ShootoutVideo" in content, "Root.tsx must import ShootoutVideo composition"

    def test_root_registers_composition(self, root_file: Path) -> None:
        """Root.tsx registers composition with Remotion."""
        content = root_file.read_text()
        # Remotion uses <Composition> component to register
        has_composition = "<Composition" in content or "Composition(" in content
        assert has_composition, "Root.tsx must register composition using Remotion's Composition"

    def test_root_exports_default(self, root_file: Path) -> None:
        """Root.tsx exports a default component."""
        content = root_file.read_text()
        assert "export default" in content, "Root.tsx must have default export"


class TestRemotionIndexEntry:
    """Test Remotion index.ts entry point."""

    @pytest.fixture
    def index_file(self) -> Path:
        """Path to index.ts file."""
        return Path("model/video/src/video/remotion/index.ts")

    def test_index_exports_root(self, index_file: Path) -> None:
        """index.ts exports Root or re-exports from Root."""
        content = index_file.read_text()
        # Must either export or re-export Root
        has_root_export = "export" in content and ("Root" in content or "from './Root'" in content)
        assert has_root_export, "index.ts must export or re-export Root"
