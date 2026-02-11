#!/usr/bin/env -S python3 -u
"""
Automated epic review with mock analysis and product functionality assessment.

Scans completed epics for mock violations, test quality metrics,
and product functionality indicators.

Usage:
    python scripts/epic_reviewer.py 111
    python scripts/epic_reviewer.py 111 --output-dir /custom/path
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TASKS_BASE = PROJECT_ROOT / ".tasks" / "projects" / "guitar-tone-shootout" / "epics"

# ---------------------------------------------------------------------------
# Mock detection patterns
# ---------------------------------------------------------------------------

MOCK_PATTERNS = [
    (r"from unittest\.mock import", "mock_import", "unittest.mock import"),
    (r"from unittest import mock", "mock_import", "unittest.mock import"),
    (r"@patch\(", "mock_patch", "@patch decorator"),
    (r"@patch\.object\(", "mock_patch", "@patch.object decorator"),
    (r"\bMock\(", "mock_usage", "Mock() constructor"),
    (r"\bMagicMock\(", "mock_usage", "MagicMock() constructor"),
    (r"\bAsyncMock\(", "mock_usage", "AsyncMock() constructor"),
    (r"\.return_value\s*=", "mock_config", ".return_value assignment"),
    (r"\.side_effect\s*=", "mock_config", ".side_effect assignment"),
    (r"\.assert_called", "mock_assertion", ".assert_called* assertion"),
    (r"\.call_args", "mock_assertion", ".call_args access"),
    (r"\.call_count", "mock_assertion", ".call_count access"),
]

# Real assertion patterns (assertions against actual objects, not mocks)
REAL_ASSERTION_PATTERNS = [
    r"assert\s+.*\.status_code\s*==",  # HTTP status code
    r"assert\s+.*\.json\(\)",  # JSON response
    r"await\s+expect\(",  # Playwright
    r"assert\s+result\b",  # DB query result
    r"assert\s+saved\b",  # Saved entity
    r"assert\s+.*\.id\b",  # Entity ID
    r"assert\s+.*\.name\b",  # Entity field
    r"assert\s+len\(",  # Collection length
    r"assert\s+.*\s+in\s+",  # Membership
    r"assert\s+.*\s+is\s+not\s+None",  # Existence
    r"assert\s+.*==",  # General equality (broad)
    r"pytest\.raises\(",  # Exception assertion
]

MOCK_ASSERTION_PATTERNS = [
    r"\.assert_called\(",
    r"\.assert_called_once\(",
    r"\.assert_called_with\(",
    r"\.assert_called_once_with\(",
    r"\.assert_not_called\(",
    r"\.assert_any_call\(",
    r"\.call_args",
    r"\.call_count",
]


@dataclass
class MockViolation:
    file: str
    line: int
    pattern: str
    description: str


@dataclass
class FileAnalysis:
    path: str
    total_lines: int
    test_count: int
    mock_lines: int
    mock_violations: list[MockViolation]
    real_assertions: int
    mock_assertions: int
    has_mocks: bool


@dataclass
class TaskAnalysis:
    task_id: str
    title: str
    state: str
    test_files: list[FileAnalysis]
    impl_files: list[str]
    commits: list[str]
    mock_density: float  # mock_lines / total_lines
    real_assertion_ratio: float  # real / (real + mock) assertions


@dataclass
class EpicReview:
    epic_number: int
    title: str
    tasks: list[TaskAnalysis]
    total_test_files: int
    files_with_mocks: int
    files_without_mocks: int
    overall_mock_density: float
    overall_real_assertion_ratio: float
    all_violations: list[MockViolation]


# ---------------------------------------------------------------------------
# File analysis
# ---------------------------------------------------------------------------


def analyse_test_file(path: Path) -> FileAnalysis:
    """Analyse a single test file for mock usage and assertion quality."""
    try:
        content = path.read_text()
    except Exception:
        return FileAnalysis(
            path=str(path),
            total_lines=0,
            test_count=0,
            mock_lines=0,
            mock_violations=[],
            real_assertions=0,
            mock_assertions=0,
            has_mocks=False,
        )

    lines = content.splitlines()
    total_lines = len(lines)

    # Count tests
    test_count = len(re.findall(r"^(?:async\s+)?def test_", content, re.MULTILINE))

    # Find mock violations
    violations: list[MockViolation] = []
    mock_line_numbers: set[int] = set()

    for i, line in enumerate(lines, 1):
        for pattern, _type, description in MOCK_PATTERNS:
            if re.search(pattern, line):
                violations.append(
                    MockViolation(
                        file=str(path),
                        line=i,
                        pattern=pattern,
                        description=description,
                    )
                )
                mock_line_numbers.add(i)

    # Count real vs mock assertions
    real_assertions = 0
    mock_assertions = 0

    for line in lines:
        for pattern in REAL_ASSERTION_PATTERNS:
            if re.search(pattern, line):
                real_assertions += 1
                break
        for pattern in MOCK_ASSERTION_PATTERNS:
            if re.search(pattern, line):
                mock_assertions += 1
                break

    has_mocks = len(violations) > 0

    return FileAnalysis(
        path=str(path),
        total_lines=total_lines,
        test_count=test_count,
        mock_lines=len(mock_line_numbers),
        mock_violations=violations,
        real_assertions=real_assertions,
        mock_assertions=mock_assertions,
        has_mocks=has_mocks,
    )


# ---------------------------------------------------------------------------
# Git analysis
# ---------------------------------------------------------------------------


def get_epic_commits(epic_number: int) -> list[dict]:
    """Get commits related to an epic from git log."""
    result = subprocess.run(
        [
            "git",
            "log",
            "--oneline",
            f"--grep=T{epic_number}",
            "--grep=E{epic_number}",
            "--all-match",
            "--format=%H %s",
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    # Also search for task-specific commits
    task_commits: list[dict] = []
    for line in result.stdout.strip().splitlines():
        if not line:
            continue
        parts = line.split(" ", 1)
        task_commits.append({"hash": parts[0], "message": parts[1] if len(parts) > 1 else ""})

    return task_commits


def get_files_for_task(task_id: str) -> tuple[list[str], list[str]]:
    """Get test and implementation files associated with a task from git."""
    # Find lock commit for this task
    result = subprocess.run(
        ["git", "log", f"--grep=test-lock: {task_id}", "-1", "--format=%H"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    lock_hash = result.stdout.strip()

    # Find impl commit for this task
    result = subprocess.run(
        ["git", "log", f"--grep=impl: {task_id}", "-1", "--format=%H"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    impl_hash = result.stdout.strip()

    test_files: list[str] = []
    impl_files: list[str] = []

    if lock_hash:
        result = subprocess.run(
            ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", lock_hash],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
        )
        for f in result.stdout.strip().splitlines():
            if f.startswith("tests/") and f.endswith(".py"):
                test_files.append(f)

    if impl_hash:
        result = subprocess.run(
            ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", impl_hash],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
        )
        for f in result.stdout.strip().splitlines():
            if not f.startswith("tests/") and not f.startswith(".tasks/"):
                impl_files.append(f)

    return test_files, impl_files


# ---------------------------------------------------------------------------
# Task analysis
# ---------------------------------------------------------------------------


def parse_task_file(path: Path) -> dict:
    """Parse a task file for metadata."""
    content = path.read_text()

    match = re.match(r"T(\d+)\.md", path.name)
    task_id = match.group(1) if match else "0"

    title_match = re.search(r"^# T\d+:\s*(.+)$", content, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else path.stem

    state = "pending"
    state_match = re.search(r"\|\s*State\s*\|\s*(\w+)\s*\|", content, re.IGNORECASE)
    if state_match:
        state = state_match.group(1).strip().lower()

    return {"task_id": task_id, "title": title, "state": state}


def analyse_task(epic_number: int, task_meta: dict) -> TaskAnalysis:
    """Analyse a single task for mock usage and quality."""
    task_id = f"T{task_meta['task_id']}"

    test_files_paths, impl_files = get_files_for_task(task_id)

    # Analyse each test file
    file_analyses: list[FileAnalysis] = []
    for tf in test_files_paths:
        full_path = PROJECT_ROOT / tf
        if full_path.exists():
            file_analyses.append(analyse_test_file(full_path))

    # Calculate task-level metrics
    total_test_lines = sum(fa.total_lines for fa in file_analyses)
    total_mock_lines = sum(fa.mock_lines for fa in file_analyses)
    total_real = sum(fa.real_assertions for fa in file_analyses)
    total_mock_asserts = sum(fa.mock_assertions for fa in file_analyses)

    mock_density = total_mock_lines / total_test_lines if total_test_lines > 0 else 0.0
    total_asserts = total_real + total_mock_asserts
    real_ratio = total_real / total_asserts if total_asserts > 0 else 1.0

    # Get commits
    commits = []
    for prefix in ["test-lock:", "impl:", "chore: mark", "chore: Mark"]:
        result = subprocess.run(
            ["git", "log", f"--grep={prefix} {task_id}", "-1", "--format=%H %s"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
        )
        if result.stdout.strip():
            commits.append(result.stdout.strip())

    return TaskAnalysis(
        task_id=task_id,
        title=task_meta["title"],
        state=task_meta["state"],
        test_files=file_analyses,
        impl_files=impl_files,
        commits=commits,
        mock_density=mock_density,
        real_assertion_ratio=real_ratio,
    )


# ---------------------------------------------------------------------------
# Epic-level review
# ---------------------------------------------------------------------------


def review_epic(epic_number: int) -> EpicReview:
    """Generate a full review of an epic."""
    epic_dir = TASKS_BASE / f"E{epic_number}"
    if not epic_dir.exists():
        print(f"Error: Epic directory not found: {epic_dir}", file=sys.stderr)
        sys.exit(1)

    # Parse epic title from index.md
    title = f"Epic E{epic_number}"
    index_path = epic_dir / "index.md"
    if index_path.exists():
        content = index_path.read_text()
        title_match = re.search(r"^# E\d+:\s*(.+)$", content, re.MULTILINE)
        if title_match:
            title = title_match.group(1).strip()

    # Parse all tasks
    tasks_dir = epic_dir / "tasks"
    task_analyses: list[TaskAnalysis] = []

    if tasks_dir.exists():
        for task_path in sorted(tasks_dir.glob("T*.md")):
            meta = parse_task_file(task_path)
            analysis = analyse_task(epic_number, meta)
            task_analyses.append(analysis)

    # Aggregate metrics
    all_test_files = [fa for ta in task_analyses for fa in ta.test_files]
    files_with_mocks = sum(1 for fa in all_test_files if fa.has_mocks)
    files_without_mocks = sum(1 for fa in all_test_files if not fa.has_mocks)

    total_test_lines = sum(fa.total_lines for fa in all_test_files)
    total_mock_lines = sum(fa.mock_lines for fa in all_test_files)
    total_real = sum(fa.real_assertions for fa in all_test_files)
    total_mock_asserts = sum(fa.mock_assertions for fa in all_test_files)

    overall_density = total_mock_lines / total_test_lines if total_test_lines > 0 else 0.0
    total_asserts = total_real + total_mock_asserts
    overall_ratio = total_real / total_asserts if total_asserts > 0 else 1.0

    all_violations = [v for fa in all_test_files for v in fa.mock_violations]

    return EpicReview(
        epic_number=epic_number,
        title=title,
        tasks=task_analyses,
        total_test_files=len(all_test_files),
        files_with_mocks=files_with_mocks,
        files_without_mocks=files_without_mocks,
        overall_mock_density=overall_density,
        overall_real_assertion_ratio=overall_ratio,
        all_violations=all_violations,
    )


# ---------------------------------------------------------------------------
# Output generation
# ---------------------------------------------------------------------------


def generate_review_md(review: EpicReview) -> str:
    """Generate REVIEW.md content."""
    lines = [
        f"# Epic Review: E{review.epic_number} — {review.title}",
        "",
        f"**Generated:** {datetime.now(UTC).isoformat()}",
        "",
        "## Mock Analysis",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Total test files | {review.total_test_files} |",
        f"| Files with mocks | {review.files_with_mocks} |",
        f"| Files without mocks | {review.files_without_mocks} |",
        f"| Mock density | {review.overall_mock_density:.1%} |",
        f"| Real assertion ratio | {review.overall_real_assertion_ratio:.1%} |",
        f"| Total violations | {len(review.all_violations)} |",
        "",
    ]

    if review.all_violations:
        lines.extend(
            [
                "### Mock Violations",
                "",
                "| File | Line | Pattern |",
                "|------|------|---------|",
            ]
        )
        for v in review.all_violations:
            rel_path = v.file.replace(str(PROJECT_ROOT) + "/", "")
            lines.append(f"| `{rel_path}` | {v.line} | {v.description} |")
        lines.append("")

    lines.extend(
        [
            "## Per-Task Metrics",
            "",
            "| Task | Title | State | Tests | Mock Density | Real Assert % | Violations |",
            "|------|-------|-------|-------|-------------|---------------|------------|",
        ]
    )

    for ta in review.tasks:
        test_count = sum(fa.test_count for fa in ta.test_files)
        violation_count = sum(len(fa.mock_violations) for fa in ta.test_files)
        lines.append(
            f"| {ta.task_id} | {ta.title[:30]} | {ta.state} | {test_count} "
            f"| {ta.mock_density:.1%} | {ta.real_assertion_ratio:.1%} | {violation_count} |"
        )

    lines.extend(
        [
            "",
            "## Product Functionality Assessment",
            "",
            "For each task, check whether implementation files create working, wired-in code",
            "(routes registered, services connected, consumers active) vs stub/mock-compatible shells.",
            "",
        ]
    )

    for ta in review.tasks:
        if ta.impl_files:
            lines.append(f"### {ta.task_id}: {ta.title}")
            lines.append("")
            lines.append("**Implementation files:**")
            for f in ta.impl_files:
                lines.append(f"- `{f}`")
            lines.append("")

    lines.extend(
        [
            "## Test Quality Score",
            "",
            f"- **Mock-free test percentage:** {review.files_without_mocks}/{review.total_test_files} "
            f"({review.files_without_mocks / review.total_test_files * 100:.0f}%)"
            if review.total_test_files > 0
            else "- **Mock-free test percentage:** N/A",
            f"- **Real assertion ratio:** {review.overall_real_assertion_ratio:.1%}",
            f"- **Mock density:** {review.overall_mock_density:.1%}",
        ]
    )

    return "\n".join(lines) + "\n"


def generate_review_json(review: EpicReview) -> dict:
    """Generate review-data.json content."""
    return {
        "epic": {
            "number": review.epic_number,
            "title": review.title,
            "task_count": len(review.tasks),
        },
        "tasks": [
            {
                "id": ta.task_id,
                "title": ta.title,
                "state": ta.state,
                "test_count": sum(fa.test_count for fa in ta.test_files),
                "test_files": [fa.path for fa in ta.test_files],
                "impl_files": ta.impl_files,
                "mock_density": round(ta.mock_density, 3),
                "real_assertion_ratio": round(ta.real_assertion_ratio, 3),
                "violation_count": sum(len(fa.mock_violations) for fa in ta.test_files),
            }
            for ta in review.tasks
        ],
        "metrics": {
            "total_test_files": review.total_test_files,
            "files_with_mocks": review.files_with_mocks,
            "files_without_mocks": review.files_without_mocks,
            "mock_density": round(review.overall_mock_density, 3),
            "real_assertion_ratio": round(review.overall_real_assertion_ratio, 3),
            "total_violations": len(review.all_violations),
            "mock_violations": [
                {
                    "file": v.file.replace(str(PROJECT_ROOT) + "/", ""),
                    "line": v.line,
                    "pattern": v.pattern,
                    "description": v.description,
                }
                for v in review.all_violations
            ],
        },
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Automated epic review with mock analysis")
    parser.add_argument("epic", type=int, help="Epic number to review")
    parser.add_argument("--output-dir", type=Path, help="Override output directory")
    args = parser.parse_args()

    print(f"Reviewing Epic E{args.epic}...")
    review = review_epic(args.epic)

    output_dir = args.output_dir or TASKS_BASE / f"E{args.epic}"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Write REVIEW.md
    review_md = generate_review_md(review)
    review_path = output_dir / "REVIEW.md"
    review_path.write_text(review_md)
    print(f"  Written: {review_path}")

    # Write review-data.json
    review_data = generate_review_json(review)
    data_path = output_dir / "review-data.json"
    data_path.write_text(json.dumps(review_data, indent=2) + "\n")
    print(f"  Written: {data_path}")

    # Summary
    print()
    print(f"=== E{args.epic} Review Summary ===")
    print(f"  Tasks: {len(review.tasks)}")
    print(f"  Test files: {review.total_test_files} ({review.files_with_mocks} with mocks)")
    print(f"  Mock density: {review.overall_mock_density:.1%}")
    print(f"  Real assertion ratio: {review.overall_real_assertion_ratio:.1%}")
    print(f"  Total violations: {len(review.all_violations)}")

    if review.all_violations:
        print()
        print("  Top violations:")
        seen: set[str] = set()
        for v in review.all_violations[:10]:
            rel_path = v.file.replace(str(PROJECT_ROOT) + "/", "")
            key = f"{rel_path}:{v.line}"
            if key not in seen:
                seen.add(key)
                print(f"    {rel_path}:{v.line} — {v.description}")


if __name__ == "__main__":
    main()
