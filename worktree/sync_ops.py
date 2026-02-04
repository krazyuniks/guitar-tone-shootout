"""Sync operations for session start/stop automation.

Provides automated git synchronization that hooks and CLI can use.
"""

import subprocess
from datetime import datetime
from pathlib import Path


def is_in_git_repo(cwd: Path | None = None) -> bool:
    """Check if the current directory is in a git repository.

    Args:
        cwd: Working directory to check

    Returns:
        True if in a git repository
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=cwd,
            capture_output=True,
            check=False,
        )
        return result.returncode == 0
    except Exception:
        return False


def has_uncommitted_changes(cwd: Path | None = None) -> bool:
    """Check for any uncommitted changes (staged or unstaged).

    Args:
        cwd: Working directory

    Returns:
        True if there are uncommitted changes
    """
    try:
        # Check staged changes
        result = subprocess.run(
            ["git", "diff", "--cached", "--quiet"],
            cwd=cwd,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            return True

        # Check unstaged changes
        result = subprocess.run(
            ["git", "diff", "--quiet"],
            cwd=cwd,
            capture_output=True,
            check=False,
        )
        return result.returncode != 0
    except Exception:
        return False


def has_untracked_files(cwd: Path | None = None) -> bool:
    """Check for untracked files.

    Args:
        cwd: Working directory

    Returns:
        True if there are untracked files
    """
    try:
        result = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
        )
        return bool(result.stdout.strip())
    except Exception:
        return False


def get_current_branch(cwd: Path | None = None) -> str:
    """Get the current branch name.

    Args:
        cwd: Working directory

    Returns:
        Branch name or 'unknown'
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except Exception:
        return "unknown"


def has_upstream(cwd: Path | None = None) -> bool:
    """Check if current branch has an upstream configured.

    Args:
        cwd: Working directory

    Returns:
        True if upstream is configured
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "@{u}"],
            cwd=cwd,
            capture_output=True,
            check=False,
        )
        return result.returncode == 0
    except Exception:
        return False


def commit_wip(cwd: Path | None = None) -> bool:
    """Create a WIP commit for any uncommitted changes.

    Args:
        cwd: Working directory

    Returns:
        True if commit was created or no changes to commit
    """
    if not has_uncommitted_changes(cwd) and not has_untracked_files(cwd):
        return True  # Nothing to commit

    try:
        branch = get_current_branch(cwd)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Stage all changes
        subprocess.run(
            ["git", "add", "-A"],
            cwd=cwd,
            capture_output=True,
            check=True,
        )

        # Create WIP commit
        subprocess.run(
            [
                "git",
                "commit",
                "-m",
                f"WIP: auto-save before sync ({timestamp})",
                "-m",
                f"Branch: {branch}",
                "-m",
                "Created by: worktree.py sync-stop",
            ],
            cwd=cwd,
            capture_output=True,
            check=True,
        )
        return True
    except subprocess.CalledProcessError:
        return False


def sync_start(cwd: Path | None = None, quiet: bool = False) -> tuple[bool, list[str]]:
    """Pre-work sync: fetch + rebase.

    Called at session start to ensure fresh state.

    Args:
        cwd: Working directory
        quiet: Suppress output messages

    Returns:
        Tuple of (success, list of messages/warnings)
    """
    messages = []

    if not is_in_git_repo(cwd):
        messages.append("Not in a git repository - skipping sync")
        return True, messages  # Not an error, just skip

    branch = get_current_branch(cwd)
    messages.append(f"Sync start on branch: {branch}")

    # Step 1: Fetch origin
    try:
        subprocess.run(
            ["git", "fetch", "origin"],
            cwd=cwd,
            capture_output=True,
            check=True,
        )
        messages.append("Fetched from origin")
    except subprocess.CalledProcessError as e:
        messages.append(f"Fetch failed (continuing): {e}")

    # Step 2: Pull with rebase (if upstream exists)
    if has_upstream(cwd):
        try:
            result = subprocess.run(
                ["git", "pull", "--rebase"],
                cwd=cwd,
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode == 0:
                messages.append("Pulled with rebase")
            else:
                # Check if it's a conflict
                if "conflict" in result.stderr.lower():
                    # Abort rebase and continue
                    subprocess.run(
                        ["git", "rebase", "--abort"],
                        cwd=cwd,
                        capture_output=True,
                        check=False,
                    )
                    messages.append("Rebase conflict - aborted, continuing with local state")
                else:
                    messages.append(f"Pull failed (continuing): {result.stderr.strip()}")
        except Exception as e:
            messages.append(f"Pull error (continuing): {e}")
    else:
        messages.append("No upstream configured - skipping pull")

    messages.append("Sync start complete")
    return True, messages


def sync_stop(cwd: Path | None = None, quiet: bool = False) -> tuple[bool, list[str]]:
    """Post-work sync: WIP commit + push.

    Called at session end to save all work.

    Args:
        cwd: Working directory
        quiet: Suppress output messages

    Returns:
        Tuple of (success, list of messages/warnings)
        Returns False if push fails (blocks session end)
    """
    messages = []

    if not is_in_git_repo(cwd):
        messages.append("Not in a git repository - skipping sync")
        return True, messages  # Not an error, just skip

    branch = get_current_branch(cwd)
    messages.append(f"Sync stop on branch: {branch}")

    # Step 1: Handle uncommitted changes
    if has_uncommitted_changes(cwd) or has_untracked_files(cwd):
        if commit_wip(cwd):
            messages.append("Created WIP commit for uncommitted changes")
        else:
            messages.append("Warning: Could not commit uncommitted changes")

    # Step 2: Push (MUST succeed)
    if has_upstream(cwd):
        try:
            result = subprocess.run(
                ["git", "push"],
                cwd=cwd,
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode == 0:
                messages.append("Pushed to remote")
            else:
                # Try push with set-upstream
                result = subprocess.run(
                    ["git", "push", "-u", "origin", branch],
                    cwd=cwd,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if result.returncode == 0:
                    messages.append("Pushed to remote (set upstream)")
                else:
                    messages.append(f"ERROR: Push failed: {result.stderr.strip()}")
                    messages.append("Session end blocked - push must succeed")
                    return False, messages
        except Exception as e:
            messages.append(f"ERROR: Push exception: {e}")
            messages.append("Session end blocked - push must succeed")
            return False, messages
    else:
        # No upstream - try to set it
        try:
            result = subprocess.run(
                ["git", "push", "-u", "origin", branch],
                cwd=cwd,
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode == 0:
                messages.append("Pushed to remote (created upstream)")
            else:
                messages.append(f"ERROR: Push failed: {result.stderr.strip()}")
                messages.append("Session end blocked - push must succeed")
                return False, messages
        except Exception as e:
            messages.append(f"ERROR: Push exception: {e}")
            messages.append("Session end blocked - push must succeed")
            return False, messages

    messages.append("Sync stop complete")
    return True, messages
