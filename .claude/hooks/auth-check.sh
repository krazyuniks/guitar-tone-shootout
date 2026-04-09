#!/usr/bin/env bash
# Auth Persistence Check Hook
#
# Runs at session start to verify T3K authentication is available.
# Delegates to the canonical just auth status command.
# Skips if worktree is fresh (< 5 min old) since setup just ran auth restore.
#
# Behavior:
# - Calls just t3k-auth-status to check and display auth state
# - Provides clear instructions if auth is missing/expired
# - Never blocks session start (exit 0)
#
# DECISION: Why "never block session start" is the correct behaviour here:
#
# Auth is only required for T3K API features (syncing guitar gear data from
# the T3K source). All other development work — backend services, unit/integration
# tests, UI, database migrations, epic workflow — proceeds without auth.
#
# Blocking session start on missing auth would prevent developers from doing
# any non-T3K work, which is the majority of the codebase. The correct pattern
# is to warn loudly at session start so the developer knows to run
# `just t3k-auth` if they intend to work on T3K features.
#
# If auth were required for ALL operations (e.g., the app wouldn't start without
# it), then blocking would be correct. That's not the case here.

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

# Run auth status - it handles all output and exit codes
# Suppress errors to avoid blocking session start
just t3k-auth-status 2>/dev/null || {
    # Auth check failed - provide instructions
    echo "# Auth Status: Not Available"
    echo ""
    echo "To authenticate (required for T3K API features):"
    echo "  just t3k-auth"
    echo ""
}

# Never block session start
exit 0
