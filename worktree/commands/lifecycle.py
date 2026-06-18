"""Lifecycle commands for worktree CLI.

Provides commands for managing the PR lifecycle: merge-pr, complete, and cleanup.
"""

import subprocess
from pathlib import Path

import typer

from ..cli_utils import (
    console,
    print_error,
    print_info,
    print_success,
    print_warning,
)
from ..config import get_worktree_root
from ..docker import remove_containers
from ..git_ops import (
    GitError,
    delete_branch,
    prune_worktrees,
    remove_worktree,
    should_force_delete_branch,
)
from ..registry import (
    WorktreeNotFoundError,
    delete_worktree,
    get_worktree,
    list_worktrees,
)


def register_lifecycle_commands(app: typer.Typer) -> None:
    """Register lifecycle commands with the Typer app."""

    @app.command("merge-pr")
    def merge_pr(
        pr_number: int = typer.Argument(..., help="PR number to merge"),
        skip_sync: bool = typer.Option(False, "--skip-sync", help="Skip syncing other worktrees"),
        skip_teardown: bool = typer.Option(
            False, "--skip-teardown", help="Skip auto-teardown of merged worktree"
        ),
    ) -> None:
        """Merge a PR and sync all worktrees (RECOMMENDED workflow).

        This command:
        1. Checks if PR is already merged (handles gracefully if so)
        2. Merges the PR via gh CLI (squash merge) if not yet merged
        3. Auto-tears down the merged worktree (prevents rebase issues)
        4. Updates main branch
        5. Rebases all active feature worktrees onto new main
        """

        worktree_root = get_worktree_root()
        main_path = worktree_root / "main"

        if not main_path.exists():
            print_error("Main worktree not found")
            raise typer.Exit(1)

        pr_branch = None

        with console.status(f"[bold green]Processing PR #{pr_number}...") as status:
            # Step 0: Check PR state and get branch name
            status.update(f"[bold blue]Checking PR #{pr_number} state...")
            result = subprocess.run(
                [
                    "gh",
                    "pr",
                    "view",
                    str(pr_number),
                    "--json",
                    "state,headRefName",
                    "--repo",
                    "krazyuniks/guitar-tone-shootout",
                ],
                cwd=main_path,
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                import json

                try:
                    pr_data = json.loads(result.stdout)
                    pr_state = pr_data.get("state", "UNKNOWN").upper()
                    pr_branch = pr_data.get("headRefName")
                except json.JSONDecodeError:
                    pr_state = "UNKNOWN"
            else:
                pr_state = "UNKNOWN"

            if pr_state == "MERGED":
                print_info(f"PR #{pr_number} is already merged - skipping merge step")
            elif pr_state == "CLOSED":
                print_error(f"PR #{pr_number} is closed (not merged)")
                raise typer.Exit(1)
            elif pr_state == "OPEN":
                # Step 1: Merge the PR
                status.update(f"[bold green]Merging PR #{pr_number}...")
                result = subprocess.run(
                    [
                        "gh",
                        "pr",
                        "merge",
                        str(pr_number),
                        "--squash",
                        "--auto",
                        "--delete-branch",
                        "--repo",
                        "krazyuniks/guitar-tone-shootout",
                    ],
                    cwd=main_path,
                    capture_output=True,
                    text=True,
                )
                if result.returncode != 0:
                    print_error(f"Failed to merge PR: {result.stderr}")
                    raise typer.Exit(1)
                print_success(f"PR #{pr_number} merged successfully")
            else:
                # Unknown state - try to merge anyway
                print_warning(
                    f"Could not determine PR state (got: {pr_state}), attempting merge..."
                )
                status.update(f"[bold green]Merging PR #{pr_number}...")
                result = subprocess.run(
                    [
                        "gh",
                        "pr",
                        "merge",
                        str(pr_number),
                        "--squash",
                        "--auto",
                        "--delete-branch",
                        "--repo",
                        "krazyuniks/guitar-tone-shootout",
                    ],
                    cwd=main_path,
                    capture_output=True,
                    text=True,
                )
                if result.returncode != 0:
                    if (
                        "already been merged" in result.stderr.lower()
                        or "not open" in result.stderr.lower()
                    ):
                        print_info(f"PR #{pr_number} appears to be already merged")
                    else:
                        print_error(f"Failed to merge PR: {result.stderr}")
                        raise typer.Exit(1)
                else:
                    print_success(f"PR #{pr_number} merged successfully")

        # Step 2: Auto-teardown the merged worktree
        if pr_branch and not skip_teardown:
            _teardown_merged_worktree(pr_branch, pr_number, main_path)

        # Step 3: Sync all remaining worktrees
        if not skip_sync:
            console.print()
            console.print("[bold]Syncing all worktrees...[/bold]")
            # Import and call sync from git module
            # Create temporary app to get sync function
            _run_sync(main_path)
        else:
            print_warning("Skipping sync - remember to run ./worktree.py sync manually!")

    @app.command()
    def complete(
        pr_number: int = typer.Argument(..., help="PR number to complete"),
    ) -> None:
        """ATOMIC: Complete a PR lifecycle (merge + close issue + teardown).

        This is the recommended way to finish work on a PR. It handles:
        1. Verify/merge the PR
        2. Update main branch (pull merged changes immediately)
        3. Close the linked GitHub issue
        4. Teardown the worktree (stop Docker, remove files, delete branch)

        All steps are tracked in a state file. On failure, reports exactly what
        succeeded and what failed.

        Exit codes:
            0 = All steps completed successfully
            1 = One or more steps failed (see output for details)

        Examples:
            ./worktree.py complete 227
        """
        from ..lifecycle import LifecycleError, atomic_complete

        worktree_root = get_worktree_root()
        main_path = worktree_root / "main"

        if not main_path.exists():
            print_error("Main worktree not found")
            raise typer.Exit(1)

        console.print(f"[bold]Completing PR #{pr_number}...[/bold]")
        console.print()

        try:
            result = atomic_complete(pr_number, main_path)

            console.print()
            if result.success:
                console.print("[bold green]✓ PR lifecycle completed successfully![/bold green]")
                result.print_status()
                raise typer.Exit(0)
            else:
                console.print("[bold red]✗ PR lifecycle completed with errors![/bold red]")
                result.print_status()
                if result.error:
                    console.print(f"\n[red]Error: {result.error}[/red]")

                console.print("\n[yellow]Recovery commands:[/yellow]")
                if not result.main_updated:
                    console.print("  cd ../main && git pull --ff-only")
                if not result.worktree_removed:
                    console.print("  ./worktree.py teardown <worktree_name>")

                raise typer.Exit(1)

        except LifecycleError as e:
            print_error(str(e))
            raise typer.Exit(1) from None

    @app.command()
    def cleanup(
        force: bool = typer.Option(
            False, "--force", "-f", help="Actually perform cleanup (default: dry-run)"
        ),
    ) -> None:
        """Clean up merged branches and orphaned Docker resources.

        By default runs in dry-run mode. Use --force to actually clean up.
        """
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

        merged_branches = []
        worktree_branches = []
        for b in result.stdout.strip().split("\n"):
            stripped = b.strip()
            if not stripped:
                continue
            branch_name = stripped.lstrip("*+ ")
            if branch_name in ["main", ""]:
                continue
            if stripped.startswith("+"):
                worktree_branches.append(branch_name)
            elif stripped.startswith("*"):
                continue
            else:
                merged_branches.append(branch_name)

        # Show protected worktree branches first
        if worktree_branches:
            console.print(
                f"[bold cyan]Protected (active worktrees) - {len(worktree_branches)}:[/bold cyan]"
            )
            for branch in worktree_branches:
                console.print(f"  [cyan]⊘ {branch}[/cyan]")
            console.print()

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
                    force_del = should_force_delete_branch(branch)
                    delete_branch(branch, force=force_del)
                    print_success(f"Deleted: {branch}")
                except GitError as e:
                    print_warning(f"Could not delete {branch}: {e}")

        print_success("Cleanup complete!")


def _teardown_merged_worktree(pr_branch: str, pr_number: int, main_path: Path) -> None:
    """Teardown the worktree associated with a merged PR."""
    try:
        merged_worktree = get_worktree(pr_branch)
        merged_path = Path(merged_worktree.worktree_path)

        # Check if running from inside the worktree being torn down
        try:
            current_dir = Path.cwd().resolve()
            if current_dir == merged_path.resolve() or merged_path.resolve() in current_dir.parents:
                print_error("Cannot tear down worktree from inside it.")
                console.print("   Run this from main worktree instead:")
                console.print(
                    f"   [cyan]cd {main_path} && ./worktree.py merge-pr {pr_number}[/cyan]"
                )
                raise typer.Exit(1)
        except OSError:
            pass

        if merged_path.exists():
            console.print()
            console.print(
                f"[bold]Tearing down merged worktree: {merged_worktree.worktree_name}[/bold]"
            )

            with console.status("[bold red]Tearing down merged worktree...") as status:
                # Stop and remove Docker resources
                status.update("[bold red]Stopping Docker services...")
                try:
                    remove_containers(merged_worktree, merged_path)
                except Exception as e:
                    print_warning(f"Docker cleanup issue: {e}")

                # Remove git worktree
                status.update("[bold red]Removing git worktree...")
                try:
                    remove_worktree(merged_path, force=True)
                except GitError as e:
                    print_warning(f"Git worktree removal issue: {e}")

                prune_worktrees()

                # Delete local branch
                status.update("[bold red]Deleting local branch...")
                try:
                    force = should_force_delete_branch(merged_worktree.branch)
                    delete_branch(merged_worktree.branch, force=force)
                except GitError as e:
                    print_warning(f"Local branch deletion issue: {e}")

                # Update registry
                status.update("[bold red]Updating registry...")
                delete_worktree(merged_worktree.worktree_name)

            print_success(f"Worktree {merged_worktree.worktree_name} torn down")
    except WorktreeNotFoundError:
        pass  # No worktree for this branch


def _run_sync(main_path: Path) -> None:
    """Run the sync operation."""
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

                result = subprocess.run(
                    ["git", "rebase", "main"],
                    cwd=wt_path,
                    capture_output=True,
                    text=True,
                )
                if result.returncode != 0:
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
                console.print(
                    "[yellow]Resolve manually and run rebase in those worktrees.[/yellow]"
                )
