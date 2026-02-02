#!/bin/bash
# SessionStart hook: Pull latest changes using worktree.py
#
# Delegates to worktree.py sync-start for git fetch/rebase.
# Skips if worktree is fresh (< 5 min old) since setup already synced.
# Runs in background to avoid blocking Claude startup.

GIT_ROOT=$(git rev-parse --show-toplevel 2>/dev/null)
[ -z "$GIT_ROOT" ] && exit 0
cd "$GIT_ROOT"

# Only run if worktree.py exists
[ -f "./worktree.py" ] || exit 0

# Skip if worktree is fresh (just created, already synced during setup)
if ./worktree.py is-fresh --quiet 2>/dev/null; then
    exit 0
fi

# Run sync-start in background with quiet mode
# The --quiet flag suppresses output, nohup+disown ensures non-blocking
nohup ./worktree.py sync-start --quiet >/dev/null 2>&1 &
disown

exit 0
