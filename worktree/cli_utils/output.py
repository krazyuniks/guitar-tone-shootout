"""CLI output helper functions.

Provides styled console output for the worktree CLI, including error,
success, warning, and info messages, as well as panel formatting.
"""

from rich.console import Console
from rich.panel import Panel

# Shared console instance for all CLI output
console = Console()


def print_error(message: str) -> None:
    """Print an error message in red."""
    console.print(f"[red]Error:[/red] {message}")


def print_success(message: str) -> None:
    """Print a success message with green checkmark."""
    console.print(f"[green]\u2713[/green] {message}")


def print_warning(message: str) -> None:
    """Print a warning message in yellow."""
    console.print(f"[yellow]Warning:[/yellow] {message}")


def print_info(message: str) -> None:
    """Print an info message in blue."""
    console.print(f"[blue]Info:[/blue] {message}")


def print_panel(title: str, content: str, style: str = "blue") -> None:
    """Print a rich panel with title and content.

    Args:
        title: The panel title displayed at the top.
        content: The panel body content (supports rich markup).
        style: The border style/color (default: "blue").
    """
    console.print(Panel(content, title=title, border_style=style))
