# Guitar Tone Shootout - Task Runner
# Docker-based development workflow

default:
    @just --list

# ============================================
# Docker Development
# ============================================

# Start all services with hot-reload
up:
    docker compose up

# Start services in background
up-d:
    docker compose up -d

# Stop all services
down:
    docker compose down

# Stop services and remove volumes (full reset)
reset:
    docker compose down -v
    @echo "✓ All services and volumes removed"

# Rebuild a specific service
rebuild service:
    docker compose build {{service}}
    docker compose up -d {{service}}
    @echo "✓ {{service}} rebuilt and restarted"

# View logs for a service
logs service="backend":
    docker compose logs -f {{service}}

# Shell into a container
shell service="backend":
    docker compose exec {{service}} bash

# ============================================
# Quality Checks (Docker)
# ============================================

# Run all backend checks
check-backend:
    docker compose exec backend ruff check app/
    docker compose exec backend mypy app/
    docker compose exec backend pytest tests/

# Run all frontend checks
check-frontend:
    docker compose exec frontend pnpm lint
    docker compose exec frontend pnpm build

# Run all checks
check: check-backend check-frontend
    @echo "✓ All checks passed"

# ============================================
# Database
# ============================================

# Run database migrations
migrate:
    docker compose exec backend alembic upgrade head

# Create new migration
migration name:
    docker compose exec backend alembic revision --autogenerate -m "{{name}}"

# Rollback last migration
rollback:
    docker compose exec backend alembic downgrade -1

# Show migration history
migration-history:
    docker compose exec backend alembic history

# ============================================
# Pipeline (Preserved CLI Tool)
# ============================================

# Process a comparison INI file
process ini_file:
    cd pipeline && uv run python -m guitar_tone_shootout {{ini_file}}

# Validate a comparison INI file
validate ini_file:
    cd pipeline && uv run python -m guitar_tone_shootout --validate {{ini_file}}

# Check pipeline code quality
check-pipeline:
    cd pipeline && uv run ruff check .
    cd pipeline && uv run mypy .
    cd pipeline && uv run pytest

# ============================================
# Git Hooks (prek)
# ============================================

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

# ============================================
# GitHub Workflow
# ============================================

# List open issues
issues:
    gh issue list

# View issue details
issue num:
    gh issue view {{num}}

# View current milestone
milestone:
    gh issue list --milestone "v2.0 - Web Application Foundation"

# View PR status
pr-status:
    gh pr status

# ============================================
# Cleanup
# ============================================

# Clean output directories
clean-outputs:
    rm -rf outputs/audio/*
    rm -rf outputs/images/*
    rm -rf outputs/clips/*
    rm -rf outputs/videos/*
    @echo "✓ Outputs cleaned"

# Clean all generated files
clean-all: clean-outputs
    rm -rf pipeline/.venv pipeline/.pytest_cache pipeline/.mypy_cache pipeline/.ruff_cache
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
    @echo "✓ All generated files cleaned"
