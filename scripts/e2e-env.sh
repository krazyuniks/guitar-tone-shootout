#!/usr/bin/env bash
# E2E test environment setup
# Source this script to set E2E environment variables
# Usage: source scripts/e2e-env.sh
#
# Variables can be pre-set (e.g., by worktree.py) and won't be overridden.

# Source project secrets (DB_PASSWORD, etc.) when not already in the environment.
if [ -z "${DB_PASSWORD:-}" ] && [ -f env.local.sh ]; then
    # shellcheck disable=SC1091
    source env.local.sh
fi

# Read worktree-specific values from .env.worktree (gitignored, auto-generated).
if [ -f .env.worktree ]; then
    WORKTREE_PUBLIC_URL=$(grep '^PUBLIC_URL=' .env.worktree | cut -d'=' -f2-)
    WORKTREE_WEBAPP_PORT=$(grep '^WEBAPP_PORT=' .env.worktree | cut -d'=' -f2-)
    WORKTREE_DB_PORT=$(grep '^DB_PORT=' .env.worktree | cut -d'=' -f2-)
fi

# Set E2E environment variables with defaults (only if not already set).
export E2E_BASE_URL="${E2E_BASE_URL:-${WORKTREE_PUBLIC_URL:-http://localhost:9000}}"
export E2E_API_URL="${E2E_API_URL:-http://localhost:${WORKTREE_WEBAPP_PORT:-8000}}"
export E2E_DATABASE_URL="${E2E_DATABASE_URL:-postgresql+asyncpg://gts:${DB_PASSWORD}@localhost:${WORKTREE_DB_PORT:-5432}/gts_core}"
