#!/usr/bin/env bash
# GTS provision hook (B3) for the worktree engine.
#
# Brings a feature worktree's stack up on the ports the engine allocated, runs
# migrations, and waits for webapp liveness. Driven solely by WORKTREE_SLOT and
# WORKTREE_PORT_{WEBAPP,DB} (see _derive.sh). The feature DB starts empty and is
# migrated; the gate's pytest fixtures build their own schema, so no dump is
# imported and main's data is never touched.
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/_derive.sh"

echo "[provision] project=$COMPOSE_PROJECT_NAME slot=$SLOT webapp=:$WEBAPP_PORT db=:$DB_PORT"

# Pre-create the astro dist bind source as the host user so Docker does not
# auto-create it root-owned and block the in-container astro build (matches up-d).
mkdir -p frontend/astro/dist

# Clear any prior run for this project (idempotent re-provision), then build the
# webapp + astro images. Docker layer cache makes a repeat build cheap.
wt_dc down --remove-orphans >/dev/null 2>&1 || true
wt_dc build

# Start the database and wait until it accepts connections.
wt_dc up -d db
db_ready=0
for _ in $(seq 1 60); do
    if wt_dc exec -T db pg_isready -U gts -d gts_core >/dev/null 2>&1; then
        db_ready=1; break
    fi
    sleep 1
done
if [ "$db_ready" -ne 1 ]; then
    echo "[provision] db did not become ready" >&2; exit 1
fi

# Start the gate-path stack: webapp (the gate target) and astro (builds dist).
# nginx and the jobs-profile workers are not on the gate path and are not started.
wt_dc up -d webapp astro

# Migrate the fresh per-worktree database (alembic inside webapp).
wt_dc exec -T webapp alembic -c infrastructure/migrations/alembic.ini upgrade head

# Wait for webapp liveness (/health needs no DB or secrets).
for _ in $(seq 1 90); do
    if curl -sf "http://localhost:$WEBAPP_PORT/health" >/dev/null 2>&1; then
        echo "[provision] ready"; exit 0
    fi
    sleep 1
done
echo "[provision] webapp did not become healthy on :$WEBAPP_PORT" >&2
exit 1
