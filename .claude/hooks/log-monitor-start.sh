#!/bin/bash
# Log Monitor Start Hook (SessionStart)
#
# Launches background Docker log monitoring at session start.
# Captures backend errors to a file that Claude can read.
#
# This runs silently - it doesn't output to the user unless there's a problem.

# Find git root (worktree support)
GIT_ROOT=$(git rev-parse --show-toplevel 2>/dev/null)
[ -z "$GIT_ROOT" ] && exit 0
cd "$GIT_ROOT"

# Log file and PID file
LOG_FILE="/tmp/gts-docker-errors.log"
PID_FILE="/tmp/gts-log-monitor.pid"

# Kill any existing monitor
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if kill -0 "$OLD_PID" 2>/dev/null; then
        kill "$OLD_PID" 2>/dev/null || true
    fi
    rm -f "$PID_FILE"
fi

# Skip if Docker is not running or backend is not up
# Check for "Up" in status (not "running" - status shows "Up X hours (healthy)")
if ! docker compose ps webapp 2>/dev/null | grep -qE "(Up|running)"; then
    exit 0
fi

# Clear old log file (start fresh each session)
> "$LOG_FILE"

# Error patterns to watch for
ERROR_PATTERNS="ERROR|CRITICAL|Exception|Traceback|status_code.*[45][0-9]{2}|IntegrityError|KeyError|AttributeError|SyntaxError|IndentationError|ImportError"

# Start background log monitor
# Uses nohup to survive if parent shell exits
nohup bash -c "
    docker compose logs -f webapp --tail=0 2>&1 | while read -r line; do
        if echo \"\$line\" | grep -qE '$ERROR_PATTERNS'; then
            echo \"[\$(date '+%H:%M:%S')] \$line\" >> '$LOG_FILE'
        fi
    done
" > /dev/null 2>&1 &

# Save PID
echo $! > "$PID_FILE"

# Success - silent exit (no output clutters session start)
exit 0
