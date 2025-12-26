#!/bin/bash
# Pre-commit hook to validate dev-docs exist
# Prevents context loss across Claude Code sessions

set -e

# Check session-state.md exists and is not empty
if [ ! -s "dev/session-state.md" ]; then
    echo "ERROR: dev/session-state.md is missing or empty"
    echo "Update dev/session-state.md with current work status before committing"
    exit 1
fi

# Check EXECUTION-PLAN.md exists
if [ ! -s "dev/EXECUTION-PLAN.md" ]; then
    echo "ERROR: dev/EXECUTION-PLAN.md is missing or empty"
    exit 1
fi

# Check for active work without dev-docs (only if gh is available)
if command -v gh &> /dev/null; then
    OPEN_EPICS=$(gh issue list --state open --label "epic" --json number 2>/dev/null | grep -c "number" || echo "0")
    if [ "$OPEN_EPICS" -gt 0 ]; then
        ACTIVE_DOCS=$(find dev/active -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l | tr -d " ")
        if [ "$ACTIVE_DOCS" -eq 0 ]; then
            echo "WARNING: Active epics exist but dev/active/ has no task folders"
            echo "Consider creating dev-docs for current work"
            # This is a warning, not an error - don't exit 1
        fi
    fi
fi

exit 0
