"""Audio processing using Pedalboard with NAM VST3 plugin support.

This module provides audio processing for guitar tone comparisons, including:
- Neural Amp Modeler (NAM) model processing via VST3 plugin
- Impulse Response (IR) convolution
- Built-in effects (EQ, reverb, delay, gain)
- Volume normalization

Architecture:
    The preferred approach uses Pedalboard with the NAM VST3 plugin for
    unified processing. Model paths are embedded in generated VST3 presets.
    A PyTorch-based fallback is available for environments without the VST3 plugin.

    Preferred (Pedalboard + VST3):
        DI Audio -> [Pedalboard: NAM VST3 + IR + Effects] -> Output

    Fallback (PyTorch):
        DI Audio -> [PyTorch NAM] -> [Pedalboard Effects] -> Output
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import pedalboard
from pedalboard import Pedalboard  # type: ignore[attr-defined]
from pedalboard.io import AudioFile

if TYPE_CHECKING:
    import torch
    from numpy.typing import NDArray

    from guitar_tone_shootout.config import ChainEffect

logger = logging.getLogger(__name__)

# Base paths for audio resources
NAM_MODELS_BASE = Path("inputs/nam_models")
IRS_BASE = Path("inputs/irs")

# Environment variable to specify NAM VST3 plugin path
NAM_VST3_ENV_VAR = "NAM_VST3_PATH"
# Default locations to search for NAM VST3 plugin
NAM_VST3_SEARCH_PATHS: list[str | Path] = [
    "/usr/lib/vst3/NeuralAmpModeler.vst3",  # Linux system
    "/usr/local/lib/vst3/NeuralAmpModeler.vst3",  # Linux local
    Path.home() / ".vst3" / "NeuralAmpModeler.vst3",  # Linux user
    "/Library/Audio/Plug-Ins/VST3/NeuralAmpModeler.vst3",  # macOS system
    Path.home() / "Library/Audio/Plug-Ins/VST3/NeuralAmpModeler.vst3",  # macOS user
]

# Cached VST3 plugin path (None = not yet searched, "" = not found)
_nam_vst3_path: str | None = None


class AudioProcessingError(Exception):
    """Error during audio processing."""


def find_nam_vst3() -> str | None:
    """
    Find the NAM VST3 plugin.

    Searches in order:
    1. NAM_VST3_PATH environment variable
    2. Common system locations

    Returns:
        Path to the VST3 plugin, or None if not found
    """
    global _nam_vst3_path  # noqa: PLW0603

    # Return cached result if already searched
    if _nam_vst3_path is not None:
        return _nam_vst3_path if _nam_vst3_path else None

    # Check environment variable first
    env_path = os.environ.get(NAM_VST3_ENV_VAR)
    if env_path and Path(env_path).exists():
        _nam_vst3_path = env_path
        logger.info(f"NAM VST3 found via env: {_nam_vst3_path}")
        return _nam_vst3_path

    # Search common locations
    for search_path in NAM_VST3_SEARCH_PATHS:
        path = Path(search_path)
        if path.exists():
            _nam_vst3_path = str(path)
            logger.info(f"NAM VST3 found: {_nam_vst3_path}")
            return _nam_vst3_path

    # Not found
    _nam_vst3_path = ""
    logger.debug("NAM VST3 plugin not found, will use PyTorch fallback")
    return None


def load_audio(path: Path) -> tuple[NDArray[np.float32], int]:
    """
    Load audio file as numpy array.

    Args:
        path: Path to audio file

    Returns:
        Tuple of (audio data as float32, sample rate)

    Raises:
        AudioProcessingError: If file cannot be loaded
    """
    try:
        with AudioFile(str(path)) as f:
            audio = f.read(f.frames)
            sample_rate = int(f.samplerate)
        # Convert to mono if stereo (take first channel)
        if audio.ndim == 2:
            audio = audio[0]
        return audio.astype(np.float32), sample_rate
    except Exception as e:
        raise AudioProcessingError(f"Failed to load audio: {path}") from e


def save_audio(
    audio: NDArray[np.float32],
    path: Path,
    sample_rate: int,
) -> Path:
    """
    Save audio array to file.

    Args:
        audio: Audio data as numpy array
        path: Output path
        sample_rate: Sample rate in Hz

    Returns:
        Path to saved file
    """
    # Ensure mono audio is 2D for pedalboard (1, samples)
    if audio.ndim == 1:
        audio = audio.reshape(1, -1)

    path.parent.mkdir(parents=True, exist_ok=True)

    with AudioFile(str(path), "w", samplerate=sample_rate, num_channels=1) as f:
        f.write(audio)

    logger.debug(f"Saved audio to {path}")
    return path


def load_nam_via_vst3(
    model_path: Path,
    vst3_path: str | None = None,
) -> pedalboard.Plugin | None:
    """
    Load a NAM model via the VST3 plugin.

    This generates a preset with the model path embedded and loads it
    into the NAM VST3 plugin via Pedalboard.

    Args:
        model_path: Absolute path to the .nam model file
        vst3_path: Optional path to NAM VST3 plugin (auto-detected if None)

    Returns:
        Loaded Pedalboard plugin, or None if VST3 not available
    """
    # Find VST3 plugin
    if vst3_path is None:
        vst3_path = find_nam_vst3()

    if not vst3_path:
        logger.debug("NAM VST3 not available")
        return None

    if not model_path.exists():
        raise AudioProcessingError(f"NAM model not found: {model_path}")

    try:
        # Import here to avoid circular dependency
        from guitar_tone_shootout.preset import generate_preset_bytes

        # Load the plugin
        plugin = pedalboard.load_plugin(vst3_path)  # type: ignore[attr-defined]

        # Generate preset with model path and load it
        preset_bytes = generate_preset_bytes(model_path)
        plugin.preset_data = preset_bytes  # type: ignore[attr-defined]

        # Disable plugin's internal IR (we use Pedalboard's Convolution)
        if hasattr(plugin, "irtoggle"):
            plugin.irtoggle = False

        logger.debug(f"Loaded NAM model via VST3: {model_path.name}")
        return plugin

    except Exception as e:
        logger.warning(f"Failed to load NAM via VST3: {e}")
        return None


def load_nam_model(model_path: Path) -> NAMModel:
    """
    Load a NAM model from a .nam file using PyTorch.

    This is the fallback method when the VST3 plugin is not available.

    Args:
        model_path: Path to .nam file (relative to NAM_MODELS_BASE or absolute)

    Returns:
        Loaded NAM model ready for inference
    """
    # Resolve path (use base if relative)
    full_path = model_path if model_path.is_absolute() else NAM_MODELS_BASE / model_path

    if not full_path.exists():
        raise AudioProcessingError(f"NAM model not found: {full_path}")

    try:
        from nam.models import init_from_nam

        with full_path.open() as fp:
            config = json.load(fp)
        model = init_from_nam(config)
        model.eval()  # Set to evaluation mode
        return NAMModel(model, full_path)
    except Exception as e:
        raise AudioProcessingError(f"Failed to load NAM model: {full_path}") from e


class NAMModel:
    """Wrapper for PyTorch NAM model to simplify processing."""

    def __init__(self, model: torch.nn.Module, path: Path) -> None:
        self._model = model
        self.path = path
        self.sample_rate: float | None = getattr(model, "sample_rate", None)

    def process(self, audio: NDArray[np.float32]) -> NDArray[np.float32]:
        """
        Process audio through the NAM model.

        Args:
            audio: Input audio as 1D numpy array

        Returns:
            Processed audio as 1D numpy array
        """
        import torch as th

        # Convert to torch tensor
        x = th.tensor(audio, dtype=th.float32)

        # Process (no grad needed for inference)
        with th.no_grad():
            y = self._model(x, pad_start=True)

        # Convert back to numpy
        result: NDArray[np.float32] = y.cpu().numpy().astype(np.float32)
        return result


def load_ir(ir_path: Path) -> pedalboard.Convolution:
    """
    Load an impulse response for convolution.

    Args:
        ir_path: Path to IR file (relative to IRS_BASE or absolute)

    Returns:
        Pedalboard Convolution effect
    """
    # Resolve path (use base if relative)
    full_path = ir_path if ir_path.is_absolute() else IRS_BASE / ir_path

    if not full_path.exists():
        raise AudioProcessingError(f"IR file not found: {full_path}")

    return pedalboard.Convolution(str(full_path))


# Effect presets - maps (effect_type, value) to plugin factory
_EFFECT_PRESETS: dict[tuple[str, str], pedalboard.Plugin] = {}


def _init_effect_presets() -> None:
    """Initialize effect presets (called lazily)."""
    global _EFFECT_PRESETS  # noqa: PLW0603
    if _EFFECT_PRESETS:
        return
    _EFFECT_PRESETS = {
        # EQ presets
        ("eq", "highpass_80hz"): pedalboard.HighpassFilter(cutoff_frequency_hz=80.0),
        ("eq", "lowpass_12k"): pedalboard.LowpassFilter(cutoff_frequency_hz=12000.0),
        ("eq", "highshelf_presence"): pedalboard.HighShelfFilter(
            cutoff_frequency_hz=3000.0, gain_db=3.0
        ),
        # Reverb presets
        ("reverb", "room"): pedalboard.Reverb(room_size=0.3, wet_level=0.2),
        ("reverb", "hall"): pedalboard.Reverb(room_size=0.7, wet_level=0.3),
        ("reverb", "spring"): pedalboard.Reverb(room_size=0.2, wet_level=0.15, damping=0.9),
        # Delay presets
        ("delay", "slapback"): pedalboard.Delay(delay_seconds=0.08, feedback=0.1, mix=0.3),
        ("delay", "quarter"): pedalboard.Delay(delay_seconds=0.375, feedback=0.3, mix=0.25),
    }


def create_effect(effect_type: str, value: str) -> pedalboard.Plugin | None:
    """
    Create a Pedalboard effect from type and value.

    Args:
        effect_type: Effect type (eq, reverb, delay, gain)
        value: Effect parameters/preset

    Returns:
        Pedalboard Plugin or None if not supported
    """
    _init_effect_presets()

    # Handle gain separately (dynamic value)
    if effect_type == "gain":
        try:
            return pedalboard.Gain(gain_db=float(value))
        except ValueError:
            logger.warning(f"Invalid gain value: {value}")
            return None

    # Look up preset
    preset_key = (effect_type, value)
    if preset_key in _EFFECT_PRESETS:
        return _EFFECT_PRESETS[preset_key]

    logger.warning(f"Unknown {effect_type} preset: {value}")
    return None


def process_chain(  # noqa: PLR0912
    audio: NDArray[np.float32],
    sample_rate: int,
    chain_effects: list[ChainEffect],
    project_root: Path | None = None,
    normalize_input: bool = False,
    normalize_output: bool = False,
    input_target_db: float = -18.0,
    output_target_db: float = -14.0,
) -> NDArray[np.float32]:
    """
    Process audio through a complete signal chain.

    Supports both VST3-based NAM processing (preferred) and PyTorch fallback.
    When VST3 is available, NAM processing is integrated into a unified
    Pedalboard chain for better performance.

    Args:
        audio: Input audio as 1D numpy array
        sample_rate: Sample rate in Hz
        chain_effects: List of ChainEffect objects defining the chain
        project_root: Project root directory for resolving input paths
        normalize_input: Apply input normalization before processing
        normalize_output: Apply output normalization after processing
        input_target_db: Target RMS for input normalization (default: -18 dB)
        output_target_db: Target RMS for output normalization (default: -14 dB)

    Returns:
        Processed audio as 1D numpy array
    """
    current_audio = audio.copy()

    # Apply input normalization if requested
    if normalize_input:
        from guitar_tone_shootout.normalize import normalize_rms

        current_audio = normalize_rms(current_audio, target_db=input_target_db)
        logger.debug(f"Applied input normalization to {input_target_db} dB RMS")

    # Resolve base paths for inputs
    if project_root:
        nam_base = project_root / "inputs" / "nam_models"
        ir_base = project_root / "inputs" / "irs"
    else:
        nam_base = NAM_MODELS_BASE
        ir_base = IRS_BASE

    # Try to use VST3-based processing
    vst3_path = find_nam_vst3()

    for effect in chain_effects:
        logger.debug(f"Applying effect: {effect.effect_type}:{effect.value}")

        if effect.effect_type == "nam":
            # Process through NAM model
            nam_path = nam_base / effect.value

            if vst3_path:
                # Preferred: Use VST3 plugin
                plugin = load_nam_via_vst3(nam_path, vst3_path)
                if plugin:
                    board = Pedalboard([plugin])
                    audio_2d = current_audio.reshape(1, -1)
                    current_audio = board(audio_2d, sample_rate)[0]
                else:
                    # Fallback to PyTorch if VST3 loading failed
                    model = load_nam_model(nam_path)
                    if model.sample_rate and model.sample_rate != sample_rate:
                        logger.warning(
                            f"Sample rate mismatch: audio={sample_rate}, model={model.sample_rate}"
                        )
                    current_audio = model.process(current_audio)
            else:
                # Fallback: Use PyTorch
                model = load_nam_model(nam_path)
                if model.sample_rate and model.sample_rate != sample_rate:
                    logger.warning(
                        f"Sample rate mismatch: audio={sample_rate}, model={model.sample_rate}"
                    )
                current_audio = model.process(current_audio)

        elif effect.effect_type == "ir":
            # Apply IR convolution
            ir_path = ir_base / effect.value
            ir_effect = load_ir(ir_path)
            board = Pedalboard([ir_effect])
            # Pedalboard expects 2D: (channels, samples)
            audio_2d = current_audio.reshape(1, -1)
            current_audio = board(audio_2d, sample_rate)[0]

        elif effect.effect_type == "vst":
            # Generic VST loading
            logger.warning(f"Generic VST loading not yet supported: {effect.value}")

        else:
            # Built-in Pedalboard effect
            plugin = create_effect(effect.effect_type, effect.value)
            if plugin:
                board = Pedalboard([plugin])
                audio_2d = current_audio.reshape(1, -1)
                current_audio = board(audio_2d, sample_rate)[0]

    # Apply output normalization if requested
    if normalize_output:
        from guitar_tone_shootout.normalize import normalize_rms

        current_audio = normalize_rms(current_audio, target_db=output_target_db)
        logger.debug(f"Applied output normalization to {output_target_db} dB RMS")

    return current_audio


def process_chain_unified(
    audio: NDArray[np.float32],
    sample_rate: int,
    chain_effects: list[ChainEffect],
    project_root: Path | None = None,
) -> NDArray[np.float32]:
    """
    Process audio through a unified Pedalboard chain (VST3 required).

    This builds a single Pedalboard with all effects for optimal performance.
    Falls back to process_chain() if VST3 is not available.

    Args:
        audio: Input audio as 1D numpy array
        sample_rate: Sample rate in Hz
        chain_effects: List of ChainEffect objects defining the chain
        project_root: Project root directory for resolving input paths

    Returns:
        Processed audio as 1D numpy array
    """
    vst3_path = find_nam_vst3()

    if not vst3_path:
        logger.debug("VST3 not available, using sequential processing")
        return process_chain(audio, sample_rate, chain_effects, project_root)

    # Resolve base paths
    if project_root:
        nam_base = project_root / "inputs" / "nam_models"
        ir_base = project_root / "inputs" / "irs"
    else:
        nam_base = NAM_MODELS_BASE
        ir_base = IRS_BASE

    # Build unified plugin chain
    plugins: list[pedalboard.Plugin] = []

    for effect in chain_effects:
        if effect.effect_type == "nam":
            nam_path = nam_base / effect.value
            plugin = load_nam_via_vst3(nam_path, vst3_path)
            if plugin:
                plugins.append(plugin)
            else:
                logger.warning(f"Failed to load NAM via VST3: {effect.value}")

        elif effect.effect_type == "ir":
            ir_path = ir_base / effect.value
            plugins.append(load_ir(ir_path))

        elif effect.effect_type == "vst":
            logger.warning(f"Generic VST not supported in unified chain: {effect.value}")

        else:
            plugin = create_effect(effect.effect_type, effect.value)
            if plugin:
                plugins.append(plugin)

    # Process through unified chain
    board = Pedalboard(plugins)
    audio_2d = audio.reshape(1, -1)
    output: NDArray[np.float32] = board(audio_2d, sample_rate)[0]

    return output
