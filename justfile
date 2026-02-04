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

# Start all services in detached mode (auto-detects Traefik)
up-d:
    #!/usr/bin/env bash
    set -euo pipefail
    COMPOSE_FILES="-f docker-compose.yml -f docker-compose.override.yml"

    # Auto-include Traefik overlay if Traefik is running
    if docker ps -q -f name=traefik 2>/dev/null | grep -q .; then
        if [ -f docker-compose.traefik.yml ]; then
            COMPOSE_FILES="$COMPOSE_FILES -f docker-compose.traefik.yml"
            echo "→ Traefik detected, including traefik overlay"
        fi
    fi

    # Main worktree runs jobs profile (worker, scheduler, redis)
    PROFILE_ARGS=""
    if [ "$(basename "$(pwd)")" = "main" ]; then
        PROFILE_ARGS="--profile jobs"
    fi

    docker compose $COMPOSE_FILES $PROFILE_ARGS up -d

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

# Run type checking (strict on core)
check-types:
    docker compose exec -T webapp mypy libs/core/ --strict

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
    docker compose --profile build run --rm astro pnpm lint --fix

# =============================================================================
# Testing
# =============================================================================

# Run unit tests (in Docker)
test-unit:
    docker compose exec -T webapp pytest tests/unit/ -v

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
    docker compose exec -T webapp pytest tests/unit/ tests/integration/ -v

# Run E2E tests (on host, hits Docker containers)
test-e2e:
    cd tests/e2e/python && uv run pytest tests/ -v

# Run a single test file or test (TDD mode, in Docker)
tdd PATH:
    docker compose exec -T webapp pytest {{PATH}} -v --tb=short

# =============================================================================
# Database
# =============================================================================

# Export database to custom format dump file
# Usage: just db-export backup.dump
db-export file:
    #!/usr/bin/env bash
    set -euo pipefail
    file="{{file}}"

    # Validate file extension
    if [[ ! "$file" == *.dump ]]; then
        echo "✗ File must have .dump extension"
        exit 1
    fi

    # Check if db container is running
    if ! docker compose ps db 2>/dev/null | grep -q "Up"; then
        echo "✗ Database container is not running"
        exit 1
    fi

    echo "→ Exporting database to $file..."
    docker compose exec -T db pg_dump -Fc -U gts gts_core > "$file"

    # Verify file was created and has content
    if [ ! -f "$file" ]; then
        echo "✗ Export file was not created"
        exit 1
    fi

    size=$(stat -c%s "$file" 2>/dev/null || stat -f%z "$file" 2>/dev/null)
    if [ "$size" -lt 100 ]; then
        rm -f "$file"
        echo "✗ Export file is too small (database may be empty)"
        exit 1
    fi

    echo "✓ Database exported: $file ($size bytes)"

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

# Build Astro frontend
build-astro:
    docker compose --profile build run --rm astro pnpm build

# Watch Astro for changes (auto-rebuild)
watch-astro:
    docker compose --profile build run --rm astro pnpm dev

# Check Astro (lint + type check)
check-astro:
    docker compose --profile build run --rm astro pnpm check

# Verify Astro dist is in sync with source
verify-astro-sync:
    @echo "Building Astro and checking for uncommitted changes..."
    docker compose --profile build run --rm astro pnpm build
    @if [ -n "$(git status --porcelain frontend/astro/dist/)" ]; then \
        echo "ERROR: frontend/astro/dist/ is out of sync with source!"; \
        echo "Run 'just build-astro' and commit the changes."; \
        exit 1; \
    fi
    @echo "Astro dist is in sync."

# =============================================================================
# Development Utilities
# =============================================================================

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

# Install prek hooks
install-hooks:
    prek install
    @echo "✓ prek hooks installed"

# Run prek hooks on all files
run-hooks:
    prek run --all-files

# Uninstall prek hooks
uninstall-hooks:
    prek uninstall
    @echo "✓ prek hooks uninstalled"
