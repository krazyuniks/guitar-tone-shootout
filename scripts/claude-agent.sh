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
    echo "  --project <name>     Workspace project (core, audio, t3k, webapp, worker, scheduler)"
    echo "                       Only 'webapp' enables Playwright MCP for browser testing"
    echo "  --mcp <servers>      Override MCP servers (playwright, chrome, none)"
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
MCP_SERVERS=""
PROJECT=""

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
        --mcp)
            MCP_SERVERS="$2"
            shift 2
            ;;
        --project)
            PROJECT="$2"
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

# Note: -p flag added at end with stdin marker

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

# Validate project if specified
VALID_PROJECTS="core audio t3k webapp worker scheduler"
if [ -n "$PROJECT" ]; then
    if ! echo "$VALID_PROJECTS" | grep -qw "$PROJECT"; then
        echo "Error: Invalid project '$PROJECT'. Must be one of: $VALID_PROJECTS" >&2
        exit 1
    fi
fi

# MCP server configuration
# - orchestrator/planner: never need MCP
# - other agents: only need MCP for webapp project (browser testing)
# --mcp flag overrides automatic detection
if [ -z "$MCP_SERVERS" ]; then
    case "$AGENT_NAME" in
        orchestrator|planner)
            MCP_SERVERS="none"
            ;;
        *)
            # Only webapp needs browser automation
            if [ "$PROJECT" = "webapp" ]; then
                MCP_SERVERS="playwright"
            else
                MCP_SERVERS="none"
            fi
            ;;
    esac
fi

# Build MCP config - always use --strict-mcp-config to avoid loading unwanted servers
build_mcp_config() {
    local servers="$1"

    if [ "$servers" = "none" ]; then
        echo '{"mcpServers":{}}'
        return
    fi

    # For built-in servers, we still need to specify them explicitly with --strict-mcp-config
    # to avoid loading other globally configured servers (like zai-mcp-server)
    local config='{"mcpServers":{'
    local first=true

    IFS=',' read -ra SERVER_LIST <<< "$servers"
    for server in "${SERVER_LIST[@]}"; do
        server=$(echo "$server" | xargs)  # trim whitespace
        [ -z "$server" ] && continue

        if [ "$first" = true ]; then
            first=false
        else
            config+=','
        fi

        case "$server" in
            playwright)
                # Use system chromium, run headless
                config+='"playwright":{"command":"npx","args":["-y","@playwright/mcp@latest","--headless","--executable-path","/usr/bin/chromium"]}'
                ;;
            chrome|chrome-devtools)
                config+='"chrome-devtools":{"command":"npx","args":["-y","chrome-devtools-mcp@latest","--isolated"]}'
                ;;
            *)
                echo "Warning: Unknown MCP server '$server', skipping" >&2
                continue
                ;;
        esac
    done

    config+='}}'
    echo "$config"
}

MCP_CONFIG=$(build_mcp_config "$MCP_SERVERS")
CLAUDE_ARGS+=("--strict-mcp-config" "--mcp-config" "$MCP_CONFIG")

# Execute claude with prompt via stdin (avoids command line length issues)
# -p - at end tells claude to read prompt from stdin
if [ -n "$PRINT_MODE" ]; then
    echo "$FULL_PROMPT" | claude "${CLAUDE_ARGS[@]}" -p -
else
    # Interactive mode - just pass the prompt directly
    exec claude "${CLAUDE_ARGS[@]}" "$FULL_PROMPT"
fi
