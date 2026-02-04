"""Info commands for worktree CLI.

Provides commands for viewing worktree information, status, health, and ports.
"""

from pathlib import Path

import typer
from rich.panel import Panel
from rich.table import Table

from ..cli_utils import (
    console,
    get_db_password,
    get_public_url,
    print_error,
    print_success,
)
from ..config import (
    calculate_ports,
    get_current_worktree_name,
    get_current_worktree_path,
)
from ..health import check_worktree_health, quick_health_check
from ..issue_ops import count_unprocessed_issues
from ..registry import (
    WorktreeNotFoundError,
    find_orphaned_worktrees,
    get_worktree_by_path,
    list_worktrees,
)
from ..resources import format_ports_display


def register_info_commands(app: typer.Typer) -> None:
    """Register info commands with the Typer app."""

    @app.command("list")
    def list_cmd(
        compact: bool = typer.Option(False, "--compact", "-c", help="Show compact table view"),
        include_orphans: bool = typer.Option(
            True, "--orphans/--no-orphans", help="Check for orphaned git worktrees"
        ),
    ) -> None:
        """List all registered worktrees with full details.

        By default shows expanded view with containers, ports, and credentials.
        Use --compact for a simple table view.

        Also checks for orphaned git worktrees (worktrees in git but not in registry).
        Use --no-orphans to skip this check.
        """
        worktrees = list_worktrees()

        # Check for orphaned worktrees
        orphans = []
        if include_orphans:
            orphans = find_orphaned_worktrees()

        if not worktrees and not orphans:
            console.print("No worktrees registered.")
            console.print(
                "Run [cyan]./worktree.py setup main[/cyan] to register the main worktree."
            )
            return

        # Get current worktree name for highlighting
        try:
            current_name = get_current_worktree_name()
        except Exception:
            current_name = None

        if compact:
            _display_compact_list(worktrees, orphans, current_name)
        else:
            _display_expanded_list(worktrees, orphans, current_name)

    @app.command()
    def status() -> None:
        """Show detailed status of current worktree."""
        try:
            current_path = get_current_worktree_path()
            worktree = get_worktree_by_path(current_path)
        except WorktreeNotFoundError:
            print_error("Current directory is not a registered worktree")
            raise typer.Exit(1) from None

        health = check_worktree_health(current_path)

        # Read DB_PASSWORD from .env file for display
        db_password = "devpassword"  # default
        env_file = current_path / ".env"
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                if line.startswith("DB_PASSWORD="):
                    db_password = line.split("=", 1)[1].strip()
                    break

        # Check for public URL (Traefik on Linux servers)
        public_url = get_public_url(worktree.branch)
        public_url_line = ""
        if public_url:
            public_url_line = f"\n  [bold green]Public:[/bold green]     {public_url}"

        console.print(
            Panel(
                f"""[bold]Worktree:[/bold] {worktree.worktree_name}
[bold]Branch:[/bold] {worktree.branch}
[bold]Path:[/bold] {worktree.worktree_path}
[bold]Status:[/bold] {"[green]Healthy[/green]" if health.healthy else "[red]Unhealthy[/red]"}

[bold cyan]Service URLs:[/bold cyan]{public_url_line}
  App (nginx): http://localhost:{worktree.ports.nginx}
  CloudBeaver: http://localhost:{worktree.ports.cloudbeaver}

[bold cyan]Internal Services (for debugging):[/bold cyan]
  Frontend:    Docker internal (4321)
  Backend:     http://localhost:{worktree.ports.backend}

[bold cyan]Database Access:[/bold cyan]
  Host: localhost:{worktree.ports.db}
  User: gts
  Pass: {db_password}

[bold cyan]CloudBeaver Login:[/bold cyan]
  User: cbadmin
  Pass: {db_password}

[bold]Ports:[/bold]
  Nginx:       {worktree.ports.nginx} (user entry point)
  Frontend:    Docker internal (4321)
  Backend:     {worktree.ports.backend} (internal)
  Database:    {worktree.ports.db}
  Redis:       {worktree.ports.redis}
  CloudBeaver: {worktree.ports.cloudbeaver}

[bold]Volumes:[/bold]
  PostgreSQL:  {worktree.volumes.postgres}
  Redis:       {worktree.volumes.redis}
  Uploads:     {worktree.volumes.uploads}
  CloudBeaver: {worktree.volumes.cloudbeaver}

[bold cyan]Observability (--profile observability):[/bold cyan]
  Grafana:     http://localhost:{worktree.ports.grafana}
  Prometheus:  http://localhost:{worktree.ports.prometheus}
  Loki:        http://localhost:{worktree.ports.loki}
  Tempo:       http://localhost:{worktree.ports.tempo}
  Alloy:       http://localhost:{worktree.ports.alloy}

[bold]Observability Volumes:[/bold]
  Grafana:     {worktree.volumes.grafana}
  Loki:        {worktree.volumes.loki}
  Tempo:       {worktree.volumes.tempo}
  Prometheus:  {worktree.volumes.prometheus}

[bold]Services:[/bold]
"""
                + "\n".join(f"  {svc}: {state}" for svc, state in health.services.items())
                + (
                    "\n\n[bold]Issues:[/bold]\n" + "\n".join(f"  - {i}" for i in health.issues)
                    if health.issues
                    else ""
                ),
                title=f"Worktree Status: {worktree.worktree_name}",
            )
        )

    @app.command()
    def health(
        check_only: bool = typer.Option(
            False,
            "--check-only",
            help="Report only, don't auto-fix issues (for CI/scripts)",
        ),
    ) -> None:
        """Check health of current worktree runtime services."""
        try:
            current_path = get_current_worktree_path()
            worktree = get_worktree_by_path(current_path)
        except WorktreeNotFoundError:
            print_error("Current directory is not a registered worktree")
            raise typer.Exit(1) from None

        with console.status("[bold]Checking health (Docker + HTTP)..."):
            result = check_worktree_health(current_path)

        if result.healthy:
            print_success("All services healthy")
            # Check for public URL (Traefik on Linux servers)
            public_url = get_public_url(worktree.branch)
            if public_url:
                console.print(f"  [bold green]Public: {public_url}[/bold green]")
            nginx_status = "[green]OK[/green]" if result.nginx_responding else "[red]DOWN[/red]"
            be_status = "[green]OK[/green]" if result.backend_responding else "[red]DOWN[/red]"
            console.print(f"  App (nginx): http://localhost:{worktree.ports.nginx} {nginx_status}")
            console.print(f"  Backend:     http://localhost:{worktree.ports.backend} {be_status}")
            console.print(f"  CloudBeaver: http://localhost:{worktree.ports.cloudbeaver}")
            console.print()
            console.print(
                "[dim]Start CloudBeaver: docker compose --profile tools up -d cloudbeaver[/dim]"
            )
            console.print("[dim]Build Astro:       just build-astro (or just watch-astro)[/dim]")
        else:
            print_error("Worktree is unhealthy")
            for issue in result.issues:
                console.print(f"  [red]\u2717[/red] {issue}")
            console.print()
            console.print("[dim]Check logs: docker compose logs[/dim]")
            raise typer.Exit(1)

    @app.command()
    def ports() -> None:
        """Show port allocations for all worktrees."""
        worktrees = list_worktrees()

        if not worktrees:
            console.print("No worktrees registered.")
            return

        table = Table(title="Port Allocations")
        table.add_column("Worktree", style="cyan")
        table.add_column("Offset")
        table.add_column("Nginx", style="green")
        table.add_column("Backend")
        table.add_column("PostgreSQL")
        table.add_column("Redis")
        table.add_column("CloudBeaver")

        for wt in worktrees:
            table.add_row(
                wt.worktree_name,
                str(wt.offset),
                str(wt.ports.nginx),
                str(wt.ports.backend),
                str(wt.ports.db),
                str(wt.ports.redis),
                str(wt.ports.cloudbeaver),
            )

        console.print(table)

        # Show next available
        used_offsets = {wt.offset for wt in worktrees}
        next_offset = 0
        while next_offset in used_offsets:
            next_offset += 1

        next_ports = calculate_ports(next_offset)
        console.print()
        console.print(f"[dim]Next available offset: {next_offset}[/dim]")
        console.print(f"[dim]Next ports: {format_ports_display(next_ports)}[/dim]")


def _display_compact_list(worktrees, orphans, current_name) -> None:
    """Display compact table view of worktrees."""
    table = Table(title="Guitar Tone Shootout Worktrees")
    table.add_column("Name", style="cyan")
    table.add_column("Status")
    table.add_column("Branch")
    table.add_column("Ports")
    table.add_column("URL")

    for wt in worktrees:
        wt_path = Path(wt.worktree_path)
        if wt_path.exists():
            healthy = quick_health_check(wt_path)
            status = "[green]●[/green]" if healthy else "[yellow]○[/yellow]"
        else:
            status = "[red]●[/red]"

        name = wt.worktree_name
        if name == current_name:
            name = f"{name} [dim](current)[/dim]"

        table.add_row(
            name,
            status,
            wt.branch,
            format_ports_display(wt.ports),
            wt.frontend_url,
        )

    # Add orphans to table with warning marker
    for orphan in orphans:
        table.add_row(
            f"[yellow]⚠ {orphan.path.name}[/yellow]",
            "[yellow]⚠ ORPHAN[/yellow]",
            orphan.branch,
            "[dim]Not assigned[/dim]",
            "[dim]Not assigned[/dim]",
        )

    console.print(table)
    console.print()
    console.print(f"Total: {len(worktrees)} registered worktrees")
    if orphans:
        console.print(f"[yellow]Warning: {len(orphans)} orphaned git worktree(s) found![/yellow]")
        console.print("[dim]Run ./worktree.py orphans to manage orphaned worktrees[/dim]")

    # Check for unprocessed GitHub issues (compact view)
    try:
        unprocessed_count, total_count = count_unprocessed_issues()
        if unprocessed_count > 0:
            console.print()
            console.print(
                f"[yellow]⚠  {unprocessed_count} unprocessed GitHub issues[/yellow] "
                f"[dim](of {total_count} total)[/dim]"
            )
            console.print("[dim]   Run /plan to integrate them into the roadmap[/dim]")
    except Exception:
        pass


def _display_expanded_list(worktrees, orphans, current_name) -> None:
    """Display expanded view with full details."""
    console.print(f"[bold]Guitar Tone Shootout Worktrees ({len(worktrees)})[/bold]\n")

    for wt in worktrees:
        wt_path = Path(wt.worktree_path)
        is_current = wt.worktree_name == current_name
        db_password = get_db_password(wt_path) if wt_path.exists() else "devpassword"

        # Get health and container status
        if wt_path.exists():
            health = check_worktree_health(wt_path)
            healthy = health.healthy
            services = health.services
        else:
            healthy = False
            services = {}

        # Build status indicator
        if not wt_path.exists():
            status_str = "[red]● Missing[/red]"
        elif healthy:
            status_str = "[green]● Healthy[/green]"
        else:
            status_str = "[yellow]○ Unhealthy[/yellow]"

        # Build container status line
        container_parts = []
        for svc, state in services.items():
            icon = "[green]●[/green]" if state == "running" else "[red]○[/red]"
            container_parts.append(f"{icon} {svc}")
        containers_line = (
            "  ".join(container_parts) if container_parts else "[dim]No containers[/dim]"
        )

        # Title with current marker
        title = f"{wt.worktree_name}"
        if is_current:
            title = f"★ {title} (current)"

        # Check for public URL (Traefik on Linux servers)
        public_url = get_public_url(wt.branch)
        public_url_line = ""
        if public_url:
            public_url_line = f"\n  [bold green]Public: {public_url}[/bold green]"

        content = f"""[bold]Branch:[/bold] {wt.branch}  |  [bold]Status:[/bold] {status_str}
[bold]Path:[/bold] {wt.worktree_path}

[bold cyan]URLs:[/bold cyan]{public_url_line}
  App: http://localhost:{wt.ports.nginx}  |  CloudBeaver: http://localhost:{wt.ports.cloudbeaver}
[bold cyan]Internal:[/bold cyan] fe:Docker  be:{wt.ports.backend}

[bold cyan]Database:[/bold cyan] localhost:{wt.ports.db}  User: [green]gts[/green]  Pass: [green]{db_password}[/green]

[bold cyan]CloudBeaver:[/bold cyan] User: [green]cbadmin[/green]  Pass: [green]{db_password}[/green]

[bold]Containers:[/bold] {containers_line}"""

        console.print(Panel(content, title=title, border_style="cyan" if is_current else "dim"))
        console.print()

    # Show orphaned worktrees if any
    if orphans:
        console.print(f"[bold yellow]Orphaned Git Worktrees ({len(orphans)})[/bold yellow]\n")
        for orphan in orphans:
            content = f"""[bold]Branch:[/bold] {orphan.branch}
[bold]Path:[/bold] {orphan.path}
[bold]Commit:[/bold] {orphan.commit[:12]}
[bold]Reason:[/bold] {orphan.reason}"""
            console.print(Panel(content, title=f"⚠ {orphan.path.name}", border_style="yellow"))
            console.print()

        console.print(
            "[yellow]These worktrees exist in git but are not tracked in the registry.[/yellow]"
        )
        console.print("[dim]Run ./worktree.py orphans --help for cleanup options[/dim]")
        console.print()

    # Check for unprocessed GitHub issues
    try:
        unprocessed_count, total_count = count_unprocessed_issues()
        if unprocessed_count > 0:
            console.print()
            console.print(
                f"[yellow]⚠  {unprocessed_count} unprocessed GitHub issues[/yellow] "
                f"[dim](of {total_count} total)[/dim]"
            )
            console.print("[dim]   Run /plan to integrate them into the roadmap[/dim]")
            console.print()
    except Exception:
        # Don't fail list command if GitHub check fails
        pass

    console.print(
        "[dim]Use --compact for table view  |  Start CloudBeaver: docker compose --profile tools up -d cloudbeaver[/dim]"
    )
