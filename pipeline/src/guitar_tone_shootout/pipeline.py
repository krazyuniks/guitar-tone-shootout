"""Main processing pipeline for Guitar Tone Shootout."""

import logging
import subprocess
import tempfile
from pathlib import Path

from guitar_tone_shootout.audio import (
    AudioProcessingError,
    load_audio,
    process_chain,
    save_audio,
)
from guitar_tone_shootout.config import Comparison, DITrack, SignalChain

logger = logging.getLogger(__name__)


class PipelineError(Exception):
    """Error during pipeline processing."""


def process_comparison(comparison: Comparison, duration: float | None = None) -> Path:
    """
    Process a complete comparison and generate outputs.

    Args:
        comparison: Validated Comparison configuration
        duration: Optional duration in seconds to trim DI tracks to

    Returns:
        Path to the generated video file
    """
    logger.info(f"Processing comparison: {comparison.meta.name}")
    logger.info(f"Segments to generate: {comparison.segment_count}")

    # Generate safe filename base from comparison name
    safe_name = _sanitize_filename(comparison.meta.name)

    # Use project root for all paths
    project_root = comparison.project_root

    # Output structure: outputs/<shootout_name>/{video, audio/, images/, clips/}
    output_dir = project_root / "outputs" / safe_name
    clips_dir = output_dir / "clips"
    audio_dir = output_dir / "audio"
    images_dir = output_dir / "images"

    # Ensure output directories exist
    for dir_path in [output_dir, clips_dir, audio_dir, images_dir]:
        dir_path.mkdir(parents=True, exist_ok=True)

    clip_paths: list[Path] = []
    audio_paths: list[Path] = []

    for i, (di_track, signal_chain) in enumerate(comparison.get_segments()):
        logger.info(f"Processing segment {i + 1}/{comparison.segment_count}")
        logger.info(f"  DI: {di_track.file.name} ({di_track.guitar}, {di_track.pickup})")
        logger.info(f"  Chain: {signal_chain.name}")

        # Step 1: Trim DI track (to duration if specified, otherwise just silence)
        if duration is not None:
            trimmed_di = trim_to_duration(di_track.file, duration)
        else:
            trimmed_di = trim_silence(di_track.file)

        # Step 2: Process audio through signal chain
        processed_audio = process_signal_chain(
            di_track=trimmed_di,
            signal_chain=signal_chain,
            output_path=audio_dir / f"{safe_name}_{i:03d}.flac",
            project_root=project_root,
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

    # Step 5: Concatenate all clips into master video (main output in root folder)
    master_video = concatenate_clips(
        clips=clip_paths,
        output_path=output_dir / f"{safe_name}.mp4",
    )

    # Step 6: Create combined FLAC audio file
    combined_audio = concatenate_audio(
        audio_files=audio_paths,
        output_path=audio_dir / f"{safe_name}_full.flac",
    )

    logger.info(f"Video: {master_video}")
    logger.info(f"Audio: {combined_audio}")

    return master_video


def trim_silence(audio_path: Path, threshold_db: float = -50.0) -> Path:
    """
    Trim leading and trailing silence from an audio file using FFmpeg.

    Args:
        audio_path: Path to input audio file
        threshold_db: Silence threshold in dB (default -50dB)

    Returns:
        Path to trimmed audio file (temp file)
    """
    if not audio_path.exists():
        raise PipelineError(f"Audio file not found: {audio_path}")

    logger.debug(f"Trimming silence from: {audio_path}")

    # Create temp file for output
    suffix = audio_path.suffix
    _temp_fd, temp_path = tempfile.mkstemp(suffix=suffix)

    try:
        # FFmpeg silenceremove filter:
        # - Remove silence from start (start_periods=1)
        # - Reverse, remove silence from start again (removes end silence)
        # - Reverse back to original direction
        filter_complex = (
            f"silenceremove=start_periods=1:start_silence=0.05"
            f":start_threshold={threshold_db}dB,"
            f"areverse,"
            f"silenceremove=start_periods=1:start_silence=0.05"
            f":start_threshold={threshold_db}dB,"
            f"areverse"
        )

        _run_ffmpeg(
            [
                "-i",
                str(audio_path),
                "-af",
                filter_complex,
                str(temp_path),
            ]
        )

        return Path(temp_path)

    except subprocess.CalledProcessError as e:
        Path(temp_path).unlink(missing_ok=True)
        raise PipelineError(f"Failed to trim silence: {e.stderr}") from e


def trim_to_duration(audio_path: Path, duration: float) -> Path:
    """
    Trim an audio file to a specific duration using FFmpeg.

    Args:
        audio_path: Path to input audio file
        duration: Duration in seconds to trim to

    Returns:
        Path to trimmed audio file (temp file)
    """
    if not audio_path.exists():
        raise PipelineError(f"Audio file not found: {audio_path}")

    logger.debug(f"Trimming to {duration}s: {audio_path}")

    # Create temp file for output
    suffix = audio_path.suffix
    _temp_fd, temp_path = tempfile.mkstemp(suffix=suffix)

    try:
        _run_ffmpeg(
            [
                "-i",
                str(audio_path),
                "-t",
                str(duration),
                "-c",
                "copy",
                str(temp_path),
            ]
        )

        return Path(temp_path)

    except subprocess.CalledProcessError as e:
        Path(temp_path).unlink(missing_ok=True)
        raise PipelineError(f"Failed to trim to duration: {e.stderr}") from e


def process_signal_chain(
    di_track: Path,
    signal_chain: SignalChain,
    output_path: Path,
    project_root: Path,
) -> Path:
    """
    Process DI track through a signal chain using NAM/Pedalboard.

    Args:
        di_track: Path to DI audio file
        signal_chain: SignalChain with ordered effects
        output_path: Path for output FLAC file
        project_root: Project root directory for resolving input paths

    Returns:
        Path to processed audio file
    """
    logger.debug(f"Processing signal chain '{signal_chain.name}' on: {di_track.name}")

    try:
        # Load audio
        audio, sample_rate = load_audio(di_track)

        # Process through chain
        processed = process_chain(audio, sample_rate, signal_chain.chain, project_root)

        # Save output
        save_audio(processed, output_path, sample_rate)

        return output_path

    except AudioProcessingError as e:
        raise PipelineError(f"Audio processing failed: {e}") from e


def generate_image(
    comparison: Comparison,
    di_track: DITrack,
    signal_chain: SignalChain,
    output_path: Path,
) -> Path:
    """
    Generate comparison image showing signal chain info.

    Uses Playwright to render HTML template to PNG.

    Args:
        comparison: Comparison configuration
        di_track: DI track with metadata
        signal_chain: Signal chain with effects
        output_path: Path for output PNG file

    Returns:
        Path to generated image
    """
    from jinja2 import Environment, FileSystemLoader

    logger.debug(f"Generating image: {output_path}")

    # Template directory (relative to project root)
    template_dir = comparison.project_root / "templates"
    if not template_dir.exists():
        template_dir.mkdir(parents=True)
        # Create default template if none exists
        _create_default_template(template_dir)

    # Render HTML from template
    env = Environment(loader=FileSystemLoader(str(template_dir)))

    try:
        template = env.get_template("comparison.html")
    except Exception:
        _create_default_template(template_dir)
        template = env.get_template("comparison.html")

    # Extract NAM model and IR info from signal chain
    amp_name, amp_source = _extract_effect_info(signal_chain, "nam")
    cab_name, cab_source = _extract_effect_info(signal_chain, "ir")

    html_content = template.render(
        comparison_name=comparison.meta.name,
        guitar=di_track.guitar,
        pickup=di_track.pickup,
        signal_chain_name=signal_chain.name,
        signal_chain_description=signal_chain.description,
        amp_name=amp_name,
        amp_source=amp_source,
        cab_name=cab_name,
        cab_source=cab_source,
        author=comparison.meta.author,
        effects=signal_chain.chain,
    )

    # Write HTML to temp file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False) as temp_html:
        temp_html.write(html_content)
        temp_html_path = Path(temp_html.name)

    try:
        # Use Playwright to screenshot HTML
        _render_html_to_png(temp_html_path, output_path)
        return output_path
    finally:
        temp_html_path.unlink(missing_ok=True)


def _create_default_template(template_dir: Path) -> None:
    """Create default HTML template for comparison images."""
    template_content = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            width: 1920px;
            height: 1080px;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            color: #fff;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            padding: 60px;
        }
        .container {
            width: 100%;
            max-width: 1600px;
        }
        h1 {
            font-size: 64px;
            font-weight: 700;
            margin-bottom: 40px;
            text-align: center;
            color: #e94560;
        }
        .info-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 40px;
            margin-bottom: 40px;
        }
        .info-box {
            background: rgba(255,255,255,0.05);
            border-radius: 20px;
            padding: 40px;
            border: 1px solid rgba(255,255,255,0.1);
        }
        .info-box h2 {
            font-size: 28px;
            color: #0f3460;
            background: #e94560;
            display: inline-block;
            padding: 8px 20px;
            border-radius: 8px;
            margin-bottom: 20px;
        }
        .info-box p {
            font-size: 24px;
            line-height: 1.6;
            color: rgba(255,255,255,0.9);
        }
        .chain-box {
            background: rgba(255,255,255,0.05);
            border-radius: 20px;
            padding: 40px;
            border: 1px solid rgba(255,255,255,0.1);
        }
        .chain-box h2 {
            font-size: 36px;
            color: #e94560;
            margin-bottom: 30px;
        }
        .chain-effects {
            display: flex;
            flex-wrap: wrap;
            gap: 20px;
        }
        .effect {
            background: linear-gradient(135deg, #e94560 0%, #0f3460 100%);
            padding: 20px 30px;
            border-radius: 12px;
            font-size: 20px;
            font-weight: 600;
        }
        .effect-type {
            text-transform: uppercase;
            font-size: 14px;
            opacity: 0.8;
            display: block;
            margin-bottom: 4px;
        }
        .author {
            text-align: center;
            margin-top: 40px;
            font-size: 20px;
            opacity: 0.6;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>{{ comparison_name }}</h1>

        <div class="info-grid">
            <div class="info-box">
                <h2>Guitar</h2>
                <p>{{ guitar }}</p>
                <p style="margin-top: 10px; opacity: 0.7;">{{ pickup }}</p>
            </div>
            <div class="info-box">
                <h2>Signal Chain</h2>
                <p>{{ signal_chain_name }}</p>
                {% if signal_chain_description %}
                <p style="margin-top: 10px; opacity: 0.7;">{{ signal_chain_description }}</p>
                {% endif %}
            </div>
        </div>

        <div class="chain-box">
            <h2>Effects Chain</h2>
            <div class="chain-effects">
                {% for effect in effects %}
                <div class="effect">
                    <span class="effect-type">{{ effect.effect_type }}</span>
                    {{ effect.value | replace('/', ' / ') }}
                </div>
                {% endfor %}
            </div>
        </div>

        <p class="author">By {{ author }}</p>
    </div>
</body>
</html>"""

    template_path = template_dir / "comparison.html"
    template_path.write_text(template_content)
    logger.info(f"Created default template: {template_path}")


def _render_html_to_png(html_path: Path, output_path: Path) -> None:
    """Render HTML file to PNG using Playwright."""
    from playwright.sync_api import sync_playwright

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1920, "height": 1080})
        page.goto(f"file://{html_path.absolute()}")
        page.screenshot(path=str(output_path), full_page=False)
        browser.close()


def create_clip(
    image: Path,
    audio: Path,
    output_path: Path,
) -> Path:
    """
    Create video clip from static image and audio using FFmpeg.

    Output: H.264 video, AAC audio at 384kbps, 48kHz, 30fps.

    Args:
        image: Path to image file
        audio: Path to audio file
        output_path: Path for output MP4 file

    Returns:
        Path to video clip
    """
    if not image.exists():
        raise PipelineError(f"Image not found: {image}")
    if not audio.exists():
        raise PipelineError(f"Audio not found: {audio}")

    logger.debug(f"Creating clip: {output_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        _run_ffmpeg(
            [
                "-loop",
                "1",
                "-i",
                str(image),
                "-i",
                str(audio),
                "-c:v",
                "libx264",
                "-tune",
                "stillimage",
                "-c:a",
                "aac",
                "-b:a",
                "384k",
                "-ar",
                "48000",
                "-shortest",
                "-pix_fmt",
                "yuv420p",
                "-r",
                "30",
                str(output_path),
            ]
        )

        return output_path

    except subprocess.CalledProcessError as e:
        raise PipelineError(f"Failed to create clip: {e.stderr}") from e


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
    if not clips:
        raise PipelineError("No clips to concatenate")

    for clip in clips:
        if not clip.exists():
            raise PipelineError(f"Clip not found: {clip}")

    logger.debug(f"Concatenating {len(clips)} clips -> {output_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Create concat file list
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as concat_file:
        for clip in clips:
            # Escape single quotes in paths
            escaped_path = str(clip.absolute()).replace("'", "'\\''")
            concat_file.write(f"file '{escaped_path}'\n")
        concat_path = Path(concat_file.name)

    try:
        _run_ffmpeg(
            [
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_path),
                "-c",
                "copy",
                str(output_path),
            ]
        )

        return output_path

    except subprocess.CalledProcessError as e:
        raise PipelineError(f"Failed to concatenate clips: {e.stderr}") from e
    finally:
        concat_path.unlink(missing_ok=True)


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
    if not audio_files:
        raise PipelineError("No audio files to concatenate")

    for audio in audio_files:
        if not audio.exists():
            raise PipelineError(f"Audio file not found: {audio}")

    logger.debug(f"Concatenating {len(audio_files)} audio files -> {output_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Create concat file list
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as concat_file:
        for audio in audio_files:
            escaped_path = str(audio.absolute()).replace("'", "'\\''")
            concat_file.write(f"file '{escaped_path}'\n")
        concat_path = Path(concat_file.name)

    try:
        _run_ffmpeg(
            [
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_path),
                "-c:a",
                "flac",
                str(output_path),
            ]
        )

        return output_path

    except subprocess.CalledProcessError as e:
        raise PipelineError(f"Failed to concatenate audio: {e.stderr}") from e
    finally:
        concat_path.unlink(missing_ok=True)


def _extract_effect_info(signal_chain: SignalChain, effect_type: str) -> tuple[str, str]:
    """
    Extract display name and source from a signal chain effect.

    Args:
        signal_chain: The signal chain to search
        effect_type: Effect type to find ("nam" or "ir")

    Returns:
        Tuple of (display_name, source) - e.g., ("JCM800 capture 3", "Tone3000")
    """
    for effect in signal_chain.chain:
        if effect.effect_type == effect_type:
            # Parse path like "tone3000/jcm800-44269/JCM800 capture 3.nam"
            path_parts = effect.value.split("/")

            # Extract name from filename (remove extension)
            filename = path_parts[-1]
            name = filename.rsplit(".", 1)[0] if "." in filename else filename

            # Extract source from first path component (e.g., "tone3000" -> "Tone3000")
            source = path_parts[0].replace("_", " ").title() if len(path_parts) > 1 else "Unknown"

            return name, source

    return "None", ""


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
