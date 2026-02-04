"""Local state validation for worktree operations.

Provides comprehensive checks for local state before starting work:
- Orphaned worktrees
- Uncommitted changes across all worktrees
- Stale lifecycle operations
"""

from dataclasses import dataclass
from pathlib import Path


@dataclass
class StateIssue:
    """Represents a local state issue that needs resolution."""

    category: str  # "orphan", "uncommitted", "stale_op", "leftover"
    severity: str  # "error", "warning"
    message: str
    path: Path | None = None
    auto_fixable: bool = False


@dataclass
class LocalStateReport:
    """Result of local state validation."""

    issues: list[StateIssue]

    @property
    def has_errors(self) -> bool:
        """Check if report contains any errors."""
        return any(i.severity == "error" for i in self.issues)

    @property
    def has_warnings(self) -> bool:
        """Check if report contains any warnings."""
        return any(i.severity == "warning" for i in self.issues)

    @property
    def is_clean(self) -> bool:
        """Check if report has no issues."""
        return len(self.issues) == 0

    def issues_by_category(self, category: str) -> list[StateIssue]:
        """Get issues filtered by category."""
        return [i for i in self.issues if i.category == category]


def check_local_state(worktree_root: Path) -> LocalStateReport:
    """Run all local state checks and return a report.

    Checks:
    1. Orphaned worktrees (not in registry)
    2. Uncommitted changes in all registered worktrees
    3. Stale lifecycle operations

    Args:
        worktree_root: Root directory containing all worktrees

    Returns:
        LocalStateReport with all discovered issues
    """
    issues: list[StateIssue] = []

    # Run all checks and collect issues
    issues.extend(check_orphaned_worktrees(worktree_root))
    issues.extend(check_leftover_directories(worktree_root))
    issues.extend(check_all_worktrees_for_changes(worktree_root))
    issues.extend(check_stale_operations(worktree_root))

    return LocalStateReport(issues=issues)


def check_orphaned_worktrees(worktree_root: Path) -> list[StateIssue]:
    """Find worktrees that exist on disk but aren't in registry.

    An orphaned worktree is one that exists as a git worktree but is not
    tracked in the registry database. This can happen when:
    - Registry was reset or corrupted
    - Worktree was created manually outside of worktree.py
    - Setup failed partway through and rollback was incomplete

    Args:
        worktree_root: Root directory containing all worktrees

    Returns:
        List of StateIssue for each orphaned worktree
    """
    from .registry import find_orphaned_worktrees

    issues: list[StateIssue] = []

    try:
        orphans = find_orphaned_worktrees()
        for orphan in orphans:
            issues.append(
                StateIssue(
                    category="orphan",
                    severity="warning",
                    message=f"Orphaned worktree: {orphan.path.name} (branch: {orphan.branch})",
                    path=orphan.path,
                    auto_fixable=True,  # Can be registered or removed
                )
            )
    except Exception as e:
        issues.append(
            StateIssue(
                category="orphan",
                severity="error",
                message=f"Failed to check for orphaned worktrees: {e}",
            )
        )

    return issues


def check_leftover_directories(worktree_root: Path) -> list[StateIssue]:
    """Find leftover directories that are not git worktrees.

    These are directories in the worktrees root that:
    - Are not registered git worktrees
    - Are not known system directories (main, backups, etc.)
    - May have been left behind after incomplete cleanup

    This catches cases where git worktree remove succeeded but the
    directory wasn't fully deleted.

    Args:
        worktree_root: Root directory containing all worktrees

    Returns:
        List of StateIssue for each leftover directory
    """
    from .git_ops import list_git_worktrees

    issues: list[StateIssue] = []

    # Known system directories that should not be flagged
    known_system_dirs = {
        "main",
        "backups",
        "di_tracks",
        "gts-storage",
        "guitar-tone-shootout-seed",
        "guitar-tone-shootout-wiki",
        "guitar-tone-shootout.git",
    }

    # Get all git worktree paths
    try:
        git_worktrees = list_git_worktrees()
        git_worktree_paths = {wt.path.name for wt in git_worktrees}
    except Exception:
        git_worktree_paths = set()

    try:
        # Scan the worktrees root for directories
        for item in worktree_root.iterdir():
            if not item.is_dir():
                continue

            # Skip hidden directories
            if item.name.startswith("."):
                continue

            # Skip known system directories
            if item.name in known_system_dirs:
                continue

            # Skip if it's a registered git worktree
            if item.name in git_worktree_paths:
                continue

            # Check if it's a git worktree (has .git file)
            git_file = item / ".git"
            if git_file.exists() and git_file.is_file():
                # It's a git worktree but not registered - handled by orphan check
                continue

            # This is a leftover directory
            # Check if it has any content besides known safe items
            safe_items = {".git", ".DS_Store", ".worktree-state"}
            try:
                contents = set(f.name for f in item.iterdir())
                unknown_contents = contents - safe_items

                if unknown_contents:
                    # Has unknown files - might have work in progress
                    issues.append(
                        StateIssue(
                            category="leftover",
                            severity="error",
                            message=f"Leftover directory with unknown files: {item.name}",
                            path=item,
                            auto_fixable=False,  # Needs manual inspection
                        )
                    )
                else:
                    # Only has safe-to-delete files
                    issues.append(
                        StateIssue(
                            category="leftover",
                            severity="warning",
                            message=f"Leftover directory (empty/safe): {item.name}",
                            path=item,
                            auto_fixable=True,  # Can be safely deleted
                        )
                    )
            except PermissionError:
                issues.append(
                    StateIssue(
                        category="leftover",
                        severity="error",
                        message=f"Leftover directory (permission denied): {item.name}",
                        path=item,
                        auto_fixable=False,
                    )
                )

    except Exception as e:
        issues.append(
            StateIssue(
                category="leftover",
                severity="error",
                message=f"Failed to check for leftover directories: {e}",
            )
        )

    return issues


def check_all_worktrees_for_changes(worktree_root: Path) -> list[StateIssue]:
    """Check all registered worktrees for uncommitted changes.

    This helps prevent losing work when switching between worktrees
    or before performing operations that might affect multiple worktrees.

    Args:
        worktree_root: Root directory containing all worktrees

    Returns:
        List of StateIssue for each worktree with uncommitted changes
    """
    from .registry import list_worktrees
    from .sync_ops import has_uncommitted_changes, has_untracked_files

    issues: list[StateIssue] = []

    try:
        worktrees = list_worktrees(include_removed=False)
        for wt in worktrees:
            wt_path = Path(wt.worktree_path)
            if not wt_path.exists():
                continue

            has_changes = has_uncommitted_changes(wt_path)
            has_untracked = has_untracked_files(wt_path)

            if has_changes or has_untracked:
                change_types = []
                if has_changes:
                    change_types.append("uncommitted changes")
                if has_untracked:
                    change_types.append("untracked files")

                issues.append(
                    StateIssue(
                        category="uncommitted",
                        severity="warning",
                        message=f"Worktree '{wt.worktree_name}' has {' and '.join(change_types)}",
                        path=wt_path,
                        auto_fixable=False,  # Needs manual commit decision
                    )
                )
    except Exception as e:
        issues.append(
            StateIssue(
                category="uncommitted",
                severity="error",
                message=f"Failed to check for uncommitted changes: {e}",
            )
        )

    return issues


def check_stale_operations(worktree_root: Path) -> list[StateIssue]:
    """Check for stale lifecycle operations (setup/teardown stuck).

    Operations that have been pending for too long may indicate a failed
    setup or teardown that needs manual cleanup.

    Args:
        worktree_root: Root directory containing all worktrees

    Returns:
        List of StateIssue for each stale operation
    """
    from .lifecycle import get_stale_operations_simple

    issues: list[StateIssue] = []

    try:
        stale_ops = get_stale_operations_simple()
        for op_id, op_data in stale_ops:
            started_at = op_data.get("started_at", "unknown time")
            issues.append(
                StateIssue(
                    category="stale_op",
                    severity="error",
                    message=f"Stale operation '{op_id}' started at {started_at}",
                    auto_fixable=True,  # Can be marked as failed
                )
            )
    except Exception as e:
        issues.append(
            StateIssue(
                category="stale_op",
                severity="error",
                message=f"Failed to check for stale operations: {e}",
            )
        )

    return issues


def fix_orphaned_worktree(worktree_path: Path, action: str = "register") -> bool:
    """Fix an orphaned worktree by registering or removing it.

    Args:
        worktree_path: Path to the orphaned worktree
        action: "register" to add to registry, "remove" to delete

    Returns:
        True if fix was successful

    Raises:
        ValueError: If action is not "register" or "remove"
    """
    if action not in ("register", "remove"):
        raise ValueError(f"Invalid action: {action}. Must be 'register' or 'remove'")

    if action == "register":
        return _register_orphaned_worktree(worktree_path)
    else:
        return _remove_orphaned_worktree(worktree_path)


def _register_orphaned_worktree(worktree_path: Path) -> bool:
    """Register an orphaned worktree in the registry.

    Args:
        worktree_path: Path to the orphaned worktree

    Returns:
        True if registration was successful
    """
    from .registry import add_orphan_to_registry, find_orphaned_worktrees

    try:
        # Find the orphan by path
        orphans = find_orphaned_worktrees()
        target_orphan = None
        for orphan in orphans:
            if orphan.path.resolve() == worktree_path.resolve():
                target_orphan = orphan
                break

        if not target_orphan:
            return False

        # Register it
        add_orphan_to_registry(target_orphan)
        return True
    except Exception:
        return False


def _remove_orphaned_worktree(worktree_path: Path) -> bool:
    """Remove an orphaned worktree from disk.

    Args:
        worktree_path: Path to the orphaned worktree

    Returns:
        True if removal was successful
    """
    from .git_ops import prune_worktrees, remove_worktree

    try:
        # Remove the git worktree
        remove_worktree(worktree_path, force=True)
        prune_worktrees()
        return True
    except Exception:
        return False


def fix_stale_operation(operation_id: str, action: str = "fail") -> bool:
    """Fix a stale operation by marking it as failed or complete.

    Args:
        operation_id: ID of the stale operation
        action: "fail" to mark as failed, "complete" to mark as complete

    Returns:
        True if fix was successful

    Raises:
        ValueError: If action is not "fail" or "complete"
    """
    if action not in ("fail", "complete"):
        raise ValueError(f"Invalid action: {action}. Must be 'fail' or 'complete'")

    from .lifecycle import mark_complete, mark_failed

    try:
        if action == "fail":
            mark_failed(operation_id, "Manually marked as failed due to stale state")
        else:
            mark_complete(operation_id)
        return True
    except Exception:
        return False
