#!/bin/bash
# Test Log Capture Hook (PostToolUse on Bash)
#
# Captures pytest and vitest/pnpm test output for adherence tracking.
# Stores results in /tmp/gts-adherence-cache/ with 5-minute TTL.
#
# Hook receives JSON on stdin:
# {
#   "tool_input": {"command": "..."},
#   "tool_result": {"stdout": "...", "stderr": "...", "exit_code": 0}
# }

set -e

CACHE_DIR="/tmp/gts-adherence-cache"
TTL_SECONDS=300  # 5 minutes

# Ensure cache directory exists
mkdir -p "$CACHE_DIR"

# Clean up cache files older than TTL
find "$CACHE_DIR" -type f -mmin +5 -delete 2>/dev/null || true

# Read tool result from stdin
INPUT=$(cat)

# Extract command from tool_input
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

if [ -z "$COMMAND" ]; then
    exit 0
fi

# Check if this is a test command
IS_PYTEST=false
IS_VITEST=false

if echo "$COMMAND" | grep -qE "(^|\s)pytest(\s|$)" || echo "$COMMAND" | grep -q "pytest"; then
    IS_PYTEST=true
elif echo "$COMMAND" | grep -qE "just\s+(tdd|test|test-unit|test-regression|test-golden-path|check)\b"; then
    IS_PYTEST=true
fi

if echo "$COMMAND" | grep -qE "(pnpm test|vitest)"; then
    IS_VITEST=true
fi

# Exit if not a test command
if [ "$IS_PYTEST" = false ] && [ "$IS_VITEST" = false ]; then
    exit 0
fi

# Extract tool_result fields
STDOUT=$(echo "$INPUT" | jq -r '.tool_result.stdout // empty')
STDERR=$(echo "$INPUT" | jq -r '.tool_result.stderr // empty')
EXIT_CODE=$(echo "$INPUT" | jq -r '.tool_result.exit_code // .tool_result.exitCode // 0')

# Detect test failures
HAS_FAILURE=false

# Check exit code
if [ "$EXIT_CODE" != "0" ]; then
    HAS_FAILURE=true
fi

# Check for failure patterns in output
if echo "$STDOUT" | grep -qiE "(FAILED|ERROR|ERRORS|failed|error)" && \
   echo "$STDOUT" | grep -qiE "(test|tests|pytest|vitest)"; then
    HAS_FAILURE=true
fi

if echo "$STDERR" | grep -qiE "(FAILED|ERROR|ERRORS|failed|error)"; then
    HAS_FAILURE=true
fi

# Determine test type for filename
if [ "$IS_PYTEST" = true ]; then
    TEST_TYPE="pytest"
else
    TEST_TYPE="vitest"
fi

# Generate timestamp-based filename
TIMESTAMP=$(date +%s)
CACHE_FILE="$CACHE_DIR/${TEST_TYPE}-${TIMESTAMP}.json"

# Create cache entry
jq -n \
    --arg test_type "$TEST_TYPE" \
    --arg command "$COMMAND" \
    --arg stdout "$STDOUT" \
    --arg stderr "$STDERR" \
    --argjson exit_code "$EXIT_CODE" \
    --argjson has_failure "$HAS_FAILURE" \
    --arg timestamp "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    '{
        test_type: $test_type,
        command: $command,
        stdout: $stdout,
        stderr: $stderr,
        exit_code: $exit_code,
        has_failure: $has_failure,
        timestamp: $timestamp
    }' > "$CACHE_FILE"

# Output a summary message for the agent
if [ "$HAS_FAILURE" = true ]; then
    echo ""
    echo "[adherence] Test failures detected in $TEST_TYPE run. Results cached."
else
    echo ""
    echo "[adherence] Test results captured ($TEST_TYPE). Results cached."
fi

exit 0
