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
            "title,state,labels,body,subIssuesSummary",
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


def _fetch_sub_issues(epic_number: int) -> list[dict]:
    """Fetch child sub-issues for a GitHub issue.

    Returns a list of dicts with keys: number, title, state.
    """
    result = subprocess.run(
        [
            "gh",
            "api",
            f"repos/{GH_REPO}/issues/{epic_number}/sub_issues",
            "--jq",
            "[.[] | {number, title, state}]",
        ],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
    )

    if result.returncode != 0:
        raise IngestionError(
            f"Failed to fetch sub-issues for #{epic_number}: {result.stderr.strip()}"
        )

    try:
        return json.loads(result.stdout) if result.stdout.strip() else []
    except json.JSONDecodeError as exc:
        raise IngestionError(f"Failed to parse sub-issues response: {exc}") from exc


def _fetch_parent_issue(epic_number: int) -> dict | None:
    """Fetch the parent issue for a GitHub issue, if any.

    Returns a dict with keys: number, title — or None if no parent.
    """
    result = subprocess.run(
        [
            "gh",
            "api",
            f"repos/{GH_REPO}/issues/{epic_number}/sub_issue",
            "--jq",
            "{number: .parent_issue_number, title: .parent_issue_title}",
        ],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
    )

    # 404 means no parent — not an error
    if result.returncode != 0:
        if "404" in result.stderr or "Not Found" in result.stderr:
            return None
        raise IngestionError(f"Failed to fetch parent for #{epic_number}: {result.stderr.strip()}")

    try:
        data = json.loads(result.stdout) if result.stdout.strip() else None
    except json.JSONDecodeError:
        return None

    return data


def check_sub_issues(epic_number: int, data: dict, children: list[dict] | None = None) -> list[str]:
    """Check whether an issue has sub-issues (making it a parent, not runnable).

    Pure function — only examines the data dict. If children are provided
    (fetched separately), includes them in the error message.

    Returns a list of error strings. Empty list means the issue is a leaf
    and can be run as an epic.
    """
    errors: list[str] = []

    sub_issues_summary = data.get("subIssuesSummary", {})
    total = sub_issues_summary.get("total", 0) if sub_issues_summary else 0

    if total > 0:
        msg = (
            f"Issue #{epic_number} is a parent with {total} sub-issue(s). "
            f"Only leaf issues can be run as epics."
        )
        if children:
            child_list = "\n".join(
                f"  - #{c['number']}: {c['title']} ({c['state']})" for c in children
            )
            msg += f"\nChildren:\n{child_list}"
        msg += "\nRun one of the child issues instead."
        errors.append(msg)

    return errors


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

    # Sub-issues gate: reject parent issues (they have children to run instead)
    sub_issues_summary = data.get("subIssuesSummary", {})
    total = sub_issues_summary.get("total", 0) if sub_issues_summary else 0
    children = _fetch_sub_issues(epic_number) if total > 0 else None
    sub_issue_errors = check_sub_issues(epic_number, data, children=children)
    if sub_issue_errors:
        error_list = "\n".join(f"  - {e}" for e in sub_issue_errors)
        raise IngestionError(f"Epic #{epic_number} cannot be ingested:\n{error_list}")

    # Informational: log if this issue is a child of another
    parent = _fetch_parent_issue(epic_number)
    if parent and parent.get("number"):
        print(f"Note: #{epic_number} is a child of #{parent['number']} ({parent.get('title', '')})")

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
