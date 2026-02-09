#!/usr/bin/env python3
"""
Pre-flight validation for epic task files.

Checks that all tasks in .tasks/projects/guitar-tone-shootout/epics/E{n}/tasks/
have the required structure for run_epic.py to execute.

Usage:
    python scripts/validate_tasks.py 70
    python scripts/validate_tasks.py 70 --strict   # Fail on warnings too

Exit codes:
    0 = all checks pass
    1 = validation errors found
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TASKS_BASE = PROJECT_ROOT / ".tasks" / "projects" / "guitar-tone-shootout" / "epics"

VALID_STATES = {"pending", "locked", "validating", "complete"}
VALID_PROJECTS = {"core", "audio", "t3k", "webapp", "worker", "scheduler", "video"}


@dataclass
class TaskInfo:
    """Parsed task metadata for validation."""

    task_id: int
    title: str
    state: str
    project: str
    blocked_by: list[int]
    has_real_ac: bool  # not just "TODO"
    ac_count: int
    has_real_scope: bool  # not just "TODO"
    scope_count: int
    scope_create_count: int
    scope_modify_count: int
    file_path: Path


@dataclass
class ValidationResult:
    """Result of validating a single task."""

    task_id: int
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0


def parse_task_for_validation(path: Path) -> TaskInfo:
    """Parse a task file and extract validation-relevant fields."""
    content = path.read_text()

    # Task ID from filename
    match = re.match(r"T(\d+)\.md", path.name)
    task_id = int(match.group(1)) if match else 0

    # Title
    title_match = re.search(r"^# T\d+:\s*(.+)$", content, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else path.stem

    # State
    state = "pending"
    state_match = re.search(r"\|\s*State\s*\|\s*(\w+)\s*\|", content, re.IGNORECASE)
    if state_match:
        state = state_match.group(1).strip().lower()

    # Project
    project = ""
    proj_match = re.search(r"\|\s*Project\s*\|\s*([^|]+)\|", content, re.IGNORECASE)
    if proj_match:
        proj_val = proj_match.group(1).strip().lower()
        if proj_val != "-":
            project = proj_val

    # Blocked By
    blocked_by: list[int] = []
    blocked_match = re.search(r"\|\s*Blocked By\s*\|\s*([^|]+)\|", content, re.IGNORECASE)
    if blocked_match:
        blocked_str = blocked_match.group(1).strip()
        if blocked_str and blocked_str.lower() not in ("none", "-"):
            blocked_by = [int(x) for x in re.findall(r"T(\d+)", blocked_str)]

    # Acceptance Criteria
    ac_section = re.search(
        r"## Acceptance Criteria\s*\n(.*?)(?=\n##|\Z)",
        content,
        re.DOTALL,
    )
    ac_items: list[str] = []
    has_real_ac = False
    if ac_section:
        ac_items = re.findall(r"- \[[ x]\] (.+)", ac_section.group(1))
        has_real_ac = bool(ac_items) and not all(
            "TODO" in item for item in ac_items
        )

    # Scope
    scope_section = re.search(
        r"## Scope\s*\n(.*?)(?=\n##|\Z)",
        content,
        re.DOTALL,
    )
    scope_files: list[str] = []
    has_real_scope = False
    scope_create_count = 0
    scope_modify_count = 0
    if scope_section:
        scope_text = scope_section.group(1)
        scope_files = re.findall(r"`([^`]+)`", scope_text)
        # Filter out glob patterns used in "Forbidden" section
        scope_files = [
            f for f in scope_files
            if not f.startswith("**") and not f.endswith("*")
        ]
        has_real_scope = bool(scope_files) and "TODO" not in scope_text.split("**Forbidden")[0]

        # Count Create vs Modify files (before Forbidden section)
        allowed_scope = scope_text.split("**Forbidden")[0]
        # Match lines like "- Create: `path`" or "- **Create:** `path`"
        scope_create_count = len(re.findall(
            r"[-*]\s*\**Create\**:?\s*`[^`]+`", allowed_scope, re.IGNORECASE,
        ))
        scope_modify_count = len(re.findall(
            r"[-*]\s*\**Modify\**:?\s*`[^`]+`", allowed_scope, re.IGNORECASE,
        ))

    return TaskInfo(
        task_id=task_id,
        title=title,
        state=state,
        project=project,
        blocked_by=blocked_by,
        has_real_ac=has_real_ac,
        ac_count=len(ac_items),
        has_real_scope=has_real_scope,
        scope_count=len(scope_files),
        scope_create_count=scope_create_count,
        scope_modify_count=scope_modify_count,
        file_path=path,
    )


def validate_task(task: TaskInfo, all_task_ids: set[int]) -> ValidationResult:
    """Validate a single task."""
    result = ValidationResult(task_id=task.task_id)

    # Skip validation for complete tasks
    if task.state == "complete":
        return result

    # AC check
    if not task.has_real_ac:
        result.errors.append("Missing acceptance criteria (has TODO placeholder)")
    elif task.ac_count < 2:
        result.warnings.append(f"Only {task.ac_count} acceptance criterion (recommend 3+)")
    elif task.ac_count > 15:
        result.warnings.append(f"{task.ac_count} acceptance criteria (consider splitting task)")

    # Scope file count check (oversized task detection)
    scope_file_count = task.scope_create_count + task.scope_modify_count
    if scope_file_count > 5:
        result.warnings.append(
            f"{scope_file_count} scope files (recommend splitting: max 3 create + 2 modify)"
        )
    elif task.scope_create_count > 3:
        result.warnings.append(
            f"{task.scope_create_count} files to create (recommend max 3)"
        )

    # Scope check
    if not task.has_real_scope:
        result.errors.append("Missing scope file paths (has TODO placeholder)")

    # State validity
    if task.state not in VALID_STATES:
        result.errors.append(f"Invalid state: '{task.state}'")

    # Dependency references
    for dep_id in task.blocked_by:
        if dep_id not in all_task_ids:
            result.errors.append(f"Blocked by T{dep_id} which does not exist")

    # Self-reference
    if task.task_id in task.blocked_by:
        result.errors.append("Task blocks itself (circular dependency)")

    return result


def detect_circular_deps(tasks: list[TaskInfo]) -> list[str]:
    """Detect circular dependency chains across tasks."""
    errors: list[str] = []
    task_map = {t.task_id: t for t in tasks}

    def visit(task_id: int, path: list[int]) -> None:
        if task_id in path:
            cycle = path[path.index(task_id) :] + [task_id]
            cycle_str = " -> ".join(f"T{t}" for t in cycle)
            errors.append(f"Circular dependency: {cycle_str}")
            return
        task = task_map.get(task_id)
        if task is None:
            return
        for dep_id in task.blocked_by:
            visit(dep_id, path + [task_id])

    for task in tasks:
        visit(task.task_id, [])

    # Deduplicate (cycles detected from different starting points)
    return list(dict.fromkeys(errors))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate epic task files for TDD execution",
    )
    parser.add_argument("epic", type=int, help="Epic number")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat warnings as errors",
    )

    args = parser.parse_args()

    epic_dir = TASKS_BASE / f"E{args.epic}"
    tasks_dir = epic_dir / "tasks"

    if not tasks_dir.exists():
        print(f"Error: {tasks_dir} not found", file=sys.stderr)
        sys.exit(1)

    # Parse all tasks
    task_files = sorted(tasks_dir.glob("T*.md"))
    if not task_files:
        print(f"Error: No task files found in {tasks_dir}", file=sys.stderr)
        sys.exit(1)

    tasks = [parse_task_for_validation(f) for f in task_files]
    all_ids = {t.task_id for t in tasks}

    print(f"Validating E{args.epic}: {len(tasks)} tasks")
    print()

    # Validate each task
    results = [validate_task(t, all_ids) for t in tasks]

    # Check for circular dependencies
    cycle_errors = detect_circular_deps(tasks)

    # Report
    total_errors = 0
    total_warnings = 0

    for task, result in zip(tasks, results):
        if not result.errors and not result.warnings:
            continue

        state_badge = f"[{task.state}]"
        print(f"T{task.task_id}: {task.title[:50]} {state_badge}")
        for err in result.errors:
            print(f"  ERROR: {err}")
            total_errors += 1
        for warn in result.warnings:
            print(f"  WARN:  {warn}")
            total_warnings += 1
        print()

    if cycle_errors:
        print("Dependency cycles:")
        for err in cycle_errors:
            print(f"  ERROR: {err}")
            total_errors += len(cycle_errors)
        print()

    # Summary
    complete = sum(1 for t in tasks if t.state == "complete")
    pending = len(tasks) - complete

    print("=" * 50)
    print(f"Tasks: {len(tasks)} total, {complete} complete, {pending} pending")
    print(f"Errors: {total_errors}, Warnings: {total_warnings}")

    if total_errors == 0 and (not args.strict or total_warnings == 0):
        print("PASS: All tasks valid")
        sys.exit(0)
    else:
        if args.strict and total_warnings > 0:
            print("FAIL: Strict mode — warnings treated as errors")
        else:
            print("FAIL: Fix errors before running epic")
        print()
        print("Fix with: /epic fix {epic}")
        sys.exit(1)


if __name__ == "__main__":
    main()
