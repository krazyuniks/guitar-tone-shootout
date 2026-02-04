#!/bin/bash
# scripts/run-epic.sh - Stateless orchestration loop
#
# Runs orchestrator with fresh context per iteration.
# Handles context exhaustion by restarting.
#
# Usage:
#   ./scripts/run-epic.sh 42

set -e

EPIC=$1
MAX_ITERATIONS=50
TASKS_DIR=".tasks/projects/guitar-tone-shootout/epics/E${EPIC}"

if [ -z "$EPIC" ]; then
    echo "Usage: $0 <epic_number>"
    exit 1
fi

# Ensure epic is synced
if [ ! -d "$TASKS_DIR" ]; then
    echo "Epic E${EPIC} not found. Syncing from GitHub..."
    just epic-sync "$EPIC"
fi

echo "Starting orchestration for Epic E${EPIC}"
echo "Max iterations: $MAX_ITERATIONS"
echo "Tasks directory: $TASKS_DIR"
echo ""

for i in $(seq 1 $MAX_ITERATIONS); do
    echo "=== Iteration $i ==="
    
    # Check if epic complete
    if grep -q "state: complete" "$TASKS_DIR/EPIC.md" 2>/dev/null; then
        echo "✓ Epic E${EPIC} complete!"
        exit 0
    fi
    
    # Check if all tasks complete
    PENDING=$(grep -l "state: pending\|state: test\|state: impl" "$TASKS_DIR/tasks/"*.md 2>/dev/null | wc -l)
    if [ "$PENDING" -eq 0 ]; then
        # Run final health check
        echo "All tasks complete. Running final health check..."
        just health "$EPIC" && {
            echo "✓ Epic E${EPIC} complete and healthy!"
            # Mark epic complete
            sed -i 's/state: .*/state: complete/' "$TASKS_DIR/EPIC.md"
            exit 0
        }
    fi
    
    # Run orchestrator with fresh context
    echo "Starting orchestrator (iteration $i)..."
    claude --agent orchestrator \
           --prompt "Continue epic E${EPIC} from .tasks/. This is iteration $i of $MAX_ITERATIONS. Read index.md for current state." \
           --max-turns 20 \
           2>&1 | tee "$TASKS_DIR/logs/orchestrator/iteration-${i}.log"
    
    # Check exit reason
    EXIT_FILE="$TASKS_DIR/session-exit.md"
    if [ -f "$EXIT_FILE" ]; then
        EXIT_REASON=$(cat "$EXIT_FILE")
        
        if echo "$EXIT_REASON" | grep -q "human_input_required"; then
            echo "⚠ Human input required. Check $TASKS_DIR for details."
            exit 1
        fi
        
        if echo "$EXIT_REASON" | grep -q "blocked"; then
            echo "⚠ Epic blocked. Check dependencies."
            cat "$EXIT_FILE"
            exit 1
        fi
        
        # Clear exit file for next iteration
        rm -f "$EXIT_FILE"
    fi
    
    # Brief pause to avoid rate limits
    sleep 2
done

echo "⚠ Max iterations ($MAX_ITERATIONS) reached"
echo "Epic may not be complete. Check: just epic-status $EPIC"
exit 1
