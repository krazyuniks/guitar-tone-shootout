"""Typer CLI for the epic workflow pipeline.

Provides subcommand routing for:
  ./wf epic run N           — Full pipeline: ingest -> context -> plan -> verify -> gate -> execute
  ./wf epic status N        — Show progress from JSONL logs
  ./wf epic validate-plan N — Run Phase A deterministic validation only (read-only)
  ./wf map codebase         — Regenerate .planning/codebase/ files
  ./wf map wiki             — Regenerate .planning/wiki-indexes/
  ./wf map all              — Both of the above
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


def flush_stdin() -> None:
    """Discard any buffered stdin data before an interactive prompt.

    Earlier prompts (e.g. typer.confirm "Skip?") leave trailing newlines
    in the stdin buffer. Without flushing, downstream input()/typer.prompt()
    calls consume these as empty input — causing auto-skips and double-prompts.
    """
    import sys

    if not sys.stdin.isatty():
        return

    import termios

    termios.tcflush(sys.stdin, termios.TCIFLUSH)


def _should_skip(artefact_path: Path, label: str) -> bool:
    """Prompt the user to skip a step if its output artefact already exists.

    Returns True if the user wants to skip, False to re-run.
    In non-interactive mode, auto-skips (returns True) when the artefact exists.
    """
    if not artefact_path.exists():
        return False

    import sys as _sys

    if not _sys.stdin.isatty():
        return True

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


def _run_planning_pipeline(epic_number: int) -> None:
    """Run Steps 1-6 of the planning pipeline: ingest -> commit+push.

    This is the Stage 3 planning pipeline. Called by the orchestrator's
    run_pipeline() which then continues to Stage 4 execution.
    """
    import logging
    import uuid

    from workflow.context_assembler import AssemblyError, assemble_context
    from workflow.epic_config import ensure_epic_config, load_config
    from workflow.epic_ingest import IngestionError, ingest_epic
    from workflow.gap_detection import GapDetectionError, run_gap_detection
    from workflow.git_helpers import GitPushError, robust_commit
    from workflow.jsonl_logger import EventLogger
    from workflow.plan_generator import PlanGenerationError, generate_plan
    from workflow.plan_verifier import (
        DecisionGateResult,
        PlanVerificationError,
        present_decision_gate,
        verify_with_revision_cycle,
    )

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    epic_dir = PROJECT_ROOT / ".planning" / "epics" / f"E{epic_number}"

    # Check for already-committed plan — caller handles Stage 4
    if _check_plan_committed(epic_dir):
        console.print("[green]Plan already committed.[/green]")
        return

    # Load epic configuration profile
    config_path = ensure_epic_config(epic_dir)
    try:
        config = load_config(override_path=config_path)
    except (ValueError, FileNotFoundError) as exc:
        console.print(f"[red]Configuration error:[/red] {exc}")
        raise typer.Exit(1) from exc

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

    # Step 2b: Gap Detection
    decisions_path = epic_dir / "user-decisions.json"
    if _should_skip(decisions_path, "user-decisions.json"):
        console.print("[dim]Step 2b: Gap Detection — skipped[/dim]")
    else:
        console.print()
        console.print("[bold]Step 2b:[/bold] Gap detection...")
        try:
            path = run_gap_detection(epic_dir, epic_logger, config=config)
            console.print(f"  [green]Written:[/green] {path.relative_to(PROJECT_ROOT)}")
        except GapDetectionError as exc:
            console.print(f"  [red]Error:[/red] {exc}")
            raise typer.Exit(1) from exc

    # Step 3: Plan Generation
    plan_json_path = epic_dir / "plan.json"
    plan_md_path = epic_dir / "PLAN.md"
    if _should_skip(plan_json_path, "plan.json"):
        console.print("[dim]Step 3: Plan Generation — skipped[/dim]")
    else:
        console.print("[bold]Step 3:[/bold] Generating plan...")

        epic_logger.log_event(
            "planner_dispatched",
            epic=epic_number,
            attempt=1,
            planner_model=config.models.planner,
        )

        try:
            plan_md_path, plan_json_path = generate_plan(epic_dir, config=config)
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

    # Step 4: Verification (structural validation + cross-model review)
    critic_model = config.models.plan_critic if config else "codex"
    console.print()
    console.print("[bold]Step 4:[/bold] Verifying plan...")

    try:
        verifier_result, success = verify_with_revision_cycle(epic_dir, config=config)
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
            console.print("  [red]Structural validation failed after revision.[/red]")
            for err in phase_a_errors[:5]:
                console.print(f"    - {err}")
        else:
            epic_logger.log_event(
                "phase_b_fail",
                epic=epic_number,
                attempt=1,
                feedback=str(verifier_result),
            )
            console.print(
                f"  [yellow]{critic_model.capitalize()} verifier raised findings"
                " after revision.[/yellow]"
            )

        console.print("\n  Review findings at the Decision Gate below.")
        # Fall through to Decision Gate — human can still approve

    # Step 5: Decision Gate
    console.print()
    plan_md_path = epic_dir / "PLAN.md"

    # Non-TTY: auto-approve if verification passed or verifier-only findings,
    # auto-reject only if structural validation failed.
    import sys as _sys

    phase_a_errors = verifier_result.get("phase_a_errors", []) if not success else []

    if not _sys.stdin.isatty():
        if success:
            gate_result = DecisionGateResult("approve", reason="Auto-approved (non-interactive)")
            console.print("[green]Decision Gate: auto-approved (non-interactive).[/green]")
        elif phase_a_errors:
            gate_result = DecisionGateResult(
                "reject", reason="Auto-rejected (non-interactive, structural validation failed)"
            )
            console.print(
                "[red]Decision Gate: auto-rejected (non-interactive, structural validation failed).[/red]"
            )
        else:
            # Verifier-only findings: reject in non-interactive mode (needs human review)
            gate_result = DecisionGateResult(
                "reject",
                reason=f"Rejected (non-interactive, {critic_model} verifier findings — requires human review)",
            )
            console.print(
                f"[red]Decision Gate: rejected (non-interactive, {critic_model} verifier findings "
                "— requires human review).[/red]"
            )
    else:
        gate_result = present_decision_gate(plan_md_path, verifier_result)

    if gate_result.approved:
        epic_logger.log_event("plan_approved", epic=epic_number)
        console.print("\n[green]Plan approved.[/green]")
    elif gate_result.needs_revision:
        epic_logger.log_event("plan_revised", epic=epic_number)

        # Feed remaining verifier findings back to planner for another revision
        from workflow.plan_validator import validate_plan
        from workflow.plan_verifier import _regenerate_plan_with_verifier_feedback

        # Snapshot before revision so we can restore if it breaks
        plan_json_path = epic_dir / "plan.json"
        snapshot_json = plan_json_path.read_text(encoding="utf-8")
        snapshot_md = plan_md_path.read_text(encoding="utf-8") if plan_md_path.exists() else ""

        console.print("\n[yellow]Revising plan with verifier findings...[/yellow]")
        try:
            _regenerate_plan_with_verifier_feedback(epic_dir, verifier_result, config=config)
        except PlanGenerationError as exc:
            console.print(f"  [red]Revision failed:[/red] {exc}")
            console.print("  Restoring pre-revision plan.")
            plan_json_path.write_text(snapshot_json, encoding="utf-8")
            if snapshot_md:
                plan_md_path.write_text(snapshot_md, encoding="utf-8")
            return

        # Re-validate structural checks (must still pass)
        console.print("  Running structural validation on revised plan...")
        phase_a_result = validate_plan(epic_dir)
        if not phase_a_result.valid:
            console.print(
                f"  [red]Structural validation failed after revision"
                f" ({len(phase_a_result.errors)} errors). Restoring pre-revision plan.[/red]"
            )
            plan_json_path.write_text(snapshot_json, encoding="utf-8")
            if snapshot_md:
                plan_md_path.write_text(snapshot_md, encoding="utf-8")
            return

        console.print("  [green]Structural validation passed.[/green]")

        # Re-run verifier on the revised plan
        from workflow.plan_verifier import verify_plan

        console.print(f"  Running {critic_model} verifier on revised plan...")
        try:
            verifier_result = verify_plan(epic_dir, config=config)
        except PlanVerificationError as exc:
            console.print(f"  [yellow]Verifier failed:[/yellow] {exc}")
            console.print("  Presenting gate with previous findings.")

        # Present the gate again with fresh verifier results
        gate_result = present_decision_gate(plan_md_path, verifier_result)
        if gate_result.approved:
            epic_logger.log_event("plan_approved", epic=epic_number)
            console.print("\n[green]Plan approved.[/green]")
        elif gate_result.rejected:
            epic_logger.log_event("plan_rejected", epic=epic_number)
            console.print("\n[red]Plan rejected.[/red] Artefacts remain uncommitted.")
            return
        else:
            # Second revise — fall back to manual
            console.print(
                "\n[yellow]Plan marked for manual revision.[/yellow]\n"
                "  Edit plan.json and PLAN.md, then re-run:\n"
                f"    ./wf epic validate-plan {epic_number}\n"
                f"    ./wf epic {epic_number}"
            )
            return
    elif gate_result.rejected:
        epic_logger.log_event("plan_rejected", epic=epic_number)
        console.print("\n[red]Plan rejected.[/red] Artefacts remain uncommitted.")
        return

    # Step 6: Commit + Push
    console.print()
    console.print("[bold]Step 6:[/bold] Committing planning artefacts...")

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
    console.print("[green]Stage 3 complete.[/green] Plan committed.")


# ---------------------------------------------------------------------------
# Epic commands
# ---------------------------------------------------------------------------


@epic_app.command("run")
def epic_run(
    epic_number: int = typer.Argument(..., help="Epic number to run the full pipeline for."),
) -> None:
    """Run the full epic pipeline: ingest -> plan -> verify -> gate -> execute."""
    import logging

    from workflow.orchestrator import run_pipeline

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    run_pipeline(epic_number)


@epic_app.command("status")
def epic_status(
    epic_number: int = typer.Argument(..., help="Epic number to check status for."),
) -> None:
    """Show epic progress from JSONL logs (read-only)."""
    from workflow.orchestrator import show_status

    show_status(epic_number)


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
