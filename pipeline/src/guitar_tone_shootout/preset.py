"""VST3 preset generation for Neural Amp Modeler plugin.

This module enables programmatic loading of NAM models via Pedalboard by
generating VST3 preset files with embedded model paths. The NAM VST3 plugin
doesn't expose the model path as an automatable parameter, so we create
presets that contain the model path in the plugin's component state.

VST3 Preset Format:
    Header (48 bytes):
        - Magic: "VST3" (4 bytes)
        - Version: 1 (4 bytes, little-endian)
        - Class ID: 32 bytes ASCII
        - Chunk list offset (8 bytes, little-endian)

    NAM Component State (iPlug2 format):
        - String: "###NeuralAmpModeler###" (marker)
        - String: plugin version (e.g., "0.7.13")
        - String: model path (the NAM model file)
        - String: IR path (optional, we use Pedalboard's Convolution)
        - Parameters: 12 doubles (normalized 0-1 values)

Usage:
    from guitar_tone_shootout.preset import generate_nam_preset

    # Generate preset with model path
    preset_path = generate_nam_preset("/path/to/model.nam", "/tmp/model.vstpreset")

    # Load into Pedalboard
    from pedalboard import load_plugin
    nam = load_plugin("NeuralAmpModeler.vst3")
    nam.load_preset(str(preset_path))
"""

from __future__ import annotations

import struct
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

# NAM VST3 plugin class ID (from the plugin's VST3 metadata)
NAM_CLASS_ID = "F2AEE70D00DE4F4E534441613159456F"

# Default NAM plugin version
DEFAULT_NAM_VERSION = "0.7.13"


class PresetGenerationError(Exception):
    """Error during VST3 preset generation."""


def _put_string(s: str) -> bytes:
    """
    Encode a string in iPlug2's PutStr format.

    Format: 4-byte length (little-endian) + string bytes + null terminator

    Args:
        s: String to encode

    Returns:
        Encoded bytes
    """
    encoded = s.encode("utf-8") + b"\x00" if s else b""
    return struct.pack("<I", len(encoded)) + encoded


def create_nam_state(
    nam_path: str,
    ir_path: str = "",
    version: str = DEFAULT_NAM_VERSION,
    parameters: Sequence[float] | None = None,
) -> bytes:
    """
    Create NAM plugin component state bytes.

    This creates the IComponent data that goes inside the VST3 preset.
    The state contains the model path that the plugin will load.

    Args:
        nam_path: Absolute path to the .nam model file
        ir_path: Optional path to IR file (we typically use Pedalboard's IR instead)
        version: NAM plugin version string
        parameters: Optional list of 12 normalized parameter values (0-1).
                   If None, uses sensible defaults.

    Returns:
        Binary state data for the VST3 preset
    """
    state = b""

    # Header strings (iPlug2 format)
    state += _put_string("###NeuralAmpModeler###")
    state += _put_string(version)
    state += _put_string(nam_path)
    state += _put_string(ir_path)

    # Default parameter values (v0.7.13 format) - normalized (0-1) values
    # Parameter order from NAM source:
    # Input, Threshold, Bass, Middle, Treble, Output,
    # NoiseGateActive, ToneStack, IRToggle, CalibrateInput,
    # InputCalibrationLevel, OutputMode
    if parameters is None:
        parameters = [
            0.5,  # Input: 0.0 dB (range -20 to 20, 0.5 = 0dB)
            0.2,  # Threshold: -80.0 dB (range -100 to 0)
            0.5,  # Bass: 5.0 (range 0-10)
            0.5,  # Middle: 5.0
            0.5,  # Treble: 5.0
            0.5,  # Output: 0.0 dB (range -40 to 40)
            1.0,  # NoiseGateActive: on (bool)
            1.0,  # ToneStack: on (bool)
            0.0,  # IRToggle: OFF - we use Pedalboard's Convolution
            0.0,  # CalibrateInput: off (bool)
            0.6,  # InputCalibrationLevel: 12.0 dBu
            0.5,  # OutputMode: Normalized (0=Raw, 0.5=Normalized, 1=Calibrated)
        ]

    if len(parameters) != 12:
        raise PresetGenerationError(f"Expected 12 parameters, got {len(parameters)}")

    for param in parameters:
        state += struct.pack("<d", float(param))  # double, little-endian

    return state


def create_vst3_preset(class_id: str, component_state: bytes) -> bytes:
    """
    Create a VST3 preset file containing the component state.

    VST3 preset format:
        - Header (48 bytes): magic, version, class_id, chunk_list_offset
        - Data chunks (component state)
        - Chunk list (index of chunks)

    Args:
        class_id: 32-character VST3 class identifier
        component_state: Binary component state data

    Returns:
        Complete VST3 preset file bytes
    """
    # Validate class ID
    if len(class_id) != 32:
        raise PresetGenerationError(f"Class ID must be 32 characters, got {len(class_id)}")

    # VST3 header components
    magic = b"VST3"
    version = 1
    class_id_bytes = class_id.encode("ascii")

    # Calculate offsets
    header_size = 48
    data_start = header_size
    comp_offset = data_start
    chunk_list_offset = data_start + len(component_state)

    # Build chunk list
    list_id = b"List"
    num_entries = 1
    chunk_list = list_id + struct.pack("<I", num_entries)

    # Entry: ID (4) + offset (8) + size (8) = 20 bytes
    comp_id = b"Comp"
    chunk_list += comp_id
    chunk_list += struct.pack("<Q", comp_offset)
    chunk_list += struct.pack("<Q", len(component_state))

    # Build header
    header = magic
    header += struct.pack("<I", version)
    header += class_id_bytes
    header += struct.pack("<Q", chunk_list_offset)

    # Combine all parts
    return header + component_state + chunk_list


def generate_nam_preset(
    nam_model_path: str | Path,
    output_preset_path: str | Path | None = None,
    ir_path: str = "",
    parameters: Sequence[float] | None = None,
) -> Path:
    """
    Generate a VST3 preset file for NAM with the specified model.

    This is the main entry point for preset generation. The generated preset
    can be loaded into the NAM VST3 plugin via Pedalboard's load_preset().

    Args:
        nam_model_path: Path to the .nam model file (will be resolved to absolute)
        output_preset_path: Where to save the .vstpreset file. If None, creates
                          a temporary file.
        ir_path: Optional path to IR file (we typically use Pedalboard's IR)
        parameters: Optional list of 12 normalized parameter values

    Returns:
        Path to the generated .vstpreset file

    Example:
        >>> preset = generate_nam_preset("/models/jcm800.nam")
        >>> nam = load_plugin("NeuralAmpModeler.vst3")
        >>> nam.load_preset(str(preset))
    """
    # Resolve model path to absolute
    model_path = Path(nam_model_path).resolve()
    if not model_path.exists():
        raise PresetGenerationError(f"NAM model not found: {model_path}")

    # Determine output path
    if output_preset_path is None:
        # Create temp file with meaningful name
        fd, temp_path = tempfile.mkstemp(suffix=".vstpreset", prefix=f"nam_{model_path.stem}_")
        import os

        os.close(fd)
        output_path = Path(temp_path)
    else:
        output_path = Path(output_preset_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

    # Create the component state with model path
    component_state = create_nam_state(str(model_path), ir_path=ir_path, parameters=parameters)

    # Create the full preset
    preset_data = create_vst3_preset(NAM_CLASS_ID, component_state)

    # Write to file
    output_path.write_bytes(preset_data)

    return output_path


def generate_preset_bytes(
    nam_model_path: str | Path,
    ir_path: str = "",
    parameters: Sequence[float] | None = None,
) -> bytes:
    """
    Generate VST3 preset bytes without writing to disk.

    This is useful when you want to load the preset directly via
    plugin.preset_data = bytes instead of using a temp file.

    Args:
        nam_model_path: Path to the .nam model file
        ir_path: Optional path to IR file
        parameters: Optional list of 12 normalized parameter values

    Returns:
        VST3 preset file bytes
    """
    model_path = Path(nam_model_path).resolve()
    if not model_path.exists():
        raise PresetGenerationError(f"NAM model not found: {model_path}")

    component_state = create_nam_state(str(model_path), ir_path=ir_path, parameters=parameters)

    return create_vst3_preset(NAM_CLASS_ID, component_state)
