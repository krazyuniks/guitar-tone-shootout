#!/usr/bin/env python3
"""
Materialise TASKS.md into .tasks/ directory files consumed by run_epic.py.

Parses the structured TASKS.md format (produced by epic-task-breakdown agent)
and writes individual task markdown files + created.json.

Usage:
    python scripts/tasks_from_plan.py <epic_number> [--slug <slug>]
    python scripts/tasks_from_plan.py 70 --slug video-bc-integration-remotion-power
    python scripts/tasks_from_plan.py 33 --slug phase-4-web-app --dry-run

Input:  .planning/epics/{slug}/TASKS.md
Output: .tasks/projects/guitar-tone-shootout/epics/E{n}/tasks/T{id}.md
        .planning/epics/{slug}/created.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PLANNING_DIR = PROJECT_ROOT / ".planning" / "epics"
TASKS_BASE = PROJECT_ROOT / ".tasks" / "projects" / "guitar-tone-shootout" / "epics"


# ---------------------------------------------------------------------------
# Task parsing
# ---------------------------------------------------------------------------


@dataclass
class ParsedTask:
    """A task parsed from TASKS.md."""

    task_id: str  # e.g. "A1", "B2"
    title: str
    objective: str = ""
    acceptance_criteria: list[str] = field(default_factory=list)
    scope_create: list[str] = field(default_factory=list)
    scope_modify: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)  # task IDs like ["A1", "B2"]
    labels: list[str] = field(default_factory=list)
    project: str = ""
    citation: str = ""


def parse_tasks_md(content: str) -> list[ParsedTask]:
    """Parse TASKS.md into a list of ParsedTask objects."""
    tasks: list[ParsedTask] = []

    # Split on task headers: ### {ID}: {Title}
    # Matches patterns like "### A1: Title" or "### B2: Title"
    task_pattern = re.compile(r"^### ([A-Z]\d+):\s*(.+)$", re.MULTILINE)
    matches = list(task_pattern.finditer(content))

    for i, match in enumerate(matches):
        task_id = match.group(1)
        title = match.group(2).strip()

        # Extract section content (until next task or end)
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        section = content[start:end]

        task = ParsedTask(task_id=task_id, title=title)

        # Objective
        obj_match = re.search(
            r"\*\*Objective:\*\*\s*(.*?)(?=\n\*\*|\n---|\Z)",
            section,
            re.DOTALL,
        )
        if obj_match:
            task.objective = obj_match.group(1).strip()

        # Citation
        cit_match = re.search(r"\*\*Citation:\*\*\s*(.+)", section)
        if cit_match:
            task.citation = cit_match.group(1).strip()

        # Acceptance Criteria
        ac_match = re.search(
            r"\*\*Acceptance Criteria:\*\*\s*\n(.*?)(?=\n\*\*|\n---|\Z)",
            section,
            re.DOTALL,
        )
        if ac_match:
            task.acceptance_criteria = re.findall(
                r"- \[[ x]\] (.+)", ac_match.group(1)
            )

        # Scope
        scope_match = re.search(
            r"\*\*Scope:\*\*\s*\n(.*?)(?=\n\*\*|\n---|\Z)",
            section,
            re.DOTALL,
        )
        if scope_match:
            scope_text = scope_match.group(1)
            task.scope_create = re.findall(
                r"- (?:Create|Add):\s*`([^`]+)`", scope_text
            )
            task.scope_modify = re.findall(
                r"- (?:Modify|Update|Change):\s*`([^`]+)`", scope_text
            )

        # Dependencies
        dep_match = re.search(
            r"\*\*Dependencies:\*\*\s*(.*?)(?=\n\*\*|\n---|\Z)",
            section,
            re.DOTALL,
        )
        if dep_match:
            dep_text = dep_match.group(1).strip()
            if dep_text.lower() not in ("none", "-", ""):
                task.dependencies = re.findall(r"([A-Z]\d+)", dep_text)

        # Labels
        label_match = re.search(r"\*\*Labels:\*\*\s*(.+)", section)
        if label_match:
            label_text = label_match.group(1).strip()
            task.labels = [
                l.strip().strip("`") for l in label_text.split(",")
            ]
            # Extract project from labels
            for label in task.labels:
                if label.startswith("project:"):
                    task.project = label.split(":")[1]
                    break

        tasks.append(task)

    return tasks


# ---------------------------------------------------------------------------
# ID mapping
# ---------------------------------------------------------------------------


def build_id_mapping(
    tasks: list[ParsedTask], epic_number: int, start_id: int
) -> dict[str, int]:
    """Map plan IDs (A1, B2) to GitHub-style task IDs (71, 72, ...).

    When start_id is provided, tasks are numbered sequentially from that value.
    """
    mapping: dict[str, int] = {}
    current_id = start_id
    for task in tasks:
        mapping[task.task_id] = current_id
        current_id += 1
    return mapping


# ---------------------------------------------------------------------------
# Task file writer
# ---------------------------------------------------------------------------


def write_task_file(
    task: ParsedTask,
    task_number: int,
    epic_number: int,
    id_map: dict[str, int],
    output_dir: Path,
    *,
    preserve_state: bool = True,
) -> Path:
    """Write a single .tasks/ task file."""
    task_path = output_dir / f"T{task_number}.md"

    # Preserve existing state if file exists
    local_state = "pending"
    if preserve_state and task_path.exists():
        existing = task_path.read_text()
        state_match = re.search(
            r"\|\s*State\s*\|\s*(\w+)\s*\|", existing, re.IGNORECASE
        )
        if state_match:
            local_state = state_match.group(1).strip().lower()

    # Resolve dependencies to task numbers
    blocked_by_nums = [id_map[dep] for dep in task.dependencies if dep in id_map]
    blocked_by = ", ".join(f"T{n}" for n in blocked_by_nums) or "None"

    # Format acceptance criteria
    criteria = "\n".join(f"- [ ] {c}" for c in task.acceptance_criteria)
    if not criteria:
        criteria = "- [ ] TODO: Add acceptance criteria"

    # Format scope
    scope_lines: list[str] = []
    if task.scope_create:
        scope_lines.append("**Create:**")
        scope_lines.extend(f"- `{f}`" for f in task.scope_create)
    if task.scope_modify:
        if scope_lines:
            scope_lines.append("")
        scope_lines.append("**Modify:**")
        scope_lines.extend(f"- `{f}`" for f in task.scope_modify)
    scope = "\n".join(scope_lines) if scope_lines else "**TODO:** Add file paths"

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    content = f"""# T{task_number}: {task.title}

> Epic: E{epic_number} | Materialised: {now}

## Status

| Field | Value |
|-------|-------|
| State | {local_state} |
| Phase | - |
| Project | {task.project or "-"} |
| Blocked By | {blocked_by} |
| Locked At | - |

## Objective

{task.objective or "See task title."}

## Acceptance Criteria

{criteria}

## Scope

{scope}

**Forbidden (test immutability):**
- `**/*.test.ts`
- `**/*.test.tsx`
- `**/*.test.py`

## Validation

```bash
just tdd-green T{task_number}
python scripts/snapshot_tests.py verify T{task_number}
```

## Done When

1. All acceptance criteria checked
2. All validation commands pass
3. State updated to `complete`

---

## Outputs

- Files created:
- Files modified:
- Notes:
"""
    task_path.write_text(content)
    return task_path


def write_index(
    tasks: list[ParsedTask],
    id_map: dict[str, int],
    epic_number: int,
    epic_dir: Path,
    epic_title: str,
) -> None:
    """Write/update index.md for the epic."""
    # Build dependency graph
    graph_lines: list[str] = []
    for task in tasks:
        num = id_map[task.task_id]
        if task.dependencies:
            dep_nums = [id_map[d] for d in task.dependencies if d in id_map]
            deps = ", ".join(f"T{n}" for n in dep_nums)
            graph_lines.append(f"{deps} -> T{num}")
        else:
            graph_lines.append(f"T{num} (unblocked)")

    # Build status table
    rows: list[str] = []
    for task in tasks:
        num = id_map[task.task_id]
        blocked = (
            ", ".join(f"T{id_map[d]}" for d in task.dependencies if d in id_map)
            or "-"
        )
        rows.append(
            f"| T{num} | {task.title[:40]} | pending | {task.project or '-'} | {blocked} |"
        )

    content = f"""# E{epic_number}: {epic_title}

## Dependency Graph

```
{chr(10).join(graph_lines)}
```

## Task Status

| Task | Title | State | Project | Blocked By |
|------|-------|-------|---------|------------|
{chr(10).join(rows)}

## Commands

```bash
python scripts/run_epic.py run {epic_number}   # Run TDD state machine
python scripts/run_epic.py status {epic_number} # Check status
```
"""
    index_path = epic_dir / "index.md"
    index_path.write_text(content)


def write_created_json(
    tasks: list[ParsedTask],
    id_map: dict[str, int],
    epic_number: int,
    output_path: Path,
) -> None:
    """Write created.json mapping plan IDs to task numbers."""
    task_entries = []
    for task in tasks:
        num = id_map[task.task_id]
        dep_nums = [id_map[d] for d in task.dependencies if d in id_map]
        task_entries.append(
            {
                "plan_id": task.task_id,
                "task_number": num,
                "title": task.title,
                "project": task.project or None,
                "blocked_by": dep_nums,
            }
        )

    data = {
        "epic_number": epic_number,
        "materialised_at": datetime.now(timezone.utc).isoformat(),
        "source": "tasks_from_plan.py",
        "tasks": task_entries,
    }

    output_path.write_text(json.dumps(data, indent=2) + "\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def find_slug(epic_number: int) -> str | None:
    """Try to find the planning slug for an epic by scanning planning dirs."""
    if not PLANNING_DIR.exists():
        return None
    for d in PLANNING_DIR.iterdir():
        if not d.is_dir():
            continue
        tasks_md = d / "TASKS.md"
        if tasks_md.exists():
            # Check if any reference to this epic number
            content = tasks_md.read_text(errors="replace")[:500]
            if f"#{epic_number}" in content or f"E{epic_number}" in content:
                return d.name
    return None


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Materialise TASKS.md into .tasks/ directory files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python scripts/tasks_from_plan.py 70 --slug video-bc\n"
            "  python scripts/tasks_from_plan.py 33 --slug phase-4-web-app\n"
            "  python scripts/tasks_from_plan.py 33 --slug phase-4-web-app --dry-run\n"
        ),
    )
    parser.add_argument("epic", type=int, help="Epic number")
    parser.add_argument(
        "--slug",
        help="Planning directory slug (auto-detected if omitted)",
    )
    parser.add_argument(
        "--start-id",
        type=int,
        help="Starting task number (default: epic_number + 1)",
    )
    parser.add_argument(
        "--epic-title",
        default="",
        help="Epic title for index.md (default: derived from TASKS.md heading)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be written without writing files",
    )

    args = parser.parse_args()

    # Find slug
    slug = args.slug
    if not slug:
        slug = find_slug(args.epic)
        if not slug:
            print(
                f"Error: Could not auto-detect slug for epic #{args.epic}. "
                f"Use --slug to specify.",
                file=sys.stderr,
            )
            sys.exit(1)

    # Read TASKS.md
    planning_dir = PLANNING_DIR / slug
    tasks_md_path = planning_dir / "TASKS.md"

    if not tasks_md_path.exists():
        print(f"Error: {tasks_md_path} not found", file=sys.stderr)
        sys.exit(1)

    content = tasks_md_path.read_text()

    # Parse tasks
    tasks = parse_tasks_md(content)
    if not tasks:
        print(f"Error: No tasks found in {tasks_md_path}", file=sys.stderr)
        sys.exit(1)

    # Derive epic title from TASKS.md heading if not provided
    epic_title = args.epic_title
    if not epic_title:
        title_match = re.search(r"^# .+?:\s*(.+)$", content, re.MULTILINE)
        epic_title = title_match.group(1).strip() if title_match else f"Epic {args.epic}"

    # Build ID mapping
    start_id = args.start_id or (args.epic + 1)
    id_map = build_id_mapping(tasks, args.epic, start_id)

    print(f"Parsed {len(tasks)} tasks from {tasks_md_path.relative_to(PROJECT_ROOT)}")
    print(f"ID mapping: {', '.join(f'{k}->T{v}' for k, v in id_map.items())}")
    print()

    if args.dry_run:
        for task in tasks:
            num = id_map[task.task_id]
            deps = ", ".join(f"T{id_map[d]}" for d in task.dependencies if d in id_map) or "none"
            ac_count = len(task.acceptance_criteria)
            scope_count = len(task.scope_create) + len(task.scope_modify)
            print(f"  T{num}: {task.title}")
            print(f"    AC: {ac_count}, Scope: {scope_count} files, Deps: {deps}")
        print()
        print("[dry-run] No files written.")
        return

    # Create output directories
    epic_dir = TASKS_BASE / f"E{args.epic}"
    tasks_dir = epic_dir / "tasks"
    for d in [tasks_dir, epic_dir / "snapshots", epic_dir / "logs" / "errors"]:
        d.mkdir(parents=True, exist_ok=True)

    # Write task files
    for task in tasks:
        num = id_map[task.task_id]
        path = write_task_file(task, num, args.epic, id_map, tasks_dir)
        print(f"  Wrote: {path.relative_to(PROJECT_ROOT)}")

    # Write index
    write_index(tasks, id_map, args.epic, epic_dir, epic_title)
    print(f"  Wrote: {(epic_dir / 'index.md').relative_to(PROJECT_ROOT)}")

    # Write created.json
    created_path = planning_dir / "created.json"
    write_created_json(tasks, id_map, args.epic, created_path)
    print(f"  Wrote: {created_path.relative_to(PROJECT_ROOT)}")

    print()
    print(f"Materialised {len(tasks)} tasks for E{args.epic}")
    print(f"  Tasks dir: {tasks_dir.relative_to(PROJECT_ROOT)}")
    print(f"  Next: python scripts/validate_tasks.py {args.epic}")


if __name__ == "__main__":
    main()
