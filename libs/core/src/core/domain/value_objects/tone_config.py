"""ToneConfig value object for domain layer.

Configuration for tone processing operations.
"""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ToneConfig:
    """Value object representing tone processing configuration.

    This is an immutable value object containing all the parameters needed
    to process a DI track through a tone configuration.

    Attributes:
        nam_model_path: Path to the NAM model file (.nam)
        ir_path: Path to the impulse response file (.wav), or None for no IR
        target_lufs: Target loudness in LUFS for normalization (default: -14.0)
        highpass_freq: Highpass filter frequency in Hz, or None to disable
        sample_rate: Sample rate for processing in Hz (default: 48000)
        output_format: Output audio format (default: 'wav')
        effects_chain: Tuple of effect identifiers to apply
    """

    nam_model_path: Path
    ir_path: Path | None = None
    target_lufs: float = -14.0
    highpass_freq: float | None = 80.0
    sample_rate: int = 48000
    output_format: str = "wav"
    effects_chain: tuple[str, ...] = field(default_factory=tuple)

    def with_ir(self, ir_path: Path | None) -> "ToneConfig":
        """Return a new ToneConfig with a different IR path.

        Args:
            ir_path: The new IR path, or None to disable IR

        Returns:
            A new ToneConfig instance with the updated IR path
        """
        return ToneConfig(
            nam_model_path=self.nam_model_path,
            ir_path=ir_path,
            target_lufs=self.target_lufs,
            highpass_freq=self.highpass_freq,
            sample_rate=self.sample_rate,
            output_format=self.output_format,
            effects_chain=self.effects_chain,
        )

    def with_target_lufs(self, target_lufs: float) -> "ToneConfig":
        """Return a new ToneConfig with a different target LUFS.

        Args:
            target_lufs: The new target loudness in LUFS

        Returns:
            A new ToneConfig instance with the updated target LUFS
        """
        return ToneConfig(
            nam_model_path=self.nam_model_path,
            ir_path=self.ir_path,
            target_lufs=target_lufs,
            highpass_freq=self.highpass_freq,
            sample_rate=self.sample_rate,
            output_format=self.output_format,
            effects_chain=self.effects_chain,
        )

    def with_highpass(self, highpass_freq: float | None) -> "ToneConfig":
        """Return a new ToneConfig with a different highpass frequency.

        Args:
            highpass_freq: The new highpass frequency in Hz, or None to disable

        Returns:
            A new ToneConfig instance with the updated highpass frequency
        """
        return ToneConfig(
            nam_model_path=self.nam_model_path,
            ir_path=self.ir_path,
            target_lufs=self.target_lufs,
            highpass_freq=highpass_freq,
            sample_rate=self.sample_rate,
            output_format=self.output_format,
            effects_chain=self.effects_chain,
        )

    def with_effects_chain(self, effects_chain: tuple[str, ...]) -> "ToneConfig":
        """Return a new ToneConfig with a different effects chain.

        Args:
            effects_chain: The new effects chain

        Returns:
            A new ToneConfig instance with the updated effects chain
        """
        return ToneConfig(
            nam_model_path=self.nam_model_path,
            ir_path=self.ir_path,
            target_lufs=self.target_lufs,
            highpass_freq=self.highpass_freq,
            sample_rate=self.sample_rate,
            output_format=self.output_format,
            effects_chain=effects_chain,
        )
