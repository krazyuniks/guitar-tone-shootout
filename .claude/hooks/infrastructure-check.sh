#!/usr/bin/env bash
# Infrastructure Health Check Hook
#
# Runs at session start to detect and auto-fix frontend Vite staleness.
# This ensures a healthy development environment before starting work.
# Skips if worktree is fresh (< 5 min old) since setup just started services.
#
# Behavior:
# - Checks if we're in a registered worktree
# - Runs health check with auto-fix enabled
# - Reports any issues that couldn't be auto-fixed
#
# Performance target: < 500ms for healthy environments

set -euo pipefail

# Only run if worktree.py exists (we're in the project)
GIT_ROOT=$(git rev-parse --show-toplevel 2>/dev/null) || exit 0
cd "$GIT_ROOT"
[ -f "./worktree.py" ] || exit 0

# Skip if worktree is fresh (just created, services were just started during setup)
if ./worktree.py is-fresh --quiet 2>/dev/null; then
    exit 0
fi

# Run health check with auto-fix.
# The health command will:
# - Check Docker container status
# - Check HTTP endpoints
# - Detect Vite staleness from logs
# - Auto-restart frontend if stale
# Failures are surfaced here — not silently swallowed.
./worktree.py health

exit 0
