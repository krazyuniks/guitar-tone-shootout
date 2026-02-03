#!/usr/bin/env bash
# post-iteration-tracking-commit.sh
# Automatically commits ralph tracking files after each iteration.
#
# This callback eliminates the need for Claude to run:
#   git add .ralph-hybrid/ && git commit -m "chore: Update ralph tracking files"
#
# INSTALLATION:
# 1. Copy to your project's .ralph-hybrid/{feature}/callbacks/ directory
# 2. Make executable: chmod +x post-iteration-tracking-commit.sh
# 3. The callback runs automatically after each iteration
#
# ENVIRONMENT VARIABLES (set by Ralph):
# - RALPH_HYBRID_FEATURE_DIR: Path to feature directory
# - RALPH_HYBRID_FEATURE_NAME: Feature name
# - RALPH_HYBRID_ITERATION: Current iteration number
#
# NOTE: This callback runs AFTER Claude finishes but BEFORE the next iteration.
# If Claude already committed the tracking files, this callback will do nothing.

set -euo pipefail

# Skip if no tracking files to commit
if git diff --quiet .ralph-hybrid/ 2>/dev/null && \
   git diff --cached --quiet .ralph-hybrid/ 2>/dev/null; then
    # No changes in .ralph-hybrid/
    exit 0
fi

# Check for untracked files in .ralph-hybrid/
if [[ -z "$(git ls-files --others --exclude-standard .ralph-hybrid/ 2>/dev/null)" ]] && \
   git diff --quiet .ralph-hybrid/ 2>/dev/null && \
   git diff --cached --quiet .ralph-hybrid/ 2>/dev/null; then
    # Nothing to commit
    exit 0
fi

# Stage and commit tracking files
git add .ralph-hybrid/

# Only commit if there are staged changes
if ! git diff --cached --quiet .ralph-hybrid/ 2>/dev/null; then
    git commit -m "chore: Update ralph tracking files (iteration ${RALPH_HYBRID_ITERATION:-?})" \
        --no-verify 2>/dev/null || true
fi

exit 0
