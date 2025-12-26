"""End-to-end workflow tests."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import pytest
from click.testing import CliRunner
from pedalboard.io import AudioFile

from guitar_tone_shootout.cli import main
from guitar_tone_shootout.config import load_comparison
from guitar_tone_shootout.pipeline import process_comparison

if TYPE_CHECKING:
    from collections.abc import Generator


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


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def e2e_environment(tmp_path: Path) -> Generator[dict[str, Path], None, None]:
    """Set up a complete test environment with DI track and IR."""
    # Create directory structure
    inputs = tmp_path / "inputs"
    (inputs / "di_tracks").mkdir(parents=True)
    (inputs / "irs" / "test").mkdir(parents=True)
    outputs = tmp_path / "outputs"
    outputs.mkdir()

    # Create test DI track (1 second of audio)
    di_path = inputs / "di_tracks" / "test_di.wav"
    sample_rate = 44100
    t = np.linspace(0, 1, sample_rate, endpoint=False)
    audio = (0.5 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    with AudioFile(str(di_path), "w", samplerate=sample_rate, num_channels=1) as af:
        af.write(audio.reshape(1, -1))

    # Create test IR (simple impulse)
    ir_path = inputs / "irs" / "test" / "test_ir.wav"
    ir_data = np.zeros((1, 4096), dtype=np.float32)
    ir_data[0, 0] = 1.0
    with AudioFile(str(ir_path), "w", samplerate=sample_rate, num_channels=1) as af:
        af.write(ir_data)

    # Create comparison INI
    comparisons_dir = tmp_path / "comparisons"
    comparisons_dir.mkdir()

    ini_content = """
[meta]
name = E2E Test
author = test_suite

[di_tracks]
1.file = test_di.wav
1.guitar = Test Guitar
1.pickup = test

[signal_chains]
1.name = Test Chain
1.description = Simple test
1.chain = ir:test/test_ir.wav
"""
    ini_path = comparisons_dir / "test.ini"
    ini_path.write_text(ini_content)

    # Change to temp directory for relative paths
    original_cwd = Path.cwd()
    os.chdir(tmp_path)

    yield {
        "root": tmp_path,
        "inputs": inputs,
        "outputs": outputs,
        "ini": ini_path,
    }

    os.chdir(original_cwd)


# =============================================================================
# Workflow Tests
# =============================================================================


@pytest.mark.skipif(not playwright_available(), reason="Playwright not available")
def test_full_comparison_workflow(e2e_environment: dict[str, Path]) -> None:
    """Test complete comparison workflow generates all expected outputs."""
    ini_path = e2e_environment["ini"]
    outputs = e2e_environment["outputs"]

    # Load and process
    comparison = load_comparison(ini_path)
    video_path = process_comparison(comparison)

    # Verify main video
    assert video_path.exists()
    assert video_path.stat().st_size > 0

    # Verify output structure
    output_dir = outputs / "e2e_test"
    assert output_dir.exists()

    # Check expected files
    expected = [
        output_dir / "e2e_test.mp4",
        output_dir / "audio" / "e2e_test_000.flac",
        output_dir / "audio" / "e2e_test_full.flac",
        output_dir / "images" / "e2e_test_000.png",
        output_dir / "clips" / "e2e_test_000.mp4",
    ]

    for path in expected:
        assert path.exists(), f"Missing: {path}"
        assert path.stat().st_size > 0, f"Empty: {path}"


# =============================================================================
# CLI Tests
# =============================================================================


def test_cli_list_commands() -> None:
    """Test list commands run without error."""
    runner = CliRunner()

    for cmd in ["list-models", "list-irs", "list-di"]:
        result = runner.invoke(main, [cmd])
        assert result.exit_code == 0
