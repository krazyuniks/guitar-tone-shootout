"""Main processing pipeline for Guitar Tone Shootout."""

import logging
import subprocess
from pathlib import Path

from guitar_tone_shootout.config import Comparison, DITrack, SignalChain

logger = logging.getLogger(__name__)


def process_comparison(comparison: Comparison) -> Path:
    """
    Process a complete comparison and generate outputs.

    Args:
        comparison: Validated Comparison configuration

    Returns:
        Path to the generated video file
    """
    logger.info(f"Processing comparison: {comparison.meta.name}")
    logger.info(f"Segments to generate: {comparison.segment_count}")

    output_dir = Path("outputs")
    clips_dir = output_dir / "clips"
    audio_dir = output_dir / "audio"
    images_dir = output_dir / "images"
    video_dir = output_dir / "videos"

    # Ensure output directories exist
    for dir_path in [clips_dir, audio_dir, images_dir, video_dir]:
        dir_path.mkdir(parents=True, exist_ok=True)

    # Generate safe filename base from comparison name
    safe_name = _sanitize_filename(comparison.meta.name)

    clip_paths: list[Path] = []
    audio_paths: list[Path] = []

    for i, (di_track, signal_chain) in enumerate(comparison.get_segments()):
        logger.info(f"Processing segment {i + 1}/{comparison.segment_count}")
        logger.info(f"  DI: {di_track.file.name} ({di_track.guitar}, {di_track.pickup})")
        logger.info(f"  Chain: {signal_chain.name}")

        # Step 1: Trim silence from DI track
        trimmed_di = trim_silence(di_track.file)

        # Step 2: Process audio through signal chain
        processed_audio = process_signal_chain(
            di_track=trimmed_di,
            signal_chain=signal_chain,
            output_path=audio_dir / f"{safe_name}_{i:03d}.flac",
        )
        audio_paths.append(processed_audio)

        # Step 3: Generate image for this segment
        image = generate_image(
            comparison=comparison,
            di_track=di_track,
            signal_chain=signal_chain,
            output_path=images_dir / f"{safe_name}_{i:03d}.png",
        )

        # Step 4: Create video clip from image + audio
        clip = create_clip(
            image=image,
            audio=processed_audio,
            output_path=clips_dir / f"{safe_name}_{i:03d}.mp4",
        )
        clip_paths.append(clip)

    # Step 5: Concatenate all clips into master video
    master_video = concatenate_clips(
        clips=clip_paths,
        output_path=video_dir / f"{safe_name}.mp4",
    )

    # Step 6: Create combined FLAC audio file
    combined_audio = concatenate_audio(
        audio_files=audio_paths,
        output_path=audio_dir / f"{safe_name}_full.flac",
    )

    logger.info(f"Video: {master_video}")
    logger.info(f"Audio: {combined_audio}")

    return master_video


def trim_silence(audio_path: Path) -> Path:
    """
    Trim leading and trailing silence from an audio file using FFmpeg.

    Args:
        audio_path: Path to input audio file

    Returns:
        Path to trimmed audio file (temp file)
    """
    # TODO: Implement FFmpeg silenceremove filter
    logger.debug(f"Trimming silence from: {audio_path}")

    # For now, return original path (no-op)
    # Real implementation:
    # ffmpeg -i input.wav -af silenceremove=start_periods=1:start_silence=0.1:start_threshold=-50dB,
    #        areverse,silenceremove=start_periods=1:start_silence=0.1:start_threshold=-50dB,areverse
    #        output.wav
    return audio_path


def process_signal_chain(
    di_track: Path,
    signal_chain: SignalChain,  # noqa: ARG001
    output_path: Path,
) -> Path:
    """
    Process DI track through a signal chain using Pedalboard/NAM.

    Args:
        di_track: Path to DI audio file
        signal_chain: SignalChain with ordered effects
        output_path: Path for output FLAC file

    Returns:
        Path to processed audio file
    """
    # TODO: Implement signal chain processing
    # For each effect in signal_chain.chain:
    #   - nam: Load NAM model and process
    #   - ir: Apply convolution with IR file
    #   - eq/reverb/delay/gain: Apply Pedalboard built-in effects
    logger.debug(f"Processing signal chain: {di_track.name}")

    # Placeholder - creates empty file for now
    output_path.touch()
    return output_path


def generate_image(
    comparison: Comparison,  # noqa: ARG001
    di_track: DITrack,  # noqa: ARG001
    signal_chain: SignalChain,  # noqa: ARG001
    output_path: Path,
) -> Path:
    """
    Generate comparison image showing signal chain info.

    Args:
        comparison: Comparison configuration
        di_track: DI track with metadata
        signal_chain: Signal chain with effects
        output_path: Path for output PNG file

    Returns:
        Path to generated image
    """
    # TODO: Implement HTML/CSS -> image rendering
    # Template will show:
    # - Comparison name
    # - DI track info (guitar, pickup, notes)
    # - Signal chain (name, description, effects visualization)
    logger.debug(f"Generating image: {output_path}")

    # Placeholder implementation
    output_path.touch()
    return output_path


def create_clip(
    image: Path,  # noqa: ARG001
    audio: Path,  # noqa: ARG001
    output_path: Path,
) -> Path:
    """
    Create video clip from static image and audio using FFmpeg.

    Args:
        image: Path to image file
        audio: Path to audio file
        output_path: Path for output MP4 file

    Returns:
        Path to video clip
    """
    # TODO: Implement FFmpeg video creation
    logger.debug(f"Creating clip: {output_path}")

    # Real implementation:
    # ffmpeg -loop 1 -i image.png -i audio.flac -c:v libx264 -tune stillimage
    #        -c:a aac -b:a 384k -ar 48000 -shortest -pix_fmt yuv420p output.mp4

    output_path.touch()
    return output_path


def concatenate_clips(
    clips: list[Path],
    output_path: Path,
) -> Path:
    """
    Concatenate multiple video clips into a single video using FFmpeg.

    Args:
        clips: List of clip paths in order
        output_path: Path for output MP4 file

    Returns:
        Path to concatenated video
    """
    # TODO: Implement FFmpeg concatenation
    logger.debug(f"Concatenating {len(clips)} clips -> {output_path}")

    # Real implementation:
    # Create concat file list, then:
    # ffmpeg -f concat -safe 0 -i concat_list.txt -c copy output.mp4

    output_path.touch()
    return output_path


def concatenate_audio(
    audio_files: list[Path],
    output_path: Path,
) -> Path:
    """
    Concatenate multiple audio files into a single FLAC file.

    Args:
        audio_files: List of audio paths in order
        output_path: Path for output FLAC file

    Returns:
        Path to concatenated audio
    """
    # TODO: Implement FFmpeg audio concatenation
    logger.debug(f"Concatenating {len(audio_files)} audio files -> {output_path}")

    output_path.touch()
    return output_path


def _sanitize_filename(name: str) -> str:
    """Convert a name to a safe filename."""
    # Replace spaces with underscores, remove special chars
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
    # Collapse multiple underscores
    while "__" in safe:
        safe = safe.replace("__", "_")
    return safe.strip("_").lower()


def _run_ffmpeg(args: list[str]) -> subprocess.CompletedProcess[str]:
    """Run FFmpeg with given arguments."""
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "warning", *args]
    logger.debug(f"Running: {' '.join(cmd)}")
    return subprocess.run(cmd, check=True, capture_output=True, text=True)
