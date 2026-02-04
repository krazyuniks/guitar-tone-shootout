"""Teardown commands for worktree CLI.

Provides commands for tearing down worktrees and cleaning up orphaned containers.
"""

from pathlib import Path

import typer

from ..cli_utils import (
    console,
    print_error,
    print_success,
    print_warning,
)
from ..docker import (
    cleanup_orphaned_containers,
    find_orphaned_containers,
    find_orphaned_networks,
    force_cleanup_project,
    remove_volumes,
)
from ..git_ops import (
    GitError,
    delete_branch,
    delete_remote_branch,
    is_branch_merged,
    prune_worktrees,
    remove_worktree,
    should_force_delete_branch,
)
from ..registry import (
    WorktreeNotFoundError,
    delete_worktree,
    get_worktree,
)
from ..resources import format_ports_display


def register_teardown_commands(app: typer.Typer) -> None:
    """Register teardown commands with the Typer app."""

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
            raise typer.Exit(1) from None

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
                # Auto-cleanup orphaned containers when graceful shutdown fails
                status.update("[bold red]Force cleaning orphaned containers...")
                try:
                    cleaned = cleanup_orphaned_containers(dry_run=False)
                    if cleaned:
                        console.print(f"  Force cleaned {len(cleaned)} orphaned containers")
                except Exception as cleanup_err:
                    print_warning(f"Force cleanup also failed: {cleanup_err}")

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
                    # Use force delete if: not merged at all, OR squash-merged
                    force_delete = not branch_merged or should_force_delete_branch(worktree.branch)
                    delete_branch(worktree.branch, force=force_delete)
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

            # Step 6: Force cleanup to ensure no orphans remain
            status.update("[bold red]Verifying cleanup...")
            success, removed = force_cleanup_project(worktree.compose_project)
            if removed:
                console.print(f"  [dim]Force-cleaned: {len(removed)} resource(s)[/dim]")

            # Step 7: Check for orphaned containers (final verification)
            status.update("[bold red]Final verification...")
            orphans = find_orphaned_containers()
            our_orphans = [o for o in orphans if o.compose_project == worktree.compose_project]
            if our_orphans:
                print_warning(
                    f"Some resources from {worktree.compose_project} may remain. "
                    "Run './worktree.py cleanup-orphans' to clean them."
                )

        print_success(f"Worktree {worktree.worktree_name} torn down successfully")
        console.print(f"  Freed ports: {format_ports_display(worktree.ports)}")

    @app.command("cleanup-orphans")
    def cleanup_orphans_cmd(
        dry_run: bool = typer.Option(
            False,
            "--dry-run",
            "-n",
            help="Show what would be cleaned without doing it",
        ),
    ) -> None:
        """Find and remove orphaned Docker containers and networks.

        Orphaned resources are Docker containers/networks from worktrees that
        no longer exist in the registry. This can happen when:
        - A worktree was deleted manually (rm -rf) without using teardown
        - The registry database was reset or corrupted
        - A setup failed partway through
        - Containers were stopped but networks remained

        Use --dry-run to see what would be cleaned without removing anything.
        """
        console.print("[bold]Scanning for orphaned Docker resources...[/bold]")

        container_orphans = find_orphaned_containers()
        network_orphans = find_orphaned_networks()

        if not container_orphans and not network_orphans:
            print_success("No orphaned Docker resources found!")
            return

        # Group containers by project
        projects: dict[str, list] = {}
        for orphan in container_orphans:
            if orphan.compose_project not in projects:
                projects[orphan.compose_project] = []
            projects[orphan.compose_project].append(orphan)

        # Display container orphans
        if projects:
            console.print(
                f"\n[yellow]Found {len(projects)} orphaned container group(s):[/yellow]\n"
            )
            for project, containers in sorted(projects.items()):
                console.print(f"  [cyan]{project}[/cyan]")
                for c in containers:
                    port_info = ", ".join(c.ports) if c.ports else "no ports"
                    console.print(f"    - {c.service}: {port_info}")

        # Display network orphans (that aren't already covered by containers)
        container_projects = set(projects.keys())
        standalone_networks = [
            n for n in network_orphans if n.compose_project not in container_projects
        ]

        if standalone_networks:
            console.print(
                f"\n[yellow]Found {len(standalone_networks)} orphaned network(s):[/yellow]\n"
            )
            for network in standalone_networks:
                subnet_info = f" ({network.subnet})" if network.subnet else ""
                console.print(f"  [cyan]{network.network_name}[/cyan]{subnet_info}")

        console.print()

        if dry_run:
            console.print("[dim]Dry run - no changes made[/dim]")
            return

        # Do the cleanup
        with console.status("[bold red]Cleaning up orphaned resources..."):
            cleaned = cleanup_orphaned_containers(dry_run=False)

        if cleaned:
            print_success(f"Cleaned up {len(cleaned)} orphaned resource(s):")
            for item in cleaned:
                console.print(f"  - {item}")
        else:
            print_warning("No resources were cleaned up")
