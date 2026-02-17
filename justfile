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

# Run all quality checks (read-only — safe in Docker with :ro mounts)
check: check-lint check-types check-tests check-imports

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

# Check lint and formatting (read-only — no file modifications)
check-lint:
    docker compose exec -T webapp ruff check libs/ sources/ apps/ tests/
    docker compose exec -T webapp ruff format --check libs/ sources/ apps/ tests/

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

# Back up all databases to ../backups/
db-backup:
    ./worktree.py backup

# Restore a database from a dump file
# Usage: just db-restore path/to/gts_core.20260217_1200.dump
db-restore file:
    ./worktree.py restore {{file}}

# Legacy aliases
db-export: db-backup
db-import file: (db-restore file)

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
# Quality Utilities (host scripts)
# =============================================================================

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

# Test quality analysis
test-quality:
    python scripts/test_quality_check.py tests/

# Check test files for mock violations (strict — errors block)
mock-check +FILES:
    python scripts/test_quality_check.py --strict {{FILES}}

# =============================================================================
# Epic Workflow V3 — Behavioural Validation
# =============================================================================

# Full epic pipeline: ingest -> plan -> verify -> gate -> execute
epic epic_num:
    ./wf epic run {{epic_num}}

# Show epic status from JSONL logs
epic-status epic_num:
    ./wf epic status {{epic_num}}

# Validate plan.json against schema (Phase A only)
epic-validate-plan epic_num:
    ./wf epic validate-plan {{epic_num}}

# Regenerate .planning/codebase/ files
map-codebase:
    ./wf map codebase

# Regenerate .planning/wiki-indexes/
index-wiki:
    ./wf map wiki

# Regenerate both codebase and wiki maps
map-context:
    ./wf map all
