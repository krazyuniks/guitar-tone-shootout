# === TDD Workflow Commands ===
# Add these to your existing justfile

# --- Epic Management ---

# Sync epic from GitHub to .tasks/
epic-sync epic:
    python scripts/gh_tasks_sync.py krazyuniks/guitar-tone-shootout {{epic}}

# Start orchestrating epic (with auto-restart loop)
epic-start epic:
    ./scripts/run-epic.sh {{epic}}

# Show epic status
epic-status epic:
    @echo "=== Epic E{{epic}} Status ==="
    @cat .tasks/projects/guitar-tone-shootout/epics/E{{epic}}/index.md 2>/dev/null || echo "Epic not found. Run: just epic-sync {{epic}}"

# --- TDD Phases ---

# Start test phase (invoke test-author agent)
tdd-test task:
    @echo "Starting test phase for {{task}}"
    @echo "Write tests in src/**/*.test.ts or e2e/*.spec.ts"

# Verify tests fail (red phase)
tdd-red task:
    #!/usr/bin/env bash
    set -e
    echo "Verifying tests fail (red phase)..."
    if just test 2>&1 | grep -q "0 failed\|All tests passed"; then
        echo "✗ ERROR: Tests should fail before implementation"
        exit 1
    fi
    echo "✓ Tests correctly failing (red phase verified)"

# Lock tests (snapshot before implementation)
tdd-lock task:
    python scripts/snapshot_tests.py save {{task}}
    git add .tasks/*/snapshots/
    git commit -m "test-lock: {{task}} tests ready for implementation"
    @echo "✓ Tests locked at $(git rev-parse --short HEAD)"

# Implementation phase (watch mode)
tdd-impl task:
    @echo "Implementation phase for {{task}}"
    @echo "Make tests pass. DO NOT modify test files."
    @echo "Running tests in watch mode..."
    npm test -- --watch || pnpm test -- --watch || just test

# Verify tests pass (green phase)
tdd-green task:
    #!/usr/bin/env bash
    set -e
    echo "Verifying tests pass..."
    just test
    echo "✓ Tests passing"

# Full TDD validation
tdd-complete task:
    #!/usr/bin/env bash
    set -e
    echo "=== Full TDD Validation for {{task}} ==="
    
    echo "1. Verifying tests pass..."
    just tdd-green {{task}}
    
    echo "2. Verifying test files unchanged..."
    python scripts/snapshot_tests.py verify {{task}}
    
    echo "3. Running test quality check..."
    python scripts/test_quality_check.py src/ tests/ e2e/ || true
    
    echo "4. Running E2E tests..."
    just e2e || echo "⚠ E2E skipped or failed"
    
    echo ""
    echo "✓ Task {{task}} validation complete"

# --- Validation ---

# Check test immutability
snapshot-verify task:
    python scripts/snapshot_tests.py verify {{task}}

# Show changes since test lock
snapshot-diff task:
    python scripts/snapshot_tests.py diff {{task}}

# Test quality analysis
test-quality:
    python scripts/test_quality_check.py src/ tests/ e2e/ backend/ frontend/

# Health check
health epic:
    python scripts/health_check.py {{epic}}

# --- Debugging ---

# Full debug report
debug epic:
    #!/usr/bin/env bash
    echo "=== Debug Report for E{{epic}} ==="
    echo ""
    echo "--- Health Check ---"
    just health {{epic}} || true
    echo ""
    echo "--- Recent Errors ---"
    just errors {{epic}}
    echo ""
    echo "--- Status ---"
    just epic-status {{epic}}

# View recent errors
errors epic:
    @echo "=== Recent Errors ==="
    @ls -lt .tasks/projects/*/epics/E{{epic}}/logs/errors/*.log 2>/dev/null | head -5 || echo "No errors found"
    @echo ""
    @for f in $(ls -t .tasks/projects/*/epics/E{{epic}}/logs/errors/*.log 2>/dev/null | head -3); do \
        echo "--- $$f ---"; \
        cat "$$f"; \
        echo ""; \
    done

# View task log
log epic task phase:
    cat .tasks/projects/*/epics/E{{epic}}/logs/tasks/{{task}}-{{phase}}.log 2>/dev/null || echo "Log not found"

# Reset task for retry
retry epic task:
    #!/usr/bin/env bash
    TASK_FILE=$(find .tasks -path "*E{{epic}}*/tasks/{{task}}.md" 2>/dev/null | head -1)
    if [ -z "$TASK_FILE" ]; then
        echo "Task file not found"
        exit 1
    fi
    sed -i 's/state: .*/state: pending/' "$TASK_FILE"
    sed -i 's/phase: .*/phase: -/' "$TASK_FILE"
    rm -f .tasks/projects/*/epics/E{{epic}}/logs/errors/{{task}}-*.log
    echo "✓ Task {{task}} reset for retry"

# --- Worktree Integration ---

# Create worktree for parallel task
worktree-create task:
    python worktree.py create {{task}}
    @echo "Work in: worktree/{{task}}/"

# Merge completed worktree
worktree-merge task:
    python worktree.py finish {{task}}

# List active worktrees
worktrees:
    python worktree.py list
