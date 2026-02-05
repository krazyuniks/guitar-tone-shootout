#!/usr/bin/env -S python3 -u
"""
Deterministic TDD state machine for epic orchestration.

Replaces run-epic.sh (bash loop) + claude-agent.sh (agent dispatch).
AI agents do creative work only. Validation is mechanical.
State transitions are controlled by Python, not AI.

Usage:
    # Run TDD state machine for an epic
    python scripts/run_epic.py run 42
    python scripts/run_epic.py run 42 --dry-run
    python scripts/run_epic.py run 42 --max-iterations 10

    # Dispatch a single agent (manual use, replaces claude-agent.sh)
    python scripts/run_epic.py dispatch test-author "Write tests for T43"
    python scripts/run_epic.py dispatch implementer --project webapp --max-turns 30 "Implement T44"
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import textwrap
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
AGENTS_DIR = PROJECT_ROOT / ".claude" / "agents"
TASKS_BASE = PROJECT_ROOT / ".tasks" / "projects" / "guitar-tone-shootout" / "epics"

VALID_PROJECTS = {"core", "audio", "t3k", "webapp", "worker", "scheduler"}

# Task states in order of progression
STATE_ORDER = ["pending", "locked", "validating", "complete"]

MAX_TEST_AUTHOR_RETRIES = 1  # retry once after initial failure
MAX_IMPLEMENTER_RETRIES = 2  # retry twice after initial failure


# ---------------------------------------------------------------------------
# Agent layer
# ---------------------------------------------------------------------------


@dataclass
class AgentDef:
    """Parsed agent definition from .claude/agents/{name}.md."""

    name: str
    tools: list[str]
    model: str | None
    prompt_body: str


def parse_agent_definition(name: str) -> AgentDef:
    """Read .claude/agents/{name}.md, parse YAML frontmatter, return AgentDef."""
    path = AGENTS_DIR / f"{name}.md"
    if not path.exists():
        available = [f.stem for f in AGENTS_DIR.glob("*.md")]
        die(f"Agent '{name}' not found at {path}\nAvailable: {', '.join(sorted(available))}")

    content = path.read_text()

    # Split YAML frontmatter from body
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            frontmatter_text = parts[1].strip()
            body = parts[2].strip()
        else:
            frontmatter_text = ""
            body = content
    else:
        frontmatter_text = ""
        body = content

    # Parse YAML manually (avoid pyyaml dependency)
    tools: list[str] = []
    model: str | None = None

    in_tools = False
    for line in frontmatter_text.splitlines():
        stripped = line.strip()

        if stripped.startswith("model:"):
            model = stripped.split(":", 1)[1].strip()
            in_tools = False
            continue

        if stripped == "tools:":
            in_tools = True
            continue

        if in_tools:
            if stripped.startswith("- "):
                tools.append(stripped[2:].strip())
            else:
                in_tools = False

    return AgentDef(name=name, tools=tools, model=model, prompt_body=body)


def build_mcp_config(agent_name: str, project: str | None) -> dict:
    """Build MCP server config. Only webapp gets Playwright."""
    if project == "webapp":
        return {
            "mcpServers": {
                "playwright": {
                    "command": "npx",
                    "args": [
                        "-y",
                        "@playwright/mcp@latest",
                        "--headless",
                        "--executable-path",
                        "/usr/bin/chromium",
                    ],
                }
            }
        }
    return {"mcpServers": {}}


def build_claude_args(
    agent_def: AgentDef,
    project: str | None = None,
    max_turns: int = 20,
) -> list[str]:
    """Build claude CLI arguments with tool enforcement from YAML frontmatter."""
    args = ["claude"]

    # ENFORCE tools from YAML frontmatter — this is the core fix
    if agent_def.tools:
        args.extend(["--allowedTools", ",".join(agent_def.tools)])

    if agent_def.model:
        args.extend(["--model", agent_def.model])

    args.extend(["--max-turns", str(max_turns)])
    args.append("--dangerously-skip-permissions")

    # MCP config
    mcp_config = build_mcp_config(agent_def.name, project)
    args.extend(["--strict-mcp-config", "--mcp-config", json.dumps(mcp_config)])

    return args


def dispatch_agent(
    agent_name: str,
    prompt: str,
    project: str | None = None,
    max_turns: int = 20,
    dry_run: bool = False,
) -> subprocess.CompletedProcess | None:
    """Dispatch a Claude agent with enforced tools and prompt."""
    agent_def = parse_agent_definition(agent_name)
    args = build_claude_args(agent_def, project=project, max_turns=max_turns)

    # Build full prompt: agent instructions + task
    full_prompt = f"# Agent: {agent_def.name}\n\n{agent_def.prompt_body}\n\n---\n\n# Task\n\n{prompt}"

    if dry_run:
        tools_str = ", ".join(agent_def.tools) if agent_def.tools else "(all)"
        print(f"  [dry-run] Would dispatch '{agent_name}' (model={agent_def.model}, tools={tools_str})")
        print(f"  [dry-run] Max turns: {max_turns}, project: {project or 'none'}")
        return None

    print(f"  Dispatching '{agent_name}' (model={agent_def.model}, max_turns={max_turns})...")

    # Pass prompt via stdin to avoid command-line length issues
    result = subprocess.run(
        [*args, "-p", "-"],
        input=full_prompt,
        capture_output=False,
        text=True,
        cwd=PROJECT_ROOT,
    )
    return result


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------


def build_test_author_prompt(task: Task, retry_context: str | None = None) -> str:
    """Build prompt for test-author agent."""
    lines = [
        f"Write tests for task T{task.task_id}: {task.title}",
        "",
        f"Epic: E{task.epic_number}",
        f"Project: {task.project or 'unknown'}",
        "",
        "## Task Specification",
        "",
        f"Read the full task spec at: .tasks/projects/guitar-tone-shootout/epics/E{task.epic_number}/tasks/T{task.task_id}.md",
        "",
        "## Instructions",
        "",
        "1. Read the task spec for acceptance criteria",
        "2. Write test files in tests/unit/, tests/integration/, or tests/e2e/python/tests/",
        "3. Run tests to verify they compile and FAIL (not error)",
        "4. Do NOT create any implementation files",
        "5. Do NOT update any .tasks/ state files",
    ]

    if retry_context:
        lines.extend([
            "",
            "## Previous Attempt Failed",
            "",
            "The previous test run did not produce properly failing tests.",
            "Fix the issues and ensure all tests fail (not error).",
            "",
            "Previous output:",
            "```",
            retry_context[-2000:],  # Truncate to last 2000 chars
            "```",
        ])

    return "\n".join(lines)


def build_implementer_prompt(
    task: Task,
    retry_context: str | None = None,
) -> str:
    """Build prompt for implementer agent."""
    lines = [
        f"Implement task T{task.task_id}: {task.title}",
        "",
        f"Epic: E{task.epic_number}",
        f"Project: {task.project or 'unknown'}",
        "",
        "## Task Specification",
        "",
        f"Read the full task spec at: .tasks/projects/guitar-tone-shootout/epics/E{task.epic_number}/tasks/T{task.task_id}.md",
        "",
        "## Instructions",
        "",
        "1. Read the task spec and test files to understand expected behaviour",
        "2. Implement code to make all tests pass",
        "3. Run tests iteratively: just tdd <test_path>",
        "4. You CANNOT modify any files in tests/",
        "5. Do NOT update any .tasks/ state files",
        "6. All commands run in Docker (use just commands)",
    ]

    if retry_context:
        lines.extend([
            "",
            "## Previous Attempt Failed",
            "",
            "Tests are still failing after the previous implementation attempt.",
            "Review the failures and fix the implementation.",
            "",
            "Previous output:",
            "```",
            retry_context[-2000:],
            "```",
        ])

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# State management
# ---------------------------------------------------------------------------


@dataclass
class Task:
    """Parsed task from .tasks/ files."""

    task_id: int
    title: str
    state: str  # pending, locked, validating, complete
    project: str | None = None
    blocked_by: list[int] = field(default_factory=list)
    epic_number: int = 0

    @property
    def is_actionable(self) -> bool:
        """Task is actionable if not complete and not blocked."""
        return self.state != "complete" and not self.blocked_by_incomplete


    # Set after resolving dependencies
    blocked_by_incomplete: list[int] = field(default_factory=list)


def parse_task_file(path: Path, epic_number: int) -> Task:
    """Parse a single task file from .tasks/."""
    content = path.read_text()

    # Extract task number from filename: T{number}.md
    match = re.match(r"T(\d+)\.md", path.name)
    if not match:
        die(f"Invalid task filename: {path.name}")
    task_id = int(match.group(1))

    # Extract title from first heading
    title_match = re.search(r"^# T\d+:\s*(.+)$", content, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else path.stem

    # Extract state from status table: | State | value |
    state = "pending"
    state_match = re.search(r"\|\s*State\s*\|\s*(\w+)\s*\|", content, re.IGNORECASE)
    if state_match:
        state = state_match.group(1).strip().lower()

    # Extract project from status table: | Project | value |
    project = None
    proj_match = re.search(r"\|\s*Project\s*\|\s*(\w+)\s*\|", content, re.IGNORECASE)
    if proj_match:
        proj_val = proj_match.group(1).strip().lower()
        if proj_val in VALID_PROJECTS:
            project = proj_val

    # Extract blocked_by from status table: | Blocked By | T43, T44 |
    blocked_by: list[int] = []
    blocked_match = re.search(r"\|\s*Blocked By\s*\|\s*([^|]+)\|", content, re.IGNORECASE)
    if blocked_match:
        blocked_str = blocked_match.group(1).strip()
        if blocked_str and blocked_str != "-":
            blocked_by = [int(x) for x in re.findall(r"T(\d+)", blocked_str)]

    return Task(
        task_id=task_id,
        title=title,
        state=state,
        project=project,
        blocked_by=blocked_by,
        epic_number=epic_number,
    )


def parse_all_tasks(epic_dir: Path, epic_number: int) -> list[Task]:
    """Parse all task files in an epic directory."""
    tasks_dir = epic_dir / "tasks"
    if not tasks_dir.exists():
        return []

    tasks = []
    for path in sorted(tasks_dir.glob("T*.md")):
        tasks.append(parse_task_file(path, epic_number))

    # Resolve blocked_by_incomplete
    complete_ids = {t.task_id for t in tasks if t.state == "complete"}
    for task in tasks:
        task.blocked_by_incomplete = [tid for tid in task.blocked_by if tid not in complete_ids]

    return tasks


def find_next_actionable(tasks: list[Task]) -> Task | None:
    """Find the next task to work on (lowest ID, not complete, not blocked)."""
    for task in sorted(tasks, key=lambda t: t.task_id):
        if task.state != "complete" and not task.blocked_by_incomplete:
            return task
    return None


def update_task_state(epic_dir: Path, task_id: int, new_state: str) -> None:
    """Update a task file's state field."""
    task_path = epic_dir / "tasks" / f"T{task_id}.md"
    if not task_path.exists():
        die(f"Task file not found: {task_path}")

    content = task_path.read_text()

    # Replace state in the status table
    new_content = re.sub(
        r"(\|\s*State\s*\|\s*)\w+(\s*\|)",
        rf"\g<1>{new_state}\g<2>",
        content,
        flags=re.IGNORECASE,
    )

    task_path.write_text(new_content)


def rebuild_index(epic_dir: Path, epic_number: int) -> None:
    """Rebuild index.md from task files (source of truth)."""
    tasks = parse_all_tasks(epic_dir, epic_number)
    if not tasks:
        return

    index_path = epic_dir / "index.md"

    # Read existing index for epic title
    epic_title = f"Epic E{epic_number}"
    if index_path.exists():
        existing = index_path.read_text()
        title_match = re.search(r"^# E\d+:\s*(.+)$", existing, re.MULTILINE)
        if title_match:
            epic_title = title_match.group(1).strip()

    # Build dependency graph
    graph_lines = []
    for t in tasks:
        if t.blocked_by:
            deps = ", ".join(f"T{n}" for n in t.blocked_by)
            graph_lines.append(f"{deps} → T{t.task_id}")
        else:
            graph_lines.append(f"T{t.task_id} (unblocked)")

    # Build status table
    rows = []
    for t in tasks:
        blocked = ", ".join(f"T{n}" for n in t.blocked_by) or "-"
        rows.append(f"| T{t.task_id} | {t.title[:35]} | {t.state} | {t.project or '-'} | {blocked} |")

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
    index_path.write_text(content)


# ---------------------------------------------------------------------------
# Validation (deterministic — no AI)
# ---------------------------------------------------------------------------


def run_just_command(command: str, task_id: str) -> tuple[bool, str]:
    """Run a just command, return (success, output)."""
    full_cmd = f"just {command} {task_id}"
    print(f"    Running: {full_cmd}")
    result = subprocess.run(
        full_cmd.split(),
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
    )
    output = result.stdout + result.stderr
    return result.returncode == 0, output


def run_tdd_red(task_id: str) -> tuple[bool, str]:
    """Verify tests fail (red phase). Returns (passed, output)."""
    return run_just_command("tdd-red", task_id)


def run_tdd_lock(task_id: str) -> tuple[bool, str]:
    """Lock tests (snapshot + commit). Returns (passed, output)."""
    return run_just_command("tdd-lock", task_id)


def run_tdd_green(task_id: str) -> tuple[bool, str]:
    """Verify tests pass (green phase). Returns (passed, output)."""
    return run_just_command("tdd-green", task_id)


def run_tdd_complete(task_id: str) -> tuple[bool, str]:
    """Run full TDD validation. Returns (passed, output)."""
    return run_just_command("tdd-complete", task_id)


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


def write_error_report(
    epic_dir: Path,
    task_id: int,
    phase: str,
    output: str,
) -> Path:
    """Write detailed error report to logs/errors/."""
    errors_dir = epic_dir / "logs" / "errors"
    errors_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    report_path = errors_dir / f"T{task_id}_{phase}_{timestamp}.md"

    content = f"""# Error Report: T{task_id} — {phase}

**Time:** {datetime.now(timezone.utc).isoformat()}
**Phase:** {phase}
**Task:** T{task_id}

## Output

```
{output[-5000:]}
```
"""
    report_path.write_text(content)
    return report_path


def stop_epic(
    epic_dir: Path,
    task_id: int,
    phase: str,
    output: str,
) -> None:
    """Stop the epic with a clear error report. Exits the process."""
    report_path = write_error_report(epic_dir, task_id, phase, output)

    print()
    print("=" * 60)
    print(f"EPIC HALTED — T{task_id} failed at phase: {phase}")
    print("=" * 60)
    print(f"Error report: {report_path}")
    print()
    print("Last output:")
    # Show last 40 lines
    for line in output.strip().splitlines()[-40:]:
        print(f"  {line}")
    print()
    print("To retry, fix the issue and re-run: python scripts/run_epic.py run <epic>")
    sys.exit(1)


def die(msg: str) -> None:
    """Print error and exit."""
    print(f"Error: {msg}", file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------------------
# TDD State Machine
# ---------------------------------------------------------------------------


def run_state_machine(
    epic_number: int,
    dry_run: bool = False,
    max_iterations: int = 50,
) -> None:
    """Run the TDD state machine for an epic."""
    epic_dir = TASKS_BASE / f"E{epic_number}"

    if not epic_dir.exists():
        die(f"Epic directory not found: {epic_dir}\nRun: just epic-sync {epic_number}")

    # Ensure log directories exist
    (epic_dir / "logs" / "errors").mkdir(parents=True, exist_ok=True)

    print(f"Starting TDD state machine for Epic E{epic_number}")
    print(f"  Tasks dir: {epic_dir}")
    print(f"  Max iterations: {max_iterations}")
    print(f"  Dry run: {dry_run}")
    print()

    for iteration in range(1, max_iterations + 1):
        print(f"=== Iteration {iteration} ===")

        # 1. Rebuild index from task files (source of truth)
        rebuild_index(epic_dir, epic_number)

        # 2. Parse all tasks
        tasks = parse_all_tasks(epic_dir, epic_number)
        if not tasks:
            die("No tasks found in epic directory")

        # 3. Check if epic is complete
        incomplete = [t for t in tasks if t.state != "complete"]
        if not incomplete:
            print()
            print("All tasks complete! Running final health check...")
            ok, output = run_just_command("epic-health", str(epic_number))
            if ok:
                print(f"Epic E{epic_number} complete and healthy!")
                return
            else:
                print("Health check failed:")
                print(output[-1000:])
                die("Epic complete but health check failed")

        # 4. Find next actionable task
        task = find_next_actionable(tasks)
        if task is None:
            blocked = [t for t in tasks if t.state != "complete"]
            print()
            print("No actionable tasks. Remaining tasks are blocked:")
            for t in blocked:
                blockers = ", ".join(f"T{b}" for b in t.blocked_by_incomplete)
                print(f"  T{t.task_id} ({t.state}) — blocked by: {blockers}")
            die("Epic is blocked")

        task_id_str = f"T{task.task_id}"
        print(f"  Next task: T{task.task_id} — {task.title} (state={task.state})")

        # 5. Execute based on current state
        if task.state == "pending":
            # --- TEST PHASE ---
            print(f"\n  Phase: TEST (writing tests for T{task.task_id})")

            prompt = build_test_author_prompt(task)
            dispatch_agent("test-author", prompt, project=task.project, dry_run=dry_run)

            if not dry_run:
                # Verify tests fail (red phase)
                print(f"\n  Phase: RED (verifying tests fail)")
                ok, output = run_tdd_red(task_id_str)

                if not ok:
                    # Retry once
                    print(f"  Red phase failed. Retrying test-author...")
                    retry_prompt = build_test_author_prompt(task, retry_context=output)
                    dispatch_agent("test-author", retry_prompt, project=task.project)

                    ok, output = run_tdd_red(task_id_str)
                    if not ok:
                        stop_epic(epic_dir, task.task_id, "red_failed", output)

                # Lock tests
                print(f"\n  Phase: LOCK (snapshotting tests)")
                ok, output = run_tdd_lock(task_id_str)
                if not ok:
                    stop_epic(epic_dir, task.task_id, "lock_failed", output)

                update_task_state(epic_dir, task.task_id, "locked")
            else:
                print(f"  [dry-run] Would run: tdd-red {task_id_str}")
                print(f"  [dry-run] Would run: tdd-lock {task_id_str}")
                print(f"  [dry-run] Would update state: pending → locked")

        elif task.state == "locked":
            # --- IMPLEMENTATION PHASE ---
            print(f"\n  Phase: IMPL (implementing T{task.task_id})")

            prompt = build_implementer_prompt(task)
            dispatch_agent("implementer", prompt, project=task.project, max_turns=30, dry_run=dry_run)

            if not dry_run:
                # Verify tests pass (green phase)
                print(f"\n  Phase: GREEN (verifying tests pass)")
                ok, output = run_tdd_green(task_id_str)

                if not ok:
                    # Retry up to MAX_IMPLEMENTER_RETRIES times
                    for attempt in range(MAX_IMPLEMENTER_RETRIES):
                        print(f"  Green phase failed. Retry {attempt + 1}/{MAX_IMPLEMENTER_RETRIES}...")
                        retry_prompt = build_implementer_prompt(task, retry_context=output)
                        dispatch_agent("implementer", retry_prompt, project=task.project, max_turns=30)

                        ok, output = run_tdd_green(task_id_str)
                        if ok:
                            break

                    if not ok:
                        stop_epic(epic_dir, task.task_id, "green_failed", output)

                # Auto-commit implementation work
                print(f"  Committing implementation for T{task.task_id}...")
                subprocess.run(
                    ["git", "add", "libs/", "apps/", "sources/", "infrastructure/"],
                    capture_output=True,
                )
                subprocess.run(
                    ["git", "commit", "-m", f"impl: T{task.task_id} make tests pass"],
                    capture_output=True,
                )

                update_task_state(epic_dir, task.task_id, "validating")
            else:
                print(f"  [dry-run] Would run: tdd-green {task_id_str}")
                print(f"  [dry-run] Would commit implementation")
                print(f"  [dry-run] Would update state: locked → validating")

        elif task.state == "validating":
            # --- VALIDATION PHASE ---
            print(f"\n  Phase: VALIDATE (full TDD validation for T{task.task_id})")

            if not dry_run:
                ok, output = run_tdd_complete(task_id_str)
                if not ok:
                    stop_epic(epic_dir, task.task_id, "validation_failed", output)

                update_task_state(epic_dir, task.task_id, "complete")
                print(f"  T{task.task_id} COMPLETE")
            else:
                print(f"  [dry-run] Would run: tdd-complete {task_id_str}")
                print(f"  [dry-run] Would update state: validating → complete")

        else:
            die(f"Unexpected task state: {task.state} for T{task.task_id}")

        print()

    # If we exhaust iterations
    print(f"Max iterations ({max_iterations}) reached.")
    print(f"Epic may not be complete. Check: just epic-status {epic_number}")
    sys.exit(1)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def cmd_run(args: argparse.Namespace) -> None:
    """Run the TDD state machine."""
    # Sync epic first (idempotent)
    print(f"Syncing epic #{args.epic}...")
    result = subprocess.run(
        ["just", "epic-sync", str(args.epic)],
        cwd=PROJECT_ROOT,
    )
    if result.returncode != 0:
        die(f"Failed to sync epic #{args.epic}")
    print()

    run_state_machine(
        epic_number=args.epic,
        dry_run=args.dry_run,
        max_iterations=args.max_iterations,
    )


def cmd_dispatch(args: argparse.Namespace) -> None:
    """Dispatch a single agent."""
    if args.project and args.project not in VALID_PROJECTS:
        die(f"Invalid project '{args.project}'. Must be one of: {', '.join(sorted(VALID_PROJECTS))}")

    result = dispatch_agent(
        agent_name=args.agent,
        prompt=args.prompt,
        project=args.project,
        max_turns=args.max_turns,
    )

    if result and result.returncode != 0:
        sys.exit(result.returncode)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="TDD state machine for epic orchestration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Examples:
              python scripts/run_epic.py run 42
              python scripts/run_epic.py run 42 --dry-run
              python scripts/run_epic.py dispatch test-author "Write tests for T43"
              python scripts/run_epic.py dispatch implementer --project webapp "Implement T44"
        """),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # --- run ---
    run_parser = subparsers.add_parser("run", help="Run TDD state machine for an epic")
    run_parser.add_argument("epic", type=int, help="Epic issue number")
    run_parser.add_argument("--dry-run", action="store_true", help="Show what would happen without dispatching agents")
    run_parser.add_argument("--max-iterations", type=int, default=50, help="Max state machine iterations (default: 50)")
    run_parser.set_defaults(func=cmd_run)

    # --- dispatch ---
    dispatch_parser = subparsers.add_parser("dispatch", help="Dispatch a single agent")
    dispatch_parser.add_argument("agent", help="Agent name (e.g., test-author, implementer)")
    dispatch_parser.add_argument("prompt", help="Prompt for the agent")
    dispatch_parser.add_argument("--project", help="Workspace project (core, audio, t3k, webapp, worker, scheduler)")
    dispatch_parser.add_argument("--max-turns", type=int, default=20, help="Max conversation turns (default: 20)")
    dispatch_parser.set_defaults(func=cmd_dispatch)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
