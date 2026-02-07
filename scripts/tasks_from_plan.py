#!/usr/bin/env python3
"""
Create .tasks/ files from a TASKS.md plan — no GitHub issues, no AI agent.

Deterministic parser: reads TASKS.md, writes task files + index + created.json.
Replaces the epic-github-creator agent for local-only task materialisation.

Usage:
    python scripts/tasks_from_plan.py .planning/epics/my-feature/TASKS.md 33
    python scripts/tasks_from_plan.py .planning/epics/my-feature/TASKS.md 33 --dry-run
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
TASKS_BASE = PROJECT_ROOT / ".tasks" / "projects" / "guitar-tone-shootout" / "epics"


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class ParsedTask:
    """A task parsed from TASKS.md."""

    plan_id: str  # e.g. "A1", "B2"
    title: str
    objective: str = ""
    acceptance_criteria: list[str] = field(default_factory=list)
    scope_create: list[str] = field(default_factory=list)
    scope_modify: list[str] = field(default_factory=list)
    blocked_by_plan_ids: list[str] = field(default_factory=list)
    labels: list[str] = field(default_factory=list)
    technical_notes: str = ""
    local_id: int = 0  # assigned after parsing (T1, T2, ...)
    blocked_by_local: list[int] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


def parse_tasks_md(content: str) -> list[ParsedTask]:
    """Parse TASKS.md into a list of ParsedTask objects.

    Expects task sections starting with: ### {ID}: {Title}
    """
    tasks: list[ParsedTask] = []

    # Split into task sections: ### A1: Title
    # Pattern: ### followed by an alphanumeric ID (letter+digits), colon, title
    task_pattern = re.compile(r"^### ([A-Z]\d+):\s*(.+)$", re.MULTILINE)
    matches = list(task_pattern.finditer(content))

    for i, match in enumerate(matches):
        plan_id = match.group(1)
        title = match.group(2).strip()

        # Extract section content (until next ### or end)
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        section = content[start:end]

        task = ParsedTask(plan_id=plan_id, title=title)

        # Extract Objective
        obj_match = re.search(
            r"\*\*Objective:\*\*\s*(.+?)(?=\n\n|\n\*\*)", section, re.DOTALL
        )
        if obj_match:
            task.objective = obj_match.group(1).strip()

        # Extract Acceptance Criteria
        ac_match = re.search(
            r"\*\*Acceptance Criteria:\*\*\s*\n(.*?)(?=\n\*\*|\n---|\Z)",
            section,
            re.DOTALL,
        )
        if ac_match:
            task.acceptance_criteria = re.findall(
                r"- \[[ x]\] (.+)", ac_match.group(1)
            )

        # Extract Scope
        scope_match = re.search(
            r"\*\*Scope:\*\*\s*\n(.*?)(?=\n\*\*|\n---|\Z)", section, re.DOTALL
        )
        if scope_match:
            scope_text = scope_match.group(1)
            # Create files
            create_match = re.search(
                r"- Create:\s*(.*?)(?=- (?:Modify|Run):|$)", scope_text, re.DOTALL
            )
            if create_match:
                task.scope_create = re.findall(r"`([^`]+)`", create_match.group(1))
            # Modify files
            modify_match = re.search(
                r"- Modify:\s*(.*?)(?=- (?:Create|Run):|$)", scope_text, re.DOTALL
            )
            if modify_match:
                task.scope_modify = re.findall(r"`([^`]+)`", modify_match.group(1))

        # Extract Dependencies
        dep_match = re.search(
            r"\*\*Dependencies:\*\*\s*(.+?)(?:\n\n|\n\*\*|\Z)", section, re.DOTALL
        )
        if dep_match:
            dep_text = dep_match.group(1).strip()
            if dep_text.lower() != "none":
                # Match plan IDs like A1, B2, C1 — both "Blocked by A1" and "Blocked by A1, B2"
                task.blocked_by_plan_ids = re.findall(r"([A-Z]\d+)", dep_text)

        # Extract Labels
        label_match = re.search(
            r"\*\*Labels:\*\*\s*(.+?)(?:\n\n|\n\*\*|\Z)", section, re.DOTALL
        )
        if label_match:
            label_text = label_match.group(1).strip()
            task.labels = [
                lbl.strip().strip("`")
                for lbl in label_text.split(",")
                if lbl.strip()
            ]

        # Extract Technical Notes (as Citation line)
        citation_match = re.search(r"\*\*Citation:\*\*\s*(.+)", section)
        if citation_match:
            task.technical_notes = citation_match.group(1).strip()

        tasks.append(task)

    return tasks


def assign_local_ids(tasks: list[ParsedTask]) -> dict[str, int]:
    """Assign sequential local IDs (T1, T2, ...) and resolve dependencies.

    Returns plan_id → local_id mapping.
    """
    mapping: dict[str, int] = {}
    for i, task in enumerate(tasks, start=1):
        task.local_id = i
        mapping[task.plan_id] = i

    # Resolve dependencies from plan IDs to local IDs
    for task in tasks:
        task.blocked_by_local = [
            mapping[pid]
            for pid in task.blocked_by_plan_ids
            if pid in mapping
        ]

    return mapping


# ---------------------------------------------------------------------------
# Writer (reuses format from gh_tasks_sync.py TasksWriter)
# ---------------------------------------------------------------------------


def write_task_file(
    path: Path,
    task: ParsedTask,
    epic_number: int,
) -> None:
    """Write a single task file in .tasks/ format."""
    # Preserve local state if file already exists
    local_state = None
    if path.exists():
        existing = path.read_text()
        state_match = re.search(
            r"\|\s*State\s*\|\s*(\w+)\s*\|", existing, re.IGNORECASE
        )
        if state_match:
            local_state = state_match.group(1).strip().lower()

    blocked_by = (
        ", ".join(f"T{n}" for n in task.blocked_by_local)
        if task.blocked_by_local
        else "None"
    )

    # Determine project from labels
    project = "-"
    for label in task.labels:
        if label.startswith("project:"):
            project = label.split(":")[1]
            break

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

    # Objective
    objective = task.objective or "See TASKS.md"

    # Technical notes
    notes = (
        f"\n## Technical Notes\n\n- {task.technical_notes}"
        if task.technical_notes
        else ""
    )

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    state = local_state or "pending"

    content = f"""# T{task.local_id}: {task.plan_id} - {task.title}

> Epic: E{epic_number} | Plan ID: {task.plan_id} | Generated: {now}

## Status

| Field | Value |
|-------|-------|
| State | {state} |
| Phase | - |
| Project | {project} |
| Blocked By | {blocked_by} |
| Locked At | - |

## Objective

{objective}

## Acceptance Criteria

{criteria}

## Scope

{scope}

**Forbidden (test immutability):**
- `**/*.test.ts`
- `**/*.test.tsx`
- `**/*.test.py`
{notes}

## Validation

```bash
just tdd-green T{task.local_id}
just tdd-complete T{task.local_id}
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
    path.write_text(content)


def write_index(
    path: Path,
    epic_number: int,
    epic_title: str,
    tasks: list[ParsedTask],
) -> None:
    """Write index.md with dependency graph and status table."""
    # Build dependency graph
    graph_lines: list[str] = []
    for t in tasks:
        if t.blocked_by_local:
            deps = ", ".join(f"T{n}" for n in t.blocked_by_local)
            graph_lines.append(f"{deps} → T{t.local_id}")
        else:
            graph_lines.append(f"T{t.local_id} (unblocked)")

    # Build status table
    rows: list[str] = []
    for t in tasks:
        project = "-"
        for label in t.labels:
            if label.startswith("project:"):
                project = label.split(":")[1]
                break
        blocked = (
            ", ".join(f"T{n}" for n in t.blocked_by_local)
            if t.blocked_by_local
            else "-"
        )
        title_display = f"{t.plan_id} - {t.title}"[:40]
        rows.append(
            f"| T{t.local_id} | {title_display} | pending | {project} | {blocked} |"
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
just epic-status {epic_number}                  # Check status
just debug E{epic_number}                       # Debug issues
```
"""
    path.write_text(content)


def write_created_json(
    path: Path,
    epic_number: int,
    epic_title: str,
    tasks: list[ParsedTask],
) -> None:
    """Write created.json with local-only task mapping."""
    data = {
        "epic": {
            "number": epic_number,
            "title": epic_title,
        },
        "tasks": [
            {
                "id": t.plan_id,
                "local_id": t.local_id,
                "title": f"{t.plan_id} - {t.title}",
                "labels": t.labels,
                "blocked_by_ids": t.blocked_by_plan_ids,
                "blocked_by_local": t.blocked_by_local,
            }
            for t in tasks
        ],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    path.write_text(json.dumps(data, indent=2) + "\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def materialise_tasks(
    tasks_md_path: Path,
    epic_number: int,
    *,
    dry_run: bool = False,
    epic_title: str | None = None,
) -> None:
    """Parse TASKS.md and write .tasks/ files."""
    if not tasks_md_path.exists():
        print(f"Error: {tasks_md_path} not found", file=sys.stderr)
        sys.exit(1)

    content = tasks_md_path.read_text()
    tasks = parse_tasks_md(content)

    if not tasks:
        print("Error: No tasks found in TASKS.md", file=sys.stderr)
        sys.exit(1)

    mapping = assign_local_ids(tasks)

    # Derive epic title from TASKS.md heading or fallback
    if not epic_title:
        title_match = re.search(r"^# .+:\s*(.+)$", content, re.MULTILINE)
        epic_title = title_match.group(1).strip() if title_match else f"Epic {epic_number}"

    print(f"Parsed {len(tasks)} tasks from {tasks_md_path.name}")
    print(f"Epic: E{epic_number} — {epic_title}")
    print()

    # Show mapping
    for t in tasks:
        deps = (
            " (blocked by " + ", ".join(f"T{d}" for d in t.blocked_by_local) + ")"
            if t.blocked_by_local
            else ""
        )
        print(f"  {t.plan_id} → T{t.local_id}: {t.title}{deps}")

    if dry_run:
        print()
        print("[dry-run] Would write to:")
        epic_dir = TASKS_BASE / f"E{epic_number}"
        print(f"  {epic_dir / 'index.md'}")
        for t in tasks:
            print(f"  {epic_dir / 'tasks' / f'T{t.local_id}.md'}")
        planning_dir = tasks_md_path.parent
        print(f"  {planning_dir / 'created.json'}")
        return

    # Write files
    epic_dir = TASKS_BASE / f"E{epic_number}"
    tasks_dir = epic_dir / "tasks"

    for d in [
        tasks_dir,
        epic_dir / "snapshots",
        epic_dir / "logs" / "orchestrator",
        epic_dir / "logs" / "tasks",
        epic_dir / "logs" / "errors",
    ]:
        d.mkdir(parents=True, exist_ok=True)

    # Write task files
    for task in tasks:
        task_path = tasks_dir / f"T{task.local_id}.md"
        write_task_file(task_path, task, epic_number)
        print(f"  Wrote: {task_path.relative_to(PROJECT_ROOT)}")

    # Write index
    index_path = epic_dir / "index.md"
    write_index(index_path, epic_number, epic_title, tasks)
    print(f"  Wrote: {index_path.relative_to(PROJECT_ROOT)}")

    # Write created.json to planning dir (alongside TASKS.md)
    planning_dir = tasks_md_path.parent
    created_path = planning_dir / "created.json"
    write_created_json(created_path, epic_number, epic_title, tasks)
    print(f"  Wrote: {created_path.relative_to(PROJECT_ROOT)}")

    print()
    print(f"Done. {len(tasks)} tasks materialised to {epic_dir.relative_to(PROJECT_ROOT)}/")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create .tasks/ files from TASKS.md (no GitHub issues)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python scripts/tasks_from_plan.py .planning/epics/my-feature/TASKS.md 33\n"
            "  python scripts/tasks_from_plan.py .planning/epics/my-feature/TASKS.md 33 --dry-run\n"
        ),
    )
    parser.add_argument("tasks_md", type=Path, help="Path to TASKS.md")
    parser.add_argument("epic", type=int, help="Epic issue number")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be written without creating files",
    )
    parser.add_argument(
        "--title",
        type=str,
        default=None,
        help="Override epic title (default: parsed from TASKS.md heading)",
    )

    args = parser.parse_args()

    materialise_tasks(
        tasks_md_path=args.tasks_md,
        epic_number=args.epic,
        dry_run=args.dry_run,
        epic_title=args.title,
    )


if __name__ == "__main__":
    main()
