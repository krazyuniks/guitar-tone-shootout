#!/bin/bash
# Adherence Check Hook (PreToolUse on Bash)
#
# Blocks git commit if:
# - Tests have never been run (no cache directory or files)
# - Cached test results have expired (older than 5 min — must re-run)
# - Cached test results show failures
#
# Reads from /tmp/gts-adherence-cache/ (written by capture-test-logs.sh).
#
# Hook receives JSON on stdin:
# {
#   "tool_input": {"command": "..."}
# }

set -e

CACHE_DIR="/tmp/gts-adherence-cache"
TTL_SECONDS=300  # 5 minutes

# Read JSON input from stdin
input=$(cat)

# Extract the command being run
command=$(echo "$input" | jq -r '.tool_input.command // ""')

# Only check for git commit commands
if ! echo "$command" | grep -qE "git\s+commit"; then
    exit 0
fi

# Check if cache directory exists
if [ ! -d "$CACHE_DIR" ]; then
    cat << 'EOF'
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": "BLOCKED: Tests have never been run in this session.\n\nYou must run tests before committing:\n  just test            # Unit + Integration\n  just test-regression # Stack connectivity check\n\nRun tests, verify they pass, then commit."
  }
}
EOF
    exit 0
fi

# Find cache files
cache_files=$(find "$CACHE_DIR" -type f -name "*.json" 2>/dev/null | sort -r)

if [ -z "$cache_files" ]; then
    cat << 'EOF'
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": "BLOCKED: Tests have never been run in this session.\n\nYou must run tests before committing:\n  just test            # Unit + Integration\n  just test-regression # Stack connectivity check\n\nRun tests, verify they pass, then commit."
  }
}
EOF
    exit 0
fi

# Get the most recent cache file
latest_cache=$(echo "$cache_files" | head -n1)

# Check if cache is expired (older than 5 minutes)
if [ "$(uname)" = "Darwin" ]; then
    # macOS: use stat -f
    file_mtime=$(stat -f %m "$latest_cache" 2>/dev/null || echo 0)
else
    # Linux: use stat -c
    file_mtime=$(stat -c %Y "$latest_cache" 2>/dev/null || echo 0)
fi
current_time=$(date +%s)
age=$((current_time - file_mtime))

if [ "$age" -gt "$TTL_SECONDS" ]; then
    cat << 'EOF'
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": "BLOCKED: Test results have expired (older than 5 minutes).\n\nRe-run tests to confirm they still pass:\n  just test            # Unit + Integration\n  just test-regression # Stack connectivity check\n\nRun tests, verify they pass, then commit."
  }
}
EOF
    exit 0
fi

# Check all cache files for failures
has_any_failure=false
for cache_file in $cache_files; do
    # Skip expired files
    if [ "$(uname)" = "Darwin" ]; then
        file_mtime=$(stat -f %m "$cache_file" 2>/dev/null || echo 0)
    else
        file_mtime=$(stat -c %Y "$cache_file" 2>/dev/null || echo 0)
    fi
    age=$((current_time - file_mtime))

    if [ "$age" -gt "$TTL_SECONDS" ]; then
        continue
    fi

    # Check for failure flag
    has_failure=$(jq -r '.has_failure // false' "$cache_file" 2>/dev/null || echo "false")
    if [ "$has_failure" = "true" ]; then
        has_any_failure=true
        break
    fi
done

# Block commit if failures detected
if [ "$has_any_failure" = "true" ]; then
    cat << 'EOF'
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": "BLOCKED: Tests failed. Run tests again before committing.\n\nCached test results show failures. You must:\n1. Fix the failing tests\n2. Re-run the tests (just test or just tdd <path>)\n3. Verify all tests pass\n4. Then try committing again"
  }
}
EOF
    exit 0
fi

# All clear - allow commit
exit 0
