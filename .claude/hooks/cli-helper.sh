#!/bin/bash
#
# PreToolUse hook: Validate CLI commands before execution
#
# Catches common mistakes with worktree.py and other CLI tools
# before they waste time on failed executions.
#

# Read JSON input from stdin
input=$(cat)

# Extract the command being run
command=$(echo "$input" | jq -r '.tool_input.command // ""')

# Skip if not a bash command
if [ -z "$command" ]; then
    exit 0
fi

# ============================================
# worktree.py validation
# ============================================

# Catch: prune --force (doesn't exist)
if echo "$command" | grep -qE "worktree\.py\s+prune\s+.*--force"; then
    cat << 'EOF'
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": "BLOCKED: `worktree.py prune` has NO --force flag.\n\n`prune` removes stale registry entries immediately (no dry-run).\n\nDid you mean:\n  - `./worktree.py cleanup --force` (clean merged branches)\n  - `./worktree.py prune` (remove stale entries, no flag needed)"
  }
}
EOF
    exit 0
fi

# Catch: cleanup without --force (dry-run warning)
if echo "$command" | grep -qE "worktree\.py\s+cleanup\s*$"; then
    # This is actually valid (dry-run), but let's warn
    echo "Note: \`cleanup\` without --force is dry-run mode. Use \`cleanup --force\` to actually clean up."
    exit 0
fi

# Catch: teardown main (dangerous)
if echo "$command" | grep -qE "worktree\.py\s+teardown\s+(main|\"main\")"; then
    cat << 'EOF'
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": "BLOCKED: Cannot teardown 'main' worktree.\n\nThe main worktree is the base for all other worktrees and cannot be removed."
  }
}
EOF
    exit 0
fi

# Catch: merge-pr without number
if echo "$command" | grep -qE "worktree\.py\s+merge-pr\s*$"; then
    cat << 'EOF'
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": "BLOCKED: `merge-pr` requires a PR number.\n\nUsage: ./worktree.py merge-pr <PR_NUMBER>\n\nExample: ./worktree.py merge-pr 123"
  }
}
EOF
    exit 0
fi

# ============================================
# just command validation
# ============================================

# Catch: just check-all (doesn't exist)
if echo "$command" | grep -qE "just\s+check-all"; then
    cat << 'EOF'
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": "BLOCKED: `just check-all` doesn't exist.\n\nDid you mean:\n  - `just check` (runs all checks)\n  - `just check-backend` (backend only)\n  - `just check-astro` (astro only)"
  }
}
EOF
    exit 0
fi

# All checks passed - allow the command
exit 0
