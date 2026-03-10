"""Typer CLI for the epic workflow pipeline.

Provides subcommand routing for:
  just epic N               — Full pipeline: ingest -> repo-facts -> plan -> verify -> gate -> execute
  just epic-status N        — Show progress from JSONL logs
  just epic-validate-plan N — Run Phase A deterministic validation only (read-only)
  just map-codebase         — Regenerate .planning/codebase/ files
  just index-wiki           — Regenerate .planning/wiki-indexes/
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING

import typer
from rich.console import Console

if TYPE_CHECKING:
    from workflow.epic_config import EpicConfig

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


class PlanningPipelineOutcome(StrEnum):
    """Terminal outcomes from the planning pipeline."""

    COMMITTED = "committed"
    STOPPED_AT_GATE = "stopped_at_gate"
    REJECTED = "rejected"
    FAILED = "failed"


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


def _confirm_pipeline_config(config_path: Path) -> EpicConfig:
    """Display pipeline agent roles and let the user confirm or edit.

    Shows all model assignments, timeouts, and MCP servers in a table
    and offers to edit config.toml before proceeding.
    """
    from rich.table import Table

    from workflow.epic_config import (
        AVAILABLE_MODELS,
        DEFAULT_CONFIG_PATH,
        BudgetConfig,
        ModelConfig,
        _get_available_mcp_servers,
        _validate_cross_model,
        _write_config_overrides,
        load_config,
    )

    config = load_config(override_path=config_path)

    # (role_name, budget_key, mcp_dispatch_key)
    all_roles = [
        ("planner", "planning", "planning"),
        ("plan_critic", "critique_plan", "critique"),
        ("implementor", "implementation", "implementation"),
        ("story_critic", "critique_story", "critique"),
        ("epic_critic", "critique_epic", "critique"),
        ("test_writer", "test_writing", "test_writing"),
    ]

    available_mcp = _get_available_mcp_servers()

    table = Table(title="Agent Roles", show_header=True)
    table.add_column("Role", style="bold")
    table.add_column("Model", style="cyan")
    table.add_column("Timeout", style="yellow")
    table.add_column("MCP Servers", style="magenta")

    for role, budget_key, dispatch_key in all_roles:
        model = getattr(config.models, role)
        budget = config.budgets.get(budget_key, BudgetConfig())
        mcp_servers = config.mcp.get(dispatch_key, [])
        table.add_row(
            role,
            model,
            f"{budget.timeout}s",
            ", ".join(mcp_servers) if mcp_servers else "(none)",
        )

    console.print()
    console.print(table)
    if available_mcp:
        console.print(f"[dim]Available MCP: {', '.join(available_mcp)}[/dim]")
    console.print()

    import sys as _sys

    if not _sys.stdin.isatty():
        return config

    flush_stdin()
    modify = typer.confirm("Modify agent config?", default=False)
    if not modify:
        return config

    overrides: dict[str, dict] = {"models": {}, "budgets": {}, "mcp": {}}
    available = ", ".join(AVAILABLE_MODELS)

    for role, budget_key, dispatch_key in all_roles:
        current_model = getattr(config.models, role)
        current_budget = config.budgets.get(budget_key, BudgetConfig())
        current_mcp = config.mcp.get(dispatch_key, [])

        console.print(f"\n  [bold]{role}[/bold] (current: {current_model})")
        console.print(f"  Available models: {available}")
        flush_stdin()
        new_model = typer.prompt("  Model", default=current_model)
        if new_model != current_model:
            overrides["models"][role] = new_model

        flush_stdin()
        new_timeout = typer.prompt("  Timeout (seconds)", default=str(current_budget.timeout))
        if int(new_timeout) != current_budget.timeout:
            overrides["budgets"][budget_key] = {"timeout": int(new_timeout)}

        if available_mcp:
            current_mcp_str = ",".join(current_mcp) if current_mcp else ""
            flush_stdin()
            new_mcp_str = typer.prompt(
                "  MCP servers (comma-separated, empty for none)",
                default=current_mcp_str,
            )
            new_mcp = (
                [s.strip() for s in new_mcp_str.split(",") if s.strip()] if new_mcp_str else []
            )
            if new_mcp != current_mcp:
                overrides["mcp"][dispatch_key] = new_mcp

    overrides = {k: v for k, v in overrides.items() if v}
    if not overrides:
        console.print("[dim]No changes.[/dim]")
        return config

    # Validate cross-model constraint
    models_data = {r: getattr(config.models, r) for r in ModelConfig.__dataclass_fields__}
    models_data.update(overrides.get("models", {}))
    test_models = ModelConfig(**models_data)
    _validate_cross_model(test_models)

    # Validate MCP server names
    if "mcp" in overrides:
        for mcp_role, servers in overrides["mcp"].items():
            unknown = [s for s in servers if s not in available_mcp]
            if unknown:
                raise ValueError(
                    f"Unknown MCP server(s) for {mcp_role}: {unknown}. Available: {available_mcp}"
                )

    _write_config_overrides(config_path, overrides)
    # Also update defaults so future epics inherit the changes
    _write_config_overrides(DEFAULT_CONFIG_PATH, overrides)
    updated = load_config(override_path=config_path)
    console.print("[green]Config updated (also saved as new defaults).[/green]")
    return updated


def _run_planning_pipeline(epic_number: int) -> PlanningPipelineOutcome:
    """Run the planning pipeline from ingest through commit+push.

    This is the Stage 3 planning pipeline. Called by the orchestrator's
    run_pipeline() which then continues to Stage 4 execution.
    """
    import logging
    import uuid

    from workflow.epic_config import ensure_epic_config
    from workflow.jsonl_logger import EventLogger

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    epic_dir = PROJECT_ROOT / ".planning" / "epics" / f"E{epic_number}"

    # Check for already-committed plan — caller handles Stage 4
    if _check_plan_committed(epic_dir):
        console.print("[green]Plan already committed.[/green]")
        return PlanningPipelineOutcome.COMMITTED

    # Load epic configuration profile and confirm agent roles
    config_path = ensure_epic_config(epic_dir)
    try:
        config = _confirm_pipeline_config(config_path)
    except (ValueError, FileNotFoundError) as exc:
        console.print(f"[red]Configuration error:[/red] {exc}")
        return PlanningPipelineOutcome.FAILED

    # Set up JSONL logging for planning events
    run_id = str(uuid.uuid4())
    epic_logger = EventLogger(epic_dir / "epic.jsonl", run_id)

    # Activate unified dispatch logging for all dispatch_agent() calls
    from workflow.dispatch_log import dispatch_logging

    with dispatch_logging(epic_dir, run_id):
        return _run_planning_steps(epic_number, epic_dir, config, epic_logger)


def _run_planning_steps(
    epic_number: int,
    epic_dir: Path,
    config,
    epic_logger,
) -> PlanningPipelineOutcome:
    """Execute the planning pipeline until commit (wrapped in dispatch_logging).

    Pipeline:
      1. Ingest — fetch epic from GitHub
      2. Repo Facts — deterministically inspect the repo for epic-specific grounding
      3. Curation — bounded agent handoff between repo-facts and planning
      4. Plan — agent explores codebase, breaks epic into stories
      5. Verify — Phase A (deterministic) + Phase B (cross-model critique)
      6. Decision Gate — human approval
      7. Commit + Push
    """
    from workflow.artifacts import (
        CurationArtifact,
        CurationCompleteArtifact,
        CurationDispatchedArtifact,
        CurationFailedArtifact,
        PhaseAValidationEventArtifact,
        PhaseBVerificationEventArtifact,
        PlannerCompleteArtifact,
        PlannerDispatchedArtifact,
        PlannerFailedArtifact,
        PlanDecisionArtifact,
    )
    from workflow.epic_ingest import IngestionError, ingest_epic
    from workflow.git_helpers import GitPushError, robust_commit
    from workflow.curation import CurationError, generate_curation
    from workflow.plan_generator import PlanGenerationError, generate_plan
    from workflow.plan_verifier import (
        PlanVerificationError,
        present_decision_gate,
        verify_with_revision_cycle,
    )
    from workflow.repo_facts import build_repo_facts

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
            return PlanningPipelineOutcome.FAILED

    # Step 2: Repo Facts
    repo_facts_path = epic_dir / "repo_facts.json"
    if _should_skip(repo_facts_path, "repo_facts.json"):
        console.print("[dim]Step 2: Repo Facts — skipped[/dim]")
    else:
        console.print("[bold]Step 2:[/bold] Building repo facts...")
        try:
            path = build_repo_facts(epic_dir)
            console.print(f"  [green]Written:[/green] {path.relative_to(PROJECT_ROOT)}")
        except (FileNotFoundError, ValueError) as exc:
            console.print(f"  [red]Error:[/red] {exc}")
            return PlanningPipelineOutcome.FAILED

    # Step 3: Curation
    curation_json_path = epic_dir / "curation.json"
    curation_md_path = epic_dir / "CURATION.md"
    if curation_json_path.exists() and curation_md_path.exists() and _should_skip(
        curation_json_path, "curation.json"
    ):
        console.print("[dim]Step 3: Curation — skipped[/dim]")
    elif curation_json_path.exists() and not curation_md_path.exists():
        console.print("[bold]Step 3:[/bold] Rendering CURATION.md from existing curation.json...")
        try:
            curation_md_path, curation_json_path = CurationArtifact.from_path(curation_json_path).write(
                epic_dir
            )
            console.print(f"  [green]Written:[/green] {curation_md_path.relative_to(PROJECT_ROOT)}")
        except (FileNotFoundError, ValueError) as exc:
            console.print(f"  [red]Error:[/red] {exc}")
            return PlanningPipelineOutcome.FAILED
    else:
        if curation_md_path.exists() and not curation_json_path.exists():
            console.print(
                "[bold]Step 3:[/bold] Rebuilding curation because CURATION.md exists without curation.json..."
            )
        else:
            console.print("[bold]Step 3:[/bold] Curating planning inputs...")

        curation_dispatch = CurationDispatchedArtifact(
            epic_number=epic_number,
            attempt=1,
            model=config.models.planner,
        )
        epic_logger.log_event(curation_dispatch.event_name, **curation_dispatch.event_payload)

        try:
            curation_md_path, curation_json_path = generate_curation(epic_dir, config=config)
            size = curation_json_path.stat().st_size
            console.print(
                f"  [green]Written:[/green] {curation_json_path.relative_to(PROJECT_ROOT)} "
                f"({size:,d} bytes)"
            )
            console.print(f"  [green]Written:[/green] {curation_md_path.relative_to(PROJECT_ROOT)}")
            curation_complete = CurationCompleteArtifact(
                epic_number=epic_number,
                attempt=1,
                response_path=str(curation_json_path.relative_to(PROJECT_ROOT)),
            )
            epic_logger.log_event(curation_complete.event_name, **curation_complete.event_payload)
        except CurationError as exc:
            curation_failed = CurationFailedArtifact(
                epic_number=epic_number,
                attempt=1,
                error=str(exc),
            )
            epic_logger.log_event(curation_failed.event_name, **curation_failed.event_payload)
            console.print(f"  [red]Error:[/red] {exc}")
            return PlanningPipelineOutcome.FAILED

    # Step 4: Plan Generation
    plan_json_path = epic_dir / "plan.json"
    plan_md_path = epic_dir / "PLAN.md"
    if _should_skip(plan_json_path, "plan.json"):
        console.print("[dim]Step 4: Plan Generation — skipped[/dim]")
    else:
        console.print("[bold]Step 4:[/bold] Generating plan...")

        planner_dispatch = PlannerDispatchedArtifact(
            epic_number=epic_number,
            attempt=1,
            model=config.models.planner,
        )
        epic_logger.log_event(planner_dispatch.event_name, **planner_dispatch.event_payload)

        try:
            plan_md_path, plan_json_path = generate_plan(epic_dir, config=config)
            size = plan_json_path.stat().st_size
            console.print(
                f"  [green]Written:[/green] {plan_json_path.relative_to(PROJECT_ROOT)} "
                f"({size:,d} bytes)"
            )
            console.print(f"  [green]Written:[/green] {plan_md_path.relative_to(PROJECT_ROOT)}")
            planner_complete = PlannerCompleteArtifact(
                epic_number=epic_number,
                attempt=1,
                response_path=str(plan_json_path.relative_to(PROJECT_ROOT)),
            )
            epic_logger.log_event(planner_complete.event_name, **planner_complete.event_payload)
        except PlanGenerationError as exc:
            planner_failed = PlannerFailedArtifact(
                epic_number=epic_number,
                attempt=1,
                error=str(exc),
            )
            epic_logger.log_event(planner_failed.event_name, **planner_failed.event_payload)
            console.print(f"  [red]Error:[/red] {exc}")
            return PlanningPipelineOutcome.FAILED

    # Step 5: Verification (structural validation + cross-model review)
    critic_model = config.models.plan_critic if config else "codex"
    console.print()
    console.print("[bold]Step 5:[/bold] Verifying plan...")

    try:
        verification_result, success = verify_with_revision_cycle(epic_dir, config=config)
    except PlanVerificationError as exc:
        console.print(f"  [red]Error:[/red] {exc}")
        return PlanningPipelineOutcome.FAILED

    if success:
        verifier_feedback = verification_result.verifier_feedback
        assert verifier_feedback is not None
        phase_a_event = PhaseAValidationEventArtifact.passed_event(epic_number, 1)
        epic_logger.log_event(phase_a_event.event_name, **phase_a_event.event_payload)
        phase_b_event = PhaseBVerificationEventArtifact.from_result(
            epic_number,
            1,
            verification_result,
        )
        epic_logger.log_event(phase_b_event.event_name, **phase_b_event.event_payload)
        console.print("  [green]Plan verified successfully.[/green]")
    else:
        phase_a_errors = list(verification_result.phase_a_errors)
        if phase_a_errors:
            phase_a_event = PhaseAValidationEventArtifact.failed_event(
                epic_number,
                1,
                phase_a_errors,
            )
            epic_logger.log_event(phase_a_event.event_name, **phase_a_event.event_payload)
            console.print("  [red]Structural validation failed after revision.[/red]")
            for err in phase_a_errors[:5]:
                console.print(f"    - {err}")
        else:
            phase_b_event = PhaseBVerificationEventArtifact.from_result(
                epic_number,
                1,
                verification_result,
            )
            epic_logger.log_event(phase_b_event.event_name, **phase_b_event.event_payload)
            console.print(
                f"  [yellow]{critic_model.capitalize()} verifier raised findings"
                " after revision.[/yellow]"
            )

        console.print("\n  Review findings at the Decision Gate below.")
        # Fall through to Decision Gate — human can still approve

    # Step 6: Decision Gate
    console.print()
    plan_md_path = epic_dir / "PLAN.md"

    import sys as _sys

    if not _sys.stdin.isatty():
        console.print(
            f"[red]Decision Gate requires an interactive TTY.[/red]\n"
            f"Re-run `just epic {epic_number}` in an interactive shell to approve, revise, or reject the plan."
        )
        return PlanningPipelineOutcome.STOPPED_AT_GATE

    gate_result = present_decision_gate(plan_md_path, verification_result)

    if gate_result.approved:
        decision = PlanDecisionArtifact(epic_number=epic_number, decision="approved")
        epic_logger.log_event(decision.event_name, **decision.event_payload)
        console.print("\n[green]Plan approved.[/green]")
    elif gate_result.needs_revision:
        decision = PlanDecisionArtifact(epic_number=epic_number, decision="revised")
        epic_logger.log_event(decision.event_name, **decision.event_payload)
        console.print(
            "\n[yellow]Plan marked for manual revision.[/yellow]\n"
            "  The automatic planner revision budget is already exhausted before the human gate.\n"
            "  Review repo_facts.json, curation.json (if present), plan.json, and PLAN.md, then re-run:\n"
            f"    just epic-validate-plan {epic_number}\n"
            f"    just epic {epic_number}"
        )
        return PlanningPipelineOutcome.STOPPED_AT_GATE
    elif gate_result.rejected:
        rejection = PlanDecisionArtifact.for_rejection(
            epic_number,
            gate_result.reason,
            verification_result,
        )
        epic_logger.log_event(rejection.event_name, **rejection.event_payload)
        console.print("\n[red]Plan rejected.[/red] Artefacts remain uncommitted.")
        return PlanningPipelineOutcome.REJECTED

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
        return PlanningPipelineOutcome.FAILED

    # Push to remote
    console.print("  Pushing to remote...")
    try:
        from workflow.git_helpers import git_sync

        git_sync()
        console.print("  [green]Pushed successfully.[/green]")
    except GitPushError as exc:
        console.print(f"  [red]Push failed:[/red] {exc}")
        return PlanningPipelineOutcome.FAILED

    epic_logger.log_event("plan_committed", epic=epic_number, commit=commit_hash)

    console.print()
    console.print("[green]Planning complete.[/green] Plan committed.")
    console.print("Continuing into story execution in this run.")
    return PlanningPipelineOutcome.COMMITTED


# ---------------------------------------------------------------------------
# Epic commands
# ---------------------------------------------------------------------------


@epic_app.command("run")
def epic_run(
    epic_number: int = typer.Argument(..., help="Epic number to run the full pipeline for."),
) -> None:
    """Run the full epic pipeline: ingest -> repo-facts -> plan -> verify -> gate -> execute."""
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
