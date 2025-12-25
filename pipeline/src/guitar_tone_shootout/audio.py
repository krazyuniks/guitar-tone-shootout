"""Audio processing using NAM and Pedalboard."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import pedalboard
from pedalboard import Pedalboard
from pedalboard.io import AudioFile

if TYPE_CHECKING:
    import torch
    from numpy.typing import NDArray

    from guitar_tone_shootout.config import ChainEffect

logger = logging.getLogger(__name__)

# Base paths for audio resources
NAM_MODELS_BASE = Path("inputs/nam_models")
IRS_BASE = Path("inputs/irs")


class AudioProcessingError(Exception):
    """Error during audio processing."""


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


def load_nam_model(model_path: Path) -> NAMModel:
    """
    Load a NAM model from a .nam file.

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
    """Wrapper for NAM model to simplify processing."""

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


def process_chain(
    audio: NDArray[np.float32],
    sample_rate: int,
    chain_effects: list[ChainEffect],
) -> NDArray[np.float32]:
    """
    Process audio through a complete signal chain.

    Args:
        audio: Input audio as 1D numpy array
        sample_rate: Sample rate in Hz
        chain_effects: List of ChainEffect objects defining the chain

    Returns:
        Processed audio as 1D numpy array
    """
    current_audio = audio.copy()

    for effect in chain_effects:
        logger.debug(f"Applying effect: {effect.effect_type}:{effect.value}")

        if effect.effect_type == "nam":
            # Process through NAM model
            model = load_nam_model(Path(effect.value))

            # Check sample rate compatibility
            if model.sample_rate and model.sample_rate != sample_rate:
                logger.warning(
                    f"Sample rate mismatch: audio={sample_rate}, model={model.sample_rate}"
                )

            current_audio = model.process(current_audio)

        elif effect.effect_type == "ir":
            # Apply IR convolution
            ir_effect = load_ir(Path(effect.value))
            board = Pedalboard([ir_effect])
            # Pedalboard expects 2D: (channels, samples)
            audio_2d = current_audio.reshape(1, -1)
            current_audio = board(audio_2d, sample_rate)[0]

        elif effect.effect_type == "vst":
            # VST loading - not implemented yet
            logger.warning(f"VST effects not yet supported: {effect.value}")

        else:
            # Built-in Pedalboard effect
            plugin = create_effect(effect.effect_type, effect.value)
            if plugin:
                board = Pedalboard([plugin])
                audio_2d = current_audio.reshape(1, -1)
                current_audio = board(audio_2d, sample_rate)[0]

    return current_audio
