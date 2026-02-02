#!/bin/bash
# CI Monitor Hook (PostToolUse on Bash)
#
# After `gh pr create`, waits for CI to start then shows status.
# Provides monitoring command for continued tracking.
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

# Only run for gh pr create commands
if ! echo "$COMMAND" | grep -qE "gh\s+pr\s+create"; then
    exit 0
fi

# Extract stdout to find PR URL
STDOUT=$(echo "$INPUT" | jq -r '.tool_result.stdout // empty')
EXIT_CODE=$(echo "$INPUT" | jq -r '.tool_result.exit_code // .tool_result.exitCode // 0')

# Skip if command failed
if [ "$EXIT_CODE" != "0" ]; then
    exit 0
fi

# Extract PR URL from output
PR_URL=$(echo "$STDOUT" | grep -oE 'https://github.com/[^/]+/[^/]+/pull/[0-9]+' | head -1)

if [ -z "$PR_URL" ]; then
    exit 0
fi

# Extract PR number
PR_NUM=$(echo "$PR_URL" | grep -oE '[0-9]+$')

if [ -z "$PR_NUM" ]; then
    exit 0
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  CI Monitor: PR #$PR_NUM"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "→ Waiting 10s for CI to start..."
sleep 10

# Check CI status
echo "→ Checking CI status..."
echo ""

if gh pr checks "$PR_NUM" --repo krazyuniks/guitar-tone-shootout 2>/dev/null; then
    echo ""
    echo "→ To continue monitoring:"
    echo "  gh pr checks $PR_NUM --repo krazyuniks/guitar-tone-shootout --watch"
else
    echo "  (CI may still be initializing)"
    echo ""
    echo "→ Check manually: $PR_URL/checks"
    echo "→ Or run: gh pr checks $PR_NUM --repo krazyuniks/guitar-tone-shootout"
fi

echo ""

exit 0
