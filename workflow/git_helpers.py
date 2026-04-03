"""Git helper utilities for the epic workflow.

Provides robust commit, sync, and branch inspection functions.
"""

import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class GitConflictError(Exception):
    """Raised when a git merge encounters conflicts."""

    def __init__(self, conflicting_files: list[str]) -> None:
        self.conflicting_files = conflicting_files
        files_str = ", ".join(conflicting_files)
        super().__init__(f"Merge conflict in: {files_str}")


class GitCommitError(Exception):
    """Raised when a git commit fails after retry."""

    def __init__(self, message: str, stderr: str) -> None:
        self.stderr = stderr
        super().__init__(message)


class GitPushError(Exception):
    """Raised when git push fails."""

    def __init__(self, stderr: str) -> None:
        super().__init__(f"Git push failed: {stderr}")


class GitDirtyWorktreeError(Exception):
    """Raised when the working tree has uncommitted changes."""

    def __init__(self, dirty_entries: list[str]) -> None:
        self.dirty_entries = dirty_entries
        preview = ", ".join(dirty_entries[:5])
        if len(dirty_entries) > 5:
            preview += ", ..."
        super().__init__(
            "Working tree is dirty. Commit or stash changes before running the pipeline: "
            f"{preview}"
        )


def check_working_tree_clean() -> None:
    """Raise when the git working tree has uncommitted changes."""
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    dirty_entries = [line for line in result.stdout.splitlines() if line.strip()]
    if dirty_entries:
        raise GitDirtyWorktreeError(dirty_entries)


def robust_commit(message: str, paths: list[str]) -> str:
    """Stage specified paths and commit with pre-commit hook retry logic.

    Pre-commit hooks (ruff, format) may auto-fix staged files, causing the
    first commit attempt to fail with exit code 1. This function detects
    that case, re-stages the auto-fixed files, and retries the commit.

    Args:
        message: Commit message.
        paths: List of file/directory paths to stage (relative to PROJECT_ROOT).

    Returns:
        The short commit hash of the new commit.

    Raises:
        GitCommitError: If the commit fails after retry.
    """
    # Stage specified paths
    subprocess.run(
        ["git", "add", *paths],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    # First commit attempt
    result = subprocess.run(
        ["git", "commit", "-m", message],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    if result.returncode == 0:
        return get_commit_hash()

    # Pre-commit hooks may have auto-fixed files — re-stage and retry once
    subprocess.run(
        ["git", "add", *paths],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    result = subprocess.run(
        ["git", "commit", "-m", message],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    if result.returncode == 0:
        return get_commit_hash()

    raise GitCommitError(
        f"Commit failed after pre-commit retry: {result.stderr.strip()}",
        stderr=result.stderr,
    )


def git_sync() -> None:
    """Pull with rebase from origin and push.

    Uses rebase (not merge) to match project conventions. If a conflict
    is detected, the rebase is aborted and a GitConflictError is raised
    with the list of conflicting files.

    Raises:
        GitConflictError: If rebase conflicts are detected.
        GitPushError: If the push fails.
    """
    branch = get_current_branch()

    # Pull with rebase
    result = subprocess.run(
        ["git", "pull", "--rebase", "origin", branch],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        # Check for unmerged paths (conflict)
        check_unmerged = subprocess.run(
            ["git", "diff", "--name-only", "--diff-filter=U"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
        )
        conflicting = [f for f in check_unmerged.stdout.strip().splitlines() if f]

        if conflicting:
            # Abort rebase to keep tree clean
            subprocess.run(
                ["git", "rebase", "--abort"],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            raise GitConflictError(conflicting)

        # Non-conflict failure (e.g. nothing to pull, already up-to-date)
        # This is not an error — proceed to push

    # Push (no force needed after rebase on own feature branch)
    result = subprocess.run(
        ["git", "push"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise GitPushError(result.stderr.strip())


def get_current_branch() -> str:
    """Return the name of the current git branch.

    Returns:
        Branch name string (e.g. "95/phase-4-completion-di-tracks-groups-shoo").
    """
    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def get_commit_hash() -> str:
    """Return the short hash of the current HEAD commit.

    Returns:
        Short commit hash string (e.g. "abc1234").
    """
    result = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()
