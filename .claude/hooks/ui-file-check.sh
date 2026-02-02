#!/bin/bash
# UI File Check Hook (PostToolUse on Edit/Write)
#
# Reminds to check Chrome DevTools after UI file modifications.
# Helps catch JS errors and failed requests early.
#
# Hook receives JSON on stdin:
# {
#   "tool_input": {"file_path": "...", ...},
#   "tool_result": {...}
# }

set -e

# Read tool result from stdin
INPUT=$(cat)

# Extract file_path from tool_input
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

if [ -z "$FILE_PATH" ]; then
    exit 0
fi

# Check if this is a UI file
is_ui_file() {
    local path="$1"
    case "$path" in
        *.astro|*.html|*.jinja|*.jinja2|*.ts|*.tsx|*.css)
            return 0
            ;;
        */templates/*.html|*/pages/*.astro|*/components/*.astro)
            return 0
            ;;
        */components/*.tsx|*/components/*.ts)
            return 0
            ;;
        *)
            return 1
            ;;
    esac
}

if ! is_ui_file "$FILE_PATH"; then
    exit 0
fi

# Get just the filename for display
FILENAME=$(basename "$FILE_PATH")

# Determine file type for context
FILE_TYPE=""
case "$FILE_PATH" in
    *.astro)
        FILE_TYPE="Astro page/component"
        ;;
    *.html|*.jinja|*.jinja2)
        FILE_TYPE="Jinja2 template"
        ;;
    *.tsx|*.ts)
        FILE_TYPE="TypeScript/React"
        ;;
    *.css)
        FILE_TYPE="Stylesheet"
        ;;
esac

echo ""
echo "[ui-debug] $FILE_TYPE modified: $FILENAME"
echo "  → Hot reload in ~3s"
echo "  → Check DevTools: console for JS errors, network for failed requests"
echo ""

exit 0
