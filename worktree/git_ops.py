"""Git and GitHub operations for worktree management."""

import re
import subprocess
from pathlib import Path

from .config import get_bare_repo_path


class GitError(Exception):
    """Git operation failed."""


class GitHubError(Exception):
    """GitHub CLI operation failed."""


def run_git(
    args: list[str],
    cwd: Path | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess:
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
) -> subprocess.CompletedProcess:
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

    if create_branch:
        # Check if branch exists
        result = run_git(
            ["branch", "--list", branch],
            cwd=bare_repo,
            check=False,
        )
        if not result.stdout.strip():
            # Create branch from main
            run_git(["branch", branch, "main"], cwd=bare_repo)

    # Create worktree
    run_git(["worktree", "add", str(worktree_path), branch], cwd=bare_repo)

    # Configure fetch in the new worktree
    run_git(
        ["config", "remote.origin.fetch", "+refs/heads/*:refs/remotes/origin/*"],
        cwd=worktree_path,
    )


def remove_worktree(worktree_path: Path, force: bool = False) -> None:
    """Remove a git worktree.

    Args:
        worktree_path: Path to the worktree
        force: Force removal even with uncommitted changes
    """
    bare_repo = get_bare_repo_path()

    args = ["worktree", "remove"]
    if force:
        args.append("--force")
    args.append(str(worktree_path))

    run_git(args, cwd=bare_repo)


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


def delete_remote_branch(branch: str) -> None:
    """Delete a remote branch.

    Args:
        branch: Branch name
    """
    bare_repo = get_bare_repo_path()
    run_git(["push", "origin", "--delete", branch], cwd=bare_repo)


def is_branch_merged(branch: str) -> bool:
    """Check if a branch has been merged into main.

    Args:
        branch: Branch name

    Returns:
        True if branch is merged into main
    """
    bare_repo = get_bare_repo_path()
    fetch_origin(bare_repo)

    result = run_git(
        ["branch", "--merged", "origin/main"],
        cwd=bare_repo,
    )

    merged_branches = [b.strip().lstrip("* ") for b in result.stdout.splitlines()]
    return branch in merged_branches


def get_issue_title(issue_number: int) -> str | None:
    """Get the title of a GitHub issue.

    Args:
        issue_number: Issue number

    Returns:
        Issue title or None if not found
    """
    try:
        result = run_gh(
            ["issue", "view", str(issue_number), "--json", "title", "-q", ".title"]
        )
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

    # Convert to lowercase, replace non-alphanumeric with hyphens
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower())
    slug = slug.strip("-")[:40]  # Limit length

    return f"{issue_number}/{slug}"


def parse_issue_input(input_str: str) -> tuple[int | None, str]:
    """Parse user input to extract issue number and branch name.

    Supports:
    - "42" -> issue 42
    - "42/feature-name" -> issue 42 with explicit branch
    - "https://github.com/.../issues/42" -> issue 42
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
    """Check if a hook is installed in the bare repo.

    Args:
        hook_name: Name of the hook (e.g., "post-commit")

    Returns:
        True if the hook exists and is executable
    """
    hook_path = get_hooks_path() / hook_name
    return hook_path.exists() and hook_path.stat().st_mode & 0o111


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
