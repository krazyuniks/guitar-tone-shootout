"""Atomic lifecycle operations for worktree management.

This module provides atomic, all-or-nothing operations for:
- setup: Create worktree + start services
- complete: Merge PR + close GitHub issue + teardown
"""

import contextlib
import json
import subprocess
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from rich.console import Console

console = Console()

# Timeout for pending operations (seconds)
PENDING_TIMEOUT_SECONDS = 120  # 2 minutes


class OperationStatus(StrEnum):
    """Status of a lifecycle operation."""

    PENDING = "pending"
    COMPLETE = "complete"
    FAILED = "failed"


@dataclass
class OperationState:
    """State of a lifecycle operation."""

    operation: str
    status: OperationStatus
    started_at: str
    completed_at: str | None = None
    error: str | None = None
    issue_number: int | None = None
    pr_number: int | None = None


class LifecycleError(Exception):
    """Raised when a lifecycle operation fails."""

    pass


def get_state_file() -> Path:
    """Get the path to the state file."""
    from .config import get_worktree_root

    state_dir = get_worktree_root() / ".worktree"
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir / "lifecycle_state.json"


def load_state() -> dict[str, Any]:
    """Load the state from the state file."""
    state_file = get_state_file()
    if state_file.exists():
        result: dict[str, Any] = json.loads(state_file.read_text())
        return result
    return {"operations": {}}


def save_state(state: dict[str, Any]) -> None:
    """Save the state to the state file."""
    state_file = get_state_file()
    state_file.write_text(json.dumps(state, indent=2))


def mark_pending(operation_id: str, **kwargs) -> None:
    """Mark an operation as pending."""
    state = load_state()
    state["operations"][operation_id] = {
        "status": OperationStatus.PENDING.value,
        "started_at": datetime.now(UTC).isoformat(),
        **kwargs,
    }
    save_state(state)


def mark_complete(operation_id: str) -> None:
    """Mark an operation as complete."""
    state = load_state()
    if operation_id in state["operations"]:
        state["operations"][operation_id]["status"] = OperationStatus.COMPLETE.value
        state["operations"][operation_id]["completed_at"] = datetime.now(UTC).isoformat()
        save_state(state)


def mark_failed(operation_id: str, error: str) -> None:
    """Mark an operation as failed."""
    state = load_state()
    if operation_id in state["operations"]:
        state["operations"][operation_id]["status"] = OperationStatus.FAILED.value
        state["operations"][operation_id]["completed_at"] = datetime.now(UTC).isoformat()
        state["operations"][operation_id]["error"] = error
        save_state(state)


def get_stale_operations(
    worktree_root: Path | None = None,
    stale_threshold_minutes: int = 30,
) -> list[dict[str, Any]]:
    """Find operations that appear stuck/stale.

    This is the enhanced version that provides detailed information about
    stale operations for diagnosis and recovery.

    Args:
        worktree_root: Root directory containing worktrees. If None, uses default.
        stale_threshold_minutes: Operations older than this are considered stale.
            Default is 30 minutes for safety (conservative).

    Returns:
        List of dicts with:
            - operation_id: The operation identifier (e.g., "complete-123")
            - operation_type: Type of operation ("setup", "teardown", "complete")
            - worktree_path: Path to affected worktree (if determinable)
            - started_at: ISO timestamp when operation started
            - duration_minutes: How long the operation has been pending
            - status: Current status (should be "pending" for stale ops)
            - details: Additional operation-specific data
    """
    state = load_state()
    stale = []
    now = datetime.now(UTC)
    threshold_seconds = stale_threshold_minutes * 60

    for op_id, op_data in state["operations"].items():
        if op_data.get("status") == OperationStatus.PENDING.value:
            started = datetime.fromisoformat(op_data["started_at"])
            elapsed_seconds = (now - started).total_seconds()

            if elapsed_seconds > threshold_seconds:
                # Parse operation type from ID (format: "type-identifier")
                op_type = "unknown"
                if "-" in op_id:
                    op_type = op_id.split("-")[0]

                # Try to determine worktree path from operation data
                worktree_path = op_data.get("worktree_path")

                stale.append(
                    {
                        "operation_id": op_id,
                        "operation_type": op_type,
                        "worktree_path": worktree_path,
                        "started_at": op_data["started_at"],
                        "duration_minutes": round(elapsed_seconds / 60, 1),
                        "status": op_data["status"],
                        "details": {
                            k: v
                            for k, v in op_data.items()
                            if k not in ("status", "started_at", "worktree_path")
                        },
                    }
                )

    return stale


def get_stale_operations_simple() -> list[tuple[str, dict]]:
    """Get operations that have been pending for too long.

    This is the original simple version used internally.
    Uses the default PENDING_TIMEOUT_SECONDS (2 minutes).

    Returns:
        List of (operation_id, operation_data) tuples.
    """
    state = load_state()
    stale = []
    now = datetime.now(UTC)

    for op_id, op_data in state["operations"].items():
        if op_data["status"] == OperationStatus.PENDING.value:
            started = datetime.fromisoformat(op_data["started_at"])
            elapsed = (now - started).total_seconds()
            if elapsed > PENDING_TIMEOUT_SECONDS:
                stale.append((op_id, op_data))

    return stale


def clear_stale_operation(
    worktree_path: Path | None = None,
    operation_type: str | None = None,
    operation_id: str | None = None,
    force: bool = False,
    stale_threshold_minutes: int = 30,
) -> bool:
    """Clear a stale lifecycle operation.

    This is used when a setup/teardown/complete operation was interrupted
    and left the worktree in a stuck state. The operation state is removed
    from the lifecycle state file.

    You must provide either operation_id directly, or both worktree_path and
    operation_type to find the operation.

    Args:
        worktree_path: Path to the worktree (used with operation_type to find op)
        operation_type: Type of operation ("setup", "teardown", "complete")
        operation_id: Direct operation ID to clear (e.g., "complete-123")
        force: If True, clear even if operation appears active (< threshold)
        stale_threshold_minutes: Operations younger than this require force=True

    Returns:
        True if operation was cleared successfully

    Raises:
        ValueError: If operation_type is invalid or required args missing
        RuntimeError: If operation appears active and force=False
    """
    valid_operation_types = {"setup", "teardown", "complete"}

    # Validate inputs
    if operation_id is None:
        if operation_type is None:
            raise ValueError("Must provide either operation_id or operation_type")
        if operation_type not in valid_operation_types:
            raise ValueError(
                f"Invalid operation_type '{operation_type}'. "
                f"Must be one of: {', '.join(sorted(valid_operation_types))}"
            )

    state = load_state()
    operations = state.get("operations", {})
    now = datetime.now(UTC)
    threshold_seconds = stale_threshold_minutes * 60

    # Find the operation to clear
    target_op_id = None
    target_op_data = None

    if operation_id:
        # Direct lookup by ID
        if operation_id in operations:
            target_op_id = operation_id
            target_op_data = operations[operation_id]
        else:
            console.print(f"[yellow]Operation '{operation_id}' not found in state[/yellow]")
            return False
    else:
        # Find by operation_type (and optionally worktree_path)
        for op_id, op_data in operations.items():
            # Check if operation type matches
            if op_id.startswith(f"{operation_type}-"):
                # If worktree_path specified, check it matches
                if worktree_path:
                    op_worktree = op_data.get("worktree_path")
                    if op_worktree and Path(op_worktree) != worktree_path:
                        continue

                target_op_id = op_id
                target_op_data = op_data
                break

        if not target_op_id:
            console.print(
                f"[yellow]No {operation_type} operation found"
                f"{' for ' + str(worktree_path) if worktree_path else ''}[/yellow]"
            )
            return False

    # At this point, both target_op_id and target_op_data are set
    assert target_op_data is not None

    # Check if operation is active (not stale) and force not set
    if target_op_data.get("status") == OperationStatus.PENDING.value:
        started = datetime.fromisoformat(target_op_data["started_at"])
        elapsed_seconds = (now - started).total_seconds()
        elapsed_minutes = elapsed_seconds / 60

        if elapsed_seconds < threshold_seconds and not force:
            raise RuntimeError(
                f"Operation '{target_op_id}' appears active "
                f"(started {elapsed_minutes:.1f} minutes ago). "
                f"Use force=True to clear anyway."
            )

    # Clear the operation
    del state["operations"][target_op_id]
    save_state(state)

    elapsed_info = ""
    if target_op_data.get("started_at"):
        started = datetime.fromisoformat(target_op_data["started_at"])
        elapsed_minutes = (now - started).total_seconds() / 60
        elapsed_info = f" (was pending for {elapsed_minutes:.1f} minutes)"

    console.print(f"[green]Cleared stale operation:[/green] {target_op_id}{elapsed_info}")

    return True


def clear_all_stale_operations(
    stale_threshold_minutes: int = 30,
    dry_run: bool = False,
) -> list[str]:
    """Clear all stale operations at once.

    Args:
        stale_threshold_minutes: Operations older than this are cleared
        dry_run: If True, just return what would be cleared without clearing

    Returns:
        List of operation IDs that were (or would be) cleared
    """
    stale_ops = get_stale_operations(stale_threshold_minutes=stale_threshold_minutes)

    if not stale_ops:
        console.print("[dim]No stale operations found[/dim]")
        return []

    cleared = []

    for op in stale_ops:
        op_id = op["operation_id"]
        if dry_run:
            console.print(
                f"[yellow]Would clear:[/yellow] {op_id} (pending {op['duration_minutes']:.1f} min)"
            )
        else:
            try:
                # Use force=True since we already verified they're stale
                clear_stale_operation(operation_id=op_id, force=True)
                cleared.append(op_id)
            except Exception as e:
                console.print(f"[red]Failed to clear {op_id}: {e}[/red]")

    if dry_run:
        console.print(f"\n[dim]Dry run - {len(stale_ops)} operations would be cleared[/dim]")
    else:
        console.print(f"\n[green]Cleared {len(cleared)} stale operations[/green]")

    return [op["operation_id"] for op in stale_ops] if dry_run else cleared


def close_github_issue(issue_number: int, cwd: Path | None = None) -> bool:
    """Close a GitHub issue."""
    try:
        result = subprocess.run(
            [
                "gh",
                "issue",
                "close",
                str(issue_number),
                "--reason",
                "completed",
                "--repo",
                "krazyuniks/guitar-tone-shootout",
            ],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        # Ignore "already closed" errors
        return result.returncode == 0 or "already closed" in result.stderr.lower()
    except Exception:
        return False


def get_pr_info(pr_number: int, cwd: Path | None = None) -> dict[str, Any]:
    """Get PR information including state, linked issue, and merge commit.

    Returns dict with keys:
        - state: OPEN, MERGED, or CLOSED
        - headRefName: branch name
        - number: PR number
        - body: PR description
        - title: PR title
        - mergeCommit: {oid: str} if merged, else None
    """
    try:
        result = subprocess.run(
            [
                "gh",
                "pr",
                "view",
                str(pr_number),
                "--json",
                "state,headRefName,number,body,title,mergeCommit",
                "--repo",
                "krazyuniks/guitar-tone-shootout",
            ],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            pr_info: dict[str, Any] = json.loads(result.stdout)
            return pr_info
    except Exception:
        pass
    return {}


def extract_issue_from_branch(branch: str) -> int | None:
    """Extract issue number from branch name like '221/feature-name'."""
    if "/" in branch:
        try:
            return int(branch.split("/")[0])
        except ValueError:
            pass
    return None


class SetupResult:
    """Result of a setup operation."""

    def __init__(
        self,
        success: bool,
        worktree_path: Path | None = None,
        error: str | None = None,
    ):
        self.success = success
        self.worktree_path = worktree_path
        self.error = error


class CompleteResult:
    """Result of a complete operation."""

    def __init__(
        self,
        success: bool,
        pr_merged: bool = False,
        main_updated: bool = False,
        issue_closed: bool = False,
        worktree_removed: bool = False,
        error: str | None = None,
    ):
        self.success = success
        self.pr_merged = pr_merged
        self.main_updated = main_updated
        self.issue_closed = issue_closed
        self.worktree_removed = worktree_removed
        self.error = error

    def print_status(self) -> None:
        """Print the status of each step."""

        def status_icon(val: bool) -> str:
            return "[green]✓[/green]" if val else "[red]✗[/red]"

        console.print(f"  {status_icon(self.pr_merged)} PR merged")
        console.print(f"  {status_icon(self.main_updated)} Main branch updated")
        console.print(f"  {status_icon(self.issue_closed)} GitHub issue closed")
        console.print(f"  {status_icon(self.worktree_removed)} Worktree removed")


def update_main_branch(
    main_path: Path,
    expected_merge_sha: str | None = None,
    retries: int = 5,
) -> bool:
    """Update the main branch to latest origin/main.

    This MUST be called after merging a PR to ensure local main is up to date.

    Args:
        main_path: Path to the main worktree
        expected_merge_sha: If provided, verify this commit is in history after pull.
            Will retry with exponential backoff until commit is present.
        retries: Number of retry attempts (default 5, giving ~30s total wait)

    Returns:
        True if update succeeded and (if provided) merge commit is present
    """
    for attempt in range(retries):
        try:
            # Fetch from origin first
            fetch_result = subprocess.run(
                ["git", "fetch", "origin"],
                cwd=main_path,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if fetch_result.returncode != 0:
                console.print(f"[yellow]Warning: fetch failed: {fetch_result.stderr}[/yellow]")

            # Pull with fast-forward only (should never conflict since main is read-only)
            pull_result = subprocess.run(
                ["git", "pull", "--ff-only", "origin", "main"],
                cwd=main_path,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if pull_result.returncode != 0:
                if attempt < retries - 1:
                    wait_time = 2**attempt  # 1, 2, 4, 8, 16 seconds
                    console.print(f"[yellow]Pull failed, retrying in {wait_time}s...[/yellow]")
                    time.sleep(wait_time)
                    continue
                return False

            # If no expected SHA, just verify pull succeeded
            if not expected_merge_sha:
                return True

            # Verify the merge commit is in our history
            verify_result = subprocess.run(
                ["git", "merge-base", "--is-ancestor", expected_merge_sha, "HEAD"],
                cwd=main_path,
                capture_output=True,
                text=True,
                timeout=10,
            )

            if verify_result.returncode == 0:
                return True  # Merge commit confirmed present

            # Merge commit not present yet - retry with backoff
            if attempt < retries - 1:
                wait_time = 2**attempt  # 1, 2, 4, 8, 16 seconds
                console.print(
                    f"[yellow]Merge commit {expected_merge_sha[:8]} not in history yet, "
                    f"retrying in {wait_time}s (attempt {attempt + 1}/{retries})...[/yellow]"
                )
                time.sleep(wait_time)

        except Exception as e:
            console.print(f"[yellow]Warning: main update failed: {e}[/yellow]")
            if attempt < retries - 1:
                time.sleep(2**attempt)

    console.print(f"[red]Failed to verify merge commit after {retries} attempts[/red]")
    return False


def atomic_complete(
    pr_number: int,
    main_path: Path,
    skip_merge: bool = False,
) -> CompleteResult:
    """Atomically complete a PR lifecycle.

    Steps:
    1. Verify/merge PR
    2. Update main branch (CRITICAL - pull merged changes)
    3. Close GitHub issue
    4. Teardown worktree

    All steps tracked in state file. On failure, reports what completed.
    """
    from .docker import remove_containers
    from .git_ops import (
        GitError,
        delete_branch,
        prune_worktrees,
        remove_worktree,
        should_force_delete_branch,
    )
    from .registry import WorktreeNotFoundError, delete_worktree, get_worktree

    operation_id = f"complete-{pr_number}"
    result = CompleteResult(success=False)

    # Mark operation as pending
    mark_pending(operation_id, pr_number=pr_number)

    try:
        # Step 1: Get PR info and verify state
        pr_info = get_pr_info(pr_number, cwd=main_path)
        if not pr_info:
            raise LifecycleError(f"Could not get PR #{pr_number} info")

        pr_state = pr_info.get("state", "UNKNOWN").upper()
        pr_branch = pr_info.get("headRefName")
        issue_number = extract_issue_from_branch(pr_branch) if pr_branch else None

        # Step 2: Merge PR if needed
        merge_sha: str | None = None

        if pr_state == "MERGED":
            result.pr_merged = True
            # Get existing merge SHA
            merge_commit = pr_info.get("mergeCommit")
            if merge_commit:
                merge_sha = merge_commit.get("oid")
        elif pr_state == "OPEN" and not skip_merge:
            merge_result = subprocess.run(
                [
                    "gh",
                    "pr",
                    "merge",
                    str(pr_number),
                    "--squash",
                    "--auto",
                    "--delete-branch",
                    "--repo",
                    "krazyuniks/guitar-tone-shootout",
                ],
                cwd=main_path,
                capture_output=True,
                text=True,
            )
            if merge_result.returncode != 0:
                raise LifecycleError(f"Failed to merge PR: {merge_result.stderr}")
            result.pr_merged = True

            # Re-fetch PR info to get the merge commit SHA
            # Wait briefly for GitHub to record the merge
            time.sleep(2)
            updated_pr_info = get_pr_info(pr_number, cwd=main_path)
            merge_commit = updated_pr_info.get("mergeCommit")
            if merge_commit:
                merge_sha = merge_commit.get("oid")
        elif pr_state == "CLOSED":
            raise LifecycleError(f"PR #{pr_number} is closed but not merged")
        else:
            result.pr_merged = pr_state == "MERGED"

        # Step 3: Update main branch (CRITICAL - pull merged changes immediately)
        # This ensures local main is up to date before any further operations
        # Pass merge SHA to verify it's present after pull (with retries)
        result.main_updated = update_main_branch(main_path, expected_merge_sha=merge_sha)
        if not result.main_updated:
            console.print("[red]CRITICAL: Failed to update main branch![/red]")
            if merge_sha:
                console.print(f"  Expected merge commit: [cyan]{merge_sha[:12]}[/cyan]")
            console.print("  Run manually: [cyan]cd main && git pull --ff-only[/cyan]")

        # Step 4: Close GitHub issue
        if issue_number:
            result.issue_closed = close_github_issue(issue_number, cwd=main_path)
        else:
            result.issue_closed = True  # No issue to close

        # Step 5: Teardown worktree
        if pr_branch:
            try:
                worktree = get_worktree(pr_branch)
                worktree_path = Path(worktree.worktree_path)

                if worktree_path.exists():
                    # Stop Docker
                    with contextlib.suppress(Exception):
                        remove_containers(worktree, worktree_path)

                    # Remove git worktree
                    with contextlib.suppress(GitError):
                        remove_worktree(worktree_path, force=True)

                    prune_worktrees()

                    # Delete branch
                    # Use force delete for squash-merged branches (commits not in git history)
                    try:
                        force = should_force_delete_branch(worktree.branch)
                        delete_branch(worktree.branch, force=force)
                    except GitError:
                        pass

                # Update registry
                delete_worktree(worktree.worktree_name)
                result.worktree_removed = True

            except WorktreeNotFoundError:
                result.worktree_removed = True  # No worktree to remove
        else:
            result.worktree_removed = True

        # All steps completed
        result.success = all(
            [
                result.pr_merged,
                result.main_updated,
                result.issue_closed,
                result.worktree_removed,
            ]
        )

        if result.success:
            mark_complete(operation_id)
        else:
            mark_failed(operation_id, "Some steps failed - see output")

        return result

    except Exception as e:
        error_msg = str(e)
        result.error = error_msg
        mark_failed(operation_id, error_msg)
        return result


def check_lifecycle_health() -> tuple[bool, list[str]]:
    """Check for stale pending operations.

    Returns (healthy, list of issues).
    """
    issues = []
    stale = get_stale_operations_simple()

    for op_id, op_data in stale:
        started = datetime.fromisoformat(op_data["started_at"])
        elapsed = (datetime.now(UTC) - started).total_seconds()
        issues.append(
            f"STALE: {op_id} has been pending for {elapsed:.0f}s (started: {op_data['started_at']})"
        )

    return len(issues) == 0, issues
