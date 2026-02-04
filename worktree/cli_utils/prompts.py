"""Interactive prompt functions for worktree CLI.

These functions handle user interaction for work selection and other
interactive workflows.
"""

from collections.abc import Callable
from pathlib import Path

from rich.prompt import Prompt
from rich.table import Table

from ..issue_ops import IssueAnalysis
from .output import console, print_error


def display_work_selection(
    analysis: IssueAnalysis,
    worktree_root: Path,
    setup_callback: Callable[[str], None],
) -> None:
    """Display interactive work selection menu.

    Args:
        analysis: The analyzed issues
        worktree_root: Root directory for worktrees
        setup_callback: Function to call with issue number to start setup
    """
    ready_issues = analysis.ready

    # Build selection table
    table = Table(title="Ready Issues", show_header=True, header_style="bold cyan")
    table.add_column("#", style="dim", width=4)
    table.add_column("Issue", style="cyan")
    table.add_column("Title")
    table.add_column("Labels", style="dim")

    for idx, issue in enumerate(ready_issues[:15], 1):  # Limit to 15
        labels = ", ".join(issue.labels[:2]) if issue.labels else ""
        if len(issue.labels) > 2:
            labels += f" +{len(issue.labels) - 2}"
        table.add_row(
            str(idx),
            f"#{issue.number}",
            issue.title[:50] + ("..." if len(issue.title) > 50 else ""),
            labels,
        )

    console.print(table)

    if len(ready_issues) > 15:
        console.print(f"[dim]...and {len(ready_issues) - 15} more issues[/dim]")

    console.print()

    # Interactive selection
    selection = Prompt.ask(
        "Select issue number to start work (or 'q' to quit)",
        default="q",
    )

    if selection.lower() == "q":
        console.print("[dim]Exiting without starting work.[/dim]")
        return

    # Parse selection
    try:
        idx = int(selection)
        if 1 <= idx <= len(ready_issues):
            selected_issue = ready_issues[idx - 1]
            console.print()
            console.print(
                f"Starting work on [cyan]#{selected_issue.number}[/cyan]: {selected_issue.title}"
            )
            console.print()

            # Call the setup command with the issue number
            setup_callback(str(selected_issue.number))
        else:
            print_error(f"Invalid selection: {idx}. Choose 1-{min(len(ready_issues), 15)}")
    except ValueError:
        # Maybe they entered an issue number directly
        try:
            issue_num = int(selection.replace("#", ""))
            matching = [i for i in ready_issues if i.number == issue_num]
            if matching:
                console.print()
                console.print(f"Starting work on [cyan]#{issue_num}[/cyan]: {matching[0].title}")
                console.print()
                setup_callback(str(issue_num))
            else:
                print_error(f"Issue #{issue_num} not found in ready issues.")
        except ValueError:
            print_error(f"Invalid input: {selection}. Enter a number or 'q' to quit.")


def prompt_start_services() -> bool:
    """Prompt user whether to start services.

    Returns:
        True if user wants to start services
    """
    choice = Prompt.ask(
        "Start services?",
        choices=["y", "n"],
        default="y",
    )
    return choice == "y"


def prompt_continue_teardown() -> bool:
    """Prompt user to confirm teardown of unmerged branch.

    Returns:
        True if user confirms
    """
    import typer

    return typer.confirm("Continue with teardown?")


def prompt_confirm_removal(targets: list, item_type: str = "item") -> bool:
    """Prompt user to confirm removal of items.

    Args:
        targets: List of items to be removed (must have .path.name and .path attributes)
        item_type: Description of what is being removed

    Returns:
        True if user confirms
    """
    import typer

    console.print(
        f"[bold red]Warning: This will permanently delete the following {item_type}s:[/bold red]"
    )
    for item in targets:
        console.print(f"  - {item.path.name} ({item.path})")
    console.print()
    return typer.confirm("Continue with removal?")
