"""Maintenance commands for worktree CLI.

Provides commands for system maintenance, validation, and configuration.
"""

import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import typer

from ..cli_utils import console, print_error, print_info, print_success, print_warning
from ..config import get_worktree_root
from ..git_ops import install_hook, is_hook_installed, uninstall_hook
from ..registry import WorktreeNotFoundError, get_worktree_by_path, list_worktrees


def register_maintenance_commands(app: typer.Typer, version: str) -> None:
    """Register maintenance commands with the Typer app.

    Args:
        app: The Typer app to register commands with.
        version: The version string to display.
    """

    @app.command()
    def version_cmd() -> None:
        """Show version information."""
        console.print(f"worktree v{version}")

    # Register version with the expected name
    version_cmd.__name__ = "version"

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
                console.print(
                    '  [dim]Disable temporarily: GTS_NO_AUTO_SYNC=1 git commit -m "msg"[/dim]'
                )
            else:
                print_warning(f"Hook '{hook_name}' is not installed")
                console.print("  Run [cyan]./worktree.py hooks install[/cyan] to enable auto-sync")

        elif action == "install":
            if is_hook_installed(hook_name):
                print_info(f"Hook '{hook_name}' is already installed, updating...")

            if install_hook(hook_name):
                print_success(f"Hook '{hook_name}' installed successfully")
                console.print(
                    "  Feature branches will now auto-rebase onto origin/main after commits"
                )
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

    @app.command("check-stale")
    def check_stale() -> None:
        """Check for stale pending operations.

        Returns exit code 1 if any operations have been pending for > 2 minutes,
        indicating a failed setup or complete operation.
        """
        from ..lifecycle import check_lifecycle_health

        healthy, issues = check_lifecycle_health()

        if healthy:
            print_success("No stale operations")
            raise typer.Exit(0)
        else:
            console.print("[bold red]STALE OPERATIONS DETECTED![/bold red]")
            for issue in issues:
                console.print(f"  [red]• {issue}[/red]")
            console.print(
                "\n[yellow]These operations may have failed. Check logs and clean up manually.[/yellow]"
            )
            raise typer.Exit(1)

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
        subprocess.run(
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
                    print_warning(
                        f"  {wt.worktree_name}: {behind_main} commits behind main (needs rebase)"
                    )
                    issues.append(f"{wt.worktree_name} behind main")

        # Summary
        console.print()
        if issues:
            console.print(f"[bold yellow]Found {len(issues)} issue(s):[/bold yellow]")
            for issue in issues:
                console.print(f"  [yellow]• {issue}[/yellow]")
            raise typer.Exit(1)
        else:
            print_success("All validation checks passed!")

    @app.command("is-fresh")
    def is_fresh_cmd(
        minutes: int = typer.Option(
            5, "--minutes", "-m", help="Threshold in minutes to consider fresh"
        ),
        quiet: bool = typer.Option(False, "--quiet", "-q", help="Suppress output, exit code only"),
    ) -> None:
        """Check if current worktree was recently created.

        Returns exit code 0 if worktree is "fresh" (created within threshold),
        exit code 1 if older or not in a registered worktree.

        Useful for hooks to skip redundant checks after worktree setup.

        Examples:
            ./worktree.py is-fresh              # Default 5 minutes
            ./worktree.py is-fresh --minutes 10 # Custom threshold
            ./worktree.py is-fresh --quiet      # Just exit code
        """
        cwd = Path.cwd()

        try:
            worktree = get_worktree_by_path(cwd)
        except WorktreeNotFoundError:
            if not quiet:
                print_info("Not in a registered worktree")
            raise typer.Exit(1) from None

        # Parse created_at timestamp (ISO format with timezone)
        created_at_str = worktree.created_at
        if created_at_str.endswith("Z"):
            created_at_str = created_at_str.replace("Z", "+00:00")
        created_at = datetime.fromisoformat(created_at_str)
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)

        now = datetime.now(UTC)
        age_minutes = (now - created_at).total_seconds() / 60

        is_fresh = age_minutes < minutes

        if not quiet:
            if is_fresh:
                print_success(
                    f"Worktree is fresh ({age_minutes:.1f} min old, threshold: {minutes} min)"
                )
            else:
                print_info(
                    f"Worktree is not fresh ({age_minutes:.1f} min old, threshold: {minutes} min)"
                )

        raise typer.Exit(0 if is_fresh else 1)
