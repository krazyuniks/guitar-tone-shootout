#!/bin/bash
#
# PreToolUse hook: Validate CLI commands before execution
#
# Catches common mistakes with worktree.py, just commands, and
# direct tool invocations that violate container-first rules.
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

# ============================================
# Container-first rule enforcement
# All project code runs in Docker via just.
# Raw host invocations of uv/pnpm violate this rule.
# Exception: E2E tests run on host in tests/e2e/python/
# ============================================

# Catch: raw uv run pytest (not in E2E path)
# Match "uv run pytest" as a real command, not inside a quoted string.
if echo "$command" | grep -qE "(^|[;&|])\s*uv\s+run\s+pytest"; then
    # Allow E2E exception: cd tests/e2e/python && uv run pytest
    if ! echo "$command" | grep -qE "tests/e2e"; then
        cat << 'EOF'
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": "BLOCKED: Raw `uv run pytest` is not allowed on host.\n\nAll tests run inside Docker via just:\n  just test              # Unit + Integration\n  just tdd <path>        # Single test during development\n  just test-regression   # Stack connectivity\n  just test-golden-path  # E2E golden path (on host, via just)\n\nException: `cd tests/e2e/python && uv run pytest` is allowed for direct E2E runs."
  }
}
EOF
        exit 0
    fi
fi

# Catch: raw uv run ruff
if echo "$command" | grep -qE "(^|[;&|])\s*uv\s+run\s+ruff"; then
    cat << 'EOF'
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": "BLOCKED: Raw `uv run ruff` is not allowed on host.\n\nRun linting inside Docker via just:\n  just check-backend     # Lint + type check backend\n  just check             # All checks"
  }
}
EOF
    exit 0
fi

# Catch: raw uv run mypy
if echo "$command" | grep -qE "(^|[;&|])\s*uv\s+run\s+mypy"; then
    cat << 'EOF'
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": "BLOCKED: Raw `uv run mypy` is not allowed on host.\n\nRun type checking inside Docker via just:\n  just check-backend     # Lint + type check backend\n  just check             # All checks"
  }
}
EOF
    exit 0
fi

# Catch: raw pnpm (not inside just recipes)
if echo "$command" | grep -qE "(^|[;&|])\s*pnpm\s"; then
    cat << 'EOF'
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": "BLOCKED: Raw `pnpm` is not allowed on host.\n\nRun frontend commands via just:\n  just build-astro       # Build Astro frontend\n  just watch-astro       # Watch mode\n  just check-astro       # Lint + type check frontend\n  just check             # All checks"
  }
}
EOF
    exit 0
fi

# ============================================
# Validation command enforcement
# NEVER use curl/wget/httpie for validation.
# Use: just test-golden-path, just tdd, Chrome DevTools MCP
# ============================================

# Catch: curl/wget/httpie used as validation
# Check first word of each pipeline segment (split on ; & | separators).
# This avoids false positives when "curl" appears in a string argument
# (e.g. inside a commit message or heredoc).
_has_curl_cmd=false
while IFS= read -r segment; do
    first_word=$(echo "$segment" | awk '{print $1}' | tr -d '"'"'" )
    if [[ "$first_word" =~ ^(curl|wget|httpie)$ ]]; then
        _has_curl_cmd=true
        break
    fi
done < <(echo "$command" | sed 's/[;&|]\+/\n/g')

if [ "$_has_curl_cmd" = "true" ]; then
    cat << 'EOF'
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": "BLOCKED: curl/wget/httpie are not allowed for validation.\n\nUse the correct validation tools:\n  just test-golden-path  # E2E golden path\n  just tdd <path>        # Run specific tests\n  just test-regression   # Stack connectivity\n\nFor UI validation: Chrome DevTools MCP (requires MCP server).\nFor admin API inspection: just commands or Chrome DevTools MCP."
  }
}
EOF
    exit 0
fi

# All checks passed - allow the command
exit 0
