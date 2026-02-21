"""Epic ingestion — fetch a GitHub issue and store it locally.

Fetches the raw body, title, state, and labels from a GitHub epic issue
using `gh issue view` and writes it to `.planning/epics/E<N>/EPIC.md`
with YAML frontmatter.  Creates the stories subdirectory.  Idempotent:
re-running overwrites the local copy.

Usage:
    python -m workflow.epic_ingest <epic_number>
"""

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PLANNING_DIR = PROJECT_ROOT / ".planning" / "epics"
GH_REPO = "krazyuniks/guitar-tone-shootout"


class IngestionError(Exception):
    """Raised when epic ingestion fails."""


def _run_gh_issue_view(epic_number: int) -> dict:
    """Fetch issue metadata and body via gh issue view.

    Returns a dict with keys: title, state, labels, body.
    """
    result = subprocess.run(
        [
            "gh",
            "issue",
            "view",
            str(epic_number),
            "--repo",
            GH_REPO,
            "--json",
            "title,state,labels,body",
        ],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
    )

    if result.returncode != 0:
        raise IngestionError(
            f"gh issue view failed (exit {result.returncode}): {result.stderr.strip()}"
        )

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise IngestionError(f"Failed to parse gh output as JSON: {exc}") from exc

    return data


def _format_epic_md(epic_number: int, data: dict) -> str:
    """Format the EPIC.md content with YAML frontmatter + verbatim body."""
    title = data.get("title", "")
    state = data.get("state", "UNKNOWN")
    labels = [label["name"] for label in data.get("labels", [])]
    body = data.get("body", "")
    fetched = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Build YAML frontmatter
    # Quote the title to handle colons, dashes, and special chars
    labels_yaml = json.dumps(labels)
    frontmatter = (
        f"---\n"
        f"github_issue: {epic_number}\n"
        f'title: "{_escape_yaml_string(title)}"\n'
        f"state: {state}\n"
        f"labels: {labels_yaml}\n"
        f"fetched: {fetched}\n"
        f"---\n"
    )

    return f"{frontmatter}\n{body}\n"


def _escape_yaml_string(value: str) -> str:
    """Escape double quotes and backslashes for a YAML double-quoted string."""
    return value.replace("\\", "\\\\").replace('"', '\\"')


REQUIRED_SECTIONS = ["Summary", "Observable Outcomes", "Decisions", "Regression Boundaries"]


def validate_epic_structure(body: str) -> list[str]:
    """Validate the enriched epic format.

    Checks:
    1. Required sections (Summary, Observable Outcomes, Decisions, Regression Boundaries)
       must be present as markdown headings.
    2. Each required section must have non-empty content after the heading.
    3. Observable Outcomes section must contain at least one checkbox (``- [ ]``).

    Returns a list of error messages. Empty list means valid.
    """
    errors: list[str] = []
    body_lower = body.lower()

    for section in REQUIRED_SECTIONS:
        # Check for ## heading (case-insensitive)
        heading_pattern = f"## {section.lower()}"
        if heading_pattern not in body_lower:
            errors.append(f"Missing required section: '## {section}'")
            continue

        # Check section has non-empty content
        # Find the heading, then check content until next ## or end
        idx = body_lower.index(heading_pattern)
        after_heading = body[idx + len(f"## {section}") :]
        # Find next ## heading or end of string
        next_heading = after_heading.find("\n## ")
        section_content = after_heading[:next_heading] if next_heading != -1 else after_heading
        # Strip the heading line itself and check for non-whitespace content
        section_content = section_content.strip()
        if not section_content:
            errors.append(f"Section '## {section}' is empty")

    # Check for at least one outcome checkbox within Observable Outcomes section
    outcomes_heading = "## observable outcomes"
    if outcomes_heading in body_lower:
        outcomes_idx = body_lower.index(outcomes_heading)
        after_outcomes = body[outcomes_idx + len("## Observable Outcomes") :]
        next_h = after_outcomes.find("\n## ")
        outcomes_content = after_outcomes[:next_h] if next_h != -1 else after_outcomes
        if "- [ ]" not in outcomes_content:
            errors.append("Observable Outcomes must contain at least one checkbox ('- [ ]')")

    return errors


def ingest_epic(epic_number: int) -> Path:
    """Fetch a GitHub epic and write it to .planning/epics/E<N>/EPIC.md.

    Creates the epic directory and stories subdirectory if they don't exist.
    Idempotent: re-running overwrites the EPIC.md file.

    Args:
        epic_number: The GitHub issue number of the epic.

    Returns:
        Path to the written EPIC.md file.

    Raises:
        IngestionError: If the GitHub fetch fails.
    """
    data = _run_gh_issue_view(epic_number)

    # Structural validation of the enriched epic format
    body = data.get("body", "")
    validation_errors = validate_epic_structure(body)
    if validation_errors:
        error_list = "\n".join(f"  - {e}" for e in validation_errors)
        raise IngestionError(
            f"Epic #{epic_number} fails structural validation:\n{error_list}\n"
            "The issue must be enriched (Stage 0 brainstorming) before ingestion."
        )

    epic_dir = PLANNING_DIR / f"E{epic_number}"
    epic_dir.mkdir(parents=True, exist_ok=True)

    stories_dir = epic_dir / "stories"
    stories_dir.mkdir(parents=True, exist_ok=True)

    epic_md_path = epic_dir / "EPIC.md"
    content = _format_epic_md(epic_number, data)
    epic_md_path.write_text(content, encoding="utf-8")

    return epic_md_path


def main() -> None:
    """CLI entry point: python -m workflow.epic_ingest <epic_number>."""
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <epic_number>", file=sys.stderr)
        sys.exit(1)

    try:
        epic_number = int(sys.argv[1])
    except ValueError:
        print(f"Error: epic_number must be an integer, got: {sys.argv[1]}", file=sys.stderr)
        sys.exit(1)

    try:
        path = ingest_epic(epic_number)
        print(f"Ingested epic #{epic_number} to {path.relative_to(PROJECT_ROOT)}")
    except IngestionError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
