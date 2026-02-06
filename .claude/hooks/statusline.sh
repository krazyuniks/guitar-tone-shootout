#!/usr/bin/env bash
# GTS Status Line — shown persistently in Claude Code UI
#
# Receives JSON on stdin with model, workspace, context_window fields.
# Must complete fast (<200ms) — no Docker or network calls.

set -euo pipefail

input=$(cat)

MODEL=$(echo "$input" | jq -r '.model.display_name // "unknown"')
PCT=$(echo "$input" | jq -r '.context_window.used_percentage // 0' | cut -d. -f1)

# Git branch (fast — reads local .git)
BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "?")

# Docker health (read cached status from session-start hook, no live check)
CACHE="/tmp/gts-docker-status"
if [ -f "$CACHE" ] && [ "$(find "$CACHE" -mmin -5 2>/dev/null)" ]; then
    DOCKER=$(cat "$CACHE")
else
    # Quick container count — faster than full health check
    UP=$(docker compose ps --status running -q 2>/dev/null | wc -l | tr -d ' ')
    if [ "$UP" -ge 6 ]; then
        DOCKER="ok"
    elif [ "$UP" -gt 0 ]; then
        DOCKER="${UP}/6"
    else
        DOCKER="down"
    fi
    echo "$DOCKER" > "$CACHE" 2>/dev/null || true
fi

# Last test result (from adherence cache)
TEST_CACHE="/tmp/gts-adherence-cache"
if [ -d "$TEST_CACHE" ]; then
    LATEST=$(find "$TEST_CACHE" -name "*.json" -type f 2>/dev/null | sort -r | head -1)
    if [ -n "$LATEST" ]; then
        HAS_FAIL=$(jq -r '.has_failure // false' "$LATEST" 2>/dev/null || echo "unknown")
        if [ "$HAS_FAIL" = "true" ]; then
            TESTS="fail"
        elif [ "$HAS_FAIL" = "false" ]; then
            TESTS="pass"
        else
            TESTS="?"
        fi
    else
        TESTS="-"
    fi
else
    TESTS="-"
fi

echo "[$MODEL] $BRANCH | docker:$DOCKER | tests:$TESTS | ${PCT}% ctx"
