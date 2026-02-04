"""Session commands for worktree CLI.

Provides the start command for beginning work sessions with full validation.
"""

from pathlib import Path

import typer

from ..cli_utils import (
    console,
    display_github_sync_result,
    display_github_sync_skipped,
    display_issue_analysis,
    display_local_state_report,
    display_remaining_errors,
    display_work_selection,
    filter_analysis,
    print_error,
    print_success,
    print_warning,
)
from ..config import get_current_worktree_path, get_worktree_root
from ..docker import start_services, wait_for_healthy
from ..health import check_worktree_health
from ..issue_ops import (
    GitHubIssue,
    analyze_issues,
    get_issues_with_cache,
    load_cached_issues,
)
from ..local_state import check_local_state
from ..registry import WorktreeNotFoundError, get_worktree_by_path


def register_session_commands(app: typer.Typer) -> None:
    """Register session commands with the Typer app."""

    @app.command()
    def start(
        interactive: bool = typer.Option(
            True,
            "--interactive/--non-interactive",
            help="Run in interactive mode for work selection",
        ),
        skip_github: bool = typer.Option(
            False,
            "--skip-github",
            help="Skip GitHub issue sync (use cache only)",
        ),
        auto_fix: bool = typer.Option(
            False,
            "--auto-fix",
            help="Automatically fix recoverable issues",
        ),
        issue_filter: str | None = typer.Option(
            None,
            "--filter",
            help="Filter issues by label or keyword",
        ),
    ) -> None:
        """Start work session with full environment validation.

        This is the main entry point for development workflow. It:
        1. Validates local state (orphaned worktrees, uncommitted changes, stale ops)
        2. Syncs with GitHub to fetch open issues
        3. Analyzes issues by readiness (ready, blocked, in_progress)
        4. Presents work selection in interactive mode

        Examples:
            ./worktree.py start                    # Full interactive workflow
            ./worktree.py start --non-interactive  # Just show status, no selection
            ./worktree.py start --skip-github      # Skip GitHub sync (offline mode)
            ./worktree.py start --auto-fix         # Auto-fix recoverable issues
            ./worktree.py start --filter backend   # Filter issues by keyword
        """
        worktree_root = get_worktree_root()

        # ========================================================================
        # PHASE 0: CHECK IF ALREADY IN A WORKTREE
        # ========================================================================
        if _handle_existing_worktree(interactive):
            return

        # ========================================================================
        # PHASE 1: LOCAL STATE CHECK (blocking on errors)
        # ========================================================================
        console.print()
        with console.status("[bold blue]Checking local state..."):
            report = check_local_state(worktree_root)

        display_local_state_report(report, auto_fix, worktree_root)

        # Re-check after auto-fix if we attempted any fixes
        if auto_fix and report.has_errors:
            with console.status("[bold blue]Re-checking local state after fixes..."):
                report = check_local_state(worktree_root)
            if report.has_errors:
                print_error("Some issues could not be fixed automatically.")
                display_remaining_errors(report)
                raise typer.Exit(1)

        # Block on errors (after auto-fix attempt)
        if report.has_errors:
            print_error(
                "Local state has errors that must be resolved before starting work.\n"
                "Use --auto-fix to attempt automatic resolution, or fix manually."
            )
            raise typer.Exit(1)

        # ========================================================================
        # PHASE 2: GITHUB SYNC (skippable)
        # ========================================================================
        console.print()
        issues: list[GitHubIssue] = []
        from_cache = False
        cached_issues: list[GitHubIssue] | None = None

        if skip_github:
            cached_issues = load_cached_issues()
            if cached_issues:
                issues = cached_issues
                from_cache = True
                display_github_sync_skipped(len(issues))
            else:
                print_warning("No cached issues available. Consider running without --skip-github.")
        else:
            with console.status("[bold blue]Syncing with GitHub..."):
                cached_issues = load_cached_issues()
                issues, from_cache = get_issues_with_cache(force_refresh=True)

            display_github_sync_result(issues, cached_issues, from_cache)

        # ========================================================================
        # PHASE 3: ISSUE ANALYSIS
        # ========================================================================
        console.print()
        analysis = analyze_issues(issues)

        # Apply filter if provided
        if issue_filter:
            analysis = filter_analysis(analysis, issue_filter)

        display_issue_analysis(analysis)

        # ========================================================================
        # PHASE 4: WORK SELECTION (interactive only)
        # ========================================================================
        if interactive and analysis.ready:
            console.print()
            # Import setup here to avoid circular imports
            from .setup import _run_setup

            def setup_callback(issue_number: str) -> None:
                """Callback to run setup for selected issue."""
                _run_setup(
                    issue_or_branch=issue_number,
                    skip_db_import=False,
                    no_start=False,
                    build=False,
                    force=False,
                    health_timeout=60,
                )

            display_work_selection(analysis, worktree_root, setup_callback)
        elif interactive and not analysis.ready:
            console.print()
            console.print(
                "[yellow]No ready issues available for selection.[/yellow]\n"
                "Check blocked or in-progress issues, or create a new issue."
            )
        else:
            console.print()
            console.print("[dim]Non-interactive mode. Use --interactive to select work.[/dim]")


def _handle_existing_worktree(interactive: bool) -> bool:
    """Check if already in a feature worktree and handle it.

    Returns:
        True if handled (should return from start), False to continue normal flow.
    """
    from rich.prompt import Prompt

    try:
        current_path = get_current_worktree_path()
        current_worktree = get_worktree_by_path(current_path)

        # Check if this is a feature worktree (not main)
        if current_worktree.branch != "main":
            console.print()
            console.print(f"[cyan]Already in worktree:[/cyan] {current_worktree.worktree_name}")
            console.print(f"[dim]Branch: {current_worktree.branch}[/dim]")
            console.print()

            # Show status and offer to start services
            health = check_worktree_health(Path(current_worktree.worktree_path))

            if health.containers_running:
                console.print("[green]✓[/green] Services are running")
                console.print(f"  Frontend: {current_worktree.frontend_url}")
                console.print(f"  Webapp: {current_worktree.webapp_url}")
            else:
                console.print("[yellow]![/yellow] Services are not running")
                if interactive:
                    start_services_choice = Prompt.ask(
                        "Start services?",
                        choices=["y", "n"],
                        default="y",
                    )
                    if start_services_choice == "y":
                        with console.status("[bold green]Starting services..."):
                            start_services(current_path)
                            if wait_for_healthy(current_path):
                                print_success("Services started and healthy")
                                console.print(f"  Frontend: {current_worktree.frontend_url}")
                                console.print(f"  Webapp: {current_worktree.webapp_url}")
                            else:
                                print_warning("Services started but may not be fully healthy")
                else:
                    console.print("[dim]Run: ./worktree.py services-start[/dim]")

            console.print()
            console.print("[dim]You're ready to work! Use Claude Code or your editor.[/dim]")
            return True

    except WorktreeNotFoundError:
        pass  # Not in a registered worktree, continue with normal flow

    return False
