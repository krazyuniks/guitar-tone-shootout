#!/usr/bin/env python3
"""
Sync GitHub epic to .tasks/ hierarchy.

Usage:
    python scripts/gh_tasks_sync.py owner/repo 42 [--out .tasks/projects/gts/epics]

Requires:
    pip install ghapi pydantic
    gh auth login (or GITHUB_TOKEN env var)
"""

import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

try:
    from ghapi.all import GhApi
except ImportError:
    print("Install ghapi: pip install ghapi")
    exit(1)


@dataclass
class Issue:
    number: int
    title: str
    body: str
    state: str
    labels: list[str]
    assignees: list[str]
    blocked_by: list[int] = field(default_factory=list)
    blocks: list[int] = field(default_factory=list)
    children: list[int] = field(default_factory=list)

    @property
    def task_id(self) -> str:
        return f"T{self.number}"


class GitHubEpicSync:
    def __init__(self, owner: str, repo: str, token: str = None):
        self.owner = owner
        self.repo = repo
        self.api = GhApi(owner=owner, repo=repo, token=token or os.getenv("GITHUB_TOKEN"))

    def fetch_epic(self, epic_number: int) -> tuple[Issue, list[Issue]]:
        """Fetch epic issue and all child issues with relationships."""
        epic_data = self.api.issues.get(epic_number)
        epic = self._parse_issue(epic_data)

        # Get child issues via tasklist parsing
        children = self._fetch_children(epic_number, epic_data.body or "")

        # Resolve dependency relationships for all children
        for child in children:
            child.blocked_by, child.blocks = self._fetch_dependencies(child.number)

        return epic, children

    def _parse_issue(self, data) -> Issue:
        return Issue(
            number=data.number,
            title=data.title,
            body=data.body or "",
            state=data.state,
            labels=[label.name for label in (data.labels or [])],
            assignees=[a.login for a in (data.assignees or [])],
        )

    def _fetch_children(self, epic_number: int, epic_body: str) -> list[Issue]:
        """Fetch child issues from tasklist in epic body."""
        children = []

        # Parse tasklist syntax: - [ ] #43 or - [x] #43
        tasklist_pattern = r"- \[[ x]\] #(\d+)"
        for match in re.finditer(tasklist_pattern, epic_body):
            issue_num = int(match.group(1))
            try:
                issue_data = self.api.issues.get(issue_num)
                children.append(self._parse_issue(issue_data))
            except Exception as e:
                print(f"Warning: Could not fetch issue #{issue_num}: {e}")

        return children

    def _fetch_dependencies(self, issue_number: int) -> tuple[list[int], list[int]]:
        """Parse dependency relationships from issue body."""
        blocked_by = []
        blocks = []

        try:
            issue = self.api.issues.get(issue_number)
            body = issue.body or ""

            # Parse "blocked by #X" or "depends on #X"
            blocked_pattern = r"(?:blocked by|depends on)\s*#(\d+)"
            for match in re.finditer(blocked_pattern, body, re.IGNORECASE):
                blocked_by.append(int(match.group(1)))

            # Parse "blocks #X"
            blocks_pattern = r"blocks\s*#(\d+)"
            for match in re.finditer(blocks_pattern, body, re.IGNORECASE):
                blocks.append(int(match.group(1)))

        except Exception as e:
            print(f"Warning: Could not fetch dependencies for #{issue_number}: {e}")

        return blocked_by, blocks


class TasksWriter:
    def __init__(self, base_path: Path, owner: str = "", repo: str = ""):
        self.base_path = base_path
        self.owner = owner
        self.repo = repo

    def write_epic(self, epic: Issue, children: list[Issue]):
        """Write epic and children to .tasks/ hierarchy."""
        epic_dir = self.base_path / f"E{epic.number}"
        tasks_dir = epic_dir / "tasks"
        snapshots_dir = epic_dir / "snapshots"
        logs_dir = epic_dir / "logs"

        for d in [tasks_dir, snapshots_dir, logs_dir / "orchestrator", logs_dir / "tasks", logs_dir / "errors"]:
            d.mkdir(parents=True, exist_ok=True)

        # Write EPIC.md
        self._write_epic_file(epic_dir / "EPIC.md", epic, children)

        # Write CLAUDE.md
        self._write_claude_file(epic_dir / "CLAUDE.md", epic, children)

        # Write individual task files
        for child in children:
            self._write_task_file(tasks_dir / f"T{child.number}.md", child, epic.number)

        # Write index.md
        self._write_index(epic_dir / "index.md", epic, children)

    def _write_epic_file(self, path: Path, epic: Issue, children: list[Issue]):
        children_list = "\n".join(
            f"- [T{c.number}](tasks/T{c.number}.md): {c.title}" for c in children
        )

        content = f"""# Epic #{epic.number}: {epic.title}

## Source
- GitHub: https://github.com/{self.owner}/{self.repo}/issues/{epic.number}
- Synced: {self._now()}

## Status
- state: {epic.state}
- labels: {', '.join(epic.labels) or 'none'}
- assignees: {', '.join(epic.assignees) or 'unassigned'}

## Description

{epic.body}

## Child Issues

{children_list}
"""
        path.write_text(content)

    def _write_claude_file(self, path: Path, epic: Issue, children: list[Issue]):
        completed = [c for c in children if c.state == "closed"]
        pending = [c for c in children if c.state == "open"]

        content = f"""# Epic E{epic.number}: {epic.title}

## Context
{epic.body[:500] if epic.body else 'No description provided.'}

## Current State
- Total tasks: {len(children)}
- Completed: {len(completed)}
- Pending: {len(pending)}

## Key Files
<!-- Add relevant files as you work -->

## Notes
<!-- Add architecture decisions, learnings, etc. -->
"""
        path.write_text(content)

    def _write_task_file(self, path: Path, task: Issue, epic_number: int):
        blocked_by_refs = [f"T{n}" for n in task.blocked_by]
        blocks_refs = [f"T{n}" for n in task.blocks]

        # Extract acceptance criteria if present
        criteria_yaml = self._extract_criteria(task.body)

        content = f"""# T{task.number}: {task.title}

## Source
- GitHub: https://github.com/{self.owner}/{self.repo}/issues/{task.number}
- Epic: E{epic_number}
- Synced: {self._now()}

## Status
- state: {"complete" if task.state == "closed" else "pending"}
- phase: -
- locked_at: -

## Dependencies
- blocked_by: {json.dumps(blocked_by_refs)}
- blocks: {json.dumps(blocks_refs)}

## Acceptance Criteria

{criteria_yaml}

## Description

{task.body}

## Scope

```yaml
allowed_paths: []
forbidden_paths:
  - "**/*.test.ts"
  - "**/*.test.tsx"
```

## Outputs
- files_created: []
- files_modified: []
- validation_result:
"""
        path.write_text(content)

    def _write_index(self, path: Path, epic: Issue, children: list[Issue]):
        # Build dependency graph
        graph_lines = []
        for child in children:
            if child.blocked_by:
                blockers = ", ".join(f"T{n}" for n in child.blocked_by)
                graph_lines.append(f"{blockers} ──► T{child.number}")
            else:
                graph_lines.append(f"T{child.number} (unblocked)")

        # Build status table
        status_rows = []
        for c in children:
            blocked = ", ".join(f"T{n}" for n in c.blocked_by) or "-"
            state = "complete" if c.state == "closed" else "pending"
            status_rows.append(f"| T{c.number} | {c.title[:40]} | {state} | - | {blocked} |")

        content = f"""# E{epic.number} Task Index

## Dependency Graph

```
{chr(10).join(graph_lines)}
```

## Status

| Task | Title | State | Phase | Blocked By |
|------|-------|-------|-------|------------|
{chr(10).join(status_rows)}

## Hydration Command

To load these tasks into a Claude Code session:

```
Read .tasks/projects/{self.repo}/epics/E{epic.number}/index.md
Execute tasks in dependency order following TDD workflow.
Start with unblocked tasks.
```
"""
        path.write_text(content)

    def _extract_criteria(self, body: str) -> str:
        """Extract acceptance criteria YAML from issue body."""
        match = re.search(r"```yaml\n(.*?)```", body, re.DOTALL)
        if match:
            return f"```yaml\n{match.group(1)}```"
        return """```yaml
criteria:
  - id: AC1
    description: "TODO: Add acceptance criteria"
    validation: "echo 'TODO'"
```"""

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Sync GitHub epic to .tasks/")
    parser.add_argument("repo", help="owner/repo")
    parser.add_argument("epic", type=int, help="Epic issue number")
    parser.add_argument("--out", default=".tasks/projects", help="Output directory")
    parser.add_argument("--force", action="store_true", help="Overwrite existing")

    args = parser.parse_args()
    owner, repo = args.repo.split("/")

    syncer = GitHubEpicSync(owner, repo)
    epic, children = syncer.fetch_epic(args.epic)

    out_path = Path(args.out) / repo / "epics"
    writer = TasksWriter(out_path, owner, repo)
    writer.write_epic(epic, children)

    print(f"Synced epic #{args.epic} with {len(children)} tasks to {out_path}/E{args.epic}/")


if __name__ == "__main__":
    main()
