"""Tests for VST3 preset generation."""

from pathlib import Path

import pytest

from guitar_tone_shootout.preset import (
    NAM_CLASS_ID,
    PresetGenerationError,
    create_nam_state,
    create_vst3_preset,
    generate_nam_preset,
    generate_preset_bytes,
)

# =============================================================================
# NAM State Creation Tests
# =============================================================================


def test_create_nam_state_minimal() -> None:
    """Create state with just model path."""
    state = create_nam_state("/path/to/model.nam")

    # Should contain the header marker
    assert b"###NeuralAmpModeler###" in state
    # Should contain the model path
    assert b"/path/to/model.nam" in state


def test_create_nam_state_with_ir() -> None:
    """Create state with model and IR paths."""
    state = create_nam_state("/path/to/model.nam", ir_path="/path/to/ir.wav")

    assert b"/path/to/model.nam" in state
    assert b"/path/to/ir.wav" in state


def test_create_nam_state_with_version() -> None:
    """Create state with custom version."""
    state = create_nam_state("/model.nam", version="0.8.0")

    assert b"0.8.0" in state


def test_create_nam_state_with_parameters() -> None:
    """Create state with custom parameters."""
    params = [0.5] * 12  # 12 default values
    state = create_nam_state("/model.nam", parameters=params)

    assert len(state) > 0


def test_create_nam_state_wrong_param_count_raises() -> None:
    """Should raise if wrong number of parameters."""
    with pytest.raises(PresetGenerationError, match="Expected 12 parameters"):
        create_nam_state("/model.nam", parameters=[0.5] * 10)


# =============================================================================
# VST3 Preset Creation Tests
# =============================================================================


def test_create_vst3_preset_format() -> None:
    """Verify VST3 preset has correct header format."""
    component_state = b"test state data"
    preset = create_vst3_preset(NAM_CLASS_ID, component_state)

    # Check VST3 magic
    assert preset[:4] == b"VST3"

    # Check version (should be 1, little-endian)
    version = int.from_bytes(preset[4:8], "little")
    assert version == 1

    # Check class ID is embedded
    assert NAM_CLASS_ID.encode("ascii") in preset

    # Check chunk list marker
    assert b"List" in preset

    # Check component chunk marker
    assert b"Comp" in preset


def test_create_vst3_preset_invalid_class_id() -> None:
    """Should raise if class ID is wrong length."""
    with pytest.raises(PresetGenerationError, match="Class ID must be 32 characters"):
        create_vst3_preset("short", b"state")


def test_create_vst3_preset_contains_state() -> None:
    """Verify component state is embedded in preset."""
    state = b"UNIQUE_STATE_MARKER_12345"
    preset = create_vst3_preset(NAM_CLASS_ID, state)

    assert state in preset


# =============================================================================
# Preset Generation Tests
# =============================================================================


def test_generate_nam_preset(tmp_path: Path) -> None:
    """Generate a preset file."""
    model_path = tmp_path / "test.nam"
    model_path.write_text("{}")  # Empty NAM model file

    preset_path = tmp_path / "test.vstpreset"
    result = generate_nam_preset(model_path, preset_path)

    assert result == preset_path
    assert preset_path.exists()
    assert preset_path.stat().st_size > 0

    # Verify it's a valid VST3 preset
    data = preset_path.read_bytes()
    assert data[:4] == b"VST3"


def test_generate_nam_preset_auto_path(tmp_path: Path) -> None:
    """Generate preset with auto-generated temp path."""
    model_path = tmp_path / "test.nam"
    model_path.write_text("{}")

    result = generate_nam_preset(model_path)

    assert result.exists()
    assert result.suffix == ".vstpreset"
    # Clean up temp file
    result.unlink()


def test_generate_nam_preset_missing_model() -> None:
    """Should raise if model file doesn't exist."""
    with pytest.raises(PresetGenerationError, match="NAM model not found"):
        generate_nam_preset("/nonexistent/model.nam")


def test_generate_nam_preset_creates_dirs(tmp_path: Path) -> None:
    """Should create parent directories for output."""
    model_path = tmp_path / "test.nam"
    model_path.write_text("{}")

    preset_path = tmp_path / "nested" / "dir" / "test.vstpreset"
    result = generate_nam_preset(model_path, preset_path)

    assert result.exists()


def test_generate_preset_bytes(tmp_path: Path) -> None:
    """Generate preset bytes without writing to disk."""
    model_path = tmp_path / "test.nam"
    model_path.write_text("{}")

    data = generate_preset_bytes(model_path)

    assert isinstance(data, bytes)
    assert data[:4] == b"VST3"
    # Should contain model path
    assert str(model_path).encode() in data


def test_generate_preset_bytes_missing_model() -> None:
    """Should raise if model file doesn't exist."""
    with pytest.raises(PresetGenerationError, match="NAM model not found"):
        generate_preset_bytes("/nonexistent/model.nam")


# =============================================================================
# Integration Tests (preset structure verification)
# =============================================================================


def test_preset_round_trip_structure(tmp_path: Path) -> None:
    """Verify preset has all expected sections."""
    model_path = tmp_path / "test_model.nam"
    model_path.write_text("{}")

    preset_path = tmp_path / "output.vstpreset"
    generate_nam_preset(model_path, preset_path)

    data = preset_path.read_bytes()

    # VST3 header (48 bytes)
    assert len(data) >= 48, "Preset too small for VST3 header"

    # Magic and version
    assert data[:4] == b"VST3"
    assert int.from_bytes(data[4:8], "little") == 1

    # Class ID (32 bytes starting at offset 8)
    class_id = data[8:40].decode("ascii")
    assert class_id == NAM_CLASS_ID

    # NAM marker in component state
    assert b"###NeuralAmpModeler###" in data

    # Model path embedded
    assert str(model_path.resolve()).encode() in data
