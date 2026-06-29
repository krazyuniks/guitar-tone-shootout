#!/bin/bash
# Block Ad-Hoc Infrastructure Commands (PreToolUse on Bash)
#
# PRINCIPLE: Use the worktree engine + just - they own the stack lifecycle.
# Never run ad-hoc Docker commands for infrastructure management.
#
# This hook blocks:
# - Docker volume deletion (data loss)
# - Docker system/container pruning (infrastructure loss)
# - Database drops/truncates (data loss)
# - Compose down with -v flag (volume deletion)
#
# CORRECT approach for ANY infrastructure issue:
#   worktree up gts <branch>     # bring a feature stack up (idempotent)
#   just up-d / just down        # start/stop the main stack
#
# If destructive cleanup is truly needed:
#   Ask the user to run the command manually

set -e

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

if [ -z "$COMMAND" ]; then
    exit 0
fi

# Normalize command: collapse whitespace, handle multiline
NORMALIZED=$(echo "$COMMAND" | tr '\n' ' ' | tr -s ' ')

# === VOLUME DELETION ===
VOLUME_PATTERNS=(
    "docker volume rm"
    "docker volume prune"
    "docker volume remove"
    "xargs.*docker volume"
    "xargs -r docker volume"
    "docker compose.*down.*-v"
    "docker-compose.*down.*-v"
    "down -v"
    "down --volumes"
)

# === SYSTEM PRUNING ===
PRUNE_PATTERNS=(
    "docker system prune"
    "docker container prune"
    "docker image prune.*-a"
    "docker builder prune.*-a"
)

# === DATABASE DESTRUCTION ===
DB_PATTERNS=(
    "DROP DATABASE"
    "DROP SCHEMA.*CASCADE"
    "TRUNCATE.*CASCADE"
    "dropdb"
    "pg_dropcluster"
)

# === DANGEROUS COMPOSE OPERATIONS ===
COMPOSE_PATTERNS=(
    "docker compose.*rm.*-v"
    "docker-compose.*rm.*-v"
    "docker compose.*down.*--volumes"
    "docker-compose.*down.*--volumes"
)

# Check all pattern categories
check_patterns() {
    local category="$1"
    shift
    local patterns=("$@")

    for pattern in "${patterns[@]}"; do
        if echo "$NORMALIZED" | grep -qiE "$pattern"; then
            echo ""
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            echo "  ⛔ BLOCKED: $category"
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            echo ""
            echo "  Pattern matched: $pattern"
            echo ""
            echo "  Command: ${COMMAND:0:200}"
            [ ${#COMMAND} -gt 200 ] && echo "  ... (truncated)"
            echo ""
            echo "  ┌─────────────────────────────────────────────────────────────┐"
            echo "  │  USE THE PROVIDED TOOLING:                                  │"
            echo "  │                                                             │"
            echo "  │    worktree up gts <branch>   # Bring a feature stack up    │"
            echo "  │    just up-d / just down      # Start/stop the main stack   │"
            echo "  │                                                             │"
            echo "  │  For destructive ops: ASK USER to run command manually.     │"
            echo "  └─────────────────────────────────────────────────────────────┘"
            echo ""
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            exit 2  # Block the command
        fi
    done
}

check_patterns "Volume deletion detected" "${VOLUME_PATTERNS[@]}"
check_patterns "System/container pruning detected" "${PRUNE_PATTERNS[@]}"
check_patterns "Database destruction detected" "${DB_PATTERNS[@]}"
check_patterns "Dangerous compose operation detected" "${COMPOSE_PATTERNS[@]}"

exit 0
