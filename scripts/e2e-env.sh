#!/usr/bin/env bash
# E2E test environment setup
# Source this script to set E2E environment variables
# Usage: source scripts/e2e-env.sh
#
# Variables can be pre-set (e.g., by worktree.py) and won't be overridden.

# Read PUBLIC_URL from .env.local (set by worktree.py based on Traefik status)
if [ -z "${E2E_BASE_URL:-}" ]; then
    if [ -f .env.local ]; then
        PUBLIC_URL=$(grep '^PUBLIC_URL=' .env.local | cut -d'=' -f2)
        E2E_BASE_URL="${PUBLIC_URL:-http://localhost:9000}"
    else
        E2E_BASE_URL="http://localhost:9000"
    fi
fi

# Extract ports from .env.local for API and database access
if [ -z "${E2E_API_URL:-}" ] || [ -z "${E2E_DATABASE_URL:-}" ]; then
    if [ -f .env.local ]; then
        WEBAPP_PORT=$(grep '^WEBAPP_PORT=' .env.local | cut -d'=' -f2)
        DB_PORT=$(grep '^DB_PORT=' .env.local | cut -d'=' -f2)
    fi
    if [ -f .env ]; then
        DB_PASSWORD=$(grep '^DB_PASSWORD=' .env | cut -d'=' -f2)
    fi
fi

# Set E2E environment variables with defaults (only if not already set)
export E2E_BASE_URL="${E2E_BASE_URL}"
export E2E_API_URL="${E2E_API_URL:-http://localhost:${WEBAPP_PORT:-8000}}"
export E2E_DATABASE_URL="${E2E_DATABASE_URL:-postgresql+asyncpg://gts:${DB_PASSWORD}@localhost:${DB_PORT:-5432}/gts_core}"
