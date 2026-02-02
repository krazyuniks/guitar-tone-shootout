#!/bin/bash
# Merge Teardown Hook (PostToolUse on Bash)
#
# After detecting a PR is MERGED (via gh pr view), automatically tears down
# the worktree. This removes the need for Claude to manually handle cleanup.
#
# Hook receives JSON on stdin:
# {
#   "tool_input": {"command": "..."},
#   "tool_result": {"stdout": "...", "stderr": "...", "exit_code": 0}
# }

set -e

# Read tool result from stdin
INPUT=$(cat)

# Extract command from tool_input
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

if [ -z "$COMMAND" ]; then
    exit 0
fi

# Only run for gh pr view commands with --json
if ! echo "$COMMAND" | grep -qE "gh\s+pr\s+view.*--json"; then
    exit 0
fi

# Extract stdout
STDOUT=$(echo "$INPUT" | jq -r '.tool_result.stdout // empty')
EXIT_CODE=$(echo "$INPUT" | jq -r '.tool_result.exit_code // .tool_result.exitCode // 0')

# Skip if command failed
if [ "$EXIT_CODE" != "0" ]; then
    exit 0
fi

# Check if PR state is MERGED
STATE=$(echo "$STDOUT" | jq -r '.state // empty' 2>/dev/null)

if [ "$STATE" != "MERGED" ]; then
    exit 0
fi

# Get current branch
CURRENT_BRANCH=$(git branch --show-current 2>/dev/null)

# Don't teardown main
if [ "$CURRENT_BRANCH" = "main" ] || [ -z "$CURRENT_BRANCH" ]; then
    exit 0
fi

# Get worktree root (parent of current worktree)
WORKTREE_ROOT=$(cd .. && pwd)
MAIN_WORKTREE="$WORKTREE_ROOT/main"

# Verify main worktree exists
if [ ! -d "$MAIN_WORKTREE" ]; then
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  ⚠️  PR Merged - Manual Teardown Required"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "Main worktree not found at: $MAIN_WORKTREE"
    echo "Run manually: ./worktree.py teardown $CURRENT_BRANCH"
    echo ""
    exit 0
fi

# Get issue number from branch (format: 123/feature-name)
ISSUE_NUM=$(echo "$CURRENT_BRANCH" | cut -d/ -f1)

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ✓ PR Merged - Auto Teardown"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Branch: $CURRENT_BRANCH"
echo "Issue:  #$ISSUE_NUM"
echo ""
echo "→ Closing GitHub issue..."

# Close the GitHub issue
if gh issue close "$ISSUE_NUM" --reason completed --repo krazyuniks/guitar-tone-shootout 2>/dev/null; then
    echo "  ✓ Issue #$ISSUE_NUM closed"
else
    echo "  ⚠️  Could not close issue (may already be closed)"
fi

echo ""
echo "→ Switching to main worktree for teardown..."
echo ""

# Change to main and run teardown
# Note: We use a subshell and background the teardown since we're about
# to delete the directory we're in
cd "$MAIN_WORKTREE"

# Update main branch first
echo "→ Updating main branch..."
git fetch origin
git pull --ff-only origin main 2>/dev/null || true

echo ""
echo "→ Tearing down worktree: $CURRENT_BRANCH"
echo ""

# Run teardown (force since branch is already merged/deleted on remote)
./worktree.py teardown "$CURRENT_BRANCH" --force 2>&1 || {
    echo ""
    echo "⚠️  Teardown had issues. Run manually if needed:"
    echo "   cd $MAIN_WORKTREE && ./worktree.py teardown $CURRENT_BRANCH --force"
}

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ✓ Cleanup Complete"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "⚠️  Your working directory was deleted."
echo ""
echo "Run this to continue:"
echo "  cd $MAIN_WORKTREE"
echo ""
echo "To start new work:"
echo "  ./worktree.py setup <issue-number>"
echo ""

exit 0
