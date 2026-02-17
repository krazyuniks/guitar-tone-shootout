#!/bin/bash
# Block writes containing unittest.mock imports (PreToolUse on Write, Edit)
#
# unittest.mock is banned project-wide. This hook prevents mocks from
# being written in the first place, rather than catching them after the fact.

set -e

INPUT=$(cat)
TOOL=$(echo "$INPUT" | jq -r '.tool_name // empty')

# Get the content being written/edited
if [ "$TOOL" = "Write" ]; then
    CONTENT=$(echo "$INPUT" | jq -r '.tool_input.content // empty')
elif [ "$TOOL" = "Edit" ]; then
    CONTENT=$(echo "$INPUT" | jq -r '.tool_input.new_string // empty')
else
    exit 0
fi

if [ -z "$CONTENT" ]; then
    exit 0
fi

# Check for mock patterns
if echo "$CONTENT" | grep -qE '(from unittest\.mock|from unittest import mock|import unittest\.mock|@patch|@mock\.)'; then
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  BLOCKED: unittest.mock is banned"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "  Test against real services. No mocking."
    echo "  See AGENTS.md Testing section."
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    exit 2
fi

exit 0
