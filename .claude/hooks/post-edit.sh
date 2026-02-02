#!/bin/bash
# Post-edit hook: Suggests running quality checks after file modifications
#
# This hook runs after Edit or Write tool usage and reminds
# to run quality gates if Python files were modified.

# Get the file that was edited from the tool result
FILE="$CLAUDE_TOOL_ARG_FILE_PATH"

# Only suggest for Python files in src or tests directories
if [[ "$FILE" == *".py" ]] && [[ "$FILE" == *"/pipeline/"* || "$FILE" == *"/web/"* ]]; then
    echo "Python file modified. Consider running: just check"
fi
