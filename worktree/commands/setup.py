"""Setup command for worktree CLI.

Provides the setup command for creating and configuring git worktrees
with isolated Docker environments.
"""

import contextlib
import shutil
import time
from contextlib import contextmanager
from pathlib import Path

import typer
from rich.panel import Panel

from ..cli_utils import (
    console,
    get_db_password,
    print_error,
    print_info,
    print_success,
    print_warning,
)
from ..config import get_worktree_root, settings
from ..docker import (
    DockerError,
    build_images,
    cleanup_containers,
    collect_container_logs,
    export_database,
    format_failure_report,
    get_backups_dir,
    get_main_worktree_path,
    get_orphan_ports_in_use,
    get_service_status,
    run_compose,
    start_services,
    wait_for_services_ready,
)
from ..git_ops import (
    GitError,
    create_worktree,
    generate_worktree_name,
    install_hook,
    is_hook_installed,
    is_main_behind_remote,
    parse_issue_input,
    rebase_on_main,
)
from ..health import check_worktree_health
from ..issue_ops import get_issue_by_number
from ..registry import (
    NoAvailableOffsetError,
    WorktreeExistsError,
    WorktreeNotFoundError,
    delete_worktree,
    get_active_worktree_count,
    get_worktree,
    init_registry,
    register_worktree,
)
from ..resources import check_ports_available, format_ports_display
from ..templates import write_worktree_configs

# Step timing for setup profiling
_step_timings: list[tuple[str, float]] = []


@contextmanager
def _timed_step(name: str):
    """Record wall-clock time for a setup step."""
    start = time.monotonic()
    try:
        yield
    finally:
        _step_timings.append((name, time.monotonic() - start))


def _print_timing_summary() -> None:
    """Print a summary of step timings."""
    if not _step_timings:
        return
    total = sum(t for _, t in _step_timings)
    console.print("\n[bold cyan]Setup timing:[/bold cyan]")
    for name, elapsed in _step_timings:
        bar = "█" * max(1, int(elapsed / total * 30))
        console.print(f"  {elapsed:5.1f}s {bar} {name}")
    console.print(f"  [bold]{total:5.1f}s total[/bold]")
    _step_timings.clear()


def register_setup_commands(app: typer.Typer) -> None:
    """Register setup commands with the Typer app."""

    @app.command()
    def setup(
        issue_or_branch: str = typer.Argument(
            ...,
            help="Issue number, branch name, or GitHub issue URL",
        ),
        skip_db_import: bool = typer.Option(
            False,
            "--skip-db-import",
            help="Skip importing database from main worktree (start with fresh database)",
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
        force: bool = typer.Option(
            False,
            "--force",
            "-f",
            help="Skip blocking health check (expert override - use with caution)",
        ),
        health_timeout: int = typer.Option(
            30,
            "--health-timeout",
            help="Seconds to wait for services to become healthy (default: 30)",
        ),
    ) -> None:
        """Create a new git worktree with isolated Docker environment.

        Examples:
            ./worktree.py setup 42
            ./worktree.py setup 42/feature-audio-analysis
            ./worktree.py setup main
            ./worktree.py setup https://github.com/.../issues/42
        """
        _run_setup(
            issue_or_branch=issue_or_branch,
            skip_db_import=skip_db_import,
            no_start=no_start,
            build=build,
            force=force,
            health_timeout=health_timeout,
        )


def _run_setup(
    issue_or_branch: str,
    skip_db_import: bool,
    no_start: bool,
    build: bool,
    force: bool,
    health_timeout: int,
) -> None:
    """Core setup logic extracted for reuse."""
    # Parse input to get issue number and branch name
    issue_number, branch = parse_issue_input(issue_or_branch)

    if issue_number:
        console.print(f"Setting up worktree for issue #{issue_number}")

        # Validate GitHub issue exists and is OPEN
        gh_issue = get_issue_by_number(issue_number)
        if gh_issue is None:
            print_error(
                f"GitHub issue #{issue_number} not found.\n\n"
                "Make sure the issue exists on GitHub before setting up a worktree."
            )
            raise typer.Exit(1)

        if gh_issue.state != "open":
            print_error(
                f"GitHub issue #{issue_number} is {gh_issue.state.upper()}, not OPEN.\n"
                f"  Title: {gh_issue.title}\n\n"
                "Cannot create worktree for closed issues. The work may already be done.\n"
                "Use 'gh issue reopen {issue_number}' if you need to continue this work."
            )
            raise typer.Exit(1)

        console.print(f"  Title: [dim]{gh_issue.title}[/dim]")

    console.print(f"Branch: [cyan]{branch}[/cyan]")

    # Check if this is "main" registration
    is_main = branch == "main"

    # Initialize registry
    init_registry()

    # Check active worktree count
    active_count = get_active_worktree_count()
    if active_count >= settings.warn_worktrees:
        print_warning(
            f"You have {active_count} active worktrees. Consider tearing down unused ones."
        )

    # Check if branch/worktree already exists (idempotent setup)
    worktree_name = generate_worktree_name(branch)
    worktree_root = get_worktree_root()
    worktree_path = worktree_root / worktree_name
    resuming = False
    worktree = None

    try:
        existing = get_worktree(branch)
        # Worktree is registered - check if directory exists for resume
        if Path(existing.worktree_path).exists():
            print_info(f"Worktree already exists, resuming setup: {existing.worktree_name}")
            console.print(f"  Path: {existing.worktree_path}")
            console.print(f"  Ports: {format_ports_display(existing.ports)}")
            resuming = True
            worktree = existing
            worktree_path = Path(existing.worktree_path)

            # Rebase on main to get latest updates (skip for main itself)
            if not is_main:
                with _timed_step("rebase"):
                    console.print("  Rebasing on origin/main...")
                    if rebase_on_main(worktree_path):
                        print_success("Rebased on latest main")
                    else:
                        print_error(
                            "Rebase failed (conflicts?). Resolve manually:\n"
                            f"  cd {worktree_path}\n"
                            "  git fetch origin && git rebase origin/main\n"
                            "Then run setup again."
                        )
                        raise typer.Exit(1)
        else:
            # Registry entry exists but directory is gone - clean up and re-create
            print_warning(
                f"Worktree registered but directory missing, re-creating: {existing.worktree_name}"
            )
            delete_worktree(existing.worktree_name)
    except WorktreeNotFoundError:
        pass  # Good, doesn't exist

    # For main, check if directory already exists
    if is_main:
        if not worktree_path.exists():
            print_error(
                "Main worktree directory not found. Run the bare repo conversion script first."
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
        # Track the backup file for later import
        backup_file: Path | None = None

        # Step 0.5: Get database backup for import
        if not resuming and not skip_db_import:
            backup_file = _get_or_create_backup(status, is_main)
            if backup_file is None:
                raise typer.Exit(1)

        # Step 0.6: Check for orphaned containers (before allocating ports)
        if not resuming:
            status.update("[bold green]Checking for orphaned containers (Step 0.6)...")
            orphan_ports = get_orphan_ports_in_use()
            if orphan_ports:
                status.stop()
                print_error("Orphaned Docker containers detected using ports:")
                for port, container in sorted(orphan_ports.items()):
                    console.print(f"  Port {port}: {container}")
                console.print()
                console.print(
                    "[yellow]These containers are from worktrees that no longer exist.[/yellow]"
                )
                console.print("[yellow]Run the following to clean them up:[/yellow]")
                console.print()
                console.print("  [cyan]./worktree.py cleanup-orphans[/cyan]")
                console.print()
                raise typer.Exit(1)

        # Step 1: Register in database (skip if resuming)
        if not resuming:
            status.update("[bold green]Registering worktree...")
            try:
                worktree = register_worktree(
                    branch=branch,
                    worktree_name=worktree_name,
                    worktree_path=worktree_path,
                )
            except (WorktreeExistsError, NoAvailableOffsetError) as e:
                print_error(str(e))
                raise typer.Exit(1) from None

            console.print(f"  Offset: {worktree.offset}")
            console.print(f"  Ports: {format_ports_display(worktree.ports)}")

        # worktree is now guaranteed to be set (either from resuming or registration)
        assert worktree is not None

        # Step 2: Check port availability (fail fast for core services)
        # Skip for resume - existing services are expected to use these ports
        if not resuming:
            status.update("[bold green]Checking port availability...")
            port_status = check_ports_available(worktree.ports)
            # Core services: main needs redis (jobs profile), feature worktrees don't
            core_services = ["webapp", "db"]
            if is_main:
                core_services.append("redis")
            core_unavailable = [name for name in core_services if not port_status.get(name, True)]
            if core_unavailable:
                delete_worktree(worktree_name)
                status.stop()
                print_error(f"Core ports unavailable: {', '.join(core_unavailable)}")
                console.print("[yellow]Another process is using these ports.[/yellow]")
                console.print("[yellow]Check for orphaned containers with:[/yellow]")
                console.print()
                console.print("  [cyan]./worktree.py cleanup-orphans --dry-run[/cyan]")
                console.print()
                raise typer.Exit(1)

            # Warn about optional services (frontend, cloudbeaver)
            optional_unavailable = [
                name
                for name, avail in port_status.items()
                if not avail and name not in core_services
            ]
            if optional_unavailable:
                print_warning(
                    f"Some optional ports may be in use: {', '.join(optional_unavailable)}. "
                    "Continuing anyway..."
                )

        # Step 3: Create git worktree (skip for main or if resuming)
        if not is_main and not resuming:
            status.update("[bold green]Creating git worktree...")
            try:
                create_worktree(branch, worktree_path, create_branch=True)
            except GitError as e:
                delete_worktree(worktree_name)
                print_error(f"Failed to create git worktree: {e}")
                raise typer.Exit(1) from None

        # Step 4: Generate configuration files
        with _timed_step("config"):
            status.update("[bold green]Generating configuration files...")
            write_worktree_configs(worktree, worktree_path)

        # Step 4.5: Install git hooks (for main worktree setup)
        if is_main and not is_hook_installed("post-commit"):
            status.update("[bold green]Installing git hooks...")
            if install_hook("post-commit"):
                console.print("  [green]✓[/green] Auto-sync hook installed")

        # Step 4.6: Install pre-commit hooks (prek)
        if shutil.which("prek"):
            import subprocess

            status.update("[bold green]Installing pre-commit hooks...")
            result = subprocess.run(
                ["prek", "install"],
                cwd=worktree_path,
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                console.print("  [green]✓[/green] Pre-commit hooks installed (prek)")
            else:
                console.print(
                    "  [yellow]![/yellow] prek install failed (lint checks may not run on commit)"
                )
        else:
            console.print("  [yellow]![/yellow] prek not found (run 'just infra' to install)")

        # Step 4.8: Start Traefik (server deployments only - guards itself)
        with _timed_step("traefik"):
            _setup_traefik(worktree_path, status)

        # Step 4.9: Check development requirements (Playwright + MCP)
        with _timed_step("requirements"):
            _check_development_requirements(worktree_path, status)

        if not no_start and not resuming:
            _start_and_configure_services(
                status=status,
                worktree=worktree,
                worktree_path=worktree_path,
                worktree_name=worktree_name,
                is_main=is_main,
                resuming=resuming,
                skip_db_import=skip_db_import,
                build=build,
                force=force,
                health_timeout=health_timeout,
                backup_file=backup_file,
            )

        # === RESUME PATH: Start services if not running ===
        if resuming and not no_start:
            _handle_resume_path(
                status=status,
                worktree=worktree,
                worktree_path=worktree_path,
                is_main=is_main,
                skip_db_import=skip_db_import,
                force=force,
                health_timeout=health_timeout,
            )

        # === VALIDATION: Run regression tests ===
        if not no_start:
            with _timed_step("regression-tests"):
                tests_passed = _run_regression_tests(worktree_path, worktree, status)
            if not tests_passed and not force:
                status.stop()
                print_error(
                    "Setup validation failed. The worktree was created but tests failed.\n\n"
                    "Options:\n"
                    "  1. Fix the issues and run: just test-regression\n"
                    "  2. Re-run setup with --force to skip validation\n"
                    "  3. Check logs: docker compose logs"
                )
                raise typer.Exit(1)
            elif not tests_passed:
                print_warning("Validation tests failed (continuing with --force)")

    # Display success summary
    _display_setup_success(
        worktree=worktree,
        worktree_path=worktree_path,
        worktree_name=worktree_name,
        branch=branch,
        resuming=resuming,
        no_start=no_start,
    )
    _print_timing_summary()


def _get_or_create_backup(status, is_main: bool) -> Path | None:
    """Get existing backup for main, or create fresh backup from main for feature worktrees.

    Returns:
        Path to backup file, or None if backup failed.
    """
    backups_dir = get_backups_dir()

    if is_main:
        # For main worktree (first-time setup): use existing backup
        status.update("[bold green]Looking for existing backup (Step 0.5)...")
        backup_file = _get_latest_backup()
        if backup_file:
            console.print(f"  [green]✓[/green] Found backup: {backup_file.name}")
            return backup_file
        else:
            status.stop()
            print_error("No database backup found at ../backups/")
            console.print()
            console.print(
                "[yellow]For first-time main setup, you need an existing backup.[/yellow]"
            )
            console.print("[yellow]Copy your backup to:[/yellow]")
            console.print(f"  [cyan]{backups_dir}[/cyan]")
            console.print()
            console.print("[dim]Or use --skip-db-import to start with empty database[/dim]")
            return None

    # For feature worktrees: export main's database
    status.update("[bold green]Exporting main worktree database (Step 0.5)...")
    main_path = get_main_worktree_path()

    # Check if main's db is running
    main_db_status = get_service_status(main_path)
    if "db" not in main_db_status or main_db_status["db"] != "running":
        status.stop()
        print_error("Main worktree's database is not running.")
        console.print()
        console.print("[yellow]Start main's database first:[/yellow]")
        console.print("  [cyan]cd ../main && docker compose up -d db[/cyan]")
        console.print()
        console.print("[dim]Or use --skip-db-import to start with empty database[/dim]")
        return None

    try:
        backup_file = export_database(main_path)
        console.print(f"  [green]✓[/green] Exported: {backup_file.name}")
        return backup_file
    except DockerError as e:
        status.stop()
        print_error(f"Database export failed: {e}")
        console.print()
        console.print("[dim]Or use --skip-db-import to start with empty database[/dim]")
        return None


def _get_latest_backup() -> Path | None:
    """Get the most recent database backup file.

    Returns:
        Path to the latest backup file, or None if no backups exist
    """
    backups_dir = get_backups_dir()
    if not backups_dir.exists():
        return None

    # Find .dump backup files
    backups = list(backups_dir.glob("shootout.*.dump"))
    if not backups:
        return None

    # Sort by modification time, newest first
    backups = sorted(backups, key=lambda p: p.stat().st_mtime, reverse=True)
    return backups[0]


def _start_and_configure_services(
    status,
    worktree,
    worktree_path: Path,
    worktree_name: str,
    is_main: bool,
    resuming: bool,
    skip_db_import: bool,
    build: bool,
    force: bool,
    health_timeout: int,
    backup_file: Path | None,
) -> None:
    """Start services and configure database."""
    import subprocess

    # Step 6: Build images if requested
    if build:
        status.update("[bold green]Building Docker images...")
        try:
            build_images(worktree_path)
        except Exception as e:
            print_warning(f"Image build failed: {e}")

    # Step 6.5: Clean up any leftover containers from previous failed attempts
    # This MUST happen BEFORE starting db, not after (start_services used to
    # do cleanup after db was already running and imported, tearing it down)
    status.update("[bold green]Cleaning up old containers...")
    cleanup_containers(worktree_path)

    # Step 7: Start database services first
    # Main worktree needs redis for jobs profile; feature worktrees don't
    status.update("[bold green]Starting database services...")
    try:
        db_services = ["db"]
        if is_main:
            db_services.append("redis")
        run_compose(["up", "-d", *db_services], cwd=worktree_path)
    except Exception as e:
        print_error(f"Failed to start database services: {e}")
        raise typer.Exit(1) from None

    # Step 7.5: Wait for database to be ready
    status.update("[bold green]Waiting for database to be ready...")
    db_ready = False
    for _ in range(30):
        db_status = get_service_status(worktree_path)
        if db_status.get("db") == "running":
            check_result = subprocess.run(
                [
                    "docker",
                    "compose",
                    "exec",
                    "-T",
                    "db",
                    "pg_isready",
                    "-U",
                    "gts",
                    "-d",
                    "gts_core",
                ],
                cwd=worktree_path,
                capture_output=True,
                timeout=5,
            )
            if check_result.returncode == 0:
                db_ready = True
                break
        time.sleep(1)

    if not db_ready:
        print_error("Database did not become ready in time")
        raise typer.Exit(1)

    # Step 8: Import database
    if not skip_db_import and backup_file and backup_file.exists():
        _import_database(status, worktree_path, backup_file, is_main=is_main)
    elif not skip_db_import:
        status.stop()
        print_error("No database backup available (this is unexpected)")
        console.print("[dim]Use --skip-db-import to start with empty database[/dim]")
        raise typer.Exit(1)

    # Step 9: Start remaining services (db is already running — skip cleanup)
    # Don't fail hard here — docker compose up -d returns non-zero when a
    # dependency health check fails (e.g. webapp crash prevents nginx start).
    # Let Step 10 health check provide proper diagnosis with log collection.
    status.update("[bold green]Starting application services...")
    startup_error: str | None = None
    try:
        start_services(worktree_path, cleanup=False)
    except DockerError as e:
        startup_error = str(e)  # Capture for failure report

    # Step 10: Wait for services to be ready
    # Skip the slow health poll if startup already failed (build error etc.)
    if startup_error:
        ready, issues = False, [f"Docker startup/build failed:\n{startup_error}"]
    else:
        status.update(
            f"[bold green]Waiting for services to be ready (timeout: {health_timeout}s)..."
        )
        ready, issues = wait_for_services_ready(worktree, worktree_path, timeout=health_timeout)

    if not ready:
        # Report but DON'T roll back — the worktree is intact (db imported,
        # configs written). Rolling back destroys work and breaks idempotency.
        # The user can fix the code and restart, or re-run setup (resume path).
        status.update("[bold red]Services unhealthy — collecting logs...")
        container_logs = collect_container_logs(worktree_path)
        service_status = get_service_status(worktree_path)
        status.stop()

        console.print()
        report = format_failure_report(issues, container_logs, service_status)
        console.print(report)
        console.print()
        console.print("[bold red]Some services did not become healthy.[/bold red]")
        console.print("[dim]The worktree is intact. Fix the issue and re-run setup.[/dim]")
        if not force:
            raise typer.Exit(1)

    # Step 11: Auto-restore auth if available
    _restore_auth(status, worktree, worktree_path)


def _import_database(status, worktree_path: Path, backup_file: Path, is_main: bool = False) -> None:
    """Import database from backup file using just db-import.

    This drops and recreates the database, then restores from the backup.
    Safe because it's atomic: drop + create + restore happens together.
    """
    import subprocess

    status.update("[bold green]Importing database...")

    try:
        result = subprocess.run(
            ["just", "db-import", str(backup_file)],
            cwd=worktree_path,
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode != 0:
            status.stop()
            print_error(f"Database import failed: {result.stderr}")
            console.print()
            console.print("[yellow]The worktree has been created but has no data.[/yellow]")
            raise typer.Exit(1)

        console.print(f"  [green]✓[/green] Database imported from {backup_file.name}")

    except subprocess.TimeoutExpired:
        status.stop()
        print_error("Database import timed out")
        raise typer.Exit(1) from None
    except Exception as e:
        status.stop()
        print_error(f"Database import failed: {e}")
        raise typer.Exit(1) from None


def _restore_auth(status, worktree, worktree_path: Path) -> None:
    """Restore auth if available."""
    status.update("[bold green]Checking auth status...")
    from ..auth import check_auth_status, get_webapp_url_for_worktree, restore_session

    auth_status = check_auth_status()
    if auth_status.valid:
        webapp_url = get_webapp_url_for_worktree(worktree_path)
        success, message = restore_session(webapp_url)
        if success:
            console.print(f"  [green]✓[/green] Auth restored for {auth_status.username}")
        else:
            print_warning(f"Auth restore failed: {message}")
            console.print("  [dim]Run 'auth-restore' manually to activate auth.[/dim]")
    else:
        console.print("  [dim]No valid auth found. Run 'auth-login' to authenticate.[/dim]")


def _handle_resume_path(
    status,
    worktree,
    worktree_path: Path,
    is_main: bool,
    skip_db_import: bool,
    force: bool,
    health_timeout: int,
) -> None:
    """Handle resuming an existing worktree.

    Feature worktrees: export main's database, import it, start services.
    Main worktree: start services only (database is the live source of truth).
    """
    import subprocess

    # Step 1: Get database backup from main (feature worktrees only)
    # Main's database is the live source of truth — never overwrite it from a backup.
    backup_file: Path | None = None
    if not skip_db_import and not is_main:
        with _timed_step("db-export"):
            backup_file = _get_or_create_backup(status, is_main=False)
            if backup_file is None:
                raise typer.Exit(1)

    # Step 1.5: Clean up any leftover containers before starting fresh
    with _timed_step("cleanup"):
        status.update("[bold green]Cleaning up old containers...")
        cleanup_containers(worktree_path)

    # Step 2: Start database services
    # Main worktree needs redis for jobs profile; feature worktrees don't
    with _timed_step("db-start"):
        status.update("[bold green]Starting database services...")
        try:
            db_services = ["db"]
            if is_main:
                db_services.append("redis")
            run_compose(["up", "-d", *db_services], cwd=worktree_path)
        except Exception as e:
            print_error(f"Failed to start database services: {e}")
            raise typer.Exit(1) from None

    # Step 3: Wait for database to be ready
    with _timed_step("db-ready"):
        status.update("[bold green]Waiting for database to be ready...")
        db_ready = False
        for _ in range(30):
            db_status = get_service_status(worktree_path)
            if db_status.get("db") == "running":
                check_result = subprocess.run(
                    [
                        "docker",
                        "compose",
                        "exec",
                        "-T",
                        "db",
                        "pg_isready",
                        "-U",
                        "gts",
                        "-d",
                        "gts_core",
                    ],
                    cwd=worktree_path,
                    capture_output=True,
                    timeout=5,
                )
                if check_result.returncode == 0:
                    db_ready = True
                    break
            time.sleep(1)

        if not db_ready:
            print_error("Database did not become ready in time")
            raise typer.Exit(1)

    # Step 4: Import database (feature worktrees only)
    # Main's database is the live source of truth — never overwrite on resume.
    with _timed_step("db-import"):
        if not skip_db_import and not is_main and backup_file and backup_file.exists():
            _import_database(status, worktree_path, backup_file)

    # Step 5: Start remaining services (db is already running — skip cleanup)
    # Don't fail hard — let Step 6 health check diagnose partial failures.
    startup_error: str | None = None
    with _timed_step("services-start"):
        status.update("[bold green]Starting application services...")
        try:
            start_services(worktree_path, cleanup=False)
        except DockerError as e:
            startup_error = str(e)  # Capture for failure report

    # Step 6: Wait for services to be ready
    # Skip the slow health poll if startup already failed (build error etc.)
    with _timed_step("health-check"):
        if startup_error:
            ready, issues = False, [f"Docker startup/build failed:\n{startup_error}"]
        else:
            status.update(
                f"[bold green]Waiting for services to be ready (timeout: {health_timeout}s)..."
            )
            ready, issues = wait_for_services_ready(worktree, worktree_path, timeout=health_timeout)
        if not ready:
            container_logs = collect_container_logs(worktree_path)
            service_status = get_service_status(worktree_path)

            console.print()
            report = format_failure_report(issues, container_logs, service_status)
            console.print(report)
            console.print()
            console.print("[bold red]Some services did not become healthy.[/bold red]")
            console.print("[dim]The worktree is intact. Fix the issue and re-run setup.[/dim]")
            if not force:
                raise typer.Exit(1)

    # Step 7: Restore auth
    with _timed_step("auth"):
        _restore_auth(status, worktree, worktree_path)


def _run_regression_tests(worktree_path: Path, worktree, status) -> bool:
    """Run regression tests to validate setup.

    Returns:
        True if tests passed, False if they failed.
    """
    import subprocess

    from ..cli_utils import get_public_url
    from ..docker import is_traefik_running

    status.update("[bold green]Running regression tests...")

    # Determine the test URL (SSL if Traefik running, otherwise localhost)
    public_url = get_public_url(worktree.branch)
    traefik_running = is_traefik_running()

    # Build environment for tests
    env = {
        "E2E_BASE_URL": public_url
        if public_url and traefik_running
        else f"http://localhost:{worktree.ports.nginx}",
        "E2E_API_URL": f"http://localhost:{worktree.ports.webapp}",
    }

    # Get database password from .env
    env_file = worktree_path / ".env"
    db_password = "gts_dev_password"  # Default
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith("DB_PASSWORD="):
                db_password = line.split("=", 1)[1]
                break

    env["E2E_DATABASE_URL"] = (
        f"postgresql+asyncpg://gts:{db_password}@localhost:{worktree.ports.db}/gts_core"
    )

    # If Traefik is running, wait for SSL endpoint to be routable
    # Traefik may need time to detect new containers after restart
    if traefik_running and public_url:
        status.update("[bold green]Waiting for Traefik routing...")
        if not _wait_for_ssl_endpoint(public_url, timeout=30):
            console.print("  [yellow]⚠[/yellow] SSL endpoint slow to respond, continuing anyway")

    # Run regression tests
    import os

    try:
        result = subprocess.run(
            ["just", "test-regression"],
            cwd=worktree_path,
            env={**os.environ, **env},
            capture_output=True,
            text=True,
            timeout=180,  # 3 minute timeout
        )

        if result.returncode == 0:
            console.print("  [green]✓[/green] Regression tests passed")
            return True
        else:
            console.print("  [red]✗[/red] Regression tests failed")
            # Show last few lines of output for context
            if result.stdout:
                lines = result.stdout.strip().split("\n")[-10:]
                for line in lines:
                    console.print(f"    [dim]{line}[/dim]")
            if result.stderr:
                lines = result.stderr.strip().split("\n")[-5:]
                for line in lines:
                    console.print(f"    [red]{line}[/red]")
            return False

    except subprocess.TimeoutExpired:
        console.print("  [red]✗[/red] Regression tests timed out")
        return False
    except FileNotFoundError:
        console.print("  [yellow]⚠[/yellow] Regression tests skipped (just not found)")
        return True  # Don't fail setup if just isn't available


def _display_setup_success(
    worktree,
    worktree_path: Path,
    worktree_name: str,
    branch: str,
    resuming: bool,
    no_start: bool,
) -> None:
    """Display success summary after setup."""
    from ..cli_utils import get_public_url

    health = check_worktree_health(worktree_path) if not no_start else None
    db_password = get_db_password(worktree_path)

    containers_line = "[dim]Not started[/dim]"
    if health:
        container_parts = []
        for svc, state in health.services.items():
            icon = "[green]●[/green]" if state == "running" else "[red]○[/red]"
            container_parts.append(f"{icon} {svc}")
        containers_line = (
            "  ".join(container_parts) if container_parts else "[dim]No containers[/dim]"
        )

    success_msg = (
        "[green bold]Worktree setup resumed![/green bold]"
        if resuming
        else "[green bold]Worktree created successfully![/green bold]"
    )

    # Check for public URL (Traefik on Linux servers)
    public_url = get_public_url(branch)
    public_url_line = ""
    if public_url:
        public_url_line = f"\n  [bold green]Public: {public_url}[/bold green]"

    console.print()
    console.print(
        Panel(
            f"""{success_msg}

[bold]Branch:[/bold] {branch}
[bold]Path:[/bold] {worktree_path}

[bold cyan]URLs:[/bold cyan]{public_url_line}
  App: http://localhost:{worktree.ports.nginx}  |  CloudBeaver: http://localhost:{worktree.ports.cloudbeaver}
[bold cyan]Internal:[/bold cyan] fe:Docker  be:{worktree.ports.webapp}

[bold cyan]Database:[/bold cyan] localhost:{worktree.ports.db}  User: [green]gts[/green]  Pass: [green]{db_password}[/green]

[bold cyan]CloudBeaver:[/bold cyan] User: [green]cbadmin[/green]  Pass: [green]{db_password}[/green]

[bold]Containers:[/bold] {containers_line}
""",
            title=f"Worktree: {worktree_name}",
            border_style="green",
        )
    )

    console.print()
    try:
        current_dir = Path.cwd().resolve()
        if current_dir == worktree_path.resolve():
            console.print("[bold green]You're ready to work![/bold green]")
        else:
            console.print("[bold yellow]To start working:[/bold yellow]")
            console.print()
            console.print(f"  [bold cyan]cd {worktree_path}[/bold cyan]")
    except Exception:
        console.print("[bold yellow]To start working:[/bold yellow]")
        console.print()
        console.print(f"  [bold cyan]cd {worktree_path}[/bold cyan]")

    console.print()
    console.print("[dim]Start CloudBeaver: docker compose --profile tools up -d cloudbeaver[/dim]")


def _ensure_compose_file_includes_traefik(worktree_path: Path) -> None:
    """Ensure COMPOSE_FILE in .env includes the traefik overlay."""
    env_file = worktree_path / ".env"
    traefik_compose = "docker-compose.traefik.yml"
    expected = "docker-compose.yml:docker-compose.override.yml:docker-compose.traefik.yml"

    if not env_file.exists():
        return

    content = env_file.read_text()
    lines = content.splitlines()

    # Check if COMPOSE_FILE already includes traefik
    for i, line in enumerate(lines):
        if line.startswith("COMPOSE_FILE="):
            if traefik_compose in line:
                return  # Already configured
            # Update to include traefik
            lines[i] = f"COMPOSE_FILE={expected}"
            env_file.write_text("\n".join(lines) + "\n")
            return

    # COMPOSE_FILE not present, add it
    with env_file.open("a") as f:
        f.write(f"COMPOSE_FILE={expected}\n")


def _setup_traefik(worktree_path: Path, status) -> None:
    """Set up Traefik integration for server deployments.

    If Traefik is already running (from any location), configure this worktree
    to use it by:
    - Ensuring COMPOSE_FILE includes traefik overlay
    - Ensuring traefik-public network exists

    If Traefik is not running but deploy/traefik/.env exists in the worktree,
    attempt to start it.
    """
    import subprocess

    from ..docker import is_traefik_running

    traefik_dir = worktree_path / "deploy" / "traefik"
    traefik_env = traefik_dir / ".env"

    # Check if Traefik is already running (from any location)
    traefik_running = is_traefik_running()

    if traefik_running:
        status.update("[bold green]Configuring Traefik integration...")

        # Ensure COMPOSE_FILE includes traefik overlay
        _ensure_compose_file_includes_traefik(worktree_path)

        # Ensure traefik-public network exists
        with contextlib.suppress(Exception):
            subprocess.run(
                ["docker", "network", "create", "traefik-public"],
                capture_output=True,
                check=False,  # OK if already exists
            )

        console.print("  [green]✓[/green] Traefik integration configured")
        return

    # Traefik not running - check if we can start it from this worktree
    if not traefik_env.exists():
        return  # No Traefik config, nothing to do

    status.update("[bold green]Starting Traefik reverse proxy...")

    # Ensure COMPOSE_FILE includes traefik overlay
    _ensure_compose_file_includes_traefik(worktree_path)

    # Ensure traefik-public network exists
    with contextlib.suppress(Exception):
        subprocess.run(
            ["docker", "network", "create", "traefik-public"],
            capture_output=True,
            check=False,  # OK if already exists
        )

    # Start traefik
    try:
        subprocess.run(
            ["docker", "compose", "up", "-d"],
            cwd=traefik_dir,
            capture_output=True,
            check=True,
            timeout=60,
        )
        console.print("  [green]✓[/green] Traefik started")
    except subprocess.CalledProcessError as e:
        status.stop()
        print_warning(f"Failed to start Traefik: {e}")
        console.print(f"  Check logs: cd {traefik_dir} && docker compose logs")
        status.start()
    except subprocess.TimeoutExpired:
        status.stop()
        print_warning("Traefik start timed out")
        status.start()


def _wait_for_ssl_endpoint(url: str, timeout: int = 30) -> bool:
    """Wait for SSL endpoint to respond via Traefik.

    After container restart, Traefik needs time to detect the new container
    and route traffic to it. This function waits until the endpoint responds.

    Args:
        url: The HTTPS URL to check (e.g., https://1.tone-shootout.com)
        timeout: Maximum wait time in seconds

    Returns:
        True if endpoint responded within timeout, False otherwise
    """
    import urllib.error
    import urllib.request
    from http.client import RemoteDisconnected

    health_url = f"{url.rstrip('/')}/health"
    start = time.time()
    delay = 1.0

    while time.time() - start < timeout:
        try:
            with urllib.request.urlopen(health_url, timeout=5) as response:
                if response.status == 200:
                    return True
        except (
            urllib.error.URLError,
            TimeoutError,
            ConnectionError,
            RemoteDisconnected,
            OSError,
        ):
            pass
        time.sleep(delay)
        delay = min(delay * 1.5, 3.0)

    return False


def _check_development_requirements(worktree_path: Path, status) -> None:
    """Check development requirements (Playwright, MCP servers).

    Fails hard if required prereqs are missing, pointing to `just infra`.
    Warns about optional prereqs (Chrome, MCP servers).
    """
    from ..requirements import (
        check_all_requirements,
        check_cld_wrapper_available,
    )

    status.update("[bold green]Checking development requirements...")
    requirements = check_all_requirements()

    # Playwright check (REQUIRED for E2E tests)
    if requirements["playwright"]:
        console.print("  [green]✓[/green] Playwright installed")
    else:
        status.stop()
        print_error(
            "Playwright not installed (required for E2E tests).\n\n"
            "Run infrastructure setup first:\n"
            "  [cyan]just infra[/cyan]\n\n"
            "Or install manually:\n"
            "  cd tests/e2e/python && uv sync && uv run playwright install chromium"
        )
        raise typer.Exit(1)

    # Chrome/Chromium check (optional - needed for Chrome DevTools MCP)
    if requirements["chrome"]:
        console.print("  [green]✓[/green] Chrome/Chromium installed")
    else:
        status.stop()
        print_warning(
            "Chrome/Chromium not found (needed for Chrome DevTools MCP).\n"
            "       UI debugging will not work without a browser.\n"
            "       Install with: [cyan]just infra[/cyan] (will prompt)"
        )
        status.start()

    # MCP checks - informational only
    # If cld wrapper is available, MCPs can be enabled on-demand
    if check_cld_wrapper_available():
        console.print("  [green]✓[/green] MCP servers available via cld wrapper")
    else:
        # Check configured MCPs
        required_mcps = ["chrome-devtools", "playwright"]
        optional_mcps = ["glm-vision"]

        for name in required_mcps:
            key = f"{name.replace('-', '_')}_mcp"
            if requirements.get(key, False):
                console.print(f"  [green]✓[/green] {name} MCP configured")

        for name in optional_mcps:
            key = f"{name.replace('-', '_')}_mcp"
            if requirements.get(key, False):
                console.print(f"  [green]✓[/green] {name} MCP configured [dim](optional)[/dim]")

        # Note about missing MCPs (don't fail, just inform)
        missing_required = [
            name
            for name in required_mcps
            if not requirements.get(f"{name.replace('-', '_')}_mcp", False)
        ]
        if missing_required:
            console.print(f"  [dim]MCP servers not configured: {', '.join(missing_required)}[/dim]")
            console.print("  [dim]See ~/.claude/settings.json to enable MCP servers[/dim]")
