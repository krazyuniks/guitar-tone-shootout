"""Interactive scope discussion for epic planning.

Extracts area-specific questions from CONTEXT.md and presents them
one at a time for the user to answer.  Writes answers to
user-decisions.json as key/value pairs (question string → answer string).

Usage:
    from workflow.scope_discussion import run_scope_discussion
    decisions = run_scope_discussion(epic_dir)
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

console = Console()


class ScopeDiscussionError(Exception):
    """Raised when scope discussion fails."""


def _extract_questions_from_context(context_path: Path) -> list[tuple[str, str]]:
    """Extract scope discussion questions from CONTEXT.md.

    Parses the '## Scope Discussion Questions' section, extracting
    area names (### headings) and their bullet-point questions.

    Args:
        context_path: Path to CONTEXT.md.

    Returns:
        List of (area_name, question) tuples.

    Raises:
        ScopeDiscussionError: If CONTEXT.md is missing or has no questions.
    """
    if not context_path.is_file():
        raise ScopeDiscussionError(
            f"CONTEXT.md not found at {context_path}. " "Run context assembly first."
        )

    content = context_path.read_text(encoding="utf-8")

    # Find the Scope Discussion Questions section
    match = re.search(
        r"^## Scope Discussion Questions\s*\n(.*?)(?=^## |\Z)",
        content,
        re.MULTILINE | re.DOTALL,
    )
    if not match:
        raise ScopeDiscussionError(
            "No '## Scope Discussion Questions' section found in CONTEXT.md."
        )

    section = match.group(1)

    # Parse ### Area headings and their bullet questions
    questions: list[tuple[str, str]] = []
    current_area = "General"

    for line in section.splitlines():
        line = line.strip()
        if line.startswith("### "):
            current_area = line[4:].strip()
        elif line.startswith("- "):
            question = line[2:].strip()
            if question:
                questions.append((current_area, question))

    return questions


def _validate_decisions(decisions: dict[str, str], schema_path: Path) -> None:
    """Validate decisions against the JSON schema.

    Args:
        decisions: The decisions dict to validate.
        schema_path: Path to user-decisions.schema.json.

    Raises:
        ScopeDiscussionError: If validation fails.
    """
    if not schema_path.is_file():
        # Schema file not found — skip validation with warning
        console.print(
            f"[yellow]Warning: Schema not found at {schema_path}, " f"skipping validation.[/yellow]"
        )
        return

    try:
        import jsonschema
    except ImportError:
        console.print("[yellow]Warning: jsonschema not installed, " "skipping validation.[/yellow]")
        return

    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    try:
        jsonschema.validate(instance=decisions, schema=schema)
    except jsonschema.ValidationError as exc:
        raise ScopeDiscussionError(f"Decisions failed schema validation: {exc.message}") from exc


def run_scope_discussion(
    epic_dir: Path,
    interactive: bool = True,
) -> dict[str, str]:
    """Run the scope discussion and return decisions.

    If interactive, extracts questions from CONTEXT.md's
    'Scope Discussion Questions' section, presents them one at a time,
    and collects answers.  Supports 'done' to finish early and 'skip'
    to skip a question.

    If not interactive, loads from existing user-decisions.json.

    Args:
        epic_dir: Path to the epic directory (e.g. .planning/epics/E95/).
        interactive: If True, run interactive Q&A.  If False, load existing.

    Returns:
        Dict of question -> answer pairs.

    Raises:
        ScopeDiscussionError: If non-interactive and user-decisions.json
            is missing, or if CONTEXT.md is missing/malformed.
    """
    decisions_path = epic_dir / "user-decisions.json"
    schema_dir = Path(__file__).resolve().parent / "schemas"
    schema_path = schema_dir / "user-decisions.schema.json"

    # Non-interactive mode: load existing decisions
    if not interactive:
        if not decisions_path.is_file():
            raise ScopeDiscussionError(
                f"Non-interactive mode requires {decisions_path}. "
                "Create it with scope decisions before running."
            )
        try:
            decisions = json.loads(decisions_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ScopeDiscussionError(f"Failed to parse {decisions_path}: {exc}") from exc

        _validate_decisions(decisions, schema_path)
        return decisions

    # Interactive mode: extract and present questions
    context_path = epic_dir / "CONTEXT.md"
    questions = _extract_questions_from_context(context_path)

    if not questions:
        console.print("[yellow]No scope discussion questions found in CONTEXT.md.[/yellow]")
        decisions: dict[str, str] = {}
        _save_decisions(decisions, decisions_path)
        _validate_decisions(decisions, schema_path)
        return decisions

    console.print()
    console.print(
        Panel(
            "Answer each question to lock scope decisions.\n"
            "Type [bold]skip[/bold] to skip a question, "
            "[bold]done[/bold] to finish early.",
            title="Scope Discussion",
            border_style="blue",
        )
    )
    console.print()

    decisions = {}
    total = len(questions)

    for i, (area, question) in enumerate(questions, 1):
        console.print(f"[dim]({i}/{total})[/dim] [bold cyan]{area}[/bold cyan]")
        console.print(f"  {question}")

        try:
            answer = Prompt.ask("  Answer", default="skip")
        except (EOFError, KeyboardInterrupt):
            console.print("\n[yellow]Scope discussion ended early.[/yellow]")
            break

        answer = answer.strip()

        if answer.lower() == "done":
            console.print("[green]Scope discussion complete.[/green]")
            break

        if answer.lower() == "skip" or not answer:
            console.print("  [dim]Skipped[/dim]")
            continue

        decisions[question] = answer
        console.print("  [green]Locked[/green]")

    console.print()
    console.print(f"[bold]{len(decisions)}[/bold] decisions recorded.")

    _save_decisions(decisions, decisions_path)
    _validate_decisions(decisions, schema_path)

    return decisions


def _save_decisions(decisions: dict[str, str], path: Path) -> None:
    """Write decisions to JSON file."""
    path.write_text(
        json.dumps(decisions, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
