"""Sync commands for worktree CLI.

Provides commands for syncing worktrees with the remote repository,
including session start/stop hooks.
"""

from pathlib import Path

import typer

from ..cli_utils import print_error, print_info, print_success, print_warning
from ..sync_ops import sync_start as do_sync_start
from ..sync_ops import sync_stop as do_sync_stop


def register_sync_commands(app: typer.Typer) -> None:
    """Register sync commands with the Typer app."""

    @app.command("sync-start")
    def sync_start_cmd(
        quiet: bool = typer.Option(False, "--quiet", "-q", help="Suppress output (for hooks)"),
    ) -> None:
        """Pull latest changes before starting work (session start hook).

        This command is called automatically by the SessionStart hook.
        It ensures the worktree is synced before work begins.

        Operations:
        - Fetch from origin
        - Pull with rebase

        Safe: Gracefully handles conflicts by aborting rebase.
        """
        cwd = Path.cwd()
        success, messages = do_sync_start(cwd, quiet=quiet)

        if not quiet:
            for msg in messages:
                if msg.startswith("ERROR"):
                    print_error(msg)
                elif (
                    msg.startswith("Warning")
                    or "failed" in msg.lower()
                    or "skipping" in msg.lower()
                ):
                    print_warning(msg)
                else:
                    print_info(msg)

        if not success:
            raise typer.Exit(1)

    @app.command("sync-stop")
    def sync_stop_cmd() -> None:
        """Save and push all work before ending session (stop hook).

        This command is called automatically by the Stop hook.
        It ensures all work is committed and pushed before the session ends.

        Operations:
        - Commit any uncommitted changes as WIP
        - Push to remote (MUST succeed)

        BLOCKING: This command will fail if push fails, preventing session end.
        """
        cwd = Path.cwd()
        success, messages = do_sync_stop(cwd)

        for msg in messages:
            if msg.startswith("ERROR"):
                print_error(msg)
            elif msg.startswith("Warning") or "failed" in msg.lower():
                print_warning(msg)
            else:
                print_info(msg)

        if not success:
            print_error("Sync stop failed - push must succeed before session can end")
            raise typer.Exit(1)

        print_success("All work saved and pushed")
