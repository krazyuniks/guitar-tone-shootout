#!/usr/bin/env python3
"""
Sync GitHub epic to .tasks/ with structure validation.

Usage:
    python scripts/gh_tasks_sync.py owner/repo 42
    python scripts/gh_tasks_sync.py owner/repo 42 --validate  # Warn on sparse issues
"""

import json
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional


class WorkspaceProject(str, Enum):
    """UV workspace project members. Only WEBAPP needs browser MCP."""
    CORE = "core"
    AUDIO = "audio"
    T3K = "t3k"
    WEBAPP = "webapp"
    WORKER = "worker"
    SCHEDULER = "scheduler"

    @classmethod
    def from_label(cls, label: str) -> Optional["WorkspaceProject"]:
        """Parse project from GitHub label (e.g., 'project:webapp')."""
        if label.startswith("project:"):
            try:
                return cls(label.split(":")[1])
            except ValueError:
                return None
        return None

    @property
    def needs_mcp(self) -> bool:
        """Only webapp needs browser automation."""
        return self == WorkspaceProject.WEBAPP

try:
    from ghapi.all import GhApi
except ImportError:
    print("Install ghapi: pip install ghapi")
    sys.exit(1)


@dataclass
class ValidationResult:
    issue_number: int
    title: str
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    
    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0


@dataclass
class Issue:
    number: int
    title: str
    body: str
    state: str
    labels: list[str]
    blocked_by: list[int] = field(default_factory=list)
    project: Optional[WorkspaceProject] = None

    # Parsed sections
    objective: str = ""
    acceptance_criteria: list[str] = field(default_factory=list)
    scope_create: list[str] = field(default_factory=list)
    scope_modify: list[str] = field(default_factory=list)
    technical_notes: str = ""

    def __post_init__(self):
        """Extract project from labels if not set."""
        if self.project is None:
            for label in self.labels:
                proj = WorkspaceProject.from_label(label)
                if proj:
                    self.project = proj
                    break


def parse_issue_body(issue: Issue) -> Issue:
    """Parse structured sections from issue body."""
    body = issue.body or ""
    
    # Extract Objective
    match = re.search(r"## Objective\s*\n(.*?)(?=\n##|\Z)", body, re.DOTALL | re.I)
    if match:
        issue.objective = match.group(1).strip()
    
    # Extract Acceptance Criteria
    match = re.search(r"## Acceptance Criteria\s*\n(.*?)(?=\n##|\Z)", body, re.DOTALL | re.I)
    if match:
        criteria_text = match.group(1)
        issue.acceptance_criteria = re.findall(r"- \[[ x]\] (.+)", criteria_text)
    
    # Extract Scope
    match = re.search(r"## Scope\s*\n(.*?)(?=\n##|\Z)", body, re.DOTALL | re.I)
    if match:
        scope_text = match.group(1)
        
        # Create section
        create_match = re.search(r"\*\*Create:?\*\*\s*\n(.*?)(?=\*\*|\Z)", scope_text, re.DOTALL)
        if create_match:
            issue.scope_create = re.findall(r"`([^`]+)`", create_match.group(1))
        
        # Modify section
        modify_match = re.search(r"\*\*Modify:?\*\*\s*\n(.*?)(?=\*\*|\Z)", scope_text, re.DOTALL)
        if modify_match:
            issue.scope_modify = re.findall(r"`([^`]+)`", modify_match.group(1))
    
    # Extract Dependencies
    for pattern in [r"[Bb]locked by:?\s*#(\d+)", r"[Dd]epends on:?\s*#(\d+)"]:
        for match in re.finditer(pattern, body):
            issue.blocked_by.append(int(match.group(1)))
    
    # Technical Notes
    match = re.search(r"## Technical Notes\s*\n(.*?)(?=\n##|\Z)", body, re.DOTALL | re.I)
    if match:
        issue.technical_notes = match.group(1).strip()
    
    return issue


def validate_issue(issue: Issue) -> ValidationResult:
    """Validate issue has required structure."""
    result = ValidationResult(issue.number, issue.title)
    
    # Required: Objective
    if not issue.objective:
        result.errors.append("Missing ## Objective section")
    elif len(issue.objective) < 20:
        result.warnings.append("Objective is very short (< 20 chars)")
    
    # Required: Acceptance Criteria
    if not issue.acceptance_criteria:
        result.errors.append("Missing ## Acceptance Criteria section")
    elif len(issue.acceptance_criteria) < 2:
        result.warnings.append("Only 1 acceptance criterion (recommend 3-5)")
    
    # Required: Scope
    if not issue.scope_create and not issue.scope_modify:
        result.errors.append("Missing ## Scope section with file paths")
    
    # Warning: No technical notes (optional but helpful)
    if not issue.technical_notes:
        result.warnings.append("No ## Technical Notes (optional)")
    
    return result


class GitHubEpicSync:
    def __init__(self, owner: str, repo: str, token: str = None):
        self.owner = owner
        self.repo = repo
        self.api = GhApi(owner=owner, repo=repo, token=token or os.getenv("GITHUB_TOKEN"))

    def fetch_epic(self, epic_number: int) -> tuple[Issue, list[Issue]]:
        epic_data = self.api.issues.get(epic_number)
        epic = self._to_issue(epic_data)
        
        children = []
        for match in re.finditer(r"- \[[ x]\] #(\d+)", epic.body):
            try:
                child_data = self.api.issues.get(int(match.group(1)))
                child = self._to_issue(child_data)
                child = parse_issue_body(child)
                children.append(child)
            except Exception as e:
                print(f"Warning: Could not fetch #{match.group(1)}: {e}")
        
        return epic, children

    def _to_issue(self, data) -> Issue:
        return Issue(
            number=data.number,
            title=data.title,
            body=data.body or "",
            state=data.state,
            labels=[l.name for l in (data.labels or [])],
        )


class TasksWriter:
    def __init__(self, base_path: Path, owner: str, repo: str):
        self.base_path = base_path
        self.owner = owner
        self.repo = repo

    def write_epic(self, epic: Issue, children: list[Issue]):
        epic_dir = self.base_path / f"E{epic.number}"
        tasks_dir = epic_dir / "tasks"
        
        for d in [tasks_dir, epic_dir / "snapshots", 
                  epic_dir / "logs/orchestrator", 
                  epic_dir / "logs/tasks", 
                  epic_dir / "logs/errors"]:
            d.mkdir(parents=True, exist_ok=True)

        self._write_index(epic_dir / "index.md", epic, children)
        
        for child in children:
            self._write_task_file(tasks_dir / f"T{child.number}.md", child, epic.number)

    def _write_task_file(self, path: Path, task: Issue, epic_number: int):
        """Generate task file from parsed issue."""
        
        blocked_by = ", ".join(f"T{n}" for n in task.blocked_by) or "None"
        
        # Format acceptance criteria
        criteria = "\n".join(f"- [ ] {c}" for c in task.acceptance_criteria)
        if not criteria:
            criteria = "- [ ] TODO: Add acceptance criteria"
        
        # Format scope
        scope_lines = []
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
        objective = task.objective or task.body[:500] or "See GitHub issue"
        
        # Technical notes
        notes = f"\n## Technical Notes\n\n{task.technical_notes}" if task.technical_notes else ""
        
        content = f"""# T{task.number}: {task.title}

> GitHub: https://github.com/{self.owner}/{self.repo}/issues/{task.number}
> Epic: E{epic_number} | Synced: {self._now()}

## Status

| Field | Value |
|-------|-------|
| State | {"complete" if task.state == "closed" else "pending"} |
| Phase | - |
| Project | {task.project.value if task.project else "-"} |
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
just tdd-green E{epic_number}-T{task.number}
python scripts/snapshot_tests.py verify E{epic_number}-T{task.number}
just e2e
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

    def _write_index(self, path: Path, epic: Issue, children: list[Issue]):
        graph_lines = []
        for c in children:
            if c.blocked_by:
                deps = ", ".join(f"T{n}" for n in c.blocked_by)
                graph_lines.append(f"{deps} → T{c.number}")
            else:
                graph_lines.append(f"T{c.number} (unblocked)")

        rows = []
        for c in children:
            state = "complete" if c.state == "closed" else "pending"
            blocked = ", ".join(f"T{n}" for n in c.blocked_by) or "-"
            rows.append(f"| T{c.number} | {c.title[:35]} | {state} | - | {blocked} |")

        content = f"""# E{epic.number}: {epic.title}

> GitHub: https://github.com/{self.owner}/{self.repo}/issues/{epic.number}

## Dependency Graph

```
{chr(10).join(graph_lines)}
```

## Task Status

| Task | Title | State | Phase | Blocked By |
|------|-------|-------|-------|------------|
{chr(10).join(rows)}

## Commands

```bash
just epic-start {epic.number}   # Begin orchestration
just epic-status {epic.number}  # Check status
just debug E{epic.number}       # Debug issues
```
"""
        path.write_text(content)

    def _now(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("repo", help="owner/repo")
    parser.add_argument("epic", type=int, help="Epic issue number")
    parser.add_argument("--out", default=".tasks/projects")
    parser.add_argument("--validate", action="store_true", 
                        help="Validate issue structure and warn on problems")
    args = parser.parse_args()
    
    owner, repo = args.repo.split("/")
    syncer = GitHubEpicSync(owner, repo)
    epic, children = syncer.fetch_epic(args.epic)
    
    # Validation
    if args.validate:
        print(f"Validating {len(children)} tasks...\n")
        has_errors = False
        
        for child in children:
            result = validate_issue(child)
            
            if result.errors or result.warnings:
                print(f"#{child.number}: {child.title}")
                for err in result.errors:
                    print(f"  ❌ {err}")
                    has_errors = True
                for warn in result.warnings:
                    print(f"  ⚠️  {warn}")
                print()
        
        if has_errors:
            print("Some issues have missing required sections.")
            print("Run `just plan {epic}` to enrich them, or fix manually.")
            print()
    
    # Write files
    out_path = Path(args.out) / repo / "epics"
    writer = TasksWriter(out_path, owner, repo)
    writer.write_epic(epic, children)
    
    print(f"✓ Synced E{args.epic} with {len(children)} tasks to {out_path}/E{args.epic}/")


if __name__ == "__main__":
    main()
