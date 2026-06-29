#!/usr/bin/env bash
# E2E test environment setup. Source to set E2E_* variables.
# Usage: source scripts/e2e-env.sh
#
# Variables can be pre-set and won't be overridden. The worktree's ports come
# from the engine registry via scripts/worktree/current-env (no .env.worktree).

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

# Source project secrets (DB_PASSWORD, etc.) when not already in the environment.
if [ -z "${DB_PASSWORD:-}" ] && [ -f env.local.sh ]; then
    # shellcheck disable=SC1091
    source env.local.sh
fi

# Derive the worktree's project + ports from the engine (main defaults otherwise).
ENV_OUT="$("$SCRIPT_DIR/worktree/current-env" 2>/dev/null || true)"
[ -n "$ENV_OUT" ] && eval "$ENV_OUT"

export E2E_BASE_URL="${E2E_BASE_URL:-${PUBLIC_URL:-http://localhost:9000}}"
export E2E_API_URL="${E2E_API_URL:-http://localhost:${WEBAPP_PORT:-8000}}"
export E2E_DATABASE_URL="${E2E_DATABASE_URL:-postgresql+asyncpg://gts:${DB_PASSWORD:-gts_dev_password}@localhost:${DB_PORT:-5432}/gts_core}"
