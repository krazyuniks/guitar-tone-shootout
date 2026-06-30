#!/usr/bin/env bash
# GTS gate hook (B4) for the worktree engine.
#
# The deterministic quality gate: lint, type, unit tests, and import rules inside
# the provisioned webapp container, plus host-side TypeScript and test-quality
# checks. Exits non-zero as soon as any check fails. The per-worktree Postgres
# starts empty (migrated by provision); pytest fixtures build their own schema.
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/_derive.sh"

echo "[gate] project=$COMPOSE_PROJECT_NAME slot=$SLOT"

# --- In-container checks (run inside the provisioned webapp) ---
wt_dc exec -T webapp ruff check model/ infra/ sources/ apps/ tests/
wt_dc exec -T webapp ruff format --check model/ infra/ sources/ apps/ tests/
wt_dc exec -T webapp mypy model/gts/ model/video/ --strict
wt_dc exec -T webapp pytest tests/unit/ -v
wt_dc exec -T webapp lint-imports

# --- Astro checks (noImplicitAny via astro check; no-explicit-any via eslint-plugin-astro) ---
wt_dc exec -T astro pnpm check
wt_dc exec -T astro pnpm lint

# --- Host-side checks (no container) ---
# A fresh feature worktree has no model/video/node_modules (gitignored); install
# the pinned deps once, then run the project-pinned tsc and eslint (not npx/global).
if [ ! -x model/video/node_modules/.bin/tsc ]; then
    (cd model/video && npm ci)
fi
(cd model/video && node_modules/.bin/tsc --noEmit)
(cd model/video && node_modules/.bin/eslint .)
python scripts/test_quality_check.py tests/

echo "[gate] passed"
