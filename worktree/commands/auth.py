"""Authentication commands for worktree CLI.

Provides commands for managing T3K OAuth authentication that persists
across all worktrees via a shared auth file.
"""

import typer
from rich.table import Table

from ..cli_utils import console, print_error, print_success, print_warning


def register_auth_commands(app: typer.Typer) -> None:
    """Register auth commands with the Typer app."""

    @app.command("auth-status")
    def auth_status_cmd(
        quiet: bool = typer.Option(
            False, "--quiet", "-q", help="Suppress output, exit code only (for hooks)"
        ),
    ) -> None:
        """Show auth status and token expiration.

        Checks the shared auth file (.gts-auth.json) and displays:
        - Whether authentication is valid
        - Username and T3K ID
        - Token expiration time
        - Hours/days remaining until expiration

        This command is also useful for hooks to check auth before operations.
        With --quiet, only returns exit code (0=valid, 1=invalid/expired).
        """
        from ..auth import check_auth_status, get_auth_file_path

        auth_path = get_auth_file_path()
        status = check_auth_status()

        # In quiet mode, just exit with status code
        if quiet:
            raise typer.Exit(0 if status.valid else 1)

        # Create status display
        table = Table(title="Auth Status", show_header=False, box=None)
        table.add_column("Key", style="cyan")
        table.add_column("Value")

        # Status indicator
        if status.valid:
            table.add_row("Status", "[green]Valid[/green]")
        else:
            table.add_row("Status", "[red]Invalid/Expired[/red]")

        if status.username:
            table.add_row("Username", status.username)

        if status.expires_at:
            table.add_row("Expires At", status.expires_at.isoformat())

        if status.expires_in_hours is not None and status.expires_in_hours > 0:
            if status.expires_in_hours < 24:
                table.add_row("Expires In", f"{status.expires_in_hours:.1f} hours")
            else:
                days = status.expires_in_hours / 24
                table.add_row("Expires In", f"{days:.1f} days")

        table.add_row("Auth File", str(auth_path))

        console.print(table)
        console.print()

        if status.valid:
            print_success(status.message)
        else:
            print_warning(status.message)

        if not status.valid:
            raise typer.Exit(1)

    @app.command("auth-login")
    def auth_login_cmd(
        webapp_port: int = typer.Option(
            8000, "--port", "-p", help="Webapp port for OAuth callback"
        ),
    ) -> None:
        """Open browser to login via T3K OAuth.

        This starts the OAuth flow by opening your browser to the T3K login page.
        After successful authentication, tokens are automatically saved to the
        shared auth file (.gts-auth.json).

        All worktrees will then be able to use these credentials.

        Args:
            webapp_port: Port of the webapp to use for OAuth callback.
        """
        from ..auth import get_auth_file_path, get_webapp_url_for_worktree, start_login_flow

        webapp_url = get_webapp_url_for_worktree()
        auth_path = get_auth_file_path()

        console.print("[bold]Starting OAuth login flow...[/bold]")
        console.print(f"Webapp: {webapp_url}")
        console.print(f"Auth will be saved to: {auth_path}")
        console.print()

        if start_login_flow(webapp_url):
            print_success("Browser opened. Complete login in your browser.")
            console.print()
            console.print("[dim]After login, tokens will be saved automatically.[/dim]")
            console.print("[dim]Then run 'auth-restore' in any worktree to activate.[/dim]")
        else:
            print_error("Failed to open browser.")
            console.print(f"Manually open: {webapp_url}/auth/login/t3k")
            raise typer.Exit(1)

    @app.command("auth-restore")
    def auth_restore_cmd(
        webapp_port: int = typer.Option(
            None, "--port", "-p", help="Webapp port (auto-detected if not specified)"
        ),
    ) -> None:
        """Restore session from saved auth file.

        Reads T3K tokens from the shared auth file and creates a session in
        the current worktree's webapp. This is automatically called during
        worktree setup if valid auth exists.

        Run this after 'auth-login' to activate auth in the current worktree.
        """
        from ..auth import (
            check_auth_status,
            get_webapp_url_for_worktree,
            restore_session,
        )

        # Always use PUBLIC_URL from .env.local (set by worktree.py setup)
        webapp_url = get_webapp_url_for_worktree()

        console.print("[bold]Restoring session...[/bold]")
        console.print(f"Webapp: {webapp_url}")
        console.print()

        # Check auth status first
        status = check_auth_status()
        if not status.valid:
            print_error(status.message)
            raise typer.Exit(1)

        console.print(f"Found valid auth for: {status.username}")

        # Call restore endpoint
        success, message = restore_session(webapp_url)

        if success:
            print_success(message)
        else:
            print_error(message)
            raise typer.Exit(1)
