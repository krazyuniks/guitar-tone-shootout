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
up-d:
    docker compose up -d

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

# Rebuild and restart services
rebuild *ARGS:
    docker compose up -d --build {{ARGS}}

# =============================================================================
# Quality Gates (all run in Docker)
# =============================================================================

# Run all quality checks
check: lint-python check-types check-tests check-imports

# Run type checking (strict on core)
check-types:
    docker compose exec -T backend mypy libs/core/ --strict

# Run unit tests
check-tests:
    docker compose exec -T backend pytest tests/unit/ -v

# Check import dependency rules
check-imports:
    docker compose exec -T backend lint-imports

# =============================================================================
# Linting (all run in Docker)
# =============================================================================

# Check all lint (Python + Astro)
lint: lint-python lint-astro

# Check Python lint only
lint-python:
    docker compose exec -T backend ruff check libs/ sources/ apps/
    docker compose exec -T backend ruff format --check libs/ sources/ apps/

# Check Astro lint only
lint-astro:
    docker compose --profile build run --rm astro pnpm lint

# Fix all lint issues (Python + Astro)
fix-lint: fix-lint-python fix-lint-astro

# Fix Python lint issues
fix-lint-python:
    docker compose exec -T backend ruff check libs/ sources/ apps/ --fix
    docker compose exec -T backend ruff format libs/ sources/ apps/

# Fix Astro lint issues
fix-lint-astro:
    docker compose --profile build run --rm astro pnpm lint --fix

# Format Python code only
format:
    docker compose exec -T backend ruff format libs/ sources/ apps/

# =============================================================================
# Testing
# =============================================================================

# Run unit tests (in Docker)
test-unit:
    docker compose exec -T backend pytest tests/unit/ -v

# Run regression tests - unit only (in Docker)
test-regression:
    docker compose exec -T backend pytest tests/unit/ -v -m "not slow"

# Run integration tests (in Docker)
test-integration:
    docker compose exec -T backend pytest tests/integration/ -v

# Run all tests except E2E (in Docker)
test:
    docker compose exec -T backend pytest tests/unit/ tests/integration/ -v

# Run E2E tests (on host, hits Docker containers)
test-e2e:
    cd tests/e2e/python && uv run pytest tests/ -v

# Run a single test file or test (TDD mode, in Docker)
tdd PATH:
    docker compose exec -T backend pytest {{PATH}} -v --tb=short

# =============================================================================
# Database
# =============================================================================

# Run migrations
migrate:
    docker compose exec -T backend alembic upgrade head

# Create a new migration
migration NAME:
    docker compose exec -T backend alembic revision --autogenerate -m "{{NAME}}"

# Show migration history
migration-history:
    docker compose exec -T backend alembic history

# Rollback last migration
migrate-down:
    docker compose exec -T backend alembic downgrade -1

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
    docker compose exec backend bash

# Open a Python REPL in the backend container
repl:
    docker compose exec backend python

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
