#!/usr/bin/env bash
# Auth Persistence Check Hook
#
# Runs at session start to verify T3K authentication is available.
# Delegates to worktree.py auth-status for the actual check.
# Skips if worktree is fresh (< 5 min old) since setup just ran auth restore.
#
# Behavior:
# - Calls worktree.py auth-status to check and display auth state
# - Provides clear instructions if auth is missing/expired
# - Never blocks session start (exit 0)

set -euo pipefail

# Get git root
GIT_ROOT=$(git rev-parse --show-toplevel 2>/dev/null) || exit 0
cd "$GIT_ROOT"

# Only run if worktree.py exists
[ -f "./worktree.py" ] || exit 0

# Skip if worktree is fresh (just created, auth was restored during setup)
if ./worktree.py is-fresh --quiet 2>/dev/null; then
    exit 0
fi

# Run auth-status - it handles all output and exit codes
# Suppress errors to avoid blocking session start
./worktree.py auth-status 2>/dev/null || {
    # Auth check failed - provide instructions
    echo "# Auth Status: Not Available"
    echo ""
    echo "To authenticate (required for T3K API features):"
    echo "  ./worktree.py auth-login"
    echo ""
}

# Never block session start
exit 0
