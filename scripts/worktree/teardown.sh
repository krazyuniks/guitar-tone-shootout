#!/usr/bin/env bash
# GTS teardown hook (B5) for the worktree engine.
#
# Brings the feature stack down and reclaims the per-worktree database volume and
# generated storage. Shared read-only data (../gts-storage/models, audio) and the
# main worktree are never touched. The engine never provisions main (slot 0 is
# reserved), but this defends in depth on resolved-path equality regardless.
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/_derive.sh"

echo "[teardown] project=$COMPOSE_PROJECT_NAME slot=$SLOT"

# Guard main: refuse if this checkout resolves to the main worktree.
ROOT_PARENT="$(cd "$WT_ROOT/.." 2>/dev/null && pwd)"
MAIN_PATH="$ROOT_PARENT/main"
if [ -d "$MAIN_PATH" ] && [ "$(cd "$WT_ROOT" && pwd -P)" = "$(cd "$MAIN_PATH" && pwd -P)" ]; then
    echo "[teardown] refusing: this is the main worktree" >&2
    exit 1
fi

# Stop containers and remove the project network. No -v at the compose level: the
# named postgres volume is deleted explicitly below so the reclaim is precise.
wt_dc down --remove-orphans >/dev/null 2>&1 || true

# Reclaim the per-worktree postgres volume (gts-postgres-<slot>, named via
# GTS_WORKTREE). Best-effort: a missing volume is not an error.
docker volume rm "gts-postgres-${SLOT}" >/dev/null 2>&1 || true

# Reclaim the generated per-worktree artefacts (override + empty storage trees).
# Shared RO data lives under ../gts-storage and is untouched.
rm -rf "$RUN_DIR"

echo "[teardown] released"
