# === Planning Commands ===
# Add these to your existing justfile

# Plan an epic - breaks it into well-structured tasks
plan epic:
    python scripts/plan_epic.py {{epic}}

# Plan with dry run (show prompt only)
plan-dry epic:
    python scripts/plan_epic.py {{epic}} --dry-run

# Sync with validation (warns on sparse issues)
epic-sync-validate epic:
    python scripts/gh_tasks_sync.py krazyuniks/guitar-tone-shootout {{epic}} --validate

# Full workflow: plan → sync → start
epic-full epic:
    #!/usr/bin/env bash
    set -e
    echo "=== Planning Epic #{{epic}} ==="
    just plan {{epic}}
    echo ""
    echo "=== Syncing to .tasks/ ==="
    just epic-sync {{epic}}
    echo ""
    echo "=== Starting Orchestration ==="
    just epic-start {{epic}}
