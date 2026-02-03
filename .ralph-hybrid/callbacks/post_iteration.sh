#!/usr/bin/env bash
#
# post_iteration.sh - Backpressure verification callback template
#
# This callback runs after each Ralph Hybrid iteration to verify that tests pass
# before allowing the story to be marked complete. It implements "backpressure"
# by failing if the test suite doesn't pass, preventing premature story completion.
#
# INSTALLATION:
#   1. Copy to .ralph-hybrid/{feature}/callbacks/post_iteration.sh
#      OR .ralph-hybrid/callbacks/post_iteration.sh (project-wide)
#   2. Make executable: chmod +x post_iteration.sh
#   3. Customize the TEST_COMMAND for your project
#
# EXIT CODES:
#   0  - Tests passed, story can be marked complete
#   75 - VERIFICATION_FAILED: Tests failed, blocks story completion
#        (This triggers circuit breaker increments)
#   1  - Other error (callback infrastructure issue)
#
# ARGUMENTS:
#   $1 - Path to JSON context file containing:
#        {
#          "story_id": "STORY-001",
#          "iteration": 1,
#          "feature_dir": "/path/to/.ralph-hybrid/feature",
#          "output_file": "/path/to/output.log",
#          "timestamp": "2026-01-23T01:58:26Z"
#        }
#
# ENVIRONMENT VARIABLES (set by Ralph Hybrid):
#   RALPH_HYBRID_CALLBACK_POINT   - "post_iteration"
#   RALPH_HYBRID_STORY_ID     - Current story ID
#   RALPH_HYBRID_ITERATION    - Current iteration number
#   RALPH_HYBRID_FEATURE_DIR  - Path to feature directory
#   RALPH_HYBRID_OUTPUT_FILE  - Path to Claude's output file
#
# CUSTOMIZATION:
#   Edit the TEST_COMMAND variable below to match your project's test runner.
#   Common patterns are provided as examples.

set -euo pipefail

#=============================================================================
# Configuration - CUSTOMIZE THIS SECTION FOR YOUR PROJECT
#=============================================================================

# Test command to run. Uncomment and modify one of these patterns:

# Node.js / npm projects:
# TEST_COMMAND="npm test"
# TEST_COMMAND="npm run test:unit"
# TEST_COMMAND="pnpm test"
# TEST_COMMAND="yarn test"

# Python projects:
# TEST_COMMAND="pytest"
# TEST_COMMAND="pytest tests/"
# TEST_COMMAND="python -m pytest -v"

# Go projects:
# TEST_COMMAND="go test ./..."
# TEST_COMMAND="go test -v ./..."

# Rust projects:
# TEST_COMMAND="cargo test"

# Ruby projects:
# TEST_COMMAND="bundle exec rspec"
# TEST_COMMAND="bundle exec rake test"

# Java/Gradle projects:
# TEST_COMMAND="./gradlew test"
# TEST_COMMAND="mvn test"

# Just test runner:
# TEST_COMMAND="just test"

# Make-based projects:
# TEST_COMMAND="make test"

# TEST_COMMAND is loaded from prd.json successCriteria.command
# Override here only if you need a different command than what's in prd.json
TEST_COMMAND=""

# Optional: Additional checks (set to "true" to enable)
CHECK_LINT="${CHECK_LINT:-false}"
CHECK_TYPES="${CHECK_TYPES:-false}"
CHECK_BUILD="${CHECK_BUILD:-false}"

# Lint command (used if CHECK_LINT=true)
LINT_COMMAND="${LINT_COMMAND:-}"

# Type check command (used if CHECK_TYPES=true)
TYPE_COMMAND="${TYPE_COMMAND:-}"

# Build command (used if CHECK_BUILD=true)
BUILD_COMMAND="${BUILD_COMMAND:-}"

#=============================================================================
# Color Output
#=============================================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${YELLOW}[callback]${NC} $*" >&2; }
log_pass() { echo -e "${GREEN}[callback]${NC} $*" >&2; }
log_fail() { echo -e "${RED}[callback]${NC} $*" >&2; }

#=============================================================================
# Parse JSON Context
#=============================================================================

parse_context() {
    local context_file="${1:-}"

    if [[ -z "$context_file" || ! -f "$context_file" ]]; then
        log_fail "No context file provided or file not found"
        return 1
    fi

    # Parse JSON using jq (if available) or basic grep fallback
    if command -v jq &>/dev/null; then
        STORY_ID=$(jq -r '.story_id // ""' "$context_file")
        ITERATION=$(jq -r '.iteration // 0' "$context_file")
        FEATURE_DIR=$(jq -r '.feature_dir // ""' "$context_file")
        OUTPUT_FILE=$(jq -r '.output_file // ""' "$context_file")
        TIMESTAMP=$(jq -r '.timestamp // ""' "$context_file")
    else
        # Basic grep/sed fallback for systems without jq
        STORY_ID=$(grep -o '"story_id"[[:space:]]*:[[:space:]]*"[^"]*"' "$context_file" | sed 's/.*: *"\([^"]*\)".*/\1/')
        ITERATION=$(grep -o '"iteration"[[:space:]]*:[[:space:]]*[0-9]*' "$context_file" | sed 's/.*: *//')
        FEATURE_DIR=$(grep -o '"feature_dir"[[:space:]]*:[[:space:]]*"[^"]*"' "$context_file" | sed 's/.*: *"\([^"]*\)".*/\1/')
        OUTPUT_FILE=$(grep -o '"output_file"[[:space:]]*:[[:space:]]*"[^"]*"' "$context_file" | sed 's/.*: *"\([^"]*\)".*/\1/')
        TIMESTAMP=$(grep -o '"timestamp"[[:space:]]*:[[:space:]]*"[^"]*"' "$context_file" | sed 's/.*: *"\([^"]*\)".*/\1/')
    fi

    # Fallback to environment variables if not in JSON
    STORY_ID="${STORY_ID:-${RALPH_HYBRID_STORY_ID:-unknown}}"
    ITERATION="${ITERATION:-${RALPH_HYBRID_ITERATION:-0}}"
    FEATURE_DIR="${FEATURE_DIR:-${RALPH_HYBRID_FEATURE_DIR:-}}"
    OUTPUT_FILE="${OUTPUT_FILE:-${RALPH_HYBRID_OUTPUT_FILE:-}}"

    log_info "Story: $STORY_ID | Iteration: $ITERATION"

    # Load TEST_COMMAND from prd.json successCriteria if not already set
    if [[ -z "$TEST_COMMAND" && -n "$FEATURE_DIR" ]]; then
        local prd_file="${FEATURE_DIR}/prd.json"
        if [[ -f "$prd_file" ]] && command -v jq &>/dev/null; then
            # Try old format first (backwards compatibility)
            TEST_COMMAND=$(jq -r '.successCriteria.command // ""' "$prd_file" 2>/dev/null || echo "")

            # If empty, try layered format
            if [[ -z "$TEST_COMMAND" ]]; then
                local gate_type="perStory"

                # Check if this is the final story
                local last_story
                last_story=$(jq -r '.userStories | last | .id // ""' "$prd_file" 2>/dev/null || echo "")
                if [[ "$STORY_ID" == "$last_story" ]]; then
                    gate_type="final"
                    log_info "Final story detected - using 'final' gate"
                fi

                # Build command from gates
                local gates
                gates=$(jq -r ".gates.${gate_type} // [] | .[]" "$prd_file" 2>/dev/null || true)
                if [[ -n "$gates" ]]; then
                    local commands=()
                    while IFS= read -r gate; do
                        local cmd
                        cmd=$(jq -r ".successCriteria.${gate} // empty" "$prd_file" 2>/dev/null || true)
                        if [[ -n "$cmd" ]]; then
                            commands+=("$cmd")
                        fi
                    done <<< "$gates"
                    if [[ ${#commands[@]} -gt 0 ]]; then
                        # Join with && for sequential execution
                        TEST_COMMAND="${commands[0]}"
                        for ((i=1; i<${#commands[@]}; i++)); do
                            TEST_COMMAND="$TEST_COMMAND && ${commands[$i]}"
                        done
                    fi
                fi
            fi

            if [[ -n "$TEST_COMMAND" ]]; then
                log_info "Loaded TEST_COMMAND from prd.json: $TEST_COMMAND"
            fi
        fi
    fi
}

#=============================================================================
# Run Checks
#=============================================================================

run_tests() {
    if [[ -z "$TEST_COMMAND" ]]; then
        log_fail "No TEST_COMMAND configured - validation is MANDATORY"
        log_fail "Set successCriteria.command in prd.json or configure TEST_COMMAND in this callback"
        return 1
    fi

    log_info "Running tests: $TEST_COMMAND"

    # Capture output to check for skipped tests
    local output
    local exit_code
    output=$($TEST_COMMAND 2>&1) || exit_code=$?
    exit_code=${exit_code:-0}

    echo "$output"

    # Check for pytest skipped tests (counts as failure - tests must actually run)
    if echo "$output" | grep -qE "^\s*[0-9]+ skipped|SKIPPED"; then
        log_fail "Tests were SKIPPED - this counts as failure. Tests must actually run."
        return 1
    fi

    # Check for "0 passed" or no tests collected
    if echo "$output" | grep -qE "0 passed|no tests ran|collected 0 items"; then
        log_fail "No tests ran - this counts as failure."
        return 1
    fi

    if [[ $exit_code -eq 0 ]]; then
        log_pass "Tests passed"
        return 0
    else
        log_fail "Tests failed (exit code: $exit_code)"
        return 1
    fi
}

run_lint() {
    if [[ "$CHECK_LINT" != "true" || -z "$LINT_COMMAND" ]]; then
        return 0
    fi

    log_info "Running lint: $LINT_COMMAND"

    if $LINT_COMMAND; then
        log_pass "Lint passed"
        return 0
    else
        log_fail "Lint failed"
        return 1
    fi
}

run_typecheck() {
    if [[ "$CHECK_TYPES" != "true" || -z "$TYPE_COMMAND" ]]; then
        return 0
    fi

    log_info "Running type check: $TYPE_COMMAND"

    if $TYPE_COMMAND; then
        log_pass "Type check passed"
        return 0
    else
        log_fail "Type check failed"
        return 1
    fi
}

run_build() {
    if [[ "$CHECK_BUILD" != "true" || -z "$BUILD_COMMAND" ]]; then
        return 0
    fi

    log_info "Running build: $BUILD_COMMAND"

    if $BUILD_COMMAND; then
        log_pass "Build passed"
        return 0
    else
        log_fail "Build failed"
        return 1
    fi
}

#=============================================================================
# Main
#=============================================================================

main() {
    local context_file="${1:-}"

    log_info "Post-iteration verification callback starting..."

    # Parse context
    if ! parse_context "$context_file"; then
        return 1
    fi

    # Track failures
    local failed=0

    # Run all checks
    run_lint || failed=1
    run_typecheck || failed=1
    run_tests || failed=1
    run_build || failed=1

    # Return appropriate exit code
    if [[ $failed -eq 0 ]]; then
        log_pass "All verification checks passed"
        return 0
    else
        log_fail "Verification failed - story completion blocked"
        # Exit code 75 = VERIFICATION_FAILED (triggers circuit breaker)
        return 75
    fi
}

# Run main with all arguments
main "$@"
