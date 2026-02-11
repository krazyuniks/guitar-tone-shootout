# GTS Justfile - Development Commands
# All commands run in Docker (except E2E tests and host tooling)
# Use: just <command>
# List all: just --list

# Default recipe - show available commands
default:
    @just --list

# =============================================================================
# Service Management
# =============================================================================

# Start all services in detached mode
# Compose files are configured via COMPOSE_FILE in .env (set by worktree.py setup)
up-d:
    #!/usr/bin/env bash
    set -euo pipefail

    # Main worktree runs jobs profile (worker, scheduler, redis)
    PROFILE_ARGS=""
    if [ "$(basename "$(pwd)")" = "main" ]; then
        PROFILE_ARGS="--profile jobs"
    fi

    docker compose $PROFILE_ARGS up -d

# Stop all services
down:
    docker compose down

# Restart all services
restart:
    docker compose restart

# View logs (follow mode)
logs *ARGS:
    docker compose logs -f {{ARGS}}

# Show service status
status:
    docker compose ps

# Check service health (used by worktree.py)
health:
    @docker compose ps --format 'table {{{{.Service}}}}\t{{{{.Status}}}}' | grep -E 'healthy|running' || echo "No healthy services found"

# Rebuild and restart services
rebuild *ARGS:
    docker compose up -d --build {{ARGS}}

# =============================================================================
# Quality Gates (all run in Docker)
# =============================================================================

# Run all quality checks
check: lint check-types check-tests check-imports

# Run type checking (strict on core, TypeScript on video)
check-types:
    docker compose exec -T webapp mypy libs/core/ --strict
    @cd libs/video && npx tsc --noEmit

# Run unit tests
check-tests:
    docker compose exec -T webapp pytest tests/unit/ -v

# Check import dependency rules
check-imports:
    docker compose exec -T webapp lint-imports

# =============================================================================
# Linting (all run in Docker)
# =============================================================================

# Fix all lint issues (Python + Astro)
lint:
    docker compose exec -T webapp ruff check libs/ sources/ apps/ tests/ --fix
    docker compose exec -T webapp ruff format libs/ sources/ apps/ tests/

# =============================================================================
# Testing
# =============================================================================

# Run unit tests (in Docker, excludes host_only tests like documentation tests)
test-unit:
    docker compose exec -T webapp pytest tests/unit/ -v -m "not host_only"

# Run documentation tests (on host - requires AGENTS.md/DEVELOPMENT.md)
test-docs:
    uv run pytest tests/unit/backend/documentation/ -v

# Run regression tests - validates stack connectivity
# Tests both internal Docker stack and external URL (Traefik SSL if available)
test-regression:
    #!/usr/bin/env bash
    set -euo pipefail

    # Run internal stack tests in Docker
    echo "→ Running internal stack regression tests..."
    docker compose exec -T webapp pytest tests/regression/ -v --tb=short

    # Source E2E environment (uses PUBLIC_URL from .env.local)
    source scripts/e2e-env.sh
    echo ""
    echo "→ Testing external endpoint: $E2E_BASE_URL"

    # Check if Traefik is running and we're using HTTPS
    if docker ps -q -f name=traefik 2>/dev/null | grep -q . && [[ "$E2E_BASE_URL" == https://* ]]; then
        echo "→ Traefik detected: Testing SSL endpoint..."
        if curl -sf --max-time 10 "$E2E_BASE_URL/health" > /dev/null 2>&1; then
            echo "  ✓ SSL endpoint responding: $E2E_BASE_URL"
        else
            echo "  ✗ SSL endpoint not responding: $E2E_BASE_URL"
            echo "    Check Traefik logs: cd deploy/traefik && docker compose logs"
            exit 1
        fi
    else
        # Test localhost endpoint
        if curl -sf --max-time 10 "$E2E_BASE_URL/health" > /dev/null 2>&1; then
            echo "  ✓ Endpoint responding: $E2E_BASE_URL"
        else
            echo "  ✗ Endpoint not responding: $E2E_BASE_URL"
            echo "    Check Docker logs: docker compose logs"
            exit 1
        fi
    fi

    echo ""
    echo "✓ All regression tests passed"

# Run integration tests (in Docker)
test-integration:
    docker compose exec -T webapp pytest tests/integration/ -v

# Run all tests except E2E (in Docker)
test:
    docker compose exec -T webapp pytest tests/unit/ tests/integration/ -v -m "not host_only"

# Run E2E golden path tests (on host, hits Docker containers)
test-golden-path:
    #!/usr/bin/env bash
    set -euo pipefail
    [ -f .env.local ] && set -a && source .env.local && set +a
    cd tests/e2e/python && uv run pytest tests/ -v

# Run a single test file or test (TDD mode, in Docker)
tdd PATH:
    docker compose exec -T webapp pytest {{PATH}} -v --tb=short

# =============================================================================
# Database
# =============================================================================

# Export database to timestamped backup in ../backups/
db-export:
    ./worktree.py db-export

# Import database from custom format dump file
# WARNING: This drops and recreates the database!
# Usage: just db-import backup.dump
db-import file:
    #!/usr/bin/env bash
    set -euo pipefail
    file="{{file}}"

    # Validate file exists
    if [ ! -f "$file" ]; then
        echo "✗ File not found: $file"
        exit 1
    fi

    # Validate file extension
    if [[ ! "$file" == *.dump ]]; then
        echo "✗ File must have .dump extension (pg_dump -Fc format)"
        exit 1
    fi

    # Check if db container is running
    if ! docker compose ps db 2>/dev/null | grep -q "Up"; then
        echo "✗ Database container is not running"
        exit 1
    fi

    echo "→ Terminating existing connections..."
    docker compose exec -T db psql -U gts -d postgres -c \
        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='gts_core' AND pid <> pg_backend_pid();" \
        > /dev/null 2>&1 || true

    echo "→ Dropping database..."
    docker compose exec -T db dropdb -U gts --if-exists gts_core

    echo "→ Creating database..."
    docker compose exec -T db createdb -U gts gts_core

    echo "→ Restoring from $file..."
    docker compose exec -T db pg_restore -U gts -d gts_core --no-owner --no-privileges < "$file" 2>&1 || true

    echo "✓ Database imported from $file"

# Run migrations
migrate:
    docker compose exec -T webapp alembic -c infrastructure/migrations/alembic.ini upgrade head

# Create a new migration
migration NAME:
    docker compose exec -T webapp alembic revision --autogenerate -m "{{NAME}}"

# Show migration history
migration-history:
    docker compose exec -T webapp alembic history

# Rollback last migration
migrate-down:
    docker compose exec -T webapp alembic downgrade -1

# =============================================================================
# Frontend (Astro)
# =============================================================================

# Build Astro frontend (triggers build inside running astro container)
build-astro:
    docker compose exec -T astro pnpm build

# Watch Astro logs (chokidar auto-rebuilds on source changes)
watch-astro:
    docker compose logs -f astro

# Check Astro (lint + type check)
check-astro:
    docker compose exec -T astro pnpm check

# Verify Astro dist is in sync with source
verify-astro-sync:
    @echo "Building Astro and checking for uncommitted changes..."
    docker compose exec -T astro pnpm build
    @if [ -n "$(git status --porcelain frontend/astro/dist/)" ]; then \
        echo "ERROR: frontend/astro/dist/ is out of sync with source!"; \
        echo "Run 'just build-astro' and commit the changes."; \
        exit 1; \
    fi
    @echo "Astro dist is in sync."

# =============================================================================
# Video Development (libs/video - Remotion)
# =============================================================================

# Open Remotion Studio for video composition development
video-studio:
    #!/usr/bin/env bash
    set -euo pipefail
    cd libs/video
    npx remotion studio src/video/remotion/index.ts

# Run video tests (Python + TypeScript)
video-test:
    docker compose exec -T webapp pytest tests/unit/video/ tests/integration/video/ -v

# Check video types (TypeScript)
video-types:
    #!/usr/bin/env bash
    set -euo pipefail
    cd libs/video
    npx tsc --noEmit

# =============================================================================
# Development Utilities
# =============================================================================

# GTS admin CLI - manage worker and source sync operations
# Usage: just admin source-status t3k, just admin jobs, etc.
admin *ARGS:
    # Calls scripts/gts-admin (Python module at scripts/gts_admin.py)
    docker compose exec -T webapp python3 -m scripts.gts_admin {{ARGS}}

# Open a shell in the backend container
shell:
    docker compose exec webapp bash

# Open a Python REPL in the backend container
repl:
    docker compose exec webapp python

# Open psql to gts_core database
psql:
    docker compose exec db psql -U gts -d gts_core

# Open psql to gts_t3k_source database
psql-t3k:
    docker compose exec db psql -U gts -d gts_t3k_source

# Open redis-cli
redis-cli:
    docker compose exec redis redis-cli

# =============================================================================
# Cleanup
# =============================================================================

# Clean Python cache files
clean:
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find . -type f -name "*.pyc" -delete 2>/dev/null || true
    find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
    find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
    find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true

# Full reset (DANGEROUS - removes all data)
# Must be run manually by user, not by Claude
reset:
    @echo "This will delete all data. Are you sure? (Ctrl+C to cancel)"
    @read -p "Type 'yes' to confirm: " confirm && [ "$$confirm" = "yes" ]
    docker compose down -v
    just up-d

# =============================================================================
# Infrastructure (host tools)
# =============================================================================

# Install host development tools (prek, playwright, etc)
infra:
    #!/usr/bin/env bash
    set -euo pipefail
    echo "Installing host development tools..."
    echo ""
    # --- prek (pre-commit in Rust) ---
    if command -v prek &>/dev/null; then
        echo "✓ prek: $(prek --version | cut -d' ' -f2)"
    else
        echo "→ Installing prek..."
        if command -v cargo &>/dev/null; then
            cargo install prek
            echo "✓ prek installed"
        elif command -v pipx &>/dev/null; then
            pipx install pre-commit
            echo "✓ pre-commit installed (prek alternative)"
        else
            echo "ERROR: Need cargo or pipx to install prek/pre-commit"
            echo "  Install cargo: https://rustup.rs"
            echo "  Or pipx: pip install pipx"
            exit 1
        fi
    fi
    echo ""
    # --- Playwright browser ---
    echo "→ Checking Playwright browser..."
    if ls ~/.cache/ms-playwright/chromium-*/INSTALLATION_COMPLETE &>/dev/null 2>&1; then
        echo "✓ Playwright browser installed"
    else
        echo "→ Installing Playwright browser..."
        (cd tests/e2e/python && uv sync && uv run playwright install chromium)
        echo "✓ Playwright browser installed"
    fi
    echo ""
    echo "Done. Run 'just install-hooks' to enable pre-commit hooks."

# =============================================================================
# Git Hooks (prek)
# =============================================================================

# Install pre-commit hook (auto-fix wrapper — do NOT use `prek install` directly)
install-hooks:
    #!/usr/bin/env bash
    set -euo pipefail
    HOOKS_DIR="$(git rev-parse --git-common-dir)/hooks"
    cp worktree/hooks/pre-commit "$HOOKS_DIR/pre-commit"
    chmod +x "$HOOKS_DIR/pre-commit"
    echo "✓ pre-commit hook installed (ruff auto-fix)"

# Run prek hooks on all files
run-hooks:
    prek run --all-files

# Uninstall pre-commit hook
uninstall-hooks:
    #!/usr/bin/env bash
    set -euo pipefail
    HOOK="$(git rev-parse --git-common-dir)/hooks/pre-commit"
    [ -f "$HOOK" ] && rm "$HOOK" && echo "✓ pre-commit hook uninstalled" || echo "No hook to uninstall"

# =============================================================================
# AI Development Workflow (Epic/TDD)
# =============================================================================
# Optional workflow for epic/feature development with automated TDD.
# See wiki: AI-Development-Workflow
#
# HOST EXCEPTION: Scripts in this section run on host (not Docker) because:
# - GitHub scripts need `gh` CLI authentication
# - Snapshot scripts write to `.tasks/` (not mounted in containers)
# - Health check orchestrates `just` commands
#
# See: .claude/rules/container-execution.md

# --- Epic Management ---

# Unified epic command — routes to appropriate tool
# Usage: just epic validate 70, just epic status 70, just epic start 70
epic subcmd epic_num:
    #!/usr/bin/env bash
    set -euo pipefail
    case "{{subcmd}}" in
        plan)
            echo "Use '/epic plan {{epic_num}}' in Claude Code (interactive)"
            ;;
        validate)
            python scripts/validate_tasks.py {{epic_num}}
            ;;
        fix)
            echo "Use '/epic fix {{epic_num}}' in Claude Code (interactive)"
            ;;
        start)
            python scripts/run_epic.py run {{epic_num}}
            ;;
        status)
            python scripts/run_epic.py status {{epic_num}}
            ;;
        *)
            echo "Unknown subcommand: {{subcmd}}"
            echo "Usage: just epic {plan|validate|fix|start|status} {epic_number}"
            exit 1
            ;;
    esac

# Run TDD state machine for epic (backward compat alias)
epic-start epic:
    python scripts/run_epic.py run {{epic}}

# Dry-run TDD state machine (show what would happen)
epic-dry-run epic:
    python scripts/run_epic.py run {{epic}} --dry-run

# Dispatch a single agent manually
dispatch agent +prompt:
    python scripts/run_epic.py dispatch {{agent}} {{prompt}}

# Show epic status (backward compat alias)
epic-status epic:
    python scripts/run_epic.py status {{epic}}

# Validate epic tasks (pre-flight)
epic-validate epic:
    python scripts/validate_tasks.py {{epic}}

# Materialise TASKS.md into .tasks/ files
epic-materialise epic *FLAGS:
    python scripts/tasks_from_plan.py {{epic}} {{FLAGS}}

# --- TDD Phases (Docker-first) ---

# Start test phase (invoke test-author agent)
tdd-test-phase task:
    @echo "Starting test phase for {{task}}"
    @echo "Write tests in tests/unit/, tests/integration/, or tests/e2e/python/"
    @echo ""
    @echo "Run: python scripts/run_epic.py dispatch test-author 'Write tests for {{task}}'"

# Verify tests fail (red phase) - runs in Docker
# Only checks NEW/MODIFIED test files (not pre-existing passing tests)
# Gate: at least one test must FAIL. Passing tests are warned but tolerated
# when failures exist (handles tasks that extend already-implemented code).
tdd-red task:
    #!/usr/bin/env bash
    set -e
    echo "Verifying new tests fail (red phase)..."

    # Find new or modified test files since last commit
    NEW_TESTS=$(git diff --name-only HEAD -- 'tests/' | grep -v 'tests/e2e/' | grep -E 'test_.*\.py$' || true)
    UNTRACKED_TESTS=$(git ls-files --others --exclude-standard -- 'tests/' | grep -v 'tests/e2e/' | grep -E 'test_.*\.py$' || true)
    ALL_NEW_TESTS=$(echo -e "${NEW_TESTS}\n${UNTRACKED_TESTS}" | sort -u | grep -v '^$' || true)

    if [ -z "$ALL_NEW_TESTS" ]; then
        echo "ERROR: No new test files found. test-author must create test files."
        exit 1
    fi

    echo "New test files:"
    echo "$ALL_NEW_TESTS" | sed 's/^/  /'

    # Run ONLY the new tests — they should fail
    OUTPUT=$(docker compose exec -T webapp pytest $ALL_NEW_TESTS -v 2>&1) || true

    # Parse pass/fail/error counts from pytest summary line
    # Matches patterns like: "3 failed, 2 passed", "5 failed", "2 passed, 1 error"
    FAILED=$(echo "$OUTPUT" | grep -oP '\d+(?= failed)' | tail -1 || true)
    PASSED=$(echo "$OUTPUT" | grep -oP '\d+(?= passed)' | tail -1 || true)
    ERRORS=$(echo "$OUTPUT" | grep -oP '\d+(?= error)' | tail -1 || true)

    FAILED=${FAILED:-0}
    PASSED=${PASSED:-0}
    ERRORS=${ERRORS:-0}

    echo ""
    echo "Results: ${FAILED} failed, ${PASSED} passed, ${ERRORS} errors"

    # Gate: at least one test must fail
    if [ "$FAILED" -eq 0 ] && [ "$ERRORS" -eq 0 ]; then
        echo "ERROR: All ${PASSED} tests passed. Tests must fail before implementation."
        echo "Either tests are trivial or code already exists for everything tested."
        echo "$OUTPUT" | tail -20
        exit 1
    fi

    # Warn on passing tests but proceed if failures exist
    if [ "$PASSED" -gt 0 ]; then
        echo "WARNING: ${PASSED} tests already pass (code may partially exist)."
        echo "  This is OK — ${FAILED} tests still fail, so there's work to do."
    fi

    if [ "$ERRORS" -gt 0 ]; then
        echo "NOTE: ${ERRORS} tests errored (import/syntax issues)."
        echo "  Errors count as 'not passing' — acceptable in red phase."
    fi

    echo ""
    echo "Red phase verified: ${FAILED} failing + ${ERRORS} erroring tests found."

# Lock tests (commit first, then snapshot the lock commit's test files)
tdd-lock task:
    #!/usr/bin/env bash
    set -e
    # Fix log files to prevent pre-commit hook failures (trailing whitespace + end-of-file)
    find .tasks/ -name '*.log' -exec sed -i -e 's/[[:space:]]*$//' -e '$a\' {} + 2>/dev/null || true
    git add .tasks/ tests/
    git commit -m "test-lock: {{task}} tests ready for implementation"
    python scripts/snapshot_tests.py save {{task}}
    echo "Tests locked at $(git rev-parse --short HEAD)"

# Implementation phase hint
tdd-impl-phase task:
    @echo "Implementation phase for {{task}}"
    @echo "Make ALL tests pass. You may fix existing tests broken by your changes."
    @echo ""
    @echo "Run tests in watch mode:"
    @echo "  docker compose exec webapp pytest tests/ -v --tb=short -x"
    @echo ""
    @echo "Or use TDD helper:"
    @echo "  just tdd tests/unit/path/to/test.py"

# Verify tests pass (green phase) - runs full test suite in Docker
# Deselects pre-existing failures listed in tests/known_failures.txt
tdd-green task:
    #!/usr/bin/env bash
    set -e
    echo "Verifying ALL tests pass for {{task}}..."
    DESELECT_ARGS=""
    if [ -f tests/known_failures.txt ]; then
        while IFS= read -r line; do
            [ -z "$line" ] && continue
            DESELECT_ARGS="$DESELECT_ARGS --deselect $line"
        done < tests/known_failures.txt
        echo "  (deselecting $(wc -l < tests/known_failures.txt | tr -d ' ') known pre-existing failures)"
    fi
    docker compose exec -T webapp pytest tests/unit/ tests/integration/ -v -m "not host_only" $DESELECT_ARGS
    echo "Tests passing"

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
    python scripts/test_quality_check.py tests/ || true

    echo "4. Running regression tests..."
    just test-regression

    echo "5. Ensuring auth user exists in DB..."
    just ensure-auth-user

    echo "6. Running golden path tests..."
    just test-golden-path

    echo ""
    echo "Task {{task}} validation complete"

# Ensure auth user from .gts-auth.json exists in gts_core DB
# Integration tests can overwrite the auth file; this ensures the user matches
ensure-auth-user:
    #!/usr/bin/env bash
    set -e
    AUTH_FILE="${GTS_AUTH_FILE:-/worktrees/.gts-auth.json}"
    USER_ID=$(docker compose exec -T webapp python3 -c "import json; print(json.load(open('$AUTH_FILE'))['user_id'])" 2>/dev/null || true)
    USERNAME=$(docker compose exec -T webapp python3 -c "import json; print(json.load(open('$AUTH_FILE'))['username'])" 2>/dev/null || true)
    if [ -n "$USER_ID" ] && [ -n "$USERNAME" ]; then
        docker compose exec -T db psql -U gts gts_core -c \
            "INSERT INTO users (id, username, is_active, created_at, updated_at) VALUES ('$USER_ID', '$USERNAME', true, NOW(), NOW()) ON CONFLICT (id) DO NOTHING;" \
            > /dev/null 2>&1
        echo "  Auth user ensured: $USERNAME ($USER_ID)"
    else
        echo "  WARNING: Could not read auth file, skipping user ensure"
    fi

# --- Validation ---

# Check test immutability
snapshot-verify task:
    python scripts/snapshot_tests.py verify {{task}}

# Show changes since test lock
snapshot-diff task:
    python scripts/snapshot_tests.py diff {{task}}

# List all test files
snapshot-list:
    python scripts/snapshot_tests.py list

# Test quality analysis
test-quality:
    python scripts/test_quality_check.py tests/

# Check test files for mock violations (strict — errors block)
mock-check +FILES:
    python scripts/test_quality_check.py --strict {{FILES}}

# Health check for epic
epic-health epic:
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
    sed -i 's/| State | [a-z_]* |/| State | pending |/' "$TASK_FILE"
    sed -i 's/| Phase | [a-z_-]* |/| Phase | - |/' "$TASK_FILE"
    rm -f .tasks/projects/*/epics/E{{epic}}/logs/errors/{{task}}-*.log
    echo "Task {{task}} reset for retry"
