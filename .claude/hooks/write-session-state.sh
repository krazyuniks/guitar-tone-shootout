#!/bin/bash
# Write session state for clean handoff between sessions
#
# Usage:
#   .claude/hooks/write-session-state.sh

GIT_ROOT=$(git rev-parse --show-toplevel 2>/dev/null)
[ -z "$GIT_ROOT" ] && exit 1
cd "$GIT_ROOT"

STATE_FILE=".claude/session-state.md"
TIMESTAMP=$(date +"%Y-%m-%d %H:%M:%S")

# Get current branch
BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")

# Extract issue number from branch name (e.g., "123/feature-name" -> "123")
ISSUE_NUM=$(echo "$BRANCH" | grep -oE '^[0-9]+' | head -1)

# Get uncommitted changes count
UNCOMMITTED=$(git status --short 2>/dev/null | wc -l | tr -d ' ')

# Determine status
if [ "$UNCOMMITTED" -gt 0 ]; then
    STATUS="**In Progress** - $UNCOMMITTED uncommitted changes."
elif [ -n "$ISSUE_NUM" ]; then
    STATUS="**Clean** - Working on issue #$ISSUE_NUM."
else
    STATUS="**Clean** - No pending work from previous session."
fi

cat > "$STATE_FILE" << EOF
# Session State

Last updated: $TIMESTAMP

## Status

$STATUS

## Current Work

**Branch:** $BRANCH
$(if [ -n "$ISSUE_NUM" ]; then echo "**GitHub Issue:** #$ISSUE_NUM"; fi)

## Git Status

\`\`\`
$(git status --short 2>/dev/null | head -20 || echo "(clean)")
\`\`\`

## Next Steps

$(if [ "$UNCOMMITTED" -gt 0 ]; then
    echo "Commit and push changes, or continue implementation."
elif [ -n "$ISSUE_NUM" ]; then
    echo "Continue work on #$ISSUE_NUM, or run \`/next-issue\` for new work."
else
    echo "Run \`/next-issue\` to find available work, or \`/plan\` to create new work."
fi)

---

*This file is auto-updated by the Stop hook. Review before \`/resume\`.*
EOF

echo "Session state written to $STATE_FILE"
