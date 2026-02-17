#!/bin/bash
# Block edits to auto-generated config files (PreToolUse on Write, Edit)
#
# These files are managed by worktree.py setup and should never be
# edited manually or by AI agents.

set -e

INPUT=$(cat)

# Get the file path being modified
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

if [ -z "$FILE_PATH" ]; then
    exit 0
fi

# Extract just the filename
BASENAME=$(basename "$FILE_PATH")

# Check against protected files
case "$BASENAME" in
    docker-compose.override.yml|.env.local|.env.secrets)
        echo ""
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "  BLOCKED: $BASENAME is auto-generated"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo ""
        echo "  This file is managed by: ./worktree.py setup <name>"
        echo "  Do not edit it directly."
        echo ""
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        exit 2
        ;;
esac

exit 0
