"""Git commands for worktree CLI.

Provides commands for git worktree synchronization and maintenance.
"""

import subprocess
from pathlib import Path

import typer

from ..cli_utils import (
    console,
    display_orphans_table,
    display_stale_branches_table,
    print_error,
    print_success,
    print_warning,
    prompt_confirm_removal,
)
from ..config import get_worktree_root
from ..git_ops import (
    GitError,
    delete_stale_branches,
    list_stale_branches,
    prune_worktrees,
    remove_worktree,
)
from ..registry import (
    WorktreeExistsError,
    add_orphan_to_registry,
    find_orphaned_worktrees,
    list_worktrees,
    prune_stale_entries,
)
from ..resources import format_ports_display


def register_git_commands(app: typer.Typer) -> None:
    """Register git commands with the Typer app."""

    @app.command()
    def sync() -> None:
        """Sync all worktrees with main (fetch, update main, rebase feature branches).

        This is CRITICAL after any PR is merged to prevent divergence.
        """
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
                console.print(
                    "[yellow]Main may have diverged. Manual resolution required.[/yellow]"
                )
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
                        print_warning(
                            f"{wt.worktree_name}: Has uncommitted changes, skipping rebase"
                        )
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
                    console.print(
                        "[yellow]Resolve manually and run rebase in those worktrees.[/yellow]"
                    )

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

    @app.command("prune-branches")
    def prune_branches(
        dry_run: bool = typer.Option(
            False,
            "--dry-run",
            "-n",
            help="Show what would be deleted without actually deleting",
        ),
    ) -> None:
        """Delete local branches whose remote tracking branch no longer exists.

        After PRs are squash-merged, GitHub deletes the remote branch but the
        local branch remains with tracking status "gone". This command cleans
        up those stale local branches.

        Equivalent to: git branch -vv | grep gone | xargs git branch -D

        Protected branches (main, master, develop, development) are never deleted.

        Examples:
            ./worktree.py prune-branches           # Delete stale branches
            ./worktree.py prune-branches --dry-run # Show what would be deleted
        """
        with console.status("[bold]Scanning for stale branches..."):
            stale = list_stale_branches()

        if not stale:
            console.print("[green]No stale branches found.[/green]")
            console.print("[dim]All local branches have valid remote tracking branches.[/dim]")
            return

        # Display branches to be deleted
        display_stale_branches_table(stale)

        if dry_run:
            console.print(f"[yellow]Dry-run: Would delete {len(stale)} branch(es)[/yellow]")
            console.print("[dim]Run without --dry-run to actually delete.[/dim]")
            return

        # Actually delete the branches
        console.print(f"Deleting {len(stale)} stale branch(es)...")
        results = delete_stale_branches(stale)

        # Report results
        success_count = 0
        for branch_name, success, message in results:
            if success:
                print_success(f"Deleted: {branch_name}")
                success_count += 1
            else:
                print_warning(f"Failed to delete {branch_name}: {message}")

        console.print()
        if success_count == len(stale):
            print_success(f"Cleaned up {success_count} stale branch(es)")
        else:
            print_warning(
                f"Deleted {success_count}/{len(stale)} branches. "
                f"Some branches could not be deleted."
            )

    @app.command()
    def orphans(
        action: str = typer.Argument(
            "list",
            help="Action: list (show orphans), adopt (add to registry), remove (delete from git)",
        ),
        name: str | None = typer.Option(
            None,
            "--name",
            "-n",
            help="Orphan name (directory name) to act on",
        ),
        all_orphans: bool = typer.Option(
            False,
            "--all",
            "-a",
            help="Apply action to all orphans (use with adopt or remove)",
        ),
        force: bool = typer.Option(
            False,
            "--force",
            "-f",
            help="Force removal without confirmation",
        ),
    ) -> None:
        """Manage orphaned git worktrees (exist in git but not in registry).

        Orphans occur when:
        - Registry database was reset or corrupted
        - Worktree was created manually with git worktree add
        - Setup failed partway through

        Actions:
            list   - Show all orphaned worktrees (default)
            adopt  - Add orphan(s) to registry with auto-assigned ports
            remove - Delete orphan(s) from git (removes worktree directory)

        Examples:
            ./worktree.py orphans                    # List all orphans
            ./worktree.py orphans adopt --name main  # Adopt specific orphan
            ./worktree.py orphans adopt --all        # Adopt all orphans
            ./worktree.py orphans remove --name old-branch --force  # Remove without confirm
        """
        orphan_list = find_orphaned_worktrees()

        if not orphan_list:
            console.print("[green]No orphaned worktrees found.[/green]")
            console.print("[dim]All git worktrees are properly tracked in the registry.[/dim]")
            return

        if action == "list":
            # Show detailed list of orphans
            display_orphans_table(orphan_list)

        elif action == "adopt":
            # Add orphans to registry
            if not name and not all_orphans:
                print_error("Specify --name <name> or --all to adopt orphans")
                raise typer.Exit(1)

            targets = (
                orphan_list if all_orphans else [o for o in orphan_list if o.path.name == name]
            )
            if not targets:
                print_error(f"No orphan found with name: {name}")
                console.print("[dim]Run ./worktree.py orphans to see available orphans[/dim]")
                raise typer.Exit(1)

            for orphan in targets:
                try:
                    worktree = add_orphan_to_registry(orphan)
                    print_success(f"Adopted: {orphan.path.name}")
                    console.print(f"  Branch: {worktree.branch}")
                    console.print(f"  Ports: {format_ports_display(worktree.ports)}")
                    console.print(f"  App: http://localhost:{worktree.ports.nginx}")
                except WorktreeExistsError as e:
                    print_warning(f"Could not adopt {orphan.path.name}: {e}")
                except Exception as e:
                    print_error(f"Failed to adopt {orphan.path.name}: {e}")

            console.print()
            console.print("[dim]Note: Docker services are NOT started automatically.[/dim]")
            console.print(
                "[dim]Run docker compose up -d in the worktree directory to start services.[/dim]"
            )

        elif action == "remove":
            # Remove orphans from git
            if not name and not all_orphans:
                print_error("Specify --name <name> or --all to remove orphans")
                raise typer.Exit(1)

            targets = (
                orphan_list if all_orphans else [o for o in orphan_list if o.path.name == name]
            )
            if not targets:
                print_error(f"No orphan found with name: {name}")
                console.print("[dim]Run ./worktree.py orphans to see available orphans[/dim]")
                raise typer.Exit(1)

            # Confirm removal
            if not force and not prompt_confirm_removal(targets, "worktree"):
                raise typer.Abort()

            for orphan in targets:
                try:
                    remove_worktree(orphan.path, force=True)
                    print_success(f"Removed: {orphan.path.name}")
                except GitError as e:
                    print_warning(f"Could not remove {orphan.path.name}: {e}")

            # Prune git worktrees
            prune_worktrees()

        else:
            print_error(f"Unknown action: {action}")
            console.print("[dim]Valid actions: list, adopt, remove[/dim]")
            raise typer.Exit(1)
