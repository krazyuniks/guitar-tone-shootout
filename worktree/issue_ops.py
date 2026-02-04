"""GitHub issue operations for worktree workflow.

Provides issue fetching, caching, and analysis for work selection:
- Fetch issues from GitHub
- Categorize by readiness (ready, blocked, in_progress)
- Detect changes since last run
- Cache results for performance
"""

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from .config import get_worktree_root
from .git_ops import GitHubError, run_gh

# Default repository for all GitHub operations
DEFAULT_REPO = "krazyuniks/guitar-tone-shootout"

# Cache configuration
CACHE_DIR_NAME = ".worktree-cache"
ISSUES_CACHE_FILE = "issues.json"
CACHE_TTL_MINUTES = 15  # Cache valid for 15 minutes

# Stale threshold - issues not updated in this many days are considered stale
STALE_DAYS = 30


@dataclass
class GitHubIssue:
    """Represents a GitHub issue."""

    number: int
    title: str
    state: str
    labels: list[str]
    assignees: list[str]
    created_at: datetime
    updated_at: datetime
    body: str | None = None

    @property
    def is_stale(self) -> bool:
        """True if issue hasn't been updated in 30+ days."""
        threshold = datetime.now(UTC) - timedelta(days=STALE_DAYS)
        return self.updated_at < threshold

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "number": self.number,
            "title": self.title,
            "state": self.state,
            "labels": self.labels,
            "assignees": self.assignees,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "body": self.body,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GitHubIssue":
        """Create from dictionary (JSON deserialization)."""
        return cls(
            number=data["number"],
            title=data["title"],
            state=data["state"],
            labels=data.get("labels", []),
            assignees=data.get("assignees", []),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            body=data.get("body"),
        )

    @classmethod
    def from_gh_json(cls, data: dict[str, Any]) -> "GitHubIssue":
        """Create from GitHub CLI JSON output.

        GitHub CLI returns labels as [{"name": "bug"}, ...] and
        assignees as [{"login": "user"}, ...].
        """
        # Parse labels - can be list of dicts or list of strings
        labels = []
        for label in data.get("labels", []):
            if isinstance(label, dict):
                labels.append(label.get("name", ""))
            else:
                labels.append(str(label))

        # Parse assignees - can be list of dicts or list of strings
        assignees = []
        for assignee in data.get("assignees", []):
            if isinstance(assignee, dict):
                assignees.append(assignee.get("login", ""))
            else:
                assignees.append(str(assignee))

        # Parse timestamps
        created_at = datetime.fromisoformat(data["createdAt"].replace("Z", "+00:00"))
        updated_at = datetime.fromisoformat(data["updatedAt"].replace("Z", "+00:00"))

        return cls(
            number=data["number"],
            title=data["title"],
            state=data["state"].lower(),
            labels=labels,
            assignees=assignees,
            created_at=created_at,
            updated_at=updated_at,
            body=data.get("body"),
        )


@dataclass
class IssueAnalysis:
    """Categorized issues by readiness."""

    ready: list[GitHubIssue] = field(default_factory=list)
    blocked: list[GitHubIssue] = field(default_factory=list)
    in_progress: list[GitHubIssue] = field(default_factory=list)
    stale: list[GitHubIssue] = field(default_factory=list)

    @property
    def total(self) -> int:
        """Total number of issues (excluding stale)."""
        return len(self.ready) + len(self.blocked) + len(self.in_progress)


def _get_cache_path() -> Path:
    """Get the path to the issues cache file."""
    cache_dir = get_worktree_root() / CACHE_DIR_NAME
    return cache_dir / ISSUES_CACHE_FILE


def fetch_github_issues(
    repo: str = DEFAULT_REPO,
    labels: list[str] | None = None,
    state: str = "open",
) -> list[GitHubIssue]:
    """Fetch issues from GitHub using gh CLI.

    Args:
        repo: Repository in owner/repo format
        labels: Filter by labels (optional)
        state: Issue state (open, closed, all)

    Returns:
        List of GitHubIssue objects, empty list on error
    """
    # Build the gh command
    args = [
        "issue",
        "list",
        "--repo",
        repo,
        "--state",
        state,
        "--json",
        "number,title,state,labels,assignees,createdAt,updatedAt,body",
        "--limit",
        "100",  # Reasonable limit for workflow
    ]

    # Add label filters if provided
    if labels:
        for label in labels:
            args.extend(["--label", label])

    try:
        result = run_gh(args, check=True)
        issues_data = json.loads(result.stdout)

        issues = []
        for issue_data in issues_data:
            try:
                issue = GitHubIssue.from_gh_json(issue_data)
                issues.append(issue)
            except (KeyError, ValueError) as e:
                # Skip malformed issues but continue processing
                print(f"Warning: Skipping malformed issue: {e}")
                continue

        return issues

    except GitHubError as e:
        print(f"Warning: Failed to fetch issues from GitHub: {e}")
        return []
    except json.JSONDecodeError as e:
        print(f"Warning: Failed to parse GitHub response: {e}")
        return []


def analyze_issues(issues: list[GitHubIssue]) -> IssueAnalysis:
    """Categorize issues by readiness for work.

    Categories:
    - ready: Has no blockers, not assigned to someone else
    - blocked: Has "blocked" label or blocking dependency
    - in_progress: Has assignee or "in progress" label
    - stale: Not updated in 30+ days

    Args:
        issues: List of GitHub issues to analyze

    Returns:
        IssueAnalysis with categorized issues
    """
    analysis = IssueAnalysis()

    # Labels that indicate blocked status (case-insensitive)
    blocked_labels = {"blocked", "waiting", "on-hold", "needs-info"}

    # Labels that indicate in-progress status (case-insensitive)
    in_progress_labels = {"in-progress", "in progress", "wip", "working"}

    for issue in issues:
        # Normalize labels for comparison
        lower_labels = {label.lower() for label in issue.labels}

        # Check stale first - stale issues go to their own category
        if issue.is_stale:
            analysis.stale.append(issue)
            continue

        # Check blocked
        if lower_labels & blocked_labels:
            analysis.blocked.append(issue)
            continue

        # Check in-progress (by label or assignee)
        if lower_labels & in_progress_labels or issue.assignees:
            analysis.in_progress.append(issue)
            continue

        # Otherwise, it's ready
        analysis.ready.append(issue)

    return analysis


def load_issue_cache(cache_path: Path | None = None) -> dict[str, Any] | None:
    """Load cached issue data from disk.

    Args:
        cache_path: Path to cache file (defaults to standard location)

    Returns:
        Cache data dict with "issues" and "cached_at" keys, or None if no valid cache
    """
    if cache_path is None:
        cache_path = _get_cache_path()

    if not cache_path.exists():
        return None

    try:
        with cache_path.open() as f:
            data = json.load(f)

        # Validate cache structure
        if "issues" not in data or "cached_at" not in data:
            return None

        # Check if cache is still valid (within TTL)
        cached_at = datetime.fromisoformat(data["cached_at"])
        now = datetime.now(UTC)
        if now - cached_at > timedelta(minutes=CACHE_TTL_MINUTES):
            return None

        return dict(data)

    except (json.JSONDecodeError, ValueError, OSError):
        return None


def save_issue_cache(
    cache_path: Path | None = None,
    issues: list[GitHubIssue] | None = None,
) -> None:
    """Save issues to cache file.

    Args:
        cache_path: Path to cache file (defaults to standard location)
        issues: List of issues to cache
    """
    if cache_path is None:
        cache_path = _get_cache_path()

    if issues is None:
        issues = []

    # Ensure cache directory exists
    cache_path.parent.mkdir(parents=True, exist_ok=True)

    cache_data = {
        "issues": [issue.to_dict() for issue in issues],
        "cached_at": datetime.now(UTC).isoformat(),
    }

    try:
        with cache_path.open("w") as f:
            json.dump(cache_data, f, indent=2)
    except OSError as e:
        print(f"Warning: Failed to save issue cache: {e}")


def load_cached_issues(cache_path: Path | None = None) -> list[GitHubIssue] | None:
    """Load issues from cache if valid.

    Convenience function that loads and deserializes cached issues.

    Args:
        cache_path: Path to cache file (defaults to standard location)

    Returns:
        List of GitHubIssue objects, or None if no valid cache
    """
    cache_data = load_issue_cache(cache_path)
    if cache_data is None:
        return None

    try:
        return [GitHubIssue.from_dict(issue_data) for issue_data in cache_data["issues"]]
    except (KeyError, ValueError):
        return None


def detect_changes_since_last_run(
    current: list[GitHubIssue],
    cached: list[GitHubIssue],
) -> dict[str, list[GitHubIssue]]:
    """Compare current issues to cached to find changes.

    Args:
        current: Current list of issues from GitHub
        cached: Previously cached list of issues

    Returns:
        Dict with keys: "new", "closed", "updated"
    """
    changes: dict[str, list[GitHubIssue]] = {
        "new": [],
        "closed": [],
        "updated": [],
    }

    # Build lookup maps
    current_by_number = {issue.number: issue for issue in current}
    cached_by_number = {issue.number: issue for issue in cached}

    current_numbers = set(current_by_number.keys())
    cached_numbers = set(cached_by_number.keys())

    # New issues (in current but not in cached)
    for number in current_numbers - cached_numbers:
        changes["new"].append(current_by_number[number])

    # Closed issues (in cached but not in current)
    # Note: These are issues that were open before but are now closed/removed
    for number in cached_numbers - current_numbers:
        changes["closed"].append(cached_by_number[number])

    # Updated issues (in both, but updated_at changed)
    for number in current_numbers & cached_numbers:
        current_issue = current_by_number[number]
        cached_issue = cached_by_number[number]

        if current_issue.updated_at != cached_issue.updated_at:
            changes["updated"].append(current_issue)

    return changes


def get_issue_by_number(
    number: int,
    repo: str = DEFAULT_REPO,
) -> GitHubIssue | None:
    """Fetch a single issue by number.

    Args:
        number: GitHub issue number
        repo: Repository in owner/repo format

    Returns:
        GitHubIssue object or None if not found/error
    """
    args = [
        "issue",
        "view",
        str(number),
        "--repo",
        repo,
        "--json",
        "number,title,state,labels,assignees,createdAt,updatedAt,body",
    ]

    try:
        result = run_gh(args, check=True)
        issue_data = json.loads(result.stdout)
        return GitHubIssue.from_gh_json(issue_data)

    except GitHubError:
        return None
    except json.JSONDecodeError:
        return None


def get_issues_with_cache(
    repo: str = DEFAULT_REPO,
    labels: list[str] | None = None,
    state: str = "open",
    force_refresh: bool = False,
) -> tuple[list[GitHubIssue], bool]:
    """Fetch issues, using cache if available and valid.

    Convenience function that handles cache loading/saving.

    Args:
        repo: Repository in owner/repo format
        labels: Filter by labels (optional)
        state: Issue state (open, closed, all)
        force_refresh: If True, skip cache and fetch fresh

    Returns:
        Tuple of (issues list, from_cache boolean)
    """
    cache_path = _get_cache_path()

    # Try cache first (unless force refresh)
    if not force_refresh:
        cached_issues = load_cached_issues(cache_path)
        if cached_issues is not None:
            return cached_issues, True

    # Fetch fresh from GitHub
    issues = fetch_github_issues(repo=repo, labels=labels, state=state)

    # Save to cache
    save_issue_cache(cache_path, issues)

    return issues, False


def format_issue_summary(issue: GitHubIssue, show_labels: bool = True) -> str:
    """Format an issue for display.

    Args:
        issue: GitHubIssue to format
        show_labels: Whether to include labels in output

    Returns:
        Formatted string like "#42: Fix audio processing [bug, high-priority]"
    """
    parts = [f"#{issue.number}: {issue.title}"]

    if show_labels and issue.labels:
        labels_str = ", ".join(issue.labels[:3])  # Limit to 3 labels
        if len(issue.labels) > 3:
            labels_str += f" +{len(issue.labels) - 3}"
        parts.append(f"[{labels_str}]")

    if issue.assignees:
        assignees_str = ", ".join(issue.assignees[:2])
        if len(issue.assignees) > 2:
            assignees_str += f" +{len(issue.assignees) - 2}"
        parts.append(f"(@{assignees_str})")

    return " ".join(parts)


# Processed marker pattern in issue body
PROCESSED_MARKER = "<!-- processed:"


def is_issue_processed(issue: GitHubIssue) -> bool:
    """Check if an issue has been processed by /plan.

    An issue is considered processed if it has the processed marker
    comment in its body: <!-- processed: YYYY-MM-DD -->

    Args:
        issue: GitHubIssue to check

    Returns:
        True if issue has been processed, False otherwise
    """
    if issue.body is None:
        return False
    return PROCESSED_MARKER in issue.body


def count_unprocessed_issues(
    repo: str = DEFAULT_REPO,
    use_cache: bool = True,
) -> tuple[int, int]:
    """Count how many open issues are unprocessed.

    Unprocessed issues are those created via browser that haven't been
    integrated into the roadmap via /plan command.

    Args:
        repo: Repository in owner/repo format
        use_cache: Whether to use cached issues if available

    Returns:
        Tuple of (unprocessed_count, total_count)
    """
    if use_cache:
        issues, _ = get_issues_with_cache(repo=repo, state="open")
    else:
        issues = fetch_github_issues(repo=repo, state="open")

    if not issues:
        return 0, 0

    unprocessed = [issue for issue in issues if not is_issue_processed(issue)]
    return len(unprocessed), len(issues)


def get_unprocessed_issues(
    repo: str = DEFAULT_REPO,
    use_cache: bool = True,
) -> list[GitHubIssue]:
    """Get all unprocessed open issues.

    Args:
        repo: Repository in owner/repo format
        use_cache: Whether to use cached issues if available

    Returns:
        List of unprocessed GitHubIssue objects
    """
    if use_cache:
        issues, _ = get_issues_with_cache(repo=repo, state="open")
    else:
        issues = fetch_github_issues(repo=repo, state="open")

    return [issue for issue in issues if not is_issue_processed(issue)]
