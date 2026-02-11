#!/usr/bin/env python3
"""
Snapshot and verify test file integrity for TDD enforcement.

Usage:
    python scripts/snapshot_tests.py save E42-T43
    python scripts/snapshot_tests.py verify E42-T43
    python scripts/snapshot_tests.py diff E42-T43
"""

import hashlib
import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

# GTS Python test patterns
TEST_PATTERNS = [
    "tests/unit/**/*.py",
    "tests/integration/**/*.py",
    "tests/regression/**/*.py",
    "tests/e2e/python/tests/**/*.py",
]


@dataclass
class FileSnapshot:
    path: str
    sha256: str
    size: int
    modified: str


@dataclass
class TestSnapshot:
    task_id: str
    created: str
    commit: str
    files: list[FileSnapshot]


def get_current_commit() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()[:12] if result.returncode == 0 else "unknown"


def hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def collect_test_files() -> list[Path]:
    """Collect all test files matching GTS patterns."""
    files = []
    for pattern in TEST_PATTERNS:
        files.extend(Path().glob(pattern))
    # Exclude __pycache__, .venv, conftest.py (fixtures, not tests)
    files = [
        f
        for f in files
        if "__pycache__" not in str(f)
        and ".venv" not in str(f)
        and f.name != "conftest.py"
        and f.name.startswith("test_")  # Only actual test files
    ]
    return sorted(set(files))


def collect_locked_test_files(task_id: str) -> list[Path]:
    """Collect only test files from the task's lock commit.

    Finds the lock commit (git log --grep="test-lock: {task_id}")
    and extracts only the test files that were part of that commit.
    """
    # Find the lock commit
    result = subprocess.run(
        ["git", "log", f"--grep=test-lock: {task_id}", "-1", "--format=%H"],
        capture_output=True,
        text=True,
    )
    lock_commit = result.stdout.strip()
    if not lock_commit:
        print(f"WARNING: No lock commit found for {task_id}")
        return []

    # Extract test files from that commit
    result = subprocess.run(
        ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", lock_commit, "--", "tests/"],
        capture_output=True,
        text=True,
    )
    paths = []
    for line in result.stdout.strip().splitlines():
        p = Path(line)
        if p.exists() and p.name.startswith("test_"):
            paths.append(p)

    return sorted(paths)


def get_snapshot_dir(task_id: str) -> Path:
    """Find or create snapshot directory for task.

    Locates the epic directory by searching for the task file (e.g. T34.md)
    under .tasks/, then returns the sibling snapshots/ directory.
    """
    # Extract numeric part from task_id (e.g. "T34" -> "34")
    num = task_id.lstrip("T")
    task_filename = f"T{num}.md"

    # Search for the task file to find the correct epic.
    # When multiple epics contain the same task ID, prefer the highest
    # epic number (most recent epic).
    candidates: list[tuple[int, Path]] = []
    for task_file in Path(".tasks").rglob(task_filename):
        # Task files live at .tasks/E{n}/tasks/T{n}.md
        # Epic dir is the grandparent of the task file
        epic_dir = task_file.parent.parent
        if epic_dir.name.startswith("E"):
            epic_num = int(epic_dir.name[1:]) if epic_dir.name[1:].isdigit() else 0
            candidates.append((epic_num, epic_dir))
    if candidates:
        # Pick the highest epic number
        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates[0][1] / "snapshots"

    # Default location
    return Path(".tasks/snapshots")


def create_snapshot(task_id: str) -> TestSnapshot:
    """Create snapshot of only the task's locked test files."""
    locked_files = collect_locked_test_files(task_id)
    if not locked_files:
        print(f"WARNING: No locked test files found for {task_id}, falling back to all test files")
        locked_files = collect_test_files()

    files = []
    for path in locked_files:
        stat = path.stat()
        files.append(
            FileSnapshot(
                path=str(path),
                sha256=hash_file(path),
                size=stat.st_size,
                modified=datetime.fromtimestamp(stat.st_mtime, UTC).isoformat(),
            )
        )

    # Store the lock commit hash
    result = subprocess.run(
        ["git", "log", f"--grep=test-lock: {task_id}", "-1", "--format=%H"],
        capture_output=True,
        text=True,
    )
    lock_commit = result.stdout.strip()[:12] or get_current_commit()

    return TestSnapshot(
        task_id=task_id,
        created=datetime.now(UTC).isoformat(),
        commit=lock_commit,
        files=files,
    )


def save_snapshot(task_id: str, snapshot_dir: Path | None = None):
    """Save snapshot before implementation phase."""
    snapshot = create_snapshot(task_id)

    if snapshot_dir is None:
        snapshot_dir = get_snapshot_dir(task_id)

    snapshot_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = snapshot_dir / f"{task_id}.json"

    snapshot_path.write_text(json.dumps(asdict(snapshot), indent=2))
    print(f"✓ Snapshot saved: {snapshot_path}")
    print(f"  {len(snapshot.files)} test files captured at commit {snapshot.commit}")

    return snapshot_path


def load_snapshot(task_id: str, snapshot_dir: Path | None = None) -> TestSnapshot | None:
    if snapshot_dir is None:
        snapshot_dir = get_snapshot_dir(task_id)

    snapshot_path = snapshot_dir / f"{task_id}.json"

    if not snapshot_path.exists():
        # Try searching
        for path in Path(".tasks").rglob(f"{task_id}.json"):
            snapshot_path = path
            break

    if not snapshot_path.exists():
        return None

    data = json.loads(snapshot_path.read_text())
    return TestSnapshot(
        task_id=data["task_id"],
        created=data["created"],
        commit=data["commit"],
        files=[FileSnapshot(**f) for f in data["files"]],
    )


def verify_snapshot(task_id: str, snapshot_dir: Path | None = None) -> tuple[bool, list[dict]]:
    """Verify locked test files unchanged since snapshot.

    Only checks the task's own test files (from the lock commit).
    Does NOT check for added files — that's enforced by agent instructions.
    """
    snapshot = load_snapshot(task_id, snapshot_dir)
    if not snapshot:
        return False, [{"error": f"No snapshot found for {task_id}"}]

    violations = []
    snapshot_files = {f.path: f for f in snapshot.files}

    # Check for modifications and deletions of locked test files only
    for path, expected in snapshot_files.items():
        current_path = Path(path)

        if not current_path.exists():
            violations.append(
                {
                    "type": "DELETED",
                    "path": path,
                    "message": "Locked test file deleted during implementation",
                }
            )
            continue

        current_hash = hash_file(current_path)
        if current_hash != expected.sha256:
            violations.append(
                {
                    "type": "MODIFIED",
                    "path": path,
                    "expected_hash": expected.sha256[:12],
                    "actual_hash": current_hash[:12],
                    "message": "Locked test file modified during implementation",
                }
            )

    passed = len(violations) == 0

    if passed:
        print(f"✓ All {len(snapshot.files)} locked test files unchanged since {snapshot.commit}")
    else:
        print(f"✗ {len(violations)} violation(s) detected:")
        for v in violations:
            print(f"  {v['type']}: {v['path']}")
            print(f"    {v['message']}")

    return passed, violations


def diff_snapshot(task_id: str, snapshot_dir: Path | None = None):
    """Show detailed diff of changes since snapshot."""
    snapshot = load_snapshot(task_id, snapshot_dir)
    if not snapshot:
        print(f"No snapshot found for {task_id}")
        return

    print(f"Changes since snapshot at {snapshot.commit}:\n")

    for f in snapshot.files:
        result = subprocess.run(
            ["git", "diff", snapshot.commit, "--", f.path],
            capture_output=True,
            text=True,
        )
        if result.stdout:
            print(f"--- {f.path} ---")
            print(result.stdout)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="TDD test file snapshot manager")
    parser.add_argument("command", choices=["save", "verify", "diff", "list"])
    parser.add_argument("task_id", nargs="?", help="Task identifier (e.g., E42-T43)")
    parser.add_argument("--snapshot-dir", type=Path, help="Override snapshot directory")

    args = parser.parse_args()

    if args.command == "list":
        files = collect_test_files()
        print(f"Found {len(files)} test files:")
        for f in files:
            print(f"  {f}")
        return

    if not args.task_id:
        parser.error(f"{args.command} requires task_id")

    if args.command == "save":
        save_snapshot(args.task_id, args.snapshot_dir)
    elif args.command == "verify":
        passed, violations = verify_snapshot(args.task_id, args.snapshot_dir)
        sys.exit(0 if passed else 1)
    elif args.command == "diff":
        diff_snapshot(args.task_id, args.snapshot_dir)


if __name__ == "__main__":
    main()
