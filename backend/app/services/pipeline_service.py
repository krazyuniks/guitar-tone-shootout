"""Pipeline service wrapper for web application context.

This service wraps the existing pipeline code for use with TaskIQ workers,
providing progress callbacks and async-compatible execution.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from guitar_tone_shootout.config import Comparison

logger = logging.getLogger(__name__)

# Type alias for progress callback
ProgressCallback = Callable[[int, str], Awaitable[None]]


class PipelineError(Exception):
    """Error during pipeline processing."""


class PipelineService:
    """Service wrapper for pipeline processing with progress callbacks.

    This service adapts the existing pipeline library for use in the web
    application context, providing:
    - Async-compatible execution via asyncio.to_thread()
    - Progress callbacks for real-time updates
    - Configurable directories for inputs/outputs
    - Error handling with proper exceptions
    """

    def __init__(
        self,
        progress_callback: ProgressCallback,
        data_dir: Path | None = None,
    ) -> None:
        """Initialize the pipeline service.

        Args:
            progress_callback: Async callback for progress updates (percent, message).
            data_dir: Base directory for data storage. Defaults to /data.
        """
        self.progress_callback = progress_callback
        self.data_dir = data_dir or Path("/data")
        self.uploads_dir = self.data_dir / "uploads"
        self.models_dir = self.data_dir / "models"
        self.outputs_dir = self.data_dir / "outputs"

    async def _progress(self, percent: int, message: str) -> None:
        """Report progress update via callback.

        Args:
            percent: Progress percentage (0-100).
            message: Human-readable status message.
        """
        logger.debug("Pipeline progress: %d%% - %s", percent, message)
        await self.progress_callback(percent, message)

    async def run_shootout(
        self,
        job_id: str,
        config: ShootoutConfig,
        di_track_path: Path,
    ) -> dict[str, str]:
        """Execute a complete shootout pipeline.

        Args:
            job_id: Unique job identifier for output directory.
            config: Shootout configuration with tones and metadata.
            di_track_path: Path to the uploaded DI track file.

        Returns:
            Dict with output paths:
                - video: Path to the master video file
                - audio: Path to the combined audio file

        Raises:
            PipelineError: If processing fails.
        """
        await self._progress(0, "Starting pipeline...")

        # Create output directory for this job
        output_dir = self.outputs_dir / job_id
        output_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Build comparison object from config
            await self._progress(5, "Preparing configuration...")
            comparison = await self._build_comparison(config, di_track_path, output_dir)

            # Run the pipeline processing
            await self._progress(10, "Processing comparison...")
            video_path = await self._process_comparison(comparison, output_dir)

            await self._progress(100, "Complete!")

            return {
                "video": str(video_path),
                "output_dir": str(output_dir),
            }

        except Exception as e:
            logger.exception("Pipeline processing failed: %s", e)
            raise PipelineError(f"Pipeline processing failed: {e}") from e

    async def _build_comparison(
        self,
        config: ShootoutConfig,
        di_track_path: Path,
        output_dir: Path,
    ) -> Comparison:
        """Build a Comparison object from web config.

        Args:
            config: Shootout configuration from web request.
            di_track_path: Path to the DI track file.
            output_dir: Output directory for this job.

        Returns:
            Comparison object ready for processing.
        """
        from guitar_tone_shootout.config import (
            ChainEffect,
            Comparison,
            ComparisonMeta,
            DITrack,
            SignalChain,
        )

        # Create metadata
        meta = ComparisonMeta(
            name=config.name,
            author=config.author or "Guitar Tone Shootout User",
            description=config.description or "",
        )

        # Create DI track entry
        di_track = DITrack(
            file=di_track_path,
            guitar=config.guitar or "Electric Guitar",
            pickup=config.pickup or "Unknown",
        )

        # Build signal chains from tones
        signal_chains: list[SignalChain] = []
        for tone in config.tones:
            # Build effects chain
            effects: list[ChainEffect] = []

            # Add highpass filter if enabled
            if tone.highpass:
                effects.append(ChainEffect(effect_type="eq", value="highpass_80hz"))

            # Add NAM model
            if tone.model_path:
                effects.append(ChainEffect(effect_type="nam", value=tone.model_path))

            # Add IR if specified
            if tone.ir_path:
                effects.append(ChainEffect(effect_type="ir", value=tone.ir_path))

            # Add any additional effects
            for effect in tone.effects or []:
                effects.append(
                    ChainEffect(effect_type=effect.effect_type, value=effect.value)
                )

            signal_chains.append(
                SignalChain(
                    name=tone.name,
                    description=tone.description or "",
                    chain=effects,
                )
            )

        # Use output_dir as project_root since we're managing paths ourselves
        return Comparison(
            meta=meta,
            di_tracks=[di_track],
            signal_chains=signal_chains,
            project_root=output_dir.parent.parent,  # Go up to data dir
        )

    async def _process_comparison(
        self,
        comparison: Comparison,
        output_dir: Path,
    ) -> Path:
        """Process the comparison and generate outputs.

        This wraps the synchronous pipeline processing in asyncio.to_thread()
        to avoid blocking the event loop.

        Args:
            comparison: The comparison configuration.
            output_dir: Output directory for this job.

        Returns:
            Path to the generated video file.
        """
        from guitar_tone_shootout.pipeline import PipelineError as PipelineLibError
        from guitar_tone_shootout.pipeline import process_comparison

        # Calculate progress steps based on segment count
        segment_count = comparison.segment_count

        async def process_with_progress() -> Path:
            """Run processing with progress updates."""
            # Since the pipeline library is synchronous, we run it in a thread
            # and provide progress updates at key milestones
            try:
                # Run the full processing in a thread
                video_path: Path = await asyncio.to_thread(
                    process_comparison,
                    comparison,
                    None,  # duration - use full DI track
                )
                return video_path
            except PipelineLibError as e:
                raise PipelineError(str(e)) from e

        # Update progress during processing (approximation)
        # The actual processing is blocking, so we report before/after
        await self._progress(15, f"Processing {segment_count} segment(s)...")

        # Run the processing
        video_path = await process_with_progress()

        await self._progress(95, "Finalizing output...")

        return video_path

    async def validate_di_track(self, file_path: Path) -> dict[str, object]:
        """Validate a DI track file.

        Args:
            file_path: Path to the DI track file.

        Returns:
            Dict with file info (duration, sample_rate, channels).

        Raises:
            PipelineError: If file is invalid.
        """
        from guitar_tone_shootout.audio import AudioProcessingError, load_audio

        try:
            # Load audio to validate format
            audio, sample_rate = await asyncio.to_thread(load_audio, file_path)

            # Calculate duration
            duration = len(audio) / sample_rate

            return {
                "duration": duration,
                "sample_rate": sample_rate,
                "samples": len(audio),
            }
        except AudioProcessingError as e:
            raise PipelineError(f"Invalid DI track: {e}") from e


class ShootoutConfig:
    """Configuration for a shootout comparison.

    This replaces the INI-based configuration for web requests.
    """

    def __init__(
        self,
        name: str,
        tones: list[ToneConfig],
        author: str | None = None,
        description: str | None = None,
        guitar: str | None = None,
        pickup: str | None = None,
    ) -> None:
        """Initialize shootout configuration.

        Args:
            name: Name of the shootout comparison.
            tones: List of tone configurations to compare.
            author: Author name.
            description: Description of the comparison.
            guitar: Guitar used for DI recording.
            pickup: Pickup configuration used.
        """
        self.name = name
        self.tones = tones
        self.author = author
        self.description = description
        self.guitar = guitar
        self.pickup = pickup


class ToneConfig:
    """Configuration for a single tone in a shootout."""

    def __init__(
        self,
        name: str,
        model_path: str | None = None,
        ir_path: str | None = None,
        tone3000_model_id: int | None = None,
        description: str | None = None,
        highpass: bool = True,
        effects: list[EffectConfig] | None = None,
    ) -> None:
        """Initialize tone configuration.

        Args:
            name: Display name for this tone.
            model_path: Path to NAM model file (relative to models dir).
            ir_path: Path to IR file (relative to IRs dir).
            tone3000_model_id: Tone 3000 model ID for downloading.
            description: Description of the tone.
            highpass: Apply 80Hz highpass filter before processing.
            effects: Additional effects to apply.
        """
        self.name = name
        self.model_path = model_path
        self.ir_path = ir_path
        self.tone3000_model_id = tone3000_model_id
        self.description = description
        self.highpass = highpass
        self.effects = effects or []


class EffectConfig:
    """Configuration for an audio effect."""

    def __init__(self, effect_type: str, value: str) -> None:
        """Initialize effect configuration.

        Args:
            effect_type: Type of effect (eq, reverb, delay, gain).
            value: Effect parameters or preset name.
        """
        self.effect_type = effect_type
        self.value = value
