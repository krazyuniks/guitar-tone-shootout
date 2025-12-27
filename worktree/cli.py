"""Typer CLI for worktree management.

Provides commands for creating, managing, and tearing down git worktrees
with isolated Docker environments.
"""

from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from . import __version__
from .config import (
    calculate_ports,
    get_current_worktree_name,
    get_current_worktree_path,
    get_worktree_root,
    settings,
)
from .docker import (
    build_images,
    create_shared_volume,
    remove_volumes,
    run_migrations,
    seed_database,
    start_services,
    stop_services,
    wait_for_healthy,
)
from .git_ops import (
    GitError,
    create_worktree,
    delete_branch,
    delete_remote_branch,
    generate_worktree_name,
    install_hook,
    is_branch_merged,
    is_hook_installed,
    is_main_behind_remote,
    parse_issue_input,
    prune_worktrees,
    remove_worktree,
    uninstall_hook,
)
from .health import check_worktree_health, quick_health_check
from .registry import (
    NoAvailableOffsetError,
    WorktreeExistsError,
    WorktreeNotFoundError,
    delete_worktree,
    get_active_worktree_count,
    get_worktree,
    get_worktree_by_path,
    init_registry,
    list_worktrees,
    prune_stale_entries,
    register_worktree,
)
from .resources import check_ports_available, format_ports_display
from .templates import write_worktree_configs

app = typer.Typer(
    name="worktree",
    help="Git Worktree management for Guitar Tone Shootout",
    no_args_is_help=False,
    invoke_without_command=True,
)
console = Console()


def print_error(message: str) -> None:
    """Print an error message."""
    console.print(f"[red]Error:[/red] {message}")


def print_success(message: str) -> None:
    """Print a success message."""
    console.print(f"[green]\u2713[/green] {message}")


def print_warning(message: str) -> None:
    """Print a warning message."""
    console.print(f"[yellow]Warning:[/yellow] {message}")


def print_info(message: str) -> None:
    """Print an info message."""
    console.print(f"[blue]Info:[/blue] {message}")


def get_db_password(worktree_path: Path) -> str:
    """Read DB_PASSWORD from .env file."""
    db_password = "devpassword"  # default
    env_file = worktree_path / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith("DB_PASSWORD="):
                db_password = line.split("=", 1)[1].strip()
                break
    return db_password


def print_worktree_info(worktree, health_result=None, show_services: bool = True) -> None:
    """Print detailed worktree information including containers and credentials."""
    wt_path = Path(worktree.worktree_path)
    db_password = get_db_password(wt_path)

    # Get health if not provided
    if health_result is None and wt_path.exists():
        health_result = check_worktree_health(wt_path)

    status_str = "[green]Healthy[/green]" if (health_result and health_result.healthy) else "[yellow]Unknown[/yellow]"
    if health_result and not health_result.healthy:
        status_str = "[red]Unhealthy[/red]"

    content = f"""[bold]Worktree:[/bold] {worktree.worktree_name}
[bold]Branch:[/bold] {worktree.branch}
[bold]Path:[/bold] {worktree.worktree_path}
[bold]Status:[/bold] {status_str}

[bold cyan]Service URLs:[/bold cyan]
  Frontend:    http://localhost:{worktree.ports.frontend}
  Backend:     http://localhost:{worktree.ports.backend}
  CloudBeaver: http://localhost:{worktree.ports.cloudbeaver}

[bold cyan]Database Access:[/bold cyan]
  Host: localhost:{worktree.ports.db}
  User: shootout
  Pass: {db_password}
  DB:   shootout

[bold cyan]CloudBeaver Login:[/bold cyan]
  User: cbadmin
  Pass: {db_password}

[bold]Ports:[/bold]
  Frontend:    {worktree.ports.frontend}
  Backend:     {worktree.ports.backend}
  Database:    {worktree.ports.db}
  Redis:       {worktree.ports.redis}
  CloudBeaver: {worktree.ports.cloudbeaver}"""

    if show_services and health_result:
        content += "\n\n[bold]Containers:[/bold]"
        for svc, state in health_result.services.items():
            icon = "[green]●[/green]" if state == "running" else "[red]○[/red]"
            content += f"\n  {icon} {svc}: {state}"

        if health_result.issues:
            content += "\n\n[bold]Issues:[/bold]"
            for issue in health_result.issues:
                content += f"\n  - {issue}"

    console.print(Panel(content, title=f"Worktree: {worktree.worktree_name}"))


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


@app.command()
def setup(
    issue_or_branch: str = typer.Argument(
        ...,
        help="Issue number, branch name, or GitHub issue URL",
    ),
    no_seed: bool = typer.Option(
        False,
        "--no-seed",
        help="Skip database seeding",
    ),
    no_start: bool = typer.Option(
        False,
        "--no-start",
        help="Don't start Docker services after setup",
    ),
    build: bool = typer.Option(
        False,
        "--build",
        help="Build Docker images before starting",
    ),
) -> None:
    """Create a new git worktree with isolated Docker environment.

    Examples:
        ./worktree.py setup 42
        ./worktree.py setup 42/feature-audio-analysis
        ./worktree.py setup main
        ./worktree.py setup https://github.com/.../issues/42
    """
    # Parse input to get issue number and branch name
    issue_number, branch = parse_issue_input(issue_or_branch)

    if issue_number:
        console.print(f"Setting up worktree for issue #{issue_number}")
    console.print(f"Branch: [cyan]{branch}[/cyan]")

    # Check if this is "main" registration
    is_main = branch == "main"

    # Initialize registry
    init_registry()

    # Check active worktree count
    active_count = get_active_worktree_count()
    if active_count >= settings.warn_worktrees:
        print_warning(
            f"You have {active_count} active worktrees. "
            f"Consider tearing down unused ones."
        )

    # Check if branch/worktree already exists
    worktree_name = generate_worktree_name(branch)
    try:
        existing = get_worktree(branch)
        print_error(f"Worktree already registered: {existing.worktree_name}")
        console.print(f"  Path: {existing.worktree_path}")
        console.print(f"  Ports: {format_ports_display(existing.ports)}")
        raise typer.Exit(1)
    except WorktreeNotFoundError:
        pass  # Good, doesn't exist

    worktree_root = get_worktree_root()
    worktree_path = worktree_root / worktree_name

    # For main, check if directory already exists
    if is_main:
        if not worktree_path.exists():
            print_error(
                "Main worktree directory not found. "
                "Run the bare repo conversion script first."
            )
            raise typer.Exit(1)
    else:
        # Check main is not behind remote
        main_path = worktree_root / "main"
        if main_path.exists():
            try:
                if is_main_behind_remote(main_path):
                    print_error(
                        "Main branch is behind origin/main. "
                        "Update main before creating new worktrees:\n"
                        "  cd ../main && git pull --ff-only"
                    )
                    raise typer.Exit(1)
            except GitError as e:
                print_warning(f"Could not check main branch status: {e}")

    with console.status("[bold green]Setting up worktree...") as status:
        # Step 1: Register in database
        status.update("[bold green]Registering worktree...")
        try:
            worktree = register_worktree(
                branch=branch,
                worktree_name=worktree_name,
                worktree_path=worktree_path,
            )
        except (WorktreeExistsError, NoAvailableOffsetError) as e:
            print_error(str(e))
            raise typer.Exit(1)

        console.print(f"  Offset: {worktree.offset}")
        console.print(f"  Ports: {format_ports_display(worktree.ports)}")

        # Step 2: Check port availability
        status.update("[bold green]Checking port availability...")
        port_status = check_ports_available(worktree.ports)
        unavailable = [name for name, avail in port_status.items() if not avail]
        if unavailable:
            print_warning(
                f"Some ports may be in use: {', '.join(unavailable)}. "
                "Continuing anyway..."
            )

        # Step 3: Create git worktree (skip for main)
        if not is_main:
            status.update("[bold green]Creating git worktree...")
            try:
                create_worktree(branch, worktree_path, create_branch=True)
            except GitError as e:
                # Rollback registry
                delete_worktree(worktree_name)
                print_error(f"Failed to create git worktree: {e}")
                raise typer.Exit(1)

        # Step 4: Generate configuration files
        status.update("[bold green]Generating configuration files...")
        write_worktree_configs(worktree, worktree_path)

        # Step 4.5: Install git hooks (for main worktree setup)
        if is_main and not is_hook_installed("post-commit"):
            status.update("[bold green]Installing git hooks...")
            if install_hook("post-commit"):
                console.print("  [green]✓[/green] Auto-sync hook installed")

        # Step 5: Create shared volume
        status.update("[bold green]Creating shared volumes...")
        create_shared_volume()

        if not no_start:
            # Step 6: Build images if requested
            if build:
                status.update("[bold green]Building Docker images...")
                try:
                    build_images(worktree_path)
                except Exception as e:
                    print_warning(f"Image build failed: {e}")

            # Step 7: Start services
            status.update("[bold green]Starting Docker services...")
            try:
                start_services(worktree_path)
            except Exception as e:
                print_error(f"Failed to start services: {e}")
                raise typer.Exit(1)

            # Step 8: Wait for healthy
            status.update("[bold green]Waiting for services to be healthy...")
            if not wait_for_healthy(worktree_path, timeout=120):
                print_warning("Services may not be fully healthy. Check logs.")

            # Step 9: Seed database
            if not no_seed:
                status.update("[bold green]Seeding database...")
                if not seed_database(worktree_path):
                    print_warning("Database seeding may have failed. Check seed.sql.")

            # Step 10: Run migrations
            status.update("[bold green]Running migrations...")
            if not run_migrations(worktree_path):
                print_warning("Migrations may have failed. Check manually.")

    # Get health status for container info
    health = check_worktree_health(worktree_path) if not no_start else None

    # Read DB_PASSWORD from .env file for display
    db_password = get_db_password(worktree_path)

    # Build container status line
    containers_line = "[dim]Not started[/dim]"
    if health:
        container_parts = []
        for svc, state in health.services.items():
            icon = "[green]●[/green]" if state == "running" else "[red]○[/red]"
            container_parts.append(f"{icon} {svc}")
        containers_line = "  ".join(container_parts) if container_parts else "[dim]No containers[/dim]"

    # Success summary with full details
    console.print()
    console.print(
        Panel(
            f"""[green bold]Worktree created successfully![/green bold]

[bold]Branch:[/bold] {branch}
[bold]Path:[/bold] {worktree_path}

[bold cyan]URLs:[/bold cyan]
  Frontend: http://localhost:{worktree.ports.frontend}  |  Backend: http://localhost:{worktree.ports.backend}  |  CloudBeaver: http://localhost:{worktree.ports.cloudbeaver}

[bold cyan]Database:[/bold cyan] localhost:{worktree.ports.db}  User: [green]shootout[/green]  Pass: [green]{db_password}[/green]

[bold cyan]CloudBeaver:[/bold cyan] User: [green]cbadmin[/green]  Pass: [green]{db_password}[/green]

[bold]Containers:[/bold] {containers_line}
""",
            title=f"Worktree: {worktree_name}",
            border_style="green",
        )
    )

    # Prominent cd command for easy copy
    console.print()
    console.print("[bold yellow]To start working:[/bold yellow]")
    console.print()
    console.print(f"  [bold cyan]cd {worktree_path}[/bold cyan]")
    console.print()
    console.print("[dim]Start CloudBeaver: docker compose --profile tools up -d cloudbeaver[/dim]")


@app.command()
def teardown(
    name_or_branch: str = typer.Argument(
        ...,
        help="Worktree name or branch to tear down",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Force teardown even if branch not merged",
    ),
    keep_branch: bool = typer.Option(
        False,
        "--keep-branch",
        help="Keep the git branch after teardown",
    ),
) -> None:
    """Remove a worktree and clean up all resources.

    Stops containers, removes volumes, deletes git worktree,
    and optionally deletes branches (local and remote).
    """
    # Find the worktree
    try:
        worktree = get_worktree(name_or_branch)
    except WorktreeNotFoundError:
        print_error(f"Worktree not found: {name_or_branch}")
        raise typer.Exit(1)

    if worktree.branch == "main":
        print_error("Cannot teardown main worktree")
        raise typer.Exit(1)

    console.print(f"Tearing down: [cyan]{worktree.worktree_name}[/cyan]")
    console.print(f"  Branch: {worktree.branch}")
    console.print(f"  Path: {worktree.worktree_path}")

    # Check if branch is merged (warn if not)
    branch_merged = is_branch_merged(worktree.branch)
    if not branch_merged and not force:
        console.print()
        print_warning("Branch has not been merged into main!")
        if not typer.confirm("Continue with teardown?"):
            raise typer.Abort()

    worktree_path = Path(worktree.worktree_path)

    with console.status("[bold red]Tearing down worktree...") as status:
        # Step 1: Stop and remove Docker resources
        status.update("[bold red]Stopping Docker services...")
        try:
            remove_volumes(worktree, worktree_path)
        except Exception as e:
            print_warning(f"Docker cleanup issue: {e}")

        # Step 2: Remove git worktree
        status.update("[bold red]Removing git worktree...")
        try:
            remove_worktree(worktree_path, force=True)
        except GitError as e:
            print_warning(f"Git worktree removal issue: {e}")

        # Step 3: Prune git worktrees
        prune_worktrees()

        # Step 4: Delete branches
        if not keep_branch:
            status.update("[bold red]Deleting branches...")
            try:
                delete_branch(worktree.branch, force=not branch_merged)
            except GitError as e:
                print_warning(f"Local branch deletion issue: {e}")

            if branch_merged:
                try:
                    delete_remote_branch(worktree.branch)
                except GitError as e:
                    print_warning(f"Remote branch deletion issue: {e}")

        # Step 5: Update registry
        status.update("[bold red]Updating registry...")
        delete_worktree(worktree.worktree_name)

    print_success(f"Worktree {worktree.worktree_name} torn down successfully")
    console.print(f"  Freed ports: {format_ports_display(worktree.ports)}")


@app.command("list")
def list_cmd(
    compact: bool = typer.Option(False, "--compact", "-c", help="Show compact table view"),
) -> None:
    """List all registered worktrees with full details.

    By default shows expanded view with containers, ports, and credentials.
    Use --compact for a simple table view.
    """
    worktrees = list_worktrees()

    if not worktrees:
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
        # Compact table view (original behavior)
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

        console.print(table)
        console.print()
        console.print(f"Total: {len(worktrees)} worktrees")
        return

    # Expanded view with full details
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
        containers_line = "  ".join(container_parts) if container_parts else "[dim]No containers[/dim]"

        # Title with current marker
        title = f"{wt.worktree_name}"
        if is_current:
            title = f"★ {title} (current)"

        content = f"""[bold]Branch:[/bold] {wt.branch}  |  [bold]Status:[/bold] {status_str}
[bold]Path:[/bold] {wt.worktree_path}

[bold cyan]URLs:[/bold cyan]
  Frontend: http://localhost:{wt.ports.frontend}  |  Backend: http://localhost:{wt.ports.backend}  |  CloudBeaver: http://localhost:{wt.ports.cloudbeaver}

[bold cyan]Database:[/bold cyan] localhost:{wt.ports.db}  User: [green]shootout[/green]  Pass: [green]{db_password}[/green]

[bold cyan]CloudBeaver:[/bold cyan] User: [green]cbadmin[/green]  Pass: [green]{db_password}[/green]

[bold]Containers:[/bold] {containers_line}"""

        console.print(Panel(content, title=title, border_style="cyan" if is_current else "dim"))
        console.print()

    console.print("[dim]Use --compact for table view  |  Start CloudBeaver: docker compose --profile tools up -d cloudbeaver[/dim]")


@app.command()
def status() -> None:
    """Show detailed status of current worktree."""
    try:
        current_path = get_current_worktree_path()
        worktree = get_worktree_by_path(current_path)
    except WorktreeNotFoundError:
        print_error("Current directory is not a registered worktree")
        raise typer.Exit(1)

    health = check_worktree_health(current_path)

    # Read DB_PASSWORD from .env file for display
    db_password = "devpassword"  # default
    env_file = current_path / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith("DB_PASSWORD="):
                db_password = line.split("=", 1)[1].strip()
                break

    console.print(
        Panel(
            f"""[bold]Worktree:[/bold] {worktree.worktree_name}
[bold]Branch:[/bold] {worktree.branch}
[bold]Path:[/bold] {worktree.worktree_path}
[bold]Status:[/bold] {"[green]Healthy[/green]" if health.healthy else "[red]Unhealthy[/red]"}

[bold cyan]Service URLs:[/bold cyan]
  Frontend:    http://localhost:{worktree.ports.frontend}
  Backend:     http://localhost:{worktree.ports.backend}
  CloudBeaver: http://localhost:{worktree.ports.cloudbeaver}

[bold cyan]Database Access:[/bold cyan]
  Host: localhost:{worktree.ports.db}
  User: shootout
  Pass: {db_password}

[bold cyan]CloudBeaver Login:[/bold cyan]
  User: cbadmin
  Pass: {db_password}

[bold]Ports:[/bold]
  Frontend:    {worktree.ports.frontend}
  Backend:     {worktree.ports.backend}
  Database:    {worktree.ports.db}
  Redis:       {worktree.ports.redis}
  CloudBeaver: {worktree.ports.cloudbeaver}

[bold]Volumes:[/bold]
  PostgreSQL:  {worktree.volumes.postgres}
  Redis:       {worktree.volumes.redis}
  Uploads:     {worktree.volumes.uploads}
  CloudBeaver: {worktree.volumes.cloudbeaver}

[bold]Services:[/bold]
"""
            + "\n".join(f"  {svc}: {state}" for svc, state in health.services.items())
            + (
                "\n\n[bold]Issues:[/bold]\n"
                + "\n".join(f"  - {i}" for i in health.issues)
                if health.issues
                else ""
            ),
            title=f"Worktree Status: {worktree.worktree_name}",
        )
    )


@app.command()
def health() -> None:
    """Check health of current worktree."""
    try:
        current_path = get_current_worktree_path()
        worktree = get_worktree_by_path(current_path)
    except WorktreeNotFoundError:
        print_error("Current directory is not a registered worktree")
        raise typer.Exit(1)

    with console.status("[bold]Checking health..."):
        result = check_worktree_health(current_path)

    if result.healthy:
        print_success("All services healthy")
        console.print(f"  Frontend:    http://localhost:{worktree.ports.frontend}")
        console.print(f"  Backend:     http://localhost:{worktree.ports.backend}")
        console.print(f"  CloudBeaver: http://localhost:{worktree.ports.cloudbeaver}")
        console.print()
        console.print("[dim]Start CloudBeaver: docker compose --profile tools up -d cloudbeaver[/dim]")
    else:
        print_error("Worktree is unhealthy")
        for issue in result.issues:
            console.print(f"  [red]\u2717[/red] {issue}")
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
    table.add_column("Frontend")
    table.add_column("Backend")
    table.add_column("PostgreSQL")
    table.add_column("Redis")
    table.add_column("CloudBeaver")

    for wt in worktrees:
        table.add_row(
            wt.worktree_name,
            str(wt.offset),
            str(wt.ports.frontend),
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


@app.command()
def prune() -> None:
    """Remove stale registry entries for non-existent worktrees."""
    with console.status("[bold]Pruning stale entries..."):
        pruned = prune_stale_entries()
        prune_worktrees()  # Also prune git

    if pruned:
        print_success(f"Pruned {len(pruned)} stale entries:")
        for name in pruned:
            console.print(f"  - {name}")
    else:
        console.print("No stale entries found.")


@app.command()
def seed() -> None:
    """Re-run database seeding from seed.sql."""
    try:
        current_path = get_current_worktree_path()
        get_worktree_by_path(current_path)
    except WorktreeNotFoundError:
        print_error("Current directory is not a registered worktree")
        raise typer.Exit(1)

    with console.status("[bold]Seeding database..."):
        if seed_database(current_path):
            print_success("Database seeded successfully")
        else:
            print_error("Database seeding failed")
            raise typer.Exit(1)


@app.command()
def start() -> None:
    """Start Docker services for current worktree."""
    try:
        current_path = get_current_worktree_path()
        get_worktree_by_path(current_path)
    except WorktreeNotFoundError:
        print_error("Current directory is not a registered worktree")
        raise typer.Exit(1)

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
        raise typer.Exit(1)

    with console.status("[bold red]Stopping services..."):
        stop_services(current_path)
        print_success("Services stopped")


@app.command()
def version() -> None:
    """Show version information."""
    console.print(f"worktree v{__version__}")


@app.command()
def sync() -> None:
    """Sync all worktrees with main (fetch, update main, rebase feature branches).

    This is CRITICAL after any PR is merged to prevent divergence.
    """
    import subprocess

    worktree_root = get_worktree_root()
    main_path = worktree_root / "main"

    if not main_path.exists():
        print_error("Main worktree not found")
        raise typer.Exit(1)

    worktrees = list_worktrees()
    feature_worktrees = [wt for wt in worktrees if wt.branch != "main"]

    with console.status("[bold blue]Syncing worktrees...") as status:
        # Step 1: Fetch origin
        status.update("[bold blue]Fetching from origin...")
        result = subprocess.run(
            ["git", "fetch", "origin"],
            cwd=main_path,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print_error(f"Failed to fetch: {result.stderr}")
            raise typer.Exit(1)
        print_success("Fetched from origin")

        # Step 2: Update main
        status.update("[bold blue]Updating main branch...")
        result = subprocess.run(
            ["git", "pull", "--ff-only", "origin", "main"],
            cwd=main_path,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print_error(f"Failed to update main: {result.stderr}")
            console.print("[yellow]Main may have diverged. Manual resolution required.[/yellow]")
            raise typer.Exit(1)
        print_success("Main branch updated")

        # Step 3: Rebase feature branches
        if not feature_worktrees:
            console.print("No feature worktrees to rebase.")
        else:
            console.print(f"Rebasing {len(feature_worktrees)} feature worktrees...")

            failed_rebases = []
            for wt in feature_worktrees:
                wt_path = Path(wt.worktree_path)
                if not wt_path.exists():
                    print_warning(f"Worktree path not found: {wt.worktree_name}")
                    continue

                status.update(f"[bold blue]Rebasing {wt.worktree_name}...")

                # Check for uncommitted changes
                result = subprocess.run(
                    ["git", "status", "--porcelain"],
                    cwd=wt_path,
                    capture_output=True,
                    text=True,
                )
                if result.stdout.strip():
                    print_warning(f"{wt.worktree_name}: Has uncommitted changes, skipping rebase")
                    failed_rebases.append((wt.worktree_name, "uncommitted changes"))
                    continue

                # Rebase onto main
                result = subprocess.run(
                    ["git", "rebase", "main"],
                    cwd=wt_path,
                    capture_output=True,
                    text=True,
                )
                if result.returncode != 0:
                    # Abort the failed rebase
                    subprocess.run(
                        ["git", "rebase", "--abort"],
                        cwd=wt_path,
                        capture_output=True,
                    )
                    print_warning(f"{wt.worktree_name}: Rebase failed, aborted")
                    failed_rebases.append((wt.worktree_name, "conflicts"))
                else:
                    print_success(f"{wt.worktree_name}: Rebased successfully")

            if failed_rebases:
                console.print()
                print_warning("Some rebases failed:")
                for name, reason in failed_rebases:
                    console.print(f"  - {name}: {reason}")
                console.print()
                console.print("[yellow]Resolve manually and run rebase in those worktrees.[/yellow]")

    console.print()
    print_success("Sync complete!")


@app.command("merge-pr")
def merge_pr(
    pr_number: int = typer.Argument(..., help="PR number to merge"),
    skip_sync: bool = typer.Option(False, "--skip-sync", help="Skip syncing other worktrees"),
) -> None:
    """Merge a PR and sync all worktrees (RECOMMENDED workflow).

    This command:
    1. Merges the PR via gh CLI (squash merge)
    2. Updates main branch
    3. Rebases all active feature worktrees onto new main
    4. Optionally tears down the merged worktree
    """
    import subprocess

    worktree_root = get_worktree_root()
    main_path = worktree_root / "main"

    if not main_path.exists():
        print_error("Main worktree not found")
        raise typer.Exit(1)

    with console.status(f"[bold green]Merging PR #{pr_number}...") as status:
        # Step 1: Merge the PR
        status.update(f"[bold green]Merging PR #{pr_number}...")
        result = subprocess.run(
            ["gh", "pr", "merge", str(pr_number), "--squash", "--delete-branch"],
            cwd=main_path,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print_error(f"Failed to merge PR: {result.stderr}")
            raise typer.Exit(1)
        print_success(f"PR #{pr_number} merged successfully")

    # Step 2: Sync all worktrees
    if not skip_sync:
        console.print()
        console.print("[bold]Syncing all worktrees...[/bold]")
        sync()  # Call the sync command
    else:
        print_warning("Skipping sync - remember to run ./worktree.py sync manually!")


@app.command()
def validate() -> None:
    """Validate environment and check for divergence.

    Performs comprehensive checks:
    - Git configuration
    - Docker status
    - Port allocations
    - Main branch sync status
    - Feature branch divergence
    """
    import shutil
    import subprocess

    worktree_root = get_worktree_root()
    main_path = worktree_root / "main"
    issues = []

    console.print("[bold]Running validation checks...[/bold]\n")

    # Check 1: Git installed
    if shutil.which("git"):
        print_success("Git: installed")
    else:
        print_error("Git: not found")
        issues.append("Git not installed")

    # Check 2: gh CLI installed
    if shutil.which("gh"):
        print_success("GitHub CLI: installed")
    else:
        print_warning("GitHub CLI: not found (optional)")

    # Check 3: Docker installed
    if shutil.which("docker"):
        print_success("Docker: installed")
    else:
        print_error("Docker: not found")
        issues.append("Docker not installed")

    # Check 4: Main worktree exists
    if main_path.exists():
        print_success(f"Main worktree: {main_path}")
    else:
        print_error("Main worktree: not found")
        issues.append("Main worktree not found")
        raise typer.Exit(1)

    # Check 5: Registry exists
    registry_path = worktree_root / ".worktree" / "registry.db"
    if registry_path.exists():
        print_success("Registry: exists")
    else:
        print_warning("Registry: not found (run ./worktree.py setup main)")
        issues.append("Registry not initialized")

    # Check 6: Main branch status
    result = subprocess.run(
        ["git", "fetch", "origin"],
        cwd=main_path,
        capture_output=True,
    )

    result = subprocess.run(
        ["git", "rev-list", "--count", "HEAD..origin/main"],
        cwd=main_path,
        capture_output=True,
        text=True,
    )
    behind = int(result.stdout.strip()) if result.returncode == 0 else 0

    result = subprocess.run(
        ["git", "rev-list", "--count", "origin/main..HEAD"],
        cwd=main_path,
        capture_output=True,
        text=True,
    )
    ahead = int(result.stdout.strip()) if result.returncode == 0 else 0

    if behind == 0 and ahead == 0:
        print_success("Main branch: in sync with origin")
    elif behind > 0 and ahead == 0:
        print_warning(f"Main branch: {behind} commits behind origin (run git pull)")
        issues.append(f"Main behind by {behind} commits")
    elif ahead > 0 and behind == 0:
        print_info(f"Main branch: {ahead} commits ahead of origin (push when ready)")
    else:
        print_error(f"Main branch: DIVERGED ({ahead} ahead, {behind} behind)")
        issues.append("Main branch has diverged - manual resolution required")

    # Check 7: Feature worktrees
    console.print()
    worktrees = list_worktrees()
    feature_worktrees = [wt for wt in worktrees if wt.branch != "main"]

    if feature_worktrees:
        console.print(f"[bold]Feature worktrees: {len(feature_worktrees)}[/bold]")
        for wt in feature_worktrees:
            wt_path = Path(wt.worktree_path)
            if not wt_path.exists():
                print_warning(f"  {wt.worktree_name}: path not found")
                continue

            # Check if behind main
            result = subprocess.run(
                ["git", "rev-list", "--count", f"{wt.branch}..main"],
                cwd=main_path,
                capture_output=True,
                text=True,
            )
            behind_main = int(result.stdout.strip()) if result.returncode == 0 else 0

            if behind_main == 0:
                print_success(f"  {wt.worktree_name}: up to date with main")
            else:
                print_warning(f"  {wt.worktree_name}: {behind_main} commits behind main (needs rebase)")
    else:
        console.print("[dim]No feature worktrees[/dim]")

    # Summary
    console.print()
    if issues:
        print_warning(f"Validation completed with {len(issues)} issue(s)")
        for issue in issues:
            console.print(f"  - {issue}")
    else:
        print_success("All validation checks passed!")


@app.command()
def cleanup(
    force: bool = typer.Option(False, "--force", "-f", help="Actually perform cleanup (default: dry-run)"),
) -> None:
    """Clean up merged branches and orphaned Docker resources.

    By default runs in dry-run mode. Use --force to actually clean up.
    """
    import subprocess

    worktree_root = get_worktree_root()
    main_path = worktree_root / "main"

    if not main_path.exists():
        print_error("Main worktree not found")
        raise typer.Exit(1)

    console.print("[bold]Checking for cleanup candidates...[/bold]\n")

    # Find merged branches
    result = subprocess.run(
        ["git", "branch", "--merged", "main"],
        cwd=main_path,
        capture_output=True,
        text=True,
    )
    merged_branches = [
        b.strip().lstrip("* ")
        for b in result.stdout.strip().split("\n")
        if b.strip() and b.strip() not in ["main", "* main"]
    ]

    if merged_branches:
        console.print(f"[bold]Merged branches ({len(merged_branches)}):[/bold]")
        for branch in merged_branches:
            console.print(f"  - {branch}")
    else:
        console.print("[dim]No merged branches to clean[/dim]")

    if not force:
        console.print()
        console.print("[yellow]Dry-run mode. Use --force to actually delete.[/yellow]")
        return

    # Actually clean up
    if merged_branches:
        console.print()
        console.print("[bold]Cleaning up merged branches...[/bold]")
        for branch in merged_branches:
            try:
                delete_branch(branch, force=False)
                print_success(f"Deleted: {branch}")
            except GitError as e:
                print_warning(f"Could not delete {branch}: {e}")

    print_success("Cleanup complete!")


@app.command()
def logs(
    lines: int = typer.Option(50, "--lines", "-n", help="Number of lines to show"),
    follow: bool = typer.Option(False, "--follow", "-f", help="Follow log output"),
) -> None:
    """Show Docker compose logs for current worktree."""
    import subprocess

    try:
        current_path = get_current_worktree_path()
        get_worktree_by_path(current_path)
    except WorktreeNotFoundError:
        print_error("Current directory is not a registered worktree")
        raise typer.Exit(1)

    cmd = ["docker", "compose", "logs"]
    if follow:
        cmd.append("-f")
    else:
        cmd.extend(["--tail", str(lines)])

    subprocess.run(cmd, cwd=current_path)


@app.command()
def hooks(
    action: str = typer.Argument(
        ...,
        help="Action: install, uninstall, or status",
    ),
) -> None:
    """Manage git hooks for automatic sync.

    Actions:
        install   - Install post-commit hook for auto-sync
        uninstall - Remove post-commit hook
        status    - Check if hooks are installed

    The post-commit hook automatically rebases your feature branch onto
    origin/main after every commit, keeping you in sync and preventing
    merge conflicts.

    To temporarily disable auto-sync:
        GTS_NO_AUTO_SYNC=1 git commit -m "message"
    """
    hook_name = "post-commit"

    if action == "status":
        if is_hook_installed(hook_name):
            print_success(f"Hook '{hook_name}' is installed")
            console.print("  Auto-sync is active for all feature worktrees")
            console.print("  [dim]Disable temporarily: GTS_NO_AUTO_SYNC=1 git commit -m \"msg\"[/dim]")
        else:
            print_warning(f"Hook '{hook_name}' is not installed")
            console.print("  Run [cyan]./worktree.py hooks install[/cyan] to enable auto-sync")

    elif action == "install":
        if is_hook_installed(hook_name):
            print_info(f"Hook '{hook_name}' is already installed, updating...")

        if install_hook(hook_name):
            print_success(f"Hook '{hook_name}' installed successfully")
            console.print("  Feature branches will now auto-rebase onto origin/main after commits")
        else:
            print_error(f"Failed to install hook '{hook_name}' (template not found)")
            raise typer.Exit(1)

    elif action == "uninstall":
        if uninstall_hook(hook_name):
            print_success(f"Hook '{hook_name}' uninstalled")
            console.print("  Auto-sync is now disabled")
        else:
            print_info(f"Hook '{hook_name}' was not installed")

    else:
        print_error(f"Unknown action: {action}")
        console.print("  Valid actions: install, uninstall, status")
        raise typer.Exit(1)


def main() -> None:
    """Entry point."""
    app()


if __name__ == "__main__":
    main()
