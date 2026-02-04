#!/usr/bin/env bash
# scripts/claude-agent.sh - Invoke Claude with a custom agent definition
#
# Reads agent definition from .claude/agents/{name}.md and prepends it to the prompt.
# This provides the --agent functionality that doesn't exist in the Claude CLI.
#
# Usage:
#   ./scripts/claude-agent.sh <agent-name> "<prompt>"
#   ./scripts/claude-agent.sh <agent-name> -f <prompt-file>
#   ./scripts/claude-agent.sh <agent-name> --max-turns 20 "<prompt>"
#
# Examples:
#   ./scripts/claude-agent.sh planner "Plan epic #42"
#   ./scripts/claude-agent.sh orchestrator -f /tmp/epic-prompt.md
#   ./scripts/claude-agent.sh implementer --max-turns 10 "Implement T43"

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
AGENTS_DIR="$PROJECT_ROOT/.claude/agents"

usage() {
    echo "Usage: $0 <agent-name> [options] <prompt|--file path>"
    echo ""
    echo "Options:"
    echo "  -f, --file <path>    Read prompt from file"
    echo "  --max-turns <n>      Maximum conversation turns"
    echo "  --print              Print mode (non-interactive)"
    echo "  -c, --continue       Continue last conversation"
    echo "  --interactive        Disable autonomous mode (prompt for permissions)"
    echo "  --allowed-tools <t>  Comma-separated list of allowed tools"
    echo ""
    echo "Available agents:"
    if [ -d "$AGENTS_DIR" ]; then
        for agent in "$AGENTS_DIR"/*.md; do
            if [ -f "$agent" ]; then
                name=$(basename "$agent" .md)
                echo "  - $name"
            fi
        done
    else
        echo "  (none found in $AGENTS_DIR)"
    fi
    exit 1
}

# Check minimum args
if [ $# -lt 2 ]; then
    usage
fi

AGENT_NAME="$1"
shift

AGENT_FILE="$AGENTS_DIR/$AGENT_NAME.md"

# Verify agent exists
if [ ! -f "$AGENT_FILE" ]; then
    {
        echo "Error: Agent '$AGENT_NAME' not found at $AGENT_FILE"
        echo ""
        echo "Available agents:"
        for agent in "$AGENTS_DIR"/*.md; do
            if [ -f "$agent" ]; then
                echo "  - $(basename "$agent" .md)"
            fi
        done
    } >&2
    exit 1
fi

# Parse remaining arguments
PROMPT=""
PROMPT_FILE=""
MAX_TURNS=""
PRINT_MODE=""
CONTINUE_MODE=""
INTERACTIVE_MODE=""
ALLOWED_TOOLS=""

while [ $# -gt 0 ]; do
    case "$1" in
        -f|--file)
            PROMPT_FILE="$2"
            shift 2
            ;;
        --max-turns)
            MAX_TURNS="$2"
            shift 2
            ;;
        --print|-p)
            PRINT_MODE="1"
            shift
            ;;
        -c|--continue)
            CONTINUE_MODE="1"
            shift
            ;;
        --interactive)
            INTERACTIVE_MODE="1"
            shift
            ;;
        --allowed-tools)
            ALLOWED_TOOLS="$2"
            shift 2
            ;;
        -*)
            echo "Unknown option: $1" >&2
            usage
            ;;
        *)
            PROMPT="$1"
            shift
            ;;
    esac
done

# Get prompt content
if [ -n "$PROMPT_FILE" ]; then
    if [ ! -f "$PROMPT_FILE" ]; then
        echo "Error: Prompt file not found: $PROMPT_FILE" >&2
        exit 1
    fi
    PROMPT_CONTENT=$(cat "$PROMPT_FILE")
elif [ -n "$PROMPT" ]; then
    PROMPT_CONTENT="$PROMPT"
else
    echo "Error: No prompt provided" >&2
    usage
fi

# Read agent definition (skip YAML frontmatter if present)
AGENT_CONTENT=$(awk '
    BEGIN { in_frontmatter = 0; started = 0 }
    /^---$/ && !started { in_frontmatter = 1; started = 1; next }
    /^---$/ && in_frontmatter { in_frontmatter = 0; next }
    !in_frontmatter { print }
' "$AGENT_FILE")

# Combine agent definition with prompt
FULL_PROMPT="# Agent: $AGENT_NAME

$AGENT_CONTENT

---

# Task

$PROMPT_CONTENT"

# Build claude command
CLAUDE_ARGS=()

if [ -n "$PRINT_MODE" ]; then
    CLAUDE_ARGS+=("--print")
fi

if [ -n "$CONTINUE_MODE" ]; then
    CLAUDE_ARGS+=("--continue")
fi

if [ -n "$MAX_TURNS" ]; then
    CLAUDE_ARGS+=("--max-turns" "$MAX_TURNS")
fi

# Autonomous mode (skip permissions) is the default for agent invocation
# Use --interactive to prompt for permissions instead
if [ -z "$INTERACTIVE_MODE" ]; then
    CLAUDE_ARGS+=("--dangerously-skip-permissions")
fi

if [ -n "$ALLOWED_TOOLS" ]; then
    CLAUDE_ARGS+=("--allowedTools" "$ALLOWED_TOOLS")
fi

# Execute claude with combined prompt
exec claude "${CLAUDE_ARGS[@]}" "$FULL_PROMPT"
