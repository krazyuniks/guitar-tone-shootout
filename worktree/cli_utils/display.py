"""Display functions for worktree CLI.

These functions handle presentation logic for various command outputs,
separated from business logic.
"""

from pathlib import Path

from rich.panel import Panel
from rich.table import Table

from ..issue_ops import GitHubIssue, IssueAnalysis, detect_changes_since_last_run
from ..local_state import LocalStateReport, StateIssue, fix_orphaned_worktree, fix_stale_operation
from .output import console


def display_local_state_report(
    report: LocalStateReport, auto_fix: bool, worktree_root: Path
) -> None:
    """Display the local state report with appropriate formatting."""
    if report.is_clean:
        content = (
            "[green]\u2713[/green] No orphaned worktrees\n"
            "[green]\u2713[/green] No leftover directories\n"
            "[green]\u2713[/green] No uncommitted changes\n"
            "[green]\u2713[/green] No stale operations"
        )
        console.print(Panel(content, title="Local State Check", border_style="green"))
        return

    # Build content with issues
    lines: list[str] = []

    # Group by category for cleaner display
    categories: dict[str, tuple[str, list[StateIssue]]] = {
        "orphan": ("Orphaned Worktrees", []),
        "leftover": ("Leftover Directories", []),
        "uncommitted": ("Uncommitted Changes", []),
        "stale_op": ("Stale Operations", []),
    }

    for issue in report.issues:
        if issue.category in categories:
            categories[issue.category][1].append(issue)

    # Build display
    for _cat_key, (cat_name, cat_issues) in categories.items():
        if cat_issues:
            for issue in cat_issues:
                icon = "[red]\u2717[/red]" if issue.severity == "error" else "[yellow]![/yellow]"
                fix_hint = " [dim](auto-fixable)[/dim]" if issue.auto_fixable else ""
                lines.append(f"{icon} {issue.message}{fix_hint}")

                # Attempt auto-fix if requested
                if auto_fix and issue.auto_fixable:
                    fixed = _attempt_auto_fix(issue, worktree_root)
                    if fixed:
                        lines.append("  [green]\u2713 Fixed[/green]")
                    else:
                        lines.append("  [red]\u2717 Fix failed[/red]")
        else:
            lines.append(f"[green]\u2713[/green] No {cat_name.lower()}")

    border_style = "red" if report.has_errors else "yellow" if report.has_warnings else "green"
    console.print(Panel("\n".join(lines), title="Local State Check", border_style=border_style))


def _attempt_auto_fix(issue: StateIssue, worktree_root: Path) -> bool:
    """Attempt to automatically fix an issue."""
    if issue.category == "orphan" and issue.path:
        # Default to registering orphaned worktrees
        return fix_orphaned_worktree(issue.path, action="register")
    elif issue.category == "leftover" and issue.path and issue.auto_fixable:
        # Remove leftover directories that only contain safe files
        return _fix_leftover_directory(issue.path)
    elif issue.category == "stale_op":
        # Extract operation ID from message
        # Message format: "Stale operation 'xxx' started at..."
        import re

        match = re.search(r"'([^']+)'", issue.message)
        if match:
            op_id = match.group(1)
            return fix_stale_operation(op_id, action="fail")
    return False


def _fix_leftover_directory(path: Path) -> bool:
    """Remove a leftover directory that only contains safe files.

    Args:
        path: Path to the leftover directory

    Returns:
        True if successfully removed
    """
    import shutil

    if not path.exists():
        return True

    # Double-check it's safe to delete
    safe_items = {".git", ".DS_Store", ".worktree-state"}
    try:
        contents = set(f.name for f in path.iterdir())
        unknown_contents = contents - safe_items
        if unknown_contents:
            return False  # Has unknown files, don't delete

        shutil.rmtree(path)
        return True
    except Exception:
        return False


def display_remaining_errors(report: LocalStateReport) -> None:
    """Display remaining errors after auto-fix attempt."""
    errors = [i for i in report.issues if i.severity == "error"]
    for error in errors:
        console.print(f"  [red]\u2717[/red] {error.message}")


def display_github_sync_skipped(cached_count: int) -> None:
    """Display message when GitHub sync is skipped."""
    content = (
        f"[yellow]GitHub sync skipped (--skip-github)[/yellow]\nUsing {cached_count} cached issues"
    )
    console.print(Panel(content, title="GitHub Sync", border_style="yellow"))


def display_github_sync_result(
    issues: list[GitHubIssue],
    cached_issues: list[GitHubIssue] | None,
    from_cache: bool,
) -> None:
    """Display GitHub sync results with change detection."""
    lines: list[str] = []

    if from_cache:
        lines.append(f"Using cached data ({len(issues)} issues)")
    else:
        lines.append(f"Fetched {len(issues)} open issues")

        # Detect changes if we have previous cache
        if cached_issues:
            changes = detect_changes_since_last_run(issues, cached_issues)
            new_count = len(changes["new"])
            closed_count = len(changes["closed"])
            updated_count = len(changes["updated"])

            if new_count or closed_count or updated_count:
                lines.append("")
                if new_count:
                    lines.append(f"[green]+{new_count} new[/green]")
                    for issue in changes["new"][:3]:  # Show up to 3
                        lines.append(f"  [green]+[/green] #{issue.number}: {issue.title[:50]}")
                    if new_count > 3:
                        lines.append(f"  [dim]...and {new_count - 3} more[/dim]")

                if closed_count:
                    lines.append(f"[red]-{closed_count} closed[/red]")

                if updated_count:
                    lines.append(f"[blue]~{updated_count} updated[/blue]")
            else:
                lines.append("[dim]No changes since last sync[/dim]")

    border_style = "green" if not from_cache else "yellow"
    console.print(Panel("\n".join(lines), title="GitHub Sync", border_style=border_style))


def display_issue_analysis(analysis: IssueAnalysis) -> None:
    """Display categorized issue analysis."""
    lines: list[str] = []

    # Summary counts
    lines.append(f"[green]Ready to work:[/green] {len(analysis.ready)} issues")
    lines.append(f"[yellow]Blocked:[/yellow] {len(analysis.blocked)} issues")
    lines.append(f"[blue]In Progress:[/blue] {len(analysis.in_progress)} issues")

    if analysis.stale:
        lines.append(f"[dim]Stale (30+ days):[/dim] {len(analysis.stale)} issues")

    console.print(Panel("\n".join(lines), title="Issue Analysis", border_style="blue"))


def filter_analysis(analysis: IssueAnalysis, filter_term: str) -> IssueAnalysis:
    """Filter analysis results by label or keyword."""
    filter_lower = filter_term.lower()

    def matches(issue: GitHubIssue) -> bool:
        # Check labels or title
        return (
            any(filter_lower in label.lower() for label in issue.labels)
            or filter_lower in issue.title.lower()
        )

    return IssueAnalysis(
        ready=[i for i in analysis.ready if matches(i)],
        blocked=[i for i in analysis.blocked if matches(i)],
        in_progress=[i for i in analysis.in_progress if matches(i)],
        stale=[i for i in analysis.stale if matches(i)],
    )


def display_orphans_table(orphan_list: list) -> None:
    """Display a table of orphaned git worktrees."""
    table = Table(title="Orphaned Git Worktrees")
    table.add_column("Name", style="yellow")
    table.add_column("Branch")
    table.add_column("Path")
    table.add_column("Commit")

    for orphan in orphan_list:
        table.add_row(
            orphan.path.name,
            orphan.branch,
            str(orphan.path),
            orphan.commit[:12],
        )

    console.print(table)
    console.print()
    console.print(f"[yellow]Found {len(orphan_list)} orphaned worktree(s)[/yellow]")
    console.print()
    console.print("[dim]To fix orphans:[/dim]")
    console.print("  [cyan]./worktree.py orphans adopt --name <name>[/cyan]  - Add to registry")
    console.print("  [cyan]./worktree.py orphans adopt --all[/cyan]          - Adopt all orphans")
    console.print("  [cyan]./worktree.py orphans remove --name <name>[/cyan] - Delete from git")


def display_stale_branches_table(stale: list) -> None:
    """Display a table of stale branches."""
    table = Table(title="Stale Branches (remote tracking gone)")
    table.add_column("Branch", style="yellow")
    table.add_column("Was Tracking")
    table.add_column("Commit")

    for branch in stale:
        table.add_row(branch.name, branch.tracking, branch.commit[:12])

    console.print(table)
    console.print()
