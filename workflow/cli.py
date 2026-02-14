"""Typer CLI for the epic workflow pipeline.

Provides subcommand routing for:
  ./wf epic N              — Full pipeline (Steps 1-7: ingest -> plan -> verify -> commit)
  ./wf epic status N       — Show progress from JSONL logs
  ./wf epic validate-plan N — Run Phase A deterministic validation only (read-only)
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
# Pipeline helpers
# ---------------------------------------------------------------------------


def _should_skip(artefact_path: Path, label: str) -> bool:
    """Prompt the user to skip a step if its output artefact already exists.

    Returns True if the user wants to skip, False to re-run.
    """
    if not artefact_path.exists():
        return False

    skip = typer.confirm(
        f"{label} already exists at {artefact_path.name}. Skip?",
        default=True,
    )
    return skip


def _check_plan_committed(epic_dir: Path) -> bool:
    """Check if a plan_committed event exists in epic.jsonl."""
    from workflow.jsonl_logger import find_last_event, read_log

    log_path = epic_dir / "epic.jsonl"
    events = read_log(log_path)
    return find_last_event(events, "plan_committed") is not None


def _load_decisions(epic_dir: Path) -> dict:
    """Load user-decisions.json from the epic directory."""
    import json

    decisions_path = epic_dir / "user-decisions.json"
    if not decisions_path.is_file():
        return {}
    return json.loads(decisions_path.read_text(encoding="utf-8"))


def _run_pipeline(epic_number: int) -> None:
    """Run Steps 1-7 of the epic pipeline: ingest -> commit+push."""
    import logging
    import uuid

    from workflow.context_assembler import AssemblyError, assemble_context
    from workflow.epic_ingest import IngestionError, ingest_epic
    from workflow.git_helpers import GitPushError, robust_commit
    from workflow.jsonl_logger import EventLogger
    from workflow.plan_generator import PlanGenerationError, generate_plan
    from workflow.plan_verifier import (
        DecisionGateResult,
        PlanVerificationError,
        present_decision_gate,
        verify_with_revision_cycle,
    )
    from workflow.scope_discussion import ScopeDiscussionError, run_scope_discussion

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    epic_dir = PROJECT_ROOT / ".planning" / "epics" / f"E{epic_number}"

    # Check for already-committed plan — skip directly to Stage 4
    if _check_plan_committed(epic_dir):
        console.print(
            "[green]Plan already committed.[/green] " "Stage 4 execution not yet implemented."
        )
        return

    # Set up JSONL logging for planning events
    run_id = str(uuid.uuid4())
    epic_logger = EventLogger(epic_dir / "epic.jsonl", run_id)

    # Step 1: Ingestion
    epic_md_path = epic_dir / "EPIC.md"
    if _should_skip(epic_md_path, "EPIC.md"):
        console.print("[dim]Step 1: Ingestion — skipped[/dim]")
    else:
        console.print(f"[bold]Step 1:[/bold] Ingesting epic #{epic_number}...")
        try:
            path = ingest_epic(epic_number)
            console.print(f"  [green]Written:[/green] {path.relative_to(PROJECT_ROOT)}")
        except IngestionError as exc:
            console.print(f"  [red]Error:[/red] {exc}")
            raise typer.Exit(1) from exc

    # Step 2: Context Assembly
    context_path = epic_dir / "CONTEXT.md"
    if _should_skip(context_path, "CONTEXT.md"):
        console.print("[dim]Step 2: Context Assembly — skipped[/dim]")
    else:
        console.print("[bold]Step 2:[/bold] Assembling context...")
        try:
            path = assemble_context(epic_dir, PROJECT_ROOT)
            size = path.stat().st_size
            console.print(
                f"  [green]Written:[/green] {path.relative_to(PROJECT_ROOT)} "
                f"({size:,d} bytes, ~{size // 4:,d} tokens)"
            )
        except AssemblyError as exc:
            console.print(f"  [red]Error:[/red] {exc}")
            raise typer.Exit(1) from exc

    # Step 3: Scope Discussion
    decisions_path = epic_dir / "user-decisions.json"
    if _should_skip(decisions_path, "user-decisions.json"):
        console.print("[dim]Step 3: Scope Discussion — skipped[/dim]")
    else:
        console.print("[bold]Step 3:[/bold] Scope discussion...")
        try:
            decisions = run_scope_discussion(epic_dir)
            console.print(f"  [green]{len(decisions)} decisions recorded.[/green]")
        except ScopeDiscussionError as exc:
            console.print(f"  [red]Error:[/red] {exc}")
            raise typer.Exit(1) from exc

    console.print()

    # Step 4: Plan Generation
    plan_json_path = epic_dir / "plan.json"
    plan_md_path = epic_dir / "PLAN.md"
    if _should_skip(plan_json_path, "plan.json"):
        console.print("[dim]Step 4: Plan Generation — skipped[/dim]")
    else:
        console.print("[bold]Step 4:[/bold] Generating plan...")
        loaded_decisions = _load_decisions(epic_dir)

        epic_logger.log_event(
            "planner_dispatched",
            epic=epic_number,
            attempt=1,
            tier="high",
        )

        try:
            plan_md_path, plan_json_path = generate_plan(epic_dir, loaded_decisions)
            size = plan_json_path.stat().st_size
            console.print(
                f"  [green]Written:[/green] {plan_json_path.relative_to(PROJECT_ROOT)} "
                f"({size:,d} bytes)"
            )
            console.print(f"  [green]Written:[/green] {plan_md_path.relative_to(PROJECT_ROOT)}")
            epic_logger.log_event(
                "planner_complete",
                epic=epic_number,
                attempt=1,
                response_path=str(plan_json_path.relative_to(PROJECT_ROOT)),
            )
        except PlanGenerationError as exc:
            epic_logger.log_event(
                "planner_failed",
                epic=epic_number,
                attempt=1,
                error=str(exc),
            )
            console.print(f"  [red]Error:[/red] {exc}")
            raise typer.Exit(1) from exc

    # Step 5: Verification (Phase A + Phase B with revision cycle)
    console.print()
    console.print("[bold]Step 5:[/bold] Verifying plan...")
    loaded_decisions = _load_decisions(epic_dir)

    try:
        verifier_result, success = verify_with_revision_cycle(epic_dir, loaded_decisions)
    except PlanVerificationError as exc:
        console.print(f"  [red]Error:[/red] {exc}")
        raise typer.Exit(1) from exc

    if success:
        epic_logger.log_event("phase_a_pass", epic=epic_number, attempt=1)
        scores = {
            dim: verifier_result.get(dim, {}).get("status", "unknown")
            for dim in [
                "journey_completeness",
                "transition_coverage",
                "intent_alignment",
                "gap_detection",
                "validation_sufficiency",
            ]
        }
        epic_logger.log_event("phase_b_pass", epic=epic_number, attempt=1, scores=scores)
        console.print("  [green]Plan verified successfully.[/green]")
    else:
        phase_a_errors = verifier_result.get("phase_a_errors", [])
        if phase_a_errors:
            epic_logger.log_event(
                "phase_a_fail",
                epic=epic_number,
                attempt=1,
                checks_failed=phase_a_errors,
            )
            console.print("  [red]Phase A validation failed after revision.[/red]")
            for err in phase_a_errors[:5]:
                console.print(f"    - {err}")
        else:
            epic_logger.log_event(
                "phase_b_fail",
                epic=epic_number,
                attempt=1,
                feedback=str(verifier_result),
            )
            console.print("  [red]Phase B verification failed after revision.[/red]")

        console.print("\n  Plan verification failed. Review plan.json and PLAN.md manually.")
        # Fall through to Decision Gate — human can still approve

    # Step 6: Decision Gate
    console.print()
    plan_md_path = epic_dir / "PLAN.md"
    gate_result: DecisionGateResult = present_decision_gate(plan_md_path, verifier_result)

    if gate_result.approved:
        epic_logger.log_event("plan_approved", epic=epic_number)
        console.print("\n[green]Plan approved.[/green]")
    elif gate_result.needs_revision:
        epic_logger.log_event("plan_revised", epic=epic_number)
        console.print(
            "\n[yellow]Plan marked for revision.[/yellow] "
            "Edit plan.json and PLAN.md, then re-run:\n"
            f"  ./wf epic validate-plan {epic_number}\n"
            f"  ./wf epic {epic_number}"
        )
        return
    elif gate_result.rejected:
        epic_logger.log_event("plan_rejected", epic=epic_number)
        console.print("\n[red]Plan rejected.[/red] Artefacts remain uncommitted.")
        return

    # Step 7: Commit + Push
    console.print()
    console.print("[bold]Step 7:[/bold] Committing planning artefacts...")

    planning_paths = [
        str(epic_dir.relative_to(PROJECT_ROOT)),
    ]

    try:
        commit_hash = robust_commit(
            f"plan(epic-{epic_number}): planning artefacts approved",
            planning_paths,
        )
        console.print(f"  [green]Committed:[/green] {commit_hash}")
    except Exception as exc:
        console.print(f"  [red]Commit failed:[/red] {exc}")
        raise typer.Exit(1) from exc

    # Push to remote
    console.print("  Pushing to remote...")
    try:
        from workflow.git_helpers import git_sync

        git_sync()
        console.print("  [green]Pushed successfully.[/green]")
    except GitPushError as exc:
        console.print(f"  [red]Push failed:[/red] {exc}")
        raise typer.Exit(1) from exc

    epic_logger.log_event("plan_committed", epic=epic_number, commit=commit_hash)

    console.print()
    console.print("[green]Stage 3 complete.[/green] " "Stage 4 execution not yet implemented.")


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
    _run_pipeline(epic_number)


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
    from workflow.plan_validator import validate_plan

    epic_dir = PROJECT_ROOT / ".planning" / "epics" / f"E{epic_number}"
    if not epic_dir.is_dir():
        console.print(f"[red]Error: Epic directory not found: {epic_dir}[/red]")
        raise typer.Exit(1)

    console.print(f"[bold]Phase A validation[/bold] for epic #{epic_number}...")
    result = validate_plan(epic_dir)

    if result.valid:
        console.print(f"[green]Phase A validation PASSED[/green] ({epic_number})")
    else:
        console.print(f"[red]Phase A validation FAILED[/red] ({epic_number}):")
        for error in result.errors:
            console.print(f"  [red]-[/red] {error}")
        console.print(f"\n{len(result.errors)} error(s) found.")
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
