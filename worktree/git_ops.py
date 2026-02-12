"""Git and GitHub operations for worktree management."""

import contextlib
import platform
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .config import get_bare_repo_path


def strip_macos_acls(path: Path) -> None:
    """Remove macOS ACLs that Docker sets on bind-mounted directories.

    Docker Desktop on macOS sets 'deny delete' ACLs on bind-mounted directories
    which prevents shutil.rmtree from working. This function removes all ACLs
    recursively using chmod -R -N (macOS-specific).

    Args:
        path: Directory to strip ACLs from
    """
    if platform.system() != "Darwin":
        return

    if not path.exists():
        return

    # Best effort - if it fails, shutil.rmtree will fail too
    with contextlib.suppress(Exception):
        subprocess.run(
            ["chmod", "-R", "-N", str(path)],
            capture_output=True,
            check=False,  # Don't raise on failure, just continue
        )


def fix_docker_ownership(path: Path) -> bool:
    """Fix ownership of files created by Docker containers.

    Docker containers often create files as root, which prevents normal users
    from deleting them. This function uses a lightweight Alpine container to
    recursively change ownership back to the current user.

    Args:
        path: Directory to fix ownership on

    Returns:
        True if ownership was fixed, False if it failed or wasn't needed
    """
    import os

    if not path.exists():
        return True

    uid = os.getuid()
    gid = os.getgid()

    # Use Docker to chown all files back to current user
    with contextlib.suppress(Exception):
        result = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "-v",
                f"{path}:/work",
                "alpine",
                "chown",
                "-R",
                f"{uid}:{gid}",
                "/work",
            ],
            capture_output=True,
            timeout=60,
            check=False,
        )
        return result.returncode == 0

    return False


class GitError(Exception):
    """Git operation failed."""


class GitHubError(Exception):
    """GitHub CLI operation failed."""


def run_git(
    args: list[str],
    cwd: Path | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Run a git command.

    Args:
        args: Git command arguments (without 'git' prefix)
        cwd: Working directory
        check: Raise exception on non-zero exit

    Returns:
        CompletedProcess result

    Raises:
        GitError: If check=True and command fails
    """
    cmd = ["git", *args]
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=check,
        )
        return result
    except subprocess.CalledProcessError as e:
        raise GitError(f"Git command failed: {' '.join(cmd)}\n{e.stderr}") from e


def run_gh(
    args: list[str],
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Run a GitHub CLI command.

    Args:
        args: gh command arguments (without 'gh' prefix)
        check: Raise exception on non-zero exit

    Returns:
        CompletedProcess result

    Raises:
        GitHubError: If check=True and command fails
    """
    cmd = ["gh", *args]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=check,
        )
        return result
    except subprocess.CalledProcessError as e:
        raise GitHubError(f"GitHub CLI failed: {' '.join(cmd)}\n{e.stderr}") from e
    except FileNotFoundError:
        raise GitHubError("GitHub CLI (gh) not installed or not in PATH") from None


def get_current_branch(cwd: Path | None = None) -> str:
    """Get the current git branch name.

    Args:
        cwd: Working directory

    Returns:
        Branch name
    """
    result = run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=cwd)
    return result.stdout.strip()


def get_commit_hash(ref: str = "HEAD", cwd: Path | None = None) -> str:
    """Get the commit hash for a ref.

    Args:
        ref: Git ref (branch, tag, or commit)
        cwd: Working directory

    Returns:
        Full commit hash
    """
    result = run_git(["rev-parse", ref], cwd=cwd)
    return result.stdout.strip()


def fetch_origin(cwd: Path | None = None) -> None:
    """Fetch from origin.

    Args:
        cwd: Working directory
    """
    run_git(["fetch", "origin"], cwd=cwd)


def is_main_behind_remote(cwd: Path | None = None) -> bool:
    """Check if local main is behind origin/main.

    Args:
        cwd: Working directory

    Returns:
        True if local main is behind origin/main
    """
    fetch_origin(cwd)

    local = get_commit_hash("main", cwd)
    remote = get_commit_hash("origin/main", cwd)

    if local == remote:
        return False

    # Check if local is ancestor of remote (behind)
    result = run_git(
        ["merge-base", "--is-ancestor", local, remote],
        cwd=cwd,
        check=False,
    )
    return result.returncode == 0


def rebase_on_main(cwd: Path) -> bool:
    """Rebase current branch on origin/main.

    Fetches from origin first, then rebases. Handles uncommitted changes
    by stashing them before rebase and restoring after.

    Args:
        cwd: Working directory (worktree path)

    Returns:
        True if rebase succeeded or no rebase needed, False if conflicts or errors
    """
    # Fetch latest
    fetch_origin(cwd)

    # Check if we're already up to date with origin/main
    # This avoids unnecessary rebases and the issues that come with them
    result = run_git(
        ["rev-list", "--count", "HEAD..origin/main"],
        cwd=cwd,
        check=False,
    )
    if result.returncode == 0 and result.stdout.strip() == "0":
        # No commits to rebase - we're already up to date
        return True

    # Check for uncommitted changes
    status_result = run_git(["status", "--porcelain"], cwd=cwd, check=False)
    has_changes = bool(status_result.stdout.strip())

    # Stash any uncommitted changes
    stashed = False
    if has_changes:
        stash_result = run_git(
            ["stash", "push", "-m", "worktree-setup-rebase"],
            cwd=cwd,
            check=False,
        )
        stashed = stash_result.returncode == 0

    try:
        # Rebase on origin/main
        result = run_git(
            ["rebase", "origin/main"],
            cwd=cwd,
            check=False,
        )

        if result.returncode != 0:
            # Abort the failed rebase
            run_git(["rebase", "--abort"], cwd=cwd, check=False)
            return False

        return True
    finally:
        # Restore stashed changes if we stashed them
        if stashed:
            run_git(["stash", "pop"], cwd=cwd, check=False)


def create_worktree(
    branch: str,
    worktree_path: Path,
    create_branch: bool = True,
) -> None:
    """Create a git worktree.

    Args:
        branch: Branch name for the worktree
        worktree_path: Path where worktree will be created
        create_branch: Create the branch if it doesn't exist

    Raises:
        GitError: If worktree creation fails
    """
    bare_repo = get_bare_repo_path()

    # Always fetch latest before creating worktree
    run_git(["fetch", "origin"], cwd=bare_repo, check=False)

    if create_branch:
        # Check if branch exists
        result = run_git(
            ["branch", "--list", branch],
            cwd=bare_repo,
            check=False,
        )
        if not result.stdout.strip():
            # Create branch from origin/main (not local main which may be behind)
            run_git(["branch", branch, "origin/main"], cwd=bare_repo)

    # Create worktree
    run_git(["worktree", "add", str(worktree_path), branch], cwd=bare_repo)

    # Configure fetch in the new worktree
    run_git(
        ["config", "remote.origin.fetch", "+refs/heads/*:refs/remotes/origin/*"],
        cwd=worktree_path,
    )

    # Push the branch to origin with -u to set up tracking
    # This creates the remote branch AND sets it as upstream in one step
    # For new branches, this is required since origin/<branch> doesn't exist yet
    run_git(
        ["push", "-u", "origin", branch],
        cwd=worktree_path,
        check=False,  # May fail if branch already exists on remote, which is fine
    )


def remove_worktree(worktree_path: Path, force: bool = False) -> None:
    """Remove a git worktree.

    Args:
        worktree_path: Path to the worktree
        force: Force removal even with uncommitted changes
    """
    bare_repo = get_bare_repo_path()

    # Fix ownership of root-owned files from Docker before removal
    fix_docker_ownership(worktree_path)

    # Strip macOS ACLs before attempting removal - Docker sets these on bind mounts
    strip_macos_acls(worktree_path)

    args = ["worktree", "remove"]
    if force:
        args.append("--force")
    args.append(str(worktree_path))

    run_git(args, cwd=bare_repo)

    # Clean up leftover directory if it still exists
    # git worktree remove may leave behind non-git files
    # Use force=True since we're in teardown mode
    cleanup_leftover_worktree_directory(worktree_path, force=True)


def cleanup_leftover_worktree_directory(worktree_path: Path, force: bool = False) -> bool:
    """Clean up a worktree directory after git worktree remove.

    Removes leftover directories that git worktree remove may leave behind.
    Handles root-owned files created by Docker containers.

    Args:
        worktree_path: Path to the worktree directory
        force: If True, delete regardless of contents (use after teardown).
               If False, only delete if directory is empty or has safe-to-delete items.

    Returns:
        True if directory was cleaned up or didn't exist
        False if directory exists but couldn't be removed
    """
    import shutil

    if not worktree_path.exists():
        return True

    # Check if it's still a git worktree - if so, don't touch it
    git_file = worktree_path / ".git"
    if git_file.exists() and git_file.is_file():
        # .git file indicates it's still a worktree
        return False

    if not force:
        # Known safe-to-delete items in worktree directories
        safe_items = {".git", ".DS_Store", ".worktree-state"}

        # Check all items in the directory
        try:
            items = set(item.name for item in worktree_path.iterdir())
        except PermissionError:
            # Can't even list the directory - try fixing ownership
            fix_docker_ownership(worktree_path)
            try:
                items = set(item.name for item in worktree_path.iterdir())
            except PermissionError:
                return False

        # Check for unknown items
        unknown_items = items - safe_items
        if unknown_items:
            # There are unknown files - don't delete without force
            return False

    # Try to delete - handle root-owned files from Docker
    try:
        # Remove macOS ACLs that Docker sets on bind-mounted directories
        strip_macos_acls(worktree_path)
        shutil.rmtree(worktree_path)
        return True
    except PermissionError:
        # Files likely owned by root from Docker - fix ownership and retry
        fix_docker_ownership(worktree_path)
        try:
            shutil.rmtree(worktree_path)
            return True
        except Exception:
            return False
    except Exception:
        return False


def prune_worktrees() -> None:
    """Prune stale worktree entries from git."""
    bare_repo = get_bare_repo_path()
    run_git(["worktree", "prune"], cwd=bare_repo)


def delete_branch(branch: str, force: bool = False) -> None:
    """Delete a local branch.

    Args:
        branch: Branch name
        force: Force delete even if not merged
    """
    bare_repo = get_bare_repo_path()
    flag = "-D" if force else "-d"
    run_git(["branch", flag, branch], cwd=bare_repo)


def remote_branch_exists(branch: str) -> bool:
    """Check if a remote branch exists on origin.

    Uses `git ls-remote --heads origin <branch>` to check if the branch exists.
    This is useful to avoid errors when trying to delete a branch that GitHub
    may have already deleted after a PR merge.

    Args:
        branch: Branch name

    Returns:
        True if the remote branch exists, False otherwise
    """
    bare_repo = get_bare_repo_path()
    result = run_git(
        ["ls-remote", "--heads", "origin", branch],
        cwd=bare_repo,
        check=False,
    )
    # ls-remote returns output if the branch exists, empty if not
    return bool(result.stdout.strip())


def delete_remote_branch(branch: str) -> None:
    """Delete a remote branch.

    Checks if the branch exists first to avoid errors when GitHub has already
    deleted the branch after a PR merge.

    Args:
        branch: Branch name
    """
    if not remote_branch_exists(branch):
        # Branch doesn't exist on remote, nothing to delete
        return

    bare_repo = get_bare_repo_path()
    run_git(["push", "origin", "--delete", branch], cwd=bare_repo)


def is_pr_merged_for_branch(branch: str) -> bool:
    """Check if a PR for this branch has been merged via GitHub API.

    This handles squash merges where the original branch commits
    are NOT in main's history (squash creates a new commit SHA).

    Args:
        branch: Branch name

    Returns:
        True if a merged PR exists for this branch
    """
    try:
        # Find PR(s) for this branch
        result = run_gh(
            [
                "pr",
                "list",
                "--head",
                branch,
                "--state",
                "merged",
                "--json",
                "number,mergedAt",
                "--repo",
                "krazyuniks/guitar-tone-shootout",
            ],
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            import json

            prs = json.loads(result.stdout)
            # If any merged PRs exist for this branch, it's merged
            return len(prs) > 0
    except (GitHubError, Exception):
        pass
    return False


def is_branch_in_git_history(branch: str) -> bool:
    """Check if a branch's commits are in main's git history.

    This is the traditional git merge check. Returns True only if
    the branch commits are ancestors of main (regular merge or fast-forward).

    Args:
        branch: Branch name

    Returns:
        True if branch commits are in main's history
    """
    bare_repo = get_bare_repo_path()
    fetch_origin(bare_repo)

    result = run_git(
        ["branch", "--merged", "origin/main"],
        cwd=bare_repo,
    )

    merged_branches = [b.strip().lstrip("* ") for b in result.stdout.splitlines()]
    return branch in merged_branches


def is_branch_merged(branch: str) -> bool:
    """Check if a branch has been merged into main.

    Uses two methods:
    1. Git history check (fast, works for regular merges)
    2. GitHub API check (handles squash merges)

    Args:
        branch: Branch name

    Returns:
        True if branch is merged into main (via any merge strategy)
    """
    # Method 1: Git history check (fast, handles regular merges)
    if is_branch_in_git_history(branch):
        return True

    # Method 2: GitHub API check (handles squash merges)
    # Squash merge creates a NEW commit on main, so the original
    # branch commits aren't in main's history. But the PR is merged.
    return is_pr_merged_for_branch(branch)


def should_force_delete_branch(branch: str) -> bool:
    """Determine if a branch needs force deletion (-D vs -d).

    For squash-merged branches, git's -d flag will fail because the
    original commits are not in main's history. We need -D.

    Args:
        branch: Branch name

    Returns:
        True if -D (force) should be used, False if -d is safe
    """
    # If the branch is in git's merged list, -d is safe
    if is_branch_in_git_history(branch):
        return False

    # If the PR was merged (squash merge), the commits aren't in
    # git history, but the branch was merged. Need -D.
    # Branch not merged at all returns False - caller should decide whether to force
    return is_pr_merged_for_branch(branch)


def get_issue_title(issue_number: int) -> str | None:
    """Get the title of a GitHub issue.

    Args:
        issue_number: Issue number

    Returns:
        Issue title or None if not found
    """
    try:
        result = run_gh(["issue", "view", str(issue_number), "--json", "title", "-q", ".title"])
        return result.stdout.strip()
    except GitHubError:
        return None


def close_issue(issue_number: int) -> None:
    """Close a GitHub issue.

    Args:
        issue_number: Issue number
    """
    run_gh(["issue", "close", str(issue_number)])


def generate_branch_name(issue_number: int, title: str | None = None) -> str:
    """Generate a branch name from an issue number and title.

    Args:
        issue_number: GitHub issue number
        title: Issue title (fetched if not provided)

    Returns:
        Branch name like "42/feature-audio-analysis"
    """
    if title is None:
        title = get_issue_title(issue_number) or "feature"

    # Clean title for branch name
    # Remove common prefixes
    title = re.sub(r"^(feat|fix|refactor|docs|test|chore):\s*", "", title, flags=re.I)

    # Remove stop words to keep branch names concise
    stop_words = {
        "the",
        "a",
        "an",
        "to",
        "from",
        "in",
        "on",
        "at",
        "by",
        "for",
        "of",
        "and",
        "or",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "with",
        "this",
        "that",
        "these",
        "those",
        "it",
        "its",
    }
    words = title.lower().split()
    words = [w for w in words if w not in stop_words]
    title = " ".join(words) if words else title.lower()

    # Convert to lowercase, replace non-alphanumeric with hyphens
    slug = re.sub(r"[^a-z0-9]+", "-", title)
    # Truncate first, then strip hyphens to avoid trailing hyphens
    slug = slug[:40].strip("-")

    return f"{issue_number}/{slug}"


def parse_issue_input(input_str: str) -> tuple[int | None, str]:
    """Parse user input to extract issue number and branch name.

    Supports:
    - "42" -> issue 42, generates descriptive branch
    - "42/feature-name" -> issue 42 with explicit branch
    - "https://github.com/.../issues/42" -> issue 42, generates descriptive branch
    - "main" -> no issue, branch "main"

    Args:
        input_str: User input

    Returns:
        Tuple of (issue_number or None, branch_name)
    """
    input_str = input_str.strip()

    # Check for GitHub URL
    url_match = re.match(r"https?://github\.com/.+/issues/(\d+)", input_str)
    if url_match:
        issue_num = int(url_match.group(1))
        return issue_num, generate_branch_name(issue_num)

    # Check for issue number with branch
    branch_match = re.match(r"(\d+)/(.+)", input_str)
    if branch_match:
        issue_num = int(branch_match.group(1))
        branch_slug = branch_match.group(2)
        return issue_num, f"{issue_num}/{branch_slug}"

    # Check for pure issue number
    if input_str.isdigit():
        issue_num = int(input_str)
        return issue_num, generate_branch_name(issue_num)

    # Treat as branch name (e.g., "main")
    return None, input_str


def generate_worktree_name(branch: str) -> str:
    """Generate a worktree directory name from a branch.

    Args:
        branch: Branch name (e.g., "main", "42/feature-audio")

    Returns:
        Directory name (e.g., "main", "42-feature-audio")
    """
    # Replace slashes with hyphens for directory naming
    return branch.replace("/", "-")


# =============================================================================
# Hook Management
# =============================================================================


def get_hooks_path() -> Path:
    """Get the path to the bare repo's hooks directory.

    Returns:
        Path to the hooks directory (e.g., .../guitar-tone-shootout.git/hooks/)
    """
    return get_bare_repo_path() / "hooks"


def get_hook_template_path() -> Path:
    """Get the path to the hook templates directory.

    Returns:
        Path to the hooks templates (worktree/hooks/)
    """
    return Path(__file__).parent / "hooks"


def is_hook_installed(hook_name: str) -> bool:
    """Check if a hook is installed in the bare repo and matches the template.

    Args:
        hook_name: Name of the hook (e.g., "post-commit")

    Returns:
        True if the hook exists, is executable, and matches the template content
    """
    hook_path = get_hooks_path() / hook_name
    if not hook_path.exists() or not bool(hook_path.stat().st_mode & 0o111):
        return False

    template_path = get_hook_template_path() / hook_name
    if not template_path.exists():
        # No template to compare against — existence check only
        return True

    return hook_path.read_text() == template_path.read_text()


def install_hook(hook_name: str) -> bool:
    """Install a hook from the templates to the bare repo.

    Args:
        hook_name: Name of the hook (e.g., "post-commit")

    Returns:
        True if installed successfully, False if template not found
    """
    template_path = get_hook_template_path() / hook_name
    if not template_path.exists():
        return False

    hooks_dir = get_hooks_path()
    hooks_dir.mkdir(parents=True, exist_ok=True)

    hook_path = hooks_dir / hook_name
    hook_path.write_text(template_path.read_text())
    hook_path.chmod(0o755)  # Make executable

    return True


def uninstall_hook(hook_name: str) -> bool:
    """Remove a hook from the bare repo.

    Args:
        hook_name: Name of the hook (e.g., "post-commit")

    Returns:
        True if removed, False if didn't exist
    """
    hook_path = get_hooks_path() / hook_name
    if hook_path.exists():
        hook_path.unlink()
        return True
    return False


# =============================================================================
# Stale Branch Management
# =============================================================================


# Protected branches that should never be deleted
PROTECTED_BRANCHES = {"main", "master", "develop", "development"}


@dataclass
class StaleBranchInfo:
    """Information about a local branch with a gone remote tracking branch."""

    name: str
    tracking: str  # The gone remote tracking ref (e.g., "origin/feature")
    commit: str  # Short commit hash


def list_stale_branches() -> list[StaleBranchInfo]:
    """List local branches whose remote tracking branch no longer exists.

    These are branches where `git branch -vv` shows "[origin/...: gone]".
    This typically happens after PRs are squash-merged and the remote
    branch is deleted by GitHub.

    Protected branches (main, master, develop, development) are never included.

    Returns:
        List of StaleBranchInfo for each stale branch
    """
    bare_repo = get_bare_repo_path()

    # Fetch to update remote tracking info (prunes deleted remote branches)
    run_git(["fetch", "--prune"], cwd=bare_repo, check=False)

    # Get branch info with tracking status
    result = run_git(["branch", "-vv"], cwd=bare_repo, check=False)
    if result.returncode != 0:
        return []

    stale_branches = []

    # Parse output like:
    #   42-feature-name    abc1234 [origin/42/feature-name: gone] commit msg
    # * main               def5678 [origin/main] commit msg
    for line in result.stdout.splitlines():
        # Skip empty lines
        if not line.strip():
            continue

        # Remove leading markers (* for current, + for worktree)
        line = line.lstrip("*+ ")

        # Parse: "branch-name  commit [tracking: gone] message"
        # The tracking info is in square brackets
        match = re.match(
            r"(\S+)\s+([a-f0-9]+)\s+\[([^:]+):\s*gone\]",
            line,
        )
        if match:
            branch_name = match.group(1)
            commit = match.group(2)
            tracking = match.group(3)

            # Skip protected branches
            if branch_name.lower() in PROTECTED_BRANCHES:
                continue

            stale_branches.append(
                StaleBranchInfo(
                    name=branch_name,
                    tracking=tracking,
                    commit=commit,
                )
            )

    return stale_branches


def delete_stale_branches(
    branches: list[StaleBranchInfo],
) -> list[tuple[str, bool, str]]:
    """Delete the specified stale branches.

    Uses -D (force delete) since the remote tracking is gone,
    meaning -d would fail even for merged branches.

    Args:
        branches: List of StaleBranchInfo to delete

    Returns:
        List of (branch_name, success, message) tuples
    """
    results = []

    for branch in branches:
        # Double-check: never delete protected branches
        if branch.name.lower() in PROTECTED_BRANCHES:
            results.append((branch.name, False, "Protected branch"))
            continue

        try:
            delete_branch(branch.name, force=True)
            results.append((branch.name, True, "Deleted"))
        except GitError as e:
            results.append((branch.name, False, str(e)))

    return results


# =============================================================================
# Git Worktree Discovery
# =============================================================================


@dataclass
class GitWorktreeInfo:
    """Information about a git worktree from `git worktree list`."""

    path: Path
    branch: str
    commit: str
    is_bare: bool = False


def list_git_worktrees() -> list[GitWorktreeInfo]:
    """Get all git worktrees from git worktree list.

    Returns:
        List of GitWorktreeInfo objects for each worktree.
        Does not include the bare repository entry.
    """
    bare_repo = get_bare_repo_path()

    result = run_git(["worktree", "list", "--porcelain"], cwd=bare_repo, check=False)
    if result.returncode != 0:
        return []

    worktrees = []
    current_wt: dict = {}

    for line in result.stdout.strip().split("\n"):
        line = line.strip()
        if not line:
            # End of a worktree entry
            if current_wt and not current_wt.get("bare"):
                # Parse branch name from "refs/heads/branch-name" or "(detached HEAD)"
                branch = current_wt.get("branch", "")
                if branch.startswith("refs/heads/"):
                    branch = branch[len("refs/heads/") :]
                elif branch == "(detached HEAD)" or not branch:
                    branch = "detached"

                worktrees.append(
                    GitWorktreeInfo(
                        path=Path(current_wt["path"]),
                        branch=branch,
                        commit=current_wt.get("HEAD", "unknown"),
                        is_bare=current_wt.get("bare", False),
                    )
                )
            current_wt = {}
        elif line.startswith("worktree "):
            current_wt["path"] = line[len("worktree ") :]
        elif line.startswith("HEAD "):
            current_wt["HEAD"] = line[len("HEAD ") :]
        elif line.startswith("branch "):
            current_wt["branch"] = line[len("branch ") :]
        elif line == "bare":
            current_wt["bare"] = True
        elif line == "detached":
            current_wt["branch"] = "(detached HEAD)"

    # Handle last entry if no trailing newline
    if current_wt and not current_wt.get("bare"):
        branch = current_wt.get("branch", "")
        if branch.startswith("refs/heads/"):
            branch = branch[len("refs/heads/") :]
        elif branch == "(detached HEAD)" or not branch:
            branch = "detached"

        worktrees.append(
            GitWorktreeInfo(
                path=Path(current_wt["path"]),
                branch=branch,
                commit=current_wt.get("HEAD", "unknown"),
                is_bare=current_wt.get("bare", False),
            )
        )

    return worktrees
