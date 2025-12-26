"""
Pytest configuration and shared fixtures.

Test Organization:
- unit/: Fast tests with mocked dependencies
- integration/: Tests with real dependencies (FFmpeg, Playwright)
- e2e/: Full end-to-end workflow tests

Run specific test categories:
    pytest -m unit          # Fast unit tests only
    pytest -m integration   # Integration tests (requires FFmpeg)
    pytest -m e2e           # End-to-end tests (requires all deps)
    pytest                  # All tests
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import pytest

if TYPE_CHECKING:
    from collections.abc import Generator


# =============================================================================
# Pytest Configuration
# =============================================================================


def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers."""
    config.addinivalue_line("markers", "unit: Fast unit tests with mocked dependencies")
    config.addinivalue_line("markers", "integration: Integration tests requiring real dependencies")
    config.addinivalue_line("markers", "e2e: End-to-end workflow tests")
    config.addinivalue_line("markers", "slow: Tests that take more than 5 seconds")


def pytest_collection_modifyitems(
    config: pytest.Config,  # noqa: ARG001
    items: list[pytest.Item],
) -> None:
    """Auto-mark tests based on their location."""
    for item in items:
        # Get the test file path relative to tests/
        test_path = Path(item.fspath).relative_to(Path(__file__).parent)
        parts = test_path.parts

        if "unit" in parts:
            item.add_marker(pytest.mark.unit)
        elif "integration" in parts:
            item.add_marker(pytest.mark.integration)
        elif "e2e" in parts:
            item.add_marker(pytest.mark.e2e)
            item.add_marker(pytest.mark.slow)


# =============================================================================
# Path Fixtures
# =============================================================================


@pytest.fixture
def fixtures_dir() -> Path:
    """Path to test fixtures directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def test_di_track(fixtures_dir: Path) -> Path:
    """Path to test DI track WAV file."""
    return fixtures_dir / "di_tracks" / "test_di.wav"


@pytest.fixture
def test_ir(fixtures_dir: Path) -> Path:
    """Path to test impulse response WAV file."""
    return fixtures_dir / "irs" / "test_ir.wav"


@pytest.fixture
def test_nam_model(fixtures_dir: Path) -> Path:
    """Path to test NAM model file."""
    return fixtures_dir / "nam_models" / "test_model.nam"


@pytest.fixture
def test_comparison_ini(fixtures_dir: Path) -> Path:
    """Path to test comparison INI file."""
    return fixtures_dir / "comparisons" / "test_comparison.ini"


# =============================================================================
# Real Test Fixtures (for full e2e tests - not committed to git)
# =============================================================================


@pytest.fixture
def real_fixtures_dir(fixtures_dir: Path) -> Path:
    """Path to real test fixtures (inputs/) directory."""
    return fixtures_dir / "inputs"


@pytest.fixture
def real_di_track(real_fixtures_dir: Path) -> Path:
    """Path to real DI track (gojira_left.wav)."""
    path = real_fixtures_dir / "di_tracks" / "gojira_left.wav"
    if not path.exists():
        pytest.skip("Real DI track not available (gojira_left.wav)")
    return path


@pytest.fixture
def real_nam_model(real_fixtures_dir: Path) -> Path:
    """Path to real NAM model (JCM800)."""
    path = real_fixtures_dir / "nam_models" / "tone3000" / "jcm800-44269" / "JCM800 capture 3.nam"
    if not path.exists():
        pytest.skip("Real NAM model not available (JCM800 capture 3.nam)")
    return path


@pytest.fixture
def real_ir(real_fixtures_dir: Path) -> Path:
    """Path to real IR (mesa fav.wav)."""
    path = real_fixtures_dir / "irs" / "tone3000" / "good-mesa-ir-5781" / "mesa fav.wav"
    if not path.exists():
        pytest.skip("Real IR not available (mesa fav.wav)")
    return path


@pytest.fixture
def mvp_test_ini(fixtures_dir: Path) -> Path:
    """Path to MVP test comparison INI (uses real fixtures)."""
    return fixtures_dir / "comparisons" / "mvp-test.ini"


# =============================================================================
# Audio Fixtures
# =============================================================================


@pytest.fixture
def sample_audio() -> np.ndarray:
    """Generate sample audio data (1 second of 440Hz sine wave)."""
    sample_rate = 44100
    duration = 1.0
    t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
    # 440Hz sine wave at 50% amplitude
    audio = (0.5 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    return audio


@pytest.fixture
def sample_audio_stereo() -> np.ndarray:
    """Generate stereo sample audio data."""
    sample_rate = 44100
    duration = 1.0
    t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
    left = (0.5 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    right = (0.5 * np.sin(2 * np.pi * 550 * t)).astype(np.float32)
    return np.stack([left, right])


@pytest.fixture
def impulse_response() -> np.ndarray:
    """Generate simple impulse response (delta function)."""
    ir = np.zeros(4096, dtype=np.float32)
    ir[0] = 1.0
    return ir


# =============================================================================
# Temporary Directory Fixtures
# =============================================================================


@pytest.fixture
def output_dir(tmp_path: Path) -> Path:
    """Temporary output directory for test artifacts."""
    output = tmp_path / "outputs"
    output.mkdir()
    return output


@pytest.fixture
def inputs_dir(tmp_path: Path) -> Path:
    """Temporary inputs directory structure."""
    inputs = tmp_path / "inputs"
    (inputs / "di_tracks").mkdir(parents=True)
    (inputs / "nam_models").mkdir(parents=True)
    (inputs / "irs").mkdir(parents=True)
    return inputs


# =============================================================================
# Integration Test Fixtures
# =============================================================================


@pytest.fixture
def real_test_files(fixtures_dir: Path, tmp_path: Path) -> Generator[dict[str, Path], None, None]:
    """
    Copy real test files to temp directory for integration tests.

    Returns dict with paths to: di_track, nam_model, ir, comparison_ini
    """
    # Create directory structure
    inputs = tmp_path / "inputs"
    (inputs / "di_tracks").mkdir(parents=True)
    (inputs / "nam_models" / "test").mkdir(parents=True)
    (inputs / "irs" / "test").mkdir(parents=True)

    # Copy fixtures
    di_src = fixtures_dir / "di_tracks" / "test_di.wav"
    ir_src = fixtures_dir / "irs" / "test_ir.wav"

    di_dest = inputs / "di_tracks" / "test_di.wav"
    ir_dest = inputs / "irs" / "test" / "test_ir.wav"

    paths: dict[str, Path] = {
        "root": tmp_path,
        "inputs": inputs,
        "di_track": di_dest,
        "ir": ir_dest,
    }

    # Copy files if they exist
    if di_src.exists():
        shutil.copy(di_src, di_dest)
    if ir_src.exists():
        shutil.copy(ir_src, ir_dest)

    yield paths


# =============================================================================
# Skip Markers
# =============================================================================


@pytest.fixture
def requires_ffmpeg() -> None:
    """Skip test if FFmpeg is not available."""
    if shutil.which("ffmpeg") is None:
        pytest.skip("FFmpeg not found")


@pytest.fixture
def requires_playwright() -> None:
    """Skip test if Playwright is not available."""
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            # Just check we can launch
            p.chromium.launch(headless=True).close()
    except Exception:
        pytest.skip("Playwright/Chromium not available")
