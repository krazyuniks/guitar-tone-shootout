# GTS Justfile - Development Commands
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
    uv sync --all-packages
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

# =============================================================================
# Dependency Management
# =============================================================================

# Sync all uv workspace dependencies
uv-sync:
    uv sync --all-packages

# Update all dependencies
uv-update:
    uv sync --all-packages --upgrade

# Lock dependencies without syncing
uv-lock:
    uv lock

# =============================================================================
# Quality Gates
# =============================================================================

# Run all quality checks
check: check-lint check-types check-tests check-imports

# Run linting
check-lint:
    uv run ruff check libs/ sources/ apps/

# Run type checking (strict on core)
check-types:
    uv run mypy libs/core/ --strict

# Run unit tests
check-tests:
    uv run pytest tests/unit/ -v

# Check import dependency rules
check-imports:
    uv run lint-imports

# =============================================================================
# Lint Fixing
# =============================================================================

# Auto-fix lint issues
fix-lint:
    uv run ruff check libs/ sources/ apps/ --fix
    uv run ruff format libs/ sources/ apps/

# Format code only
format:
    uv run ruff format libs/ sources/ apps/

# =============================================================================
# Testing
# =============================================================================

# Run all tests
test:
    uv run pytest tests/ -v

# Run regression tests (golden path)
test-regression:
    uv run pytest tests/ -v -m "not slow and not integration"

# Run integration tests
test-integration:
    docker compose exec backend uv run pytest tests/integration/ -v

# Run E2E tests
test-e2e:
    uv run pytest tests/e2e/python/ -v

# Run a single test file or test (TDD mode)
tdd PATH:
    uv run pytest {{PATH}} -v --tb=short

# =============================================================================
# Database
# =============================================================================

# Run migrations
migrate:
    docker compose exec backend uv run alembic upgrade head

# Create a new migration
migration NAME:
    docker compose exec backend uv run alembic revision --autogenerate -m "{{NAME}}"

# Show migration history
migration-history:
    docker compose exec backend uv run alembic history

# Rollback last migration
migrate-down:
    docker compose exec backend uv run alembic downgrade -1

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
    docker compose exec backend uv run python

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
