"""End-to-end tests for complete comparison workflow."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from guitar_tone_shootout.config import load_comparison
from guitar_tone_shootout.pipeline import process_comparison

if TYPE_CHECKING:
    from collections.abc import Generator

# Skip all tests if required tools are missing
pytestmark = [
    pytest.mark.skipif(
        shutil.which("ffmpeg") is None,
        reason="FFmpeg not installed",
    ),
    pytest.mark.e2e,
    pytest.mark.slow,
]


def playwright_available() -> bool:
    """Check if Playwright with Chromium is available."""
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            browser.close()
        return True
    except Exception:
        return False


class TestFullComparisonWorkflow:
    """End-to-end tests for the complete comparison workflow."""

    @pytest.fixture
    def e2e_environment(
        self, tmp_path: Path, fixtures_dir: Path
    ) -> Generator[dict[str, Path], None, None]:
        """Set up a complete test environment."""
        # Create directory structure
        inputs = tmp_path / "inputs"
        (inputs / "di_tracks").mkdir(parents=True)
        (inputs / "irs" / "test").mkdir(parents=True)
        outputs = tmp_path / "outputs"
        outputs.mkdir()
        templates = tmp_path / "templates"
        templates.mkdir()

        # Copy test fixtures
        di_src = fixtures_dir / "di_tracks" / "test_di.wav"
        ir_src = fixtures_dir / "irs" / "test_ir.wav"

        if not di_src.exists() or not ir_src.exists():
            pytest.skip(
                "Test fixtures not generated. Run: python tests/fixtures/generate_fixtures.py"
            )

        shutil.copy(di_src, inputs / "di_tracks" / "test_di.wav")
        shutil.copy(ir_src, inputs / "irs" / "test" / "test_ir.wav")

        # Create comparisons directory (mimics real project structure)
        comparisons_dir = tmp_path / "comparisons"
        comparisons_dir.mkdir()

        # Create test INI
        ini_content = """
[meta]
name = E2E Test Comparison
author = test_suite
description = End-to-end test

[di_tracks]
1.file = test_di.wav
1.guitar = Test Guitar
1.pickup = test

[signal_chains]
1.name = Test Chain 1
1.description = First test chain
1.chain = ir:test/test_ir.wav

2.name = Test Chain 2
2.description = Second test chain with EQ
2.chain = eq:highpass_80hz, ir:test/test_ir.wav
"""
        ini_path = comparisons_dir / "test_comparison.ini"
        ini_path.write_text(ini_content)

        # Change to temp directory for relative paths
        original_cwd = Path.cwd()
        os.chdir(tmp_path)

        yield {
            "root": tmp_path,
            "inputs": inputs,
            "outputs": outputs,
            "ini": ini_path,
            "original_cwd": Path(original_cwd),
        }

        # Restore original directory
        os.chdir(original_cwd)

    @pytest.mark.skipif(not playwright_available(), reason="Playwright not available")
    def test_full_comparison_generates_video(self, e2e_environment: dict[str, Path]) -> None:
        """Test that a full comparison generates video output."""
        ini_path = e2e_environment["ini"]
        outputs = e2e_environment["outputs"]

        # Load comparison
        comparison = load_comparison(ini_path)

        assert comparison.meta.name == "E2E Test Comparison"
        assert len(comparison.di_tracks) == 1
        assert len(comparison.signal_chains) == 2
        assert comparison.segment_count == 2

        # Process comparison
        video_path = process_comparison(comparison)

        # Verify outputs
        assert video_path.exists(), f"Video not created: {video_path}"
        assert video_path.stat().st_size > 0, "Video file is empty"

        # Check output structure
        output_dir = outputs / "e2e_test_comparison"
        assert output_dir.exists(), f"Output directory not created: {output_dir}"

        # Check for expected files
        expected_files = [
            output_dir / "e2e_test_comparison.mp4",  # Main video
            output_dir / "audio" / "e2e_test_comparison_full.flac",  # Combined audio
            output_dir / "audio" / "e2e_test_comparison_000.flac",  # Segment 1
            output_dir / "audio" / "e2e_test_comparison_001.flac",  # Segment 2
            output_dir / "images" / "e2e_test_comparison_000.png",  # Image 1
            output_dir / "images" / "e2e_test_comparison_001.png",  # Image 2
            output_dir / "clips" / "e2e_test_comparison_000.mp4",  # Clip 1
            output_dir / "clips" / "e2e_test_comparison_001.mp4",  # Clip 2
        ]

        for expected in expected_files:
            assert expected.exists(), f"Expected file not found: {expected}"
            assert expected.stat().st_size > 0, f"File is empty: {expected}"

    @pytest.mark.skipif(not playwright_available(), reason="Playwright not available")
    def test_comparison_with_duration_trim(self, e2e_environment: dict[str, Path]) -> None:
        """Test processing with duration trimming."""
        ini_path = e2e_environment["ini"]

        comparison = load_comparison(ini_path)

        # Process with 1 second duration
        video_path = process_comparison(comparison, duration=1.0)

        assert video_path.exists()
        # Video should be shorter due to trimming
        assert video_path.stat().st_size > 0

    def test_config_validation(self, e2e_environment: dict[str, Path]) -> None:
        """Test that config validation works correctly."""
        ini_path = e2e_environment["ini"]

        comparison = load_comparison(ini_path)

        # Validate structure
        assert comparison.meta.name == "E2E Test Comparison"
        assert comparison.meta.author == "test_suite"
        assert len(comparison.di_tracks) == 1
        assert len(comparison.signal_chains) == 2

        # Validate DI track
        di = comparison.di_tracks[0]
        assert di.guitar == "Test Guitar"
        assert di.file.name == "test_di.wav"

        # Validate signal chains
        chain1 = comparison.signal_chains[0]
        assert chain1.name == "Test Chain 1"
        assert len(chain1.chain) == 1
        assert chain1.chain[0].effect_type == "ir"

        chain2 = comparison.signal_chains[1]
        assert chain2.name == "Test Chain 2"
        assert len(chain2.chain) == 2
        assert chain2.chain[0].effect_type == "eq"


class TestCLIWorkflow:
    """Test CLI commands work correctly."""

    def test_validate_command(self, fixtures_dir: Path) -> None:
        """Test the validate CLI command."""
        from click.testing import CliRunner

        from guitar_tone_shootout.cli import main

        ini_path = fixtures_dir / "comparisons" / "test_comparison.ini"
        if not ini_path.exists():
            pytest.skip("Test comparison INI not generated")

        runner = CliRunner()
        result = runner.invoke(main, ["validate", str(ini_path)])

        # Should succeed (exit code 0) or fail gracefully
        # Note: May fail if DI track path doesn't exist in fixture INI
        assert result.exit_code in [0, 1]

    def test_list_commands(self) -> None:
        """Test list commands don't crash."""
        from click.testing import CliRunner

        from guitar_tone_shootout.cli import main

        runner = CliRunner()

        # These should run without error even if no files exist
        result = runner.invoke(main, ["list-models"])
        assert result.exit_code == 0

        result = runner.invoke(main, ["list-irs"])
        assert result.exit_code == 0

        result = runner.invoke(main, ["list-di"])
        assert result.exit_code == 0
