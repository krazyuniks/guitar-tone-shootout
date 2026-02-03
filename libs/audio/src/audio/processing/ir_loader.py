"""IR (Impulse Response) file loader.

This module provides functionality to load impulse response files for cabinet
simulation and convolution processing.
"""

import wave
from pathlib import Path

from pedalboard import Convolution


class IRLoadError(Exception):
    """Exception raised when IR file loading fails."""

    pass


def load_ir(path: str | Path) -> Convolution:
    """Load an impulse response file and return a Convolution effect.

    Args:
        path: Path to the IR file (.wav or .flac format)

    Returns:
        Pedalboard Convolution effect configured with the loaded IR

    Raises:
        IRLoadError: If the file doesn't exist, isn't readable, or is invalid

    Examples:
        >>> convolution = load_ir("path/to/cabinet.wav")
        >>> # Apply to audio using pedalboard
        >>> board = Pedalboard([convolution])
        >>> processed = board(audio, sample_rate)
    """
    # Convert to Path for consistent handling
    ir_path = Path(path) if isinstance(path, str) else path

    # Validate file exists
    if not ir_path.exists():
        raise IRLoadError(f"IR file not found: {ir_path}")

    # Validate file is readable
    if not ir_path.is_file():
        raise IRLoadError(f"IR path is not a file: {ir_path}")

    # Validate file is non-empty
    if ir_path.stat().st_size == 0:
        raise IRLoadError(f"Failed to load IR from {ir_path}: File is empty")

    # Validate file format by attempting to read header
    # WAV files have RIFF header, FLAC files have fLaC header
    try:
        with ir_path.open("rb") as f:
            header = f.read(12)

        # Check for WAV (RIFF...WAVE)
        is_wav = header[:4] == b"RIFF" and header[8:12] == b"WAVE"
        # Check for FLAC (fLaC)
        is_flac = header[:4] == b"fLaC"

        if not (is_wav or is_flac):
            raise IRLoadError(
                f"Failed to load IR from {ir_path}: Invalid file format (not WAV or FLAC)"
            )

        # For WAV files, verify it's valid by opening with wave module
        if is_wav:
            try:
                with wave.open(str(ir_path), "rb") as wav:
                    # Verify has at least one frame
                    if wav.getnframes() == 0:
                        raise IRLoadError(
                            f"Failed to load IR from {ir_path}: WAV file has no audio data"
                        )
            except wave.Error as e:
                raise IRLoadError(
                    f"Failed to load IR from {ir_path}: Invalid WAV file - {e}"
                ) from e

    except OSError as e:
        raise IRLoadError(f"Failed to load IR from {ir_path}: {e}") from e

    try:
        # Load IR using Pedalboard's Convolution
        # Convolution automatically handles WAV and FLAC formats
        convolution = Convolution(str(ir_path))
        return convolution
    except Exception as e:
        # Catch any loading errors and wrap in IRLoadError
        raise IRLoadError(f"Failed to load IR from {ir_path}: {e}") from e
