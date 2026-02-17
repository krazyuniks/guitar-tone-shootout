"""Docker services commands for worktree CLI.

Provides commands for managing Docker services in worktrees.
"""

import subprocess

import typer

from ..backup import BackupError, backup_all_databases
from ..cli_utils import (
    console,
    print_error,
    print_success,
    print_warning,
)
from ..config import get_current_worktree_path
from ..docker import start_services, stop_services, wait_for_healthy
from ..registry import WorktreeNotFoundError, get_worktree_by_path


def register_services_commands(app: typer.Typer) -> None:
    """Register services commands with the Typer app."""

    @app.command("services-start")
    def services_start() -> None:
        """Start Docker services for current worktree."""
        try:
            current_path = get_current_worktree_path()
            get_worktree_by_path(current_path)
        except WorktreeNotFoundError:
            print_error("Current directory is not a registered worktree")
            raise typer.Exit(1) from None

        with console.status("[bold green]Starting services..."):
            start_services(current_path)
            if wait_for_healthy(current_path):
                print_success("Services started and healthy")
            else:
                print_warning("Services started but may not be fully healthy")

    @app.command()
    def stop() -> None:
        """Stop Docker services for current worktree."""
        try:
            current_path = get_current_worktree_path()
            get_worktree_by_path(current_path)
        except WorktreeNotFoundError:
            print_error("Current directory is not a registered worktree")
            raise typer.Exit(1) from None

        with console.status("[bold red]Stopping services..."):
            stop_services(current_path)
            print_success("Services stopped")

    @app.command("backup")
    def backup_cmd() -> None:
        """Back up all databases to timestamped files in ../backups/."""
        try:
            current_path = get_current_worktree_path()
            get_worktree_by_path(current_path)
        except WorktreeNotFoundError:
            print_error("Current directory is not a registered worktree")
            raise typer.Exit(1) from None

        try:
            with console.status("[bold green]Backing up databases..."):
                backup_files = backup_all_databases(current_path)
            for bf in backup_files:
                size_mb = bf.stat().st_size / (1024 * 1024)
                print_success(f"{bf.name} ({size_mb:.1f} MB)")
        except BackupError as e:
            print_error(str(e))
            raise typer.Exit(1) from None

    @app.command()
    def logs(
        lines: int = typer.Option(50, "--lines", "-n", help="Number of lines to show"),
        follow: bool = typer.Option(False, "--follow", "-f", help="Follow log output"),
    ) -> None:
        """Show Docker compose logs for current worktree."""
        try:
            current_path = get_current_worktree_path()
            get_worktree_by_path(current_path)
        except WorktreeNotFoundError:
            print_error("Current directory is not a registered worktree")
            raise typer.Exit(1) from None

        cmd = ["docker", "compose", "logs"]
        if follow:
            cmd.append("-f")
        else:
            cmd.extend(["--tail", str(lines)])

        subprocess.run(cmd, cwd=current_path)
