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

    # Validate epic tasks (pre-flight check)
    python scripts/run_epic.py validate 42
    python scripts/run_epic.py validate 42 --strict

    # Show epic status
    python scripts/run_epic.py status 42

    # Dispatch a single agent (manual use, replaces claude-agent.sh)
    python scripts/run_epic.py dispatch test-author "Write tests for T43"
    python scripts/run_epic.py dispatch implementer --project webapp --max-turns 30 "Implement T44"
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import subprocess
import sys
import textwrap
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
AGENTS_DIR = PROJECT_ROOT / ".claude" / "agents"
TASKS_BASE = PROJECT_ROOT / ".tasks" / "projects" / "guitar-tone-shootout" / "epics"

VALID_PROJECTS = {"core", "audio", "t3k", "webapp", "worker", "scheduler"}

# Task states in order of progression
STATE_ORDER = ["pending", "locked", "validating", "complete"]

MAX_TEST_AUTHOR_RETRIES = (
    2  # retry twice after initial failure (36% first-attempt failure rate in E86)
)
MAX_IMPLEMENTER_RETRIES = 2  # retry twice after initial failure


# ---------------------------------------------------------------------------
# Session logging
# ---------------------------------------------------------------------------

_session_log: logging.Logger | None = None


def init_session_log(epic_dir: Path, epic_number: int) -> None:
    """Initialise session log file under epic logs directory."""
    global _session_log

    logs_dir = epic_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    log_path = logs_dir / f"session_{timestamp}.log"

    logger = logging.getLogger(f"epic-{epic_number}")
    logger.setLevel(logging.DEBUG)

    # File handler — verbose
    fh = logging.FileHandler(log_path)
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(fh)

    # Console handler — summary only
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(ch)

    _session_log = logger
    _session_log.info(f"Session log: {log_path}")


def log(msg: str, level: str = "info") -> None:
    """Log a message to session log and console."""
    if _session_log is None:
        print(msg)
        return
    getattr(_session_log, level)(msg)


def log_structured(event: str, **data: object) -> None:
    """Write a structured JSON log entry for machine parsing."""
    entry = {
        "event": event,
        "timestamp": datetime.now(UTC).isoformat(),
        **data,
    }
    log(f"STRUCTURED: {json.dumps(entry)}", "debug")


# ---------------------------------------------------------------------------
# Infrastructure health check
# ---------------------------------------------------------------------------


def detect_preexisting_failures() -> None:
    """Run full test suite to find pre-existing failures not in known_failures.txt.

    Appends any newly discovered failures to the file so TDD green phases
    don't waste time on them. Runs before the task loop.
    """
    known_failures_path = PROJECT_ROOT / "tests" / "known_failures.txt"

    # Load existing known failures
    existing: set[str] = set()
    if known_failures_path.exists():
        for line in known_failures_path.read_text().splitlines():
            line = line.strip()
            if line:
                existing.add(line)

    log("Pre-flight: detecting pre-existing test failures...")

    # Build deselect args for currently known failures
    deselect_args: list[str] = []
    for failure in sorted(existing):
        deselect_args.extend(["--deselect", failure])

    # Run full suite with known failures deselected
    result = subprocess.run(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "webapp",
            "pytest",
            "tests/unit/",
            "tests/integration/",
            "-v",
            "-m",
            "not host_only",
            *deselect_args,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=300,
    )

    if result.returncode == 0:
        log("Pre-flight: all tests pass (no new pre-existing failures)")
        return

    # Parse FAILED and ERROR lines from output
    output = result.stdout + result.stderr
    new_failures: list[str] = []
    for match in re.finditer(r"(?:FAILED|ERROR) (tests/\S+\.py::\S+)", output):
        test_id = match.group(1)
        if test_id not in existing:
            new_failures.append(test_id)

    if not new_failures:
        log("Pre-flight: failures detected but all are already in known_failures.txt")
        return

    # Append new failures
    with known_failures_path.open("a") as f:
        for failure in sorted(set(new_failures)):
            f.write(f"{failure}\n")

    log(f"Pre-flight: added {len(new_failures)} new pre-existing failure(s) to known_failures.txt:")
    for failure in sorted(set(new_failures)):
        log(f"  + {failure}")


def check_infra_health() -> bool:
    """Check that Docker services are healthy before dispatching agents.

    Returns True if healthy, False otherwise.
    """
    result = subprocess.run(
        ["just", "health"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0 or "No healthy services found" in result.stdout:
        log("  WARNING: Infrastructure health check failed", "warning")
        log(f"  {result.stdout.strip()}", "warning")
        return False
    return True


# ---------------------------------------------------------------------------
# Git sync — rebase + push after commits
# ---------------------------------------------------------------------------


def git_sync() -> None:
    """Rebase on origin/main and push after commits."""
    # Stage any unstaged changes (epic-sync updates .tasks/ timestamps)
    subprocess.run(
        ["git", "add", ".tasks/", "tests/", "frontend/"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    # Commit if there are staged changes (no-op if clean)
    check = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    if check.returncode != 0:
        subprocess.run(
            ["git", "commit", "-m", "chore: sync task state"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
        )

    log("  Git sync: pull --rebase --autostash origin main")
    result = subprocess.run(
        ["git", "pull", "--rebase", "--autostash", "origin", "main"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        log(f"  Git rebase failed (non-fatal): {result.stderr.strip()}", "warning")
    else:
        log(f"  Rebased: {result.stdout.strip()}", "debug")

    log("  Git sync: push --force-with-lease")
    result = subprocess.run(
        ["git", "push", "--force-with-lease"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        log(f"  Git push failed (non-fatal): {result.stderr.strip()}", "warning")
    else:
        log(f"  Pushed: {result.stdout.strip()}", "debug")


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


def detect_chrome_executable() -> str | None:
    """Find Chrome/Chromium executable on the system."""
    for candidate in ["google-chrome", "chromium", "chromium-browser"]:
        result = subprocess.run(
            ["which", candidate],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    return None


def build_mcp_config(agent_name: str, project: str | None) -> dict:
    """Build MCP server config based on agent and project.

    - implementer with webapp project: Chrome DevTools (for UI verification)
    - test-author with webapp project: Playwright (for E2E test writing)
    - All other combinations: no MCP (saves context)
    """
    chrome_exe = detect_chrome_executable()

    chrome_args = ["-y", "chrome-devtools-mcp@latest"]
    if chrome_exe:
        chrome_args.extend(["--executablePath", chrome_exe])
    chrome_args.append("--headless")

    chrome_config = {
        "chrome-devtools": {
            "command": "npx",
            "args": chrome_args,
        }
    }
    playwright_config = {
        "playwright": {
            "command": "npx",
            "args": ["-y", "@playwright/mcp@latest"],
        }
    }

    if project == "webapp":
        if agent_name == "implementer":
            return {"mcpServers": {**chrome_config, **playwright_config}}
        if agent_name == "test-author":
            return {"mcpServers": {**playwright_config}}

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
    full_prompt = (
        f"# Agent: {agent_def.name}\n\n{agent_def.prompt_body}\n\n---\n\n# Task\n\n{prompt}"
    )

    if dry_run:
        tools_str = ", ".join(agent_def.tools) if agent_def.tools else "(all)"
        log(
            f"  [dry-run] Would dispatch '{agent_name}' (model={agent_def.model}, tools={tools_str})"
        )
        log(f"  [dry-run] Max turns: {max_turns}, project: {project or 'none'}")
        return None

    log(f"  Dispatching '{agent_name}' (model={agent_def.model}, max_turns={max_turns})...")
    log_structured("agent_dispatch", agent=agent_name, model=agent_def.model, max_turns=max_turns)

    # Pass prompt via stdin to avoid command-line length issues
    result = subprocess.run(
        [*args, "-p", "-"],
        input=full_prompt,
        capture_output=False,
        text=True,
        cwd=PROJECT_ROOT,
    )
    log(f"  Agent '{agent_name}' exited with code {result.returncode}", "debug")
    return result


# ---------------------------------------------------------------------------
# Pre-flight checks
# ---------------------------------------------------------------------------


def preflight_scope_check(task: Task) -> list[tuple[str, bool]]:
    """Parse **Create:** section from task spec, check which files exist.

    Returns list of (filepath, exists) tuples.
    """
    task_path = TASKS_BASE / f"E{task.epic_number}" / "tasks" / f"T{task.task_id}.md"
    if not task_path.exists():
        return []

    content = task_path.read_text()

    # Find the **Create:** section and extract file paths
    # Matches lines like: - `apps/webapp/src/webapp/.../file.py`
    in_create = False
    results: list[tuple[str, bool]] = []

    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("**Create:**"):
            in_create = True
            continue
        if in_create:
            # Stop at next section header or empty line after files
            if stripped.startswith("**") or (not stripped and results):
                break
            match = re.match(r"^-\s*`([^`]+)`", stripped)
            if match:
                filepath = match.group(1)
                exists = (PROJECT_ROOT / filepath).exists()
                results.append((filepath, exists))

    return results


def find_existing_tests(task: Task) -> list[tuple[str, int]]:
    """Find existing test files that cover modules in this task's scope.

    Returns list of (test_filepath, test_count) tuples.
    """
    # Get scope modules from the Create section
    scope_files = preflight_scope_check(task)
    if not scope_files:
        return []

    # Extract module names from scope files (e.g. "gear" from "models/gear.py")
    scope_modules: set[str] = set()
    for filepath, _ in scope_files:
        stem = Path(filepath).stem  # e.g. "gear", "gear_model", "gear_type"
        scope_modules.add(stem)

    # Directories to search (skip e2e venvs and unrelated dirs)
    search_dirs = [
        PROJECT_ROOT / "tests" / "unit",
        PROJECT_ROOT / "tests" / "integration",
        PROJECT_ROOT / "tests" / "regression",
    ]

    results: list[tuple[str, int]] = []
    for test_dir in search_dirs:
        if not test_dir.exists():
            continue
        for test_file in test_dir.rglob("test_*.py"):
            # Check filename contains a scope module name
            file_stem = test_file.stem.removeprefix("test_")
            if any(module in file_stem for module in scope_modules):
                content = test_file.read_text()
                test_count = len(re.findall(r"^(?:async\s+)?def test_", content, re.MULTILINE))
                rel_path = str(test_file.relative_to(PROJECT_ROOT))
                results.append((rel_path, test_count))

    return results


def parse_pytest_counts(output: str) -> tuple[int, int, int]:
    """Parse passed/failed/error counts from pytest output.

    Returns (passed, failed, errors).
    """

    def _extract(pattern: str) -> int:
        match = re.search(pattern, output)
        return int(match.group(1)) if match else 0

    return (
        _extract(r"(\d+) passed"),
        _extract(r"(\d+) failed"),
        _extract(r"(\d+) error"),
    )


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
    ]

    # --- Pre-flight context ---
    scope_files = preflight_scope_check(task)
    existing_tests = find_existing_tests(task)

    existing_scope = [(f, e) for f, e in scope_files if e]
    missing_scope = [(f, e) for f, e in scope_files if not e]

    if existing_scope or existing_tests:
        lines.extend(
            [
                "",
                "## Pre-flight Context (IMPORTANT)",
                "",
                "Some scope files already exist. This means code is partially implemented.",
                "Every test you write MUST FAIL against the current code.",
                "Do NOT write tests that verify already-working functionality.",
                "",
            ]
        )

        if existing_scope:
            lines.append("**Scope files that ALREADY EXIST (read these first):**")
            for filepath, _ in existing_scope:
                lines.append(f"- `{filepath}` — READ this file before writing tests")
            lines.append("")

        if missing_scope:
            lines.append("**Scope files that DO NOT exist yet (safe to test freely):**")
            for filepath, _ in missing_scope:
                lines.append(f"- `{filepath}`")
            lines.append("")

        if existing_tests:
            lines.append("**Existing test files covering these modules (DO NOT duplicate):**")
            for test_path, count in existing_tests:
                lines.append(f"- `{test_path}` ({count} tests)")
            lines.append("")

        lines.extend(
            [
                "**Strategy for partially-implemented tasks:**",
                "1. Read all existing scope files to understand what's already implemented",
                "2. Read existing test files to avoid duplication",
                "3. Write tests ONLY for genuinely missing functionality",
                "4. If everything is already implemented, write tests for edge cases or",
                "   acceptance criteria that existing tests don't cover",
                "5. Every test MUST FAIL — if you can't find anything untested, STOP and",
                "   report that the task appears fully implemented",
            ]
        )
    elif missing_scope:
        lines.extend(
            [
                "",
                "## Scope Context",
                "",
                "None of the scope files exist yet — this is a fresh implementation task.",
                "All tests should fail (imports will error on missing modules).",
            ]
        )

    lines.extend(
        [
            "",
            "## Instructions",
            "",
            "1. Read the task spec for acceptance criteria",
            "2. Write test files in tests/unit/, tests/integration/, or tests/e2e/python/tests/",
            "3. Run tests to verify they compile and FAIL (not error)",
            "4. Do NOT create any implementation files",
            "5. Do NOT update any .tasks/ state files",
            "6. You MAY modify existing test files when the task spec explicitly requires it",
            "7. When modifying, ADD new test functions — do not alter existing tests",
            "8. Prefer creating new files unless the task spec names a specific file to modify",
        ]
    )

    if retry_context:
        passed, failed, errors = parse_pytest_counts(retry_context)
        lines.extend(
            [
                "",
                "## Previous Attempt Failed — RED GATE REJECTED",
                "",
                f"**Results:** {passed} passed, {failed} failed, {errors} errors",
                "",
            ]
        )

        if passed > 0 and failed == 0 and errors == 0:
            lines.extend(
                [
                    f"ALL {passed} tests passed. The red gate requires at least one failure.",
                    "",
                    "**You MUST:**",
                    "1. DELETE all test files you created (they test already-implemented code)",
                    "2. Read the existing implementation files listed in scope",
                    "3. Write NEW tests that target genuinely MISSING functionality",
                    "4. If everything is implemented, test edge cases or validation not yet covered",
                ]
            )
        elif passed > 0:
            lines.extend(
                [
                    f"{passed} tests already pass against current code.",
                    "The red gate tolerates some passing tests IF failures exist too,",
                    "but you should still review passing tests — they may be testing",
                    "already-implemented behaviour (wasting test budget).",
                ]
            )

        lines.extend(
            [
                "",
                "Previous output (last 2000 chars):",
                "```",
                retry_context[-2000:],
                "```",
            ]
        )

    # Agent .md body now contains all needed testing reference — no external skill loading

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
        "4. You MAY modify existing test files to fix breakage from your changes",
        "5. You MUST NOT modify the task's own test files (the spec from test-author)",
        "6. You MUST NOT create new test files",
        "7. Use Grep to find ALL affected patterns before making changes",
        "8. Fix existing tests FIRST, then fix code, then verify with full suite",
        "9. Do NOT update any .tasks/ state files",
        "10. All commands run in Docker (use just commands)",
    ]

    if retry_context:
        passed, failed, errors = parse_pytest_counts(retry_context)

        # Categorise errors for the agent
        error_types: list[str] = []
        if "ImportError" in retry_context or "ModuleNotFoundError" in retry_context:
            error_types.append("ImportError (missing module or wrong import path)")
        if "AssertionError" in retry_context:
            error_types.append("AssertionError (logic/value mismatch)")
        if "RuntimeError" in retry_context or "TypeError" in retry_context:
            error_types.append("RuntimeError/TypeError (code structure issue)")
        if "422" in retry_context:
            error_types.append("422 Unprocessable Entity (check Depends() / annotations)")

        # Get files modified so far
        diff_result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
        )
        modified_files = diff_result.stdout.strip()

        lines.extend(
            [
                "",
                "## Previous Attempt Failed",
                "",
                f"**Results:** {passed} passed, {failed} failed, {errors} errors",
                "",
            ]
        )

        if error_types:
            lines.append("**Error categories:** " + "; ".join(error_types))
            lines.append("")

        if modified_files:
            lines.append("**Files created/modified so far:**")
            for f in modified_files.splitlines()[:20]:
                lines.append(f"- `{f}`")
            lines.append("")

        lines.extend(
            [
                "Review the failures and fix the implementation.",
                "",
                "Previous output (last 3000 chars):",
                "```",
                retry_context[-3000:],
                "```",
            ]
        )

    return "\n".join(lines)


def is_likely_test_bug(task: Task, green_output: str) -> bool:
    """Heuristic: did the implementer do the work but tests have bugs?

    Returns True when:
    - Most scope files exist (implementation was done, >= 75% present)
    - AND one of:
      a) Small number of failures (<= 3) with most tests passing
      b) All failures are in a single test file (likely one bad pattern)
    """
    scope_files = preflight_scope_check(task)
    if not scope_files:
        return False

    existing = sum(1 for _, exists in scope_files if exists)
    total = len(scope_files)
    if total == 0 or existing / total < 0.75:
        return False

    passed, failed, errors = parse_pytest_counts(green_output)
    total_tests = passed + failed + errors
    if total_tests == 0:
        return False

    failure_count = failed + errors

    # Heuristic A: few failures and most tests pass
    if failure_count <= 3 and passed > failure_count:
        return True

    # Heuristic B: all failures in a single test file (one bad pattern)
    failing_files = find_failing_test_files(green_output)
    return bool(len(failing_files) == 1 and passed > 0)


def find_failing_test_files(green_output: str) -> list[str]:
    """Extract failing test file paths from pytest output."""
    # Match FAILED lines: FAILED tests/unit/webapp/test_foo.py::test_bar
    files: set[str] = set()
    for match in re.finditer(r"FAILED (tests/\S+\.py)::", green_output):
        files.add(match.group(1))
    return sorted(files)


def find_erroring_test_files(green_output: str) -> list[str]:
    """Extract erroring test file paths from pytest output."""
    files: set[str] = set()
    for match in re.finditer(r"ERROR (tests/\S+\.py)::", green_output):
        files.add(match.group(1))
    for match in re.finditer(r"(tests/\S+\.py):\d+: (?:NameError|ImportError)", green_output):
        files.add(match.group(1))
    return sorted(files)


def get_scope_test_files(task: Task) -> list[str]:
    """Extract test file paths from task scope (Create + Modify sections)."""
    scope_files = preflight_scope_check(task)
    return sorted(f for f, _ in scope_files if f.startswith("tests/"))


def is_test_only_task(task: Task) -> bool:
    """Check if all scope files are in tests/ (no implementation code to write).

    Returns True when the task only modifies/creates test files.
    """
    scope_files = preflight_scope_check(task)
    if not scope_files:
        return False
    return all(filepath.startswith("tests/") for filepath, _ in scope_files)


def build_test_fix_prompt(
    task: Task,
    green_output: str,
    failing_test_files: list[str],
) -> str:
    """Build prompt for test-author in FIX mode (bounce-back from green failure)."""
    lines = [
        f"FIX tests for task T{task.task_id}: {task.title}",
        "",
        "## Context",
        "",
        "The implementer completed the code, but some tests have bugs.",
        "You are being called back to FIX the failing tests — not write new ones.",
        "",
        "## Failing Test Files (you MAY modify these)",
        "",
    ]

    for f in failing_test_files:
        lines.append(f"- `{f}`")

    lines.extend(
        [
            "",
            "## Rules",
            "",
            "1. ONLY modify the files listed above — no other test files",
            "2. Read each failing test file and the implementation it tests",
            "3. Fix the test bugs (wrong imports, wrong assertions, wrong patterns)",
            "4. Do NOT add new tests — only fix existing ones",
            "5. Do NOT modify implementation files (libs/, apps/, sources/)",
            "6. Do NOT update any .tasks/ state files",
            "",
            "## BANNED Patterns (NEVER USE)",
            "",
            "- `importlib.util` / `find_spec` / `module_from_spec` — use standard `from X import Y`",
            "- `db_session.get_bind()` — returns sync Engine, use fixtures directly",
            "- Ad-hoc session fixtures when conftest fixtures exist",
            "- `AsyncClient(app=...)` — removed in HTTPX 0.28+, use `AsyncClient(transport=ASGITransport(app=app), ...)`",
            "",
            "## Green Phase Output (failures to fix)",
            "",
            "```",
            green_output[-3000:],
            "```",
        ]
    )

    # Agent .md body now contains all needed testing reference — no external skill loading

    return "\n".join(lines)


def restore_locked_test_files(task_id_str: str) -> tuple[bool, str]:
    """Restore test files modified by implementer to their locked versions.

    Uses snapshot_tests.py to detect violations, then git-restores
    modified files from the lock commit. Returns (success, output).
    """
    # Run snapshot verification to get violations
    result = subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / "scripts" / "snapshot_tests.py"),
            "verify",
            task_id_str,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    if result.returncode == 0:
        return True, "No violations found"

    # Parse modified file paths from output: "  MODIFIED: tests/path/to/file.py"
    modified_files = []
    for line in result.stdout.splitlines():
        stripped = line.strip()
        if stripped.startswith("MODIFIED:") or stripped.startswith("DELETED:"):
            filepath = stripped.split(":", 1)[1].strip()
            modified_files.append(filepath)

    if not modified_files:
        return False, f"Validation failed but couldn't parse violations:\n{result.stdout}"

    # Find the lock commit
    lock_result = subprocess.run(
        ["git", "log", f"--grep=test-lock: {task_id_str}", "-1", "--format=%H"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    lock_commit = lock_result.stdout.strip()
    if not lock_commit:
        return False, f"Could not find lock commit for {task_id_str}"

    # Restore each modified file from the lock commit
    restored = []
    for filepath in modified_files:
        restore = subprocess.run(
            ["git", "checkout", lock_commit, "--", filepath],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
        )
        if restore.returncode == 0:
            restored.append(filepath)
        else:
            return False, f"Failed to restore {filepath}: {restore.stderr}"

    # Stage and commit the restoration
    subprocess.run(
        ["git", "add", *restored],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "commit", "-m", f"fix(tests): restore locked test files for {task_id_str}"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    return True, f"Restored {len(restored)} file(s): {', '.join(restored)}"


def re_lock_after_bounce(task_id_str: str) -> tuple[bool, str]:
    """Re-snapshot and commit fixed tests after bounce-back.

    Returns (success, output).
    """
    # Stage and commit test fixes
    result = subprocess.run(
        ["git", "add", "tests/"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return False, result.stderr

    result = subprocess.run(
        ["git", "commit", "-m", f"fix(tests): Fix test bugs for {task_id_str} (bounce-back)"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    # commit may fail if nothing changed — that's OK
    commit_output = result.stdout + result.stderr

    # Re-snapshot
    ok, snapshot_output = run_just_command("tdd-lock", task_id_str)
    return ok, commit_output + "\n" + snapshot_output


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
        rows.append(
            f"| T{t.task_id} | {t.title[:35]} | {t.state} | {t.project or '-'} | {blocked} |"
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
    index_path.write_text(content)


# ---------------------------------------------------------------------------
# Validation (deterministic — no AI)
# ---------------------------------------------------------------------------


def run_just_command(command: str, task_id: str) -> tuple[bool, str]:
    """Run a just command, return (success, output)."""
    full_cmd = f"just {command} {task_id}"
    log(f"    Running: {full_cmd}")
    result = subprocess.run(
        full_cmd.split(),
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
    )
    output = result.stdout + result.stderr
    ok = result.returncode == 0
    status = "OK" if ok else f"FAILED (exit {result.returncode})"
    log(f"    {full_cmd} -> {status}", "debug")
    # Log output to file (last 3000 chars)
    if output.strip():
        log(f"    Output:\n{output[-3000:]}", "debug")
    return ok, output


def _get_new_test_files() -> list[str]:
    """Get new/modified test files since last commit (for mock quality gate)."""
    modified = subprocess.run(
        ["git", "diff", "--name-only", "HEAD", "--", "tests/"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard", "--", "tests/"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    all_files = set(modified.stdout.strip().splitlines() + untracked.stdout.strip().splitlines())
    return sorted(
        f
        for f in all_files
        if f.endswith(".py")
        and ("test_" in f or f.endswith("_test.py"))
        and not f.startswith("tests/e2e/")
        and f  # filter empty strings
    )


def run_tdd_red(task_id: str) -> tuple[bool, str]:
    """Verify tests fail (red phase). Returns (passed, output)."""
    return run_just_command("tdd-red", task_id)


def run_tdd_lock(task_id: str) -> tuple[bool, str]:
    """Lock tests (snapshot + commit). Returns (passed, output)."""
    return run_just_command("tdd-lock", task_id)


def run_tdd_green(task_id: str, task: Task | None = None) -> tuple[bool, str]:
    """Verify tests pass (green phase). Returns (passed, output).

    When a Task is provided, runs pytest directly on scope-derived test files
    (fast feedback during retries). When task is None, runs the full suite
    via `just tdd-green`.
    """
    if task is not None:
        test_files = get_scope_test_files(task)
        if test_files:
            files_display = " ".join(test_files)
            log(f"    Running scope-derived green: pytest {files_display} -v")
            result = subprocess.run(
                ["docker", "compose", "exec", "-T", "webapp", "pytest", *test_files, "-v"],
                capture_output=True,
                text=True,
                cwd=PROJECT_ROOT,
            )
            output = result.stdout + result.stderr
            ok = result.returncode == 0
            log(
                f"    scope-derived green -> {'OK' if ok else f'FAILED (exit {result.returncode})'}",
                "debug",
            )
            if output.strip():
                log(f"    Output:\n{output[-3000:]}", "debug")
            return ok, output
        else:
            log("    No test files in task scope, falling back to just tdd-green")
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

    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    report_path = errors_dir / f"T{task_id}_{phase}_{timestamp}.md"

    content = f"""# Error Report: T{task_id} — {phase}

**Time:** {datetime.now(UTC).isoformat()}
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

    log("")
    log("=" * 60)
    log(f"EPIC HALTED — T{task_id} failed at phase: {phase}")
    log("=" * 60)
    log(f"Error report: {report_path}")
    log("")
    log("Last output:")
    # Show last 40 lines
    for line in output.strip().splitlines()[-40:]:
        log(f"  {line}")
    log("")
    log("To retry, fix the issue and re-run: python scripts/run_epic.py run <epic>")
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

    # Track bounce-backs: task_id -> count (max 1 per task)
    bounce_backs: dict[int, int] = {}

    # Initialise session log
    init_session_log(epic_dir, epic_number)

    log(f"Starting TDD state machine for Epic E{epic_number}")
    log(f"  Tasks dir: {epic_dir}")
    log(f"  Max iterations: {max_iterations}")
    log(f"  Dry run: {dry_run}")
    log("")

    for iteration in range(1, max_iterations + 1):
        log(f"=== Iteration {iteration} ===")

        # 1. Rebuild index from task files (source of truth)
        rebuild_index(epic_dir, epic_number)

        # 2. Parse all tasks
        tasks = parse_all_tasks(epic_dir, epic_number)
        if not tasks:
            die("No tasks found in epic directory")

        # 3. Check if epic is complete
        incomplete = [t for t in tasks if t.state != "complete"]
        if not incomplete:
            log("")
            log("All tasks complete! Running final health check...")
            ok, output = run_just_command("epic-health", str(epic_number))
            if ok:
                log(f"Epic E{epic_number} complete and healthy!")
                return
            else:
                log("Health check failed:")
                log(output[-1000:])
                die("Epic complete but health check failed")

        # 4. Find next actionable task
        task = find_next_actionable(tasks)
        if task is None:
            blocked = [t for t in tasks if t.state != "complete"]
            log("")
            log("No actionable tasks. Remaining tasks are blocked:")
            for t in blocked:
                blockers = ", ".join(f"T{b}" for b in t.blocked_by_incomplete)
                log(f"  T{t.task_id} ({t.state}) — blocked by: {blockers}")
            die("Epic is blocked")

        task_id_str = f"T{task.task_id}"
        log(f"  Next task: T{task.task_id} — {task.title} (state={task.state})")

        # 4b. Infrastructure health check before dispatch
        if not dry_run and not check_infra_health():
            log("  Waiting 15s for services to recover...")
            import time

            time.sleep(15)
            if not check_infra_health():
                log("  Infrastructure still unhealthy. Halting.", "error")
                stop_epic(epic_dir, task.task_id, "infra_unhealthy", "Docker services not healthy")

        # 5. Execute based on current state
        if task.state == "pending":
            # --- TEST PHASE ---
            log(f"\n  Phase: TEST (writing tests for T{task.task_id})")
            log_structured("phase_start", task_id=task.task_id, phase="test")

            prompt = build_test_author_prompt(task)
            dispatch_agent("test-author", prompt, project=task.project, dry_run=dry_run)

            if not dry_run:
                # Verify tests fail (red phase)
                log("\n  Phase: RED (verifying tests fail)")
                ok, output = run_tdd_red(task_id_str)

                if not ok:
                    # Retry up to MAX_TEST_AUTHOR_RETRIES times
                    for attempt in range(MAX_TEST_AUTHOR_RETRIES):
                        log(f"  Red phase failed. Retry {attempt + 1}/{MAX_TEST_AUTHOR_RETRIES}...")
                        retry_prompt = build_test_author_prompt(task, retry_context=output)
                        dispatch_agent("test-author", retry_prompt, project=task.project)

                        ok, output = run_tdd_red(task_id_str)
                        if ok:
                            break

                    if not ok:
                        stop_epic(epic_dir, task.task_id, "red_failed", output)

                # Mock quality gate — only check new/modified test files
                log("\n  Phase: MOCK CHECK (verifying no mock violations)")
                new_test_files = _get_new_test_files()
                if new_test_files:
                    mock_result = subprocess.run(
                        [
                            sys.executable,
                            str(PROJECT_ROOT / "scripts" / "test_quality_check.py"),
                            "--strict",
                            *new_test_files,
                        ],
                        cwd=PROJECT_ROOT,
                        capture_output=True,
                        text=True,
                    )
                    if mock_result.returncode != 0:
                        stop_epic(
                            epic_dir,
                            task.task_id,
                            "mock_quality_failed",
                            mock_result.stdout + mock_result.stderr,
                        )
                    log("    Mock check passed")
                else:
                    log("    No new test files to check")

                # Lock tests
                log("\n  Phase: LOCK (snapshotting tests)")
                ok, output = run_tdd_lock(task_id_str)
                if not ok:
                    stop_epic(epic_dir, task.task_id, "lock_failed", output)

                update_task_state(epic_dir, task.task_id, "locked")
                log_structured("phase_end", task_id=task.task_id, phase="test", result="locked")
                git_sync()  # tdd-lock creates a commit; sync it
            else:
                log(f"  [dry-run] Would run: tdd-red {task_id_str}")
                log(f"  [dry-run] Would run: tdd-lock {task_id_str}")
                log("  [dry-run] Would update state: pending → locked")
                update_task_state(epic_dir, task.task_id, "locked")

        elif task.state == "locked":
            # --- CHECK: is this a test-only task? ---
            test_only = is_test_only_task(task)

            if test_only:
                # Test-only tasks: verify task's own tests pass first
                log(f"\n  Phase: TEST-FIX (test-only task T{task.task_id})")
                log_structured("phase_start", task_id=task.task_id, phase="test_fix")

                if not dry_run:
                    ok, output = run_tdd_green(task_id_str, task)  # scope-derived
                else:
                    log("  [dry-run] Would run scope-derived green for test-only task")
                    ok, output = True, ""

                if not dry_run and not ok:
                    failing_files = find_failing_test_files(output)
                    error_files = find_erroring_test_files(output)
                    all_problem_files = sorted(set(failing_files) | set(error_files))

                    if all_problem_files:
                        log(
                            f"  Test-only task has {len(all_problem_files)} problem file(s), dispatching test-author FIX..."
                        )
                        fix_prompt = build_test_fix_prompt(task, output, all_problem_files)
                        dispatch_agent("test-author", fix_prompt, project=task.project)

                        log("\n  Re-locking tests after fix...")
                        lock_ok, lock_output = re_lock_after_bounce(task_id_str)
                        if not lock_ok:
                            stop_epic(epic_dir, task.task_id, "test_fix_lock_failed", lock_output)

                        ok, output = run_tdd_green(task_id_str, task)
                        if not ok:
                            stop_epic(epic_dir, task.task_id, "test_fix_green_failed", output)
                    else:
                        stop_epic(epic_dir, task.task_id, "green_failed", output)
            else:
                # --- IMPLEMENTATION PHASE (normal) ---
                log(f"\n  Phase: IMPL (implementing T{task.task_id})")
                log_structured("phase_start", task_id=task.task_id, phase="impl")

                prompt = build_implementer_prompt(task)
                dispatch_agent(
                    "implementer", prompt, project=task.project, max_turns=30, dry_run=dry_run
                )

                if not dry_run:
                    # Verify task's own tests pass (scope-derived, fast feedback)
                    log("\n  Phase: GREEN (verifying task tests pass)")
                    ok, output = run_tdd_green(task_id_str, task)

                    if not ok:
                        # Retry up to MAX_IMPLEMENTER_RETRIES times with scope-derived
                        for attempt in range(MAX_IMPLEMENTER_RETRIES):
                            log(
                                f"  Green phase failed. Retry {attempt + 1}/{MAX_IMPLEMENTER_RETRIES}..."
                            )
                            retry_prompt = build_implementer_prompt(task, retry_context=output)
                            dispatch_agent(
                                "implementer", retry_prompt, project=task.project, max_turns=30
                            )

                            ok, output = run_tdd_green(task_id_str, task)
                            if ok:
                                break

                        if not ok:
                            # --- BOUNCE-BACK: try fixing tests if likely test bug ---
                            bounced = bounce_backs.get(task.task_id, 0)
                            if bounced == 0 and is_likely_test_bug(task, output):
                                bounce_backs[task.task_id] = 1
                                failing_files = find_failing_test_files(output)
                                log(
                                    f"\n  BOUNCE-BACK: likely test bug ({len(failing_files)} failing test file(s))"
                                )
                                log("  Dispatching test-author in FIX mode...")

                                fix_prompt = build_test_fix_prompt(task, output, failing_files)
                                dispatch_agent("test-author", fix_prompt, project=task.project)

                                log("\n  Re-locking tests after bounce-back...")
                                lock_ok, lock_output = re_lock_after_bounce(task_id_str)
                                if not lock_ok:
                                    stop_epic(
                                        epic_dir, task.task_id, "bounce_lock_failed", lock_output
                                    )

                                log("\n  Re-running GREEN after bounce-back...")
                                ok, output = run_tdd_green(task_id_str, task)
                                if not ok:
                                    stop_epic(
                                        epic_dir, task.task_id, "green_failed_after_bounce", output
                                    )
                            else:
                                stop_epic(epic_dir, task.task_id, "green_failed", output)

            # --- FULL SUITE GREEN (both paths must pass the full suite) ---
            if not dry_run:
                log("\n  Phase: FULL-SUITE GREEN (verifying ALL tests pass)")
                ok, output = run_tdd_green(task_id_str)  # no task = just tdd-green = full suite

                if not ok:
                    # Dispatch implementer to fix broken existing tests
                    for attempt in range(MAX_IMPLEMENTER_RETRIES):
                        log(
                            f"  Full suite failed. Dispatching implementer (attempt {attempt + 1}/{MAX_IMPLEMENTER_RETRIES})..."
                        )
                        retry_prompt = build_implementer_prompt(task, retry_context=output)
                        dispatch_agent(
                            "implementer", retry_prompt, project=task.project, max_turns=30
                        )

                        ok, output = run_tdd_green(task_id_str)
                        if ok:
                            break

                    if not ok:
                        stop_epic(epic_dir, task.task_id, "full_suite_green_failed", output)

                # Auto-commit implementation + test fixes + task state
                log("\n  Committing changes...")
                impl_paths = [
                    "libs/",
                    "apps/",
                    "sources/",
                    "infrastructure/",
                    "frontend/",
                    "tests/",
                    ".tasks/",
                ]
                subprocess.run(
                    ["git", "add", *impl_paths],
                    cwd=PROJECT_ROOT,
                    capture_output=True,
                    text=True,
                )
                subprocess.run(
                    ["git", "commit", "-m", f"impl: {task_id_str} — {task.title}"],
                    cwd=PROJECT_ROOT,
                    capture_output=True,
                    text=True,
                )
                git_sync()

                update_task_state(epic_dir, task.task_id, "validating")
                log_structured("phase_end", task_id=task.task_id, phase="impl", result="validating")
            else:
                log(f"  [dry-run] Would run: tdd-green {task_id_str} (full suite)")
                log("  [dry-run] Would commit implementation files")
                log("  [dry-run] Would update state: locked → validating")
                update_task_state(epic_dir, task.task_id, "validating")

        elif task.state == "validating":
            # --- VALIDATION PHASE ---
            log(f"\n  Phase: VALIDATE (full TDD validation for T{task.task_id})")
            log_structured("phase_start", task_id=task.task_id, phase="validate")

            if not dry_run:
                ok, output = run_tdd_complete(task_id_str)
                if not ok:
                    # Check if failure is due to test file modifications
                    if "MODIFIED:" in output or "DELETED:" in output:
                        log(
                            "  Validation failed: test files modified by implementer. Auto-restoring..."
                        )
                        restore_ok, restore_output = restore_locked_test_files(task_id_str)
                        if restore_ok:
                            log(f"  {restore_output}")
                            log("  Re-running validation after restore...")
                            ok, output = run_tdd_complete(task_id_str)
                            if not ok:
                                write_error_report(
                                    epic_dir,
                                    task.task_id,
                                    "validation_failed_after_restore",
                                    output,
                                )
                                stop_epic(epic_dir, task.task_id, "validation_failed", output)
                        else:
                            log(f"  Auto-restore failed: {restore_output}", "error")
                            stop_epic(epic_dir, task.task_id, "validation_failed", output)
                    else:
                        stop_epic(epic_dir, task.task_id, "validation_failed", output)

                update_task_state(epic_dir, task.task_id, "complete")
                log(f"  T{task.task_id} COMPLETE")
                log_structured(
                    "phase_end", task_id=task.task_id, phase="validate", result="complete"
                )

                # Commit task state change and sync
                subprocess.run(
                    ["git", "add", ".tasks/"],
                    cwd=PROJECT_ROOT,
                    capture_output=True,
                    text=True,
                )
                subprocess.run(
                    ["git", "commit", "-m", f"chore: Mark {task_id_str} complete"],
                    cwd=PROJECT_ROOT,
                    capture_output=True,
                    text=True,
                )
                git_sync()
            else:
                log(f"  [dry-run] Would run: tdd-complete {task_id_str}")
                log("  [dry-run] Would update state: validating → complete")
                update_task_state(epic_dir, task.task_id, "complete")

        else:
            die(f"Unexpected task state: {task.state} for T{task.task_id}")

        log("")

    # If we exhaust iterations
    log(f"Max iterations ({max_iterations}) reached.")
    log(f"Epic may not be complete. Check: just epic-status {epic_number}")
    sys.exit(1)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def show_approval_screen(epic_number: int, dry_run: bool, max_iterations: int) -> None:
    """Display epic run summary and wait for user confirmation."""
    epic_dir = TASKS_BASE / f"E{epic_number}"
    tasks = parse_all_tasks(epic_dir, epic_number) if epic_dir.exists() else []

    complete = sum(1 for t in tasks if t.state == "complete")
    pending = len(tasks) - complete

    # Read agent definitions for model info
    test_author_def = parse_agent_definition("test-author")
    implementer_def = parse_agent_definition("implementer")

    # Detect MCP availability
    has_webapp = any(t.project == "webapp" for t in tasks if t.state != "complete")
    mcp_note = "Chrome DevTools + Playwright (webapp tasks)" if has_webapp else "None required"

    # Read epic title
    title = f"Epic E{epic_number}"
    index_path = epic_dir / "index.md"
    if index_path.exists():
        content = index_path.read_text()
        title_match = re.search(r"^# E\d+:\s*(.+)$", content, re.MULTILINE)
        if title_match:
            title = title_match.group(1).strip()

    print()
    print("=" * 50)
    print(f"  Epic E{epic_number} — {title}")
    print("=" * 50)
    print(f"  Tasks:        {len(tasks)} ({complete} complete, {pending} pending)")
    print(
        f"  Agents:       test-author ({test_author_def.model}), implementer ({implementer_def.model})"
    )
    print("  Max turns:    test-author=20, implementer=30")
    print(
        f"  Max retries:  test-author={MAX_TEST_AUTHOR_RETRIES}, implementer={MAX_IMPLEMENTER_RETRIES}"
    )
    print(f"  MCP:          {mcp_note}")
    print(f"  Dry run:      {'Yes' if dry_run else 'No'}")
    print()
    print("  Quality gates:")
    print("    - tdd-red (tests must fail)")
    print("    - mock-check (no Mock/patch violations)")
    print("    - tdd-lock (snapshot + commit)")
    print("    - tdd-green (tests must pass)")
    print("    - tdd-complete (full suite + golden path)")
    print("=" * 50)


def cmd_run(args: argparse.Namespace) -> None:
    """Run the TDD state machine."""
    # Pre-flight validation (fail-fast if tasks are invalid)
    print(f"Validating epic #{args.epic}...")
    validate_script = PROJECT_ROOT / "scripts" / "validate_tasks.py"
    result = subprocess.run(
        [sys.executable, str(validate_script), str(args.epic)],
        cwd=PROJECT_ROOT,
    )
    if result.returncode != 0:
        die(f"Pre-flight validation failed for epic #{args.epic}. Fix with: /epic fix {args.epic}")

    # Detect pre-existing test failures before starting
    if not args.dry_run:
        detect_preexisting_failures()

    # Approval screen
    show_approval_screen(args.epic, args.dry_run, args.max_iterations)

    if not getattr(args, "yes", False):
        try:
            answer = input("  Proceed? [Y/n] ").strip().lower()
            if answer and answer not in ("y", "yes"):
                print("Aborted.")
                sys.exit(0)
        except (EOFError, KeyboardInterrupt):
            print("\nAborted.")
            sys.exit(0)

    print()

    run_state_machine(
        epic_number=args.epic,
        dry_run=args.dry_run,
        max_iterations=args.max_iterations,
    )


def cmd_validate(args: argparse.Namespace) -> None:
    """Run pre-flight validation on epic tasks."""
    validate_script = PROJECT_ROOT / "scripts" / "validate_tasks.py"
    cmd = [sys.executable, str(validate_script), str(args.epic)]
    if args.strict:
        cmd.append("--strict")
    result = subprocess.run(cmd, cwd=PROJECT_ROOT)
    sys.exit(result.returncode)


def cmd_status(args: argparse.Namespace) -> None:
    """Show epic status from .tasks/ files."""
    epic_dir = TASKS_BASE / f"E{args.epic}"

    if not epic_dir.exists():
        die(f"Epic directory not found: {epic_dir}")

    tasks = parse_all_tasks(epic_dir, args.epic)
    if not tasks:
        die("No tasks found in epic directory")

    # Rebuild index to ensure it's current
    rebuild_index(epic_dir, args.epic)

    # Print status
    complete = [t for t in tasks if t.state == "complete"]
    blocked = [t for t in tasks if t.state != "complete" and t.blocked_by_incomplete]
    actionable = [t for t in tasks if t.state != "complete" and not t.blocked_by_incomplete]

    print(f"=== Epic E{args.epic} Status ===")
    print(
        f"  Total: {len(tasks)} | Complete: {len(complete)} | Actionable: {len(actionable)} | Blocked: {len(blocked)}"
    )
    print()

    if actionable:
        print("Actionable:")
        for t in sorted(actionable, key=lambda x: x.task_id):
            print(f"  T{t.task_id} [{t.state}] {t.title}")

    if blocked:
        print()
        print("Blocked:")
        for t in sorted(blocked, key=lambda x: x.task_id):
            blockers = ", ".join(f"T{b}" for b in t.blocked_by_incomplete)
            print(f"  T{t.task_id} [{t.state}] {t.title} (by: {blockers})")

    if complete:
        print()
        print(
            f"Complete: {', '.join(f'T{t.task_id}' for t in sorted(complete, key=lambda x: x.task_id))}"
        )

    # Print index.md path
    print()
    print(f"Index: {(epic_dir / 'index.md').relative_to(PROJECT_ROOT)}")


def cmd_dispatch(args: argparse.Namespace) -> None:
    """Dispatch a single agent."""
    if args.project and args.project not in VALID_PROJECTS:
        die(
            f"Invalid project '{args.project}'. Must be one of: {', '.join(sorted(VALID_PROJECTS))}"
        )

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
              python scripts/run_epic.py validate 42
              python scripts/run_epic.py status 42
              python scripts/run_epic.py dispatch test-author "Write tests for T43"
              python scripts/run_epic.py dispatch implementer --project webapp "Implement T44"
        """),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # --- run ---
    run_parser = subparsers.add_parser("run", help="Run TDD state machine for an epic")
    run_parser.add_argument("epic", type=int, help="Epic issue number")
    run_parser.add_argument(
        "--dry-run", action="store_true", help="Show what would happen without dispatching agents"
    )
    run_parser.add_argument(
        "--max-iterations", type=int, default=50, help="Max state machine iterations (default: 50)"
    )
    run_parser.add_argument(
        "--yes", "-y", action="store_true", help="Skip approval screen confirmation"
    )
    run_parser.set_defaults(func=cmd_run)

    # --- validate ---
    validate_parser = subparsers.add_parser("validate", help="Pre-flight validation of epic tasks")
    validate_parser.add_argument("epic", type=int, help="Epic issue number")
    validate_parser.add_argument("--strict", action="store_true", help="Treat warnings as errors")
    validate_parser.set_defaults(func=cmd_validate)

    # --- status ---
    status_parser = subparsers.add_parser("status", help="Show epic task status")
    status_parser.add_argument("epic", type=int, help="Epic issue number")
    status_parser.set_defaults(func=cmd_status)

    # --- dispatch ---
    dispatch_parser = subparsers.add_parser("dispatch", help="Dispatch a single agent")
    dispatch_parser.add_argument("agent", help="Agent name (e.g., test-author, implementer)")
    dispatch_parser.add_argument("prompt", help="Prompt for the agent")
    dispatch_parser.add_argument(
        "--project", help="Workspace project (core, audio, t3k, webapp, worker, scheduler)"
    )
    dispatch_parser.add_argument(
        "--max-turns", type=int, default=20, help="Max conversation turns (default: 20)"
    )
    dispatch_parser.set_defaults(func=cmd_dispatch)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
