"""Typer CLI for the epic workflow pipeline.

Provides subcommand routing for:
  ./wf epic N              — Full pipeline (ingest -> execute)
  ./wf epic status N       — Show progress from JSONL logs
  ./wf epic validate-plan N — Run Phase A deterministic validation only
  ./wf map codebase        — Regenerate .planning/codebase/ files
  ./wf map wiki            — Regenerate .planning/wiki-indexes/
  ./wf map all             — Both of the above
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

app = typer.Typer(
    name="wf",
    help="Epic workflow pipeline for Guitar Tone Shootout.",
    no_args_is_help=True,
)

epic_app = typer.Typer(
    name="epic",
    help="Epic pipeline commands.",
    no_args_is_help=True,
    invoke_without_command=True,
)

map_app = typer.Typer(
    name="map",
    help="Regenerate codebase and wiki maps.",
    no_args_is_help=True,
)

app.add_typer(epic_app, name="epic")
app.add_typer(map_app, name="map")

console = Console()

PROJECT_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Epic commands
# ---------------------------------------------------------------------------


@epic_app.callback(invoke_without_command=True)
def epic_callback(
    ctx: typer.Context,
    epic_number: int = typer.Argument(None, help="Epic number to run the full pipeline for."),
) -> None:
    """Run the full epic pipeline, or use a subcommand."""
    if ctx.invoked_subcommand is not None:
        return
    if epic_number is None:
        raise typer.BadParameter("Epic number is required. Usage: ./wf epic N")
    console.print(f"[yellow]Epic {epic_number} full pipeline — not yet implemented.[/yellow]")
    raise typer.Exit(1)


@epic_app.command("status")
def epic_status(
    epic_number: int = typer.Argument(..., help="Epic number to check status for."),
) -> None:
    """Show epic progress from JSONL logs (read-only)."""
    console.print(f"[yellow]Epic {epic_number} status — not yet implemented.[/yellow]")
    raise typer.Exit(1)


@epic_app.command("validate-plan")
def epic_validate_plan(
    epic_number: int = typer.Argument(..., help="Epic number to validate plan for."),
) -> None:
    """Run Phase A deterministic validation only (read-only)."""
    console.print(f"[yellow]Epic {epic_number} plan validation — not yet implemented.[/yellow]")
    raise typer.Exit(1)


# ---------------------------------------------------------------------------
# Map commands
# ---------------------------------------------------------------------------


@map_app.command("codebase")
def map_codebase() -> None:
    """Regenerate .planning/codebase/ files (deterministic, <10s)."""
    from workflow.codebase_mapper import (
        _write_endpoints,
        _write_imports,
        _write_schema,
        _write_structure,
        _write_tests,
    )

    output_dir = PROJECT_ROOT / ".planning" / "codebase"
    output_dir.mkdir(parents=True, exist_ok=True)

    console.print(f"Project root: {PROJECT_ROOT}")
    console.print(f"Output dir:   {output_dir}")
    console.print()

    writers = [
        ("STRUCTURE.md", _write_structure),
        ("SCHEMA.md", _write_schema),
        ("ENDPOINTS.md", _write_endpoints),
        ("IMPORTS.md", _write_imports),
        ("TESTS.md", _write_tests),
    ]

    total_chars = 0
    for label, writer in writers:
        path = writer(PROJECT_ROOT, output_dir)
        size = path.stat().st_size
        total_chars += size
        console.print(f"  {label:20s} {size:>8,d} bytes")

    est_tokens = total_chars // 4
    console.print()
    console.print(f"Total: {total_chars:,d} characters (~{est_tokens:,d} tokens)")


@map_app.command("wiki")
def map_wiki() -> None:
    """Regenerate .planning/wiki-indexes/ (deterministic, <5s)."""
    from workflow.wiki_indexer import index_wiki

    wiki_dir = (PROJECT_ROOT.parent / "wiki").resolve()
    output_dir = PROJECT_ROOT / ".planning" / "wiki-indexes"

    if not wiki_dir.is_dir():
        console.print(f"[red]Error: wiki directory does not exist: {wiki_dir}[/red]")
        raise typer.Exit(1)

    console.print(f"Wiki dir:    {wiki_dir}")
    console.print(f"Output dir:  {output_dir}")
    console.print()

    generated = index_wiki(wiki_dir, output_dir)

    console.print()
    console.print(f"Generated {len(generated)} index files in {output_dir}")


@map_app.command("all")
def map_all() -> None:
    """Regenerate both codebase and wiki maps."""
    map_codebase()
    console.print()
    console.rule()
    console.print()
    map_wiki()


def main() -> None:
    """Entry point called by the wf script."""
    app()
