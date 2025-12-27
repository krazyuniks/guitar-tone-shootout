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
    is_branch_merged,
    is_main_behind_remote,
    parse_issue_input,
    prune_worktrees,
    remove_worktree,
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
    no_args_is_help=True,
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

    # Success summary
    console.print()
    console.print(
        Panel(
            f"""[green]Worktree created successfully![/green]

[bold]Path:[/bold] {worktree_path}
[bold]Branch:[/bold] {branch}
[bold]Frontend:[/bold] http://localhost:{worktree.ports.frontend}
[bold]Backend:[/bold] http://localhost:{worktree.ports.backend}
[bold]Database:[/bold] localhost:{worktree.ports.db}

[dim]Next steps:[/dim]
  cd {worktree_path}
  ./worktree.py health
""",
            title="Worktree Setup Complete",
        )
    )


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
def list_cmd() -> None:
    """List all registered worktrees."""
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

    table = Table(title="Guitar Tone Shootout Worktrees")
    table.add_column("Name", style="cyan")
    table.add_column("Status")
    table.add_column("Branch")
    table.add_column("Ports")
    table.add_column("URL")

    for wt in worktrees:
        # Check health
        wt_path = Path(wt.worktree_path)
        if wt_path.exists():
            healthy = quick_health_check(wt_path)
            status = "[green]\u25cf[/green]" if healthy else "[yellow]\u25cb[/yellow]"
        else:
            status = "[red]\u25cf[/red]"

        # Mark current
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

    console.print(
        Panel(
            f"""[bold]Worktree:[/bold] {worktree.worktree_name}
[bold]Branch:[/bold] {worktree.branch}
[bold]Path:[/bold] {worktree.worktree_path}
[bold]Status:[/bold] {"[green]Healthy[/green]" if health.healthy else "[red]Unhealthy[/red]"}

[bold]Ports:[/bold]
  Frontend: {worktree.ports.frontend} -> http://localhost:{worktree.ports.frontend}
  Backend:  {worktree.ports.backend} -> http://localhost:{worktree.ports.backend}
  Database: {worktree.ports.db}
  Redis:    {worktree.ports.redis}

[bold]Volumes:[/bold]
  PostgreSQL: {worktree.volumes.postgres}
  Redis:      {worktree.volumes.redis}
  Uploads:    {worktree.volumes.uploads}

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
        console.print(f"  Frontend: http://localhost:{worktree.ports.frontend}")
        console.print(f"  Backend:  http://localhost:{worktree.ports.backend}")
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

    for wt in worktrees:
        table.add_row(
            wt.worktree_name,
            str(wt.offset),
            str(wt.ports.frontend),
            str(wt.ports.backend),
            str(wt.ports.db),
            str(wt.ports.redis),
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


def main() -> None:
    """Entry point."""
    app()


if __name__ == "__main__":
    main()
