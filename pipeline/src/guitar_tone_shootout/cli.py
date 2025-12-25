"""Command-line interface for Guitar Tone Shootout."""

import logging
from pathlib import Path

import click
from rich.console import Console
from rich.logging import RichHandler

from guitar_tone_shootout.config import load_comparison
from guitar_tone_shootout.pipeline import process_comparison

console = Console()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[RichHandler(console=console, rich_tracebacks=True)],
)
logger = logging.getLogger(__name__)


@click.group()
@click.version_option()
def main() -> None:
    """Guitar Tone Shootout - Create amp/cab comparison videos."""
    pass


@main.command()
@click.argument("ini_file", type=click.Path(exists=True, path_type=Path))
def process(ini_file: Path) -> None:
    """Process a comparison INI file and generate outputs."""
    logger.info(f"Processing: {ini_file}")

    try:
        comparison = load_comparison(ini_file)
        process_comparison(comparison)
        logger.info("✓ Processing complete")
    except Exception as e:
        logger.error(f"Processing failed: {e}")
        raise click.Abort() from e


@main.command()
@click.argument("ini_file", type=click.Path(exists=True, path_type=Path))
def validate(ini_file: Path) -> None:
    """Validate a comparison INI file without processing."""
    logger.info(f"Validating: {ini_file}")

    try:
        comparison = load_comparison(ini_file)
        console.print(f"[green]✓ Valid comparison: {comparison.meta.name}[/green]")
        console.print(f"  DI tracks: {len(comparison.di_tracks)}")
        console.print(f"  Signal chains: {len(comparison.signal_chains)}")
        console.print(f"  Total segments: {comparison.segment_count}")
    except Exception as e:
        console.print(f"[red]✗ Invalid: {e}[/red]")
        raise click.Abort() from e


@main.command("list-models")
def list_models() -> None:
    """List available NAM models."""
    models_dir = Path("inputs/nam_models")
    if not models_dir.exists():
        console.print("[yellow]No NAM models directory found[/yellow]")
        return

    models = list(models_dir.rglob("*.nam"))
    if not models:
        console.print("[yellow]No NAM models found[/yellow]")
        return

    console.print(f"[green]Found {len(models)} NAM models:[/green]")
    for model in sorted(models):
        console.print(f"  {model.relative_to(models_dir)}")


@main.command("list-irs")
def list_irs() -> None:
    """List available impulse responses."""
    irs_dir = Path("inputs/irs")
    if not irs_dir.exists():
        console.print("[yellow]No IRs directory found[/yellow]")
        return

    irs = list(irs_dir.rglob("*.wav"))
    if not irs:
        console.print("[yellow]No IRs found[/yellow]")
        return

    console.print(f"[green]Found {len(irs)} IRs:[/green]")
    for ir in sorted(irs):
        console.print(f"  {ir.relative_to(irs_dir)}")


@main.command("list-di")
def list_di() -> None:
    """List available DI tracks."""
    di_dir = Path("inputs/di_tracks")
    if not di_dir.exists():
        console.print("[yellow]No DI tracks directory found[/yellow]")
        return

    tracks = list(di_dir.glob("*.wav")) + list(di_dir.glob("*.flac"))
    if not tracks:
        console.print("[yellow]No DI tracks found[/yellow]")
        return

    console.print(f"[green]Found {len(tracks)} DI tracks:[/green]")
    for track in sorted(tracks):
        console.print(f"  {track.name}")


@main.command("download-model")
@click.argument("url")
def download_model(url: str) -> None:
    """Download a NAM model from Tone3000.com."""
    # TODO: Implement Tone3000 download
    console.print(f"[yellow]Download not yet implemented: {url}[/yellow]")


if __name__ == "__main__":
    main()
