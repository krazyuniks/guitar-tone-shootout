"""Typer CLI for worktree management.

This is the entry point for the worktree CLI. All commands are organized
into modules under worktree/commands/ and registered here.

Provides commands for creating, managing, and tearing down git worktrees
with isolated Docker environments.
"""

import typer

from . import __version__
from .cli_utils import console, print_worktree_info
from .commands import (
    register_auth_commands,
    register_git_commands,
    register_info_commands,
    register_lifecycle_commands,
    register_maintenance_commands,
    register_services_commands,
    register_session_commands,
    register_setup_commands,
    register_sync_commands,
    register_teardown_commands,
)
from .config import get_current_worktree_path
from .health import check_worktree_health
from .registry import WorktreeNotFoundError, get_worktree_by_path

app = typer.Typer(
    name="worktree",
    help="Git Worktree management for Guitar Tone Shootout",
    no_args_is_help=False,
    invoke_without_command=True,
)

# Register all command groups from modules
register_auth_commands(app)
register_git_commands(app)
register_info_commands(app)
register_lifecycle_commands(app)
register_maintenance_commands(app, __version__)
register_services_commands(app)
register_session_commands(app)
register_setup_commands(app)
register_sync_commands(app)
register_teardown_commands(app)


@app.callback()
def main_callback(ctx: typer.Context) -> None:
    """Show current worktree info when called without a command.

    Run without arguments to see info for the current worktree,
    or use a command like 'list', 'setup', 'health', etc.
    """
    # Only show info if no command was invoked
    if ctx.invoked_subcommand is not None:
        return

    # Try to show current worktree info
    try:
        current_path = get_current_worktree_path()
        worktree = get_worktree_by_path(current_path)
    except WorktreeNotFoundError:
        # Not in a worktree - show help
        console.print("[yellow]Not in a registered worktree.[/yellow]")
        console.print()
        console.print("Available commands:")
        console.print("  [cyan]./worktree.py list[/cyan]     - List all worktrees")
        console.print("  [cyan]./worktree.py setup <issue>[/cyan] - Create new worktree")
        console.print("  [cyan]./worktree.py --help[/cyan]  - Show all commands")
        return

    with console.status("[bold]Loading worktree info..."):
        health = check_worktree_health(current_path)

    print_worktree_info(worktree, health)

    console.print()
    console.print("[dim]Start CloudBeaver: docker compose --profile tools up -d cloudbeaver[/dim]")


def main() -> None:
    """Entry point."""
    app()


if __name__ == "__main__":
    main()
