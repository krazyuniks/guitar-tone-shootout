#!/usr/bin/env bash
# Astro type-check hook — runs inside Docker.
# Warn-only: prints diagnostics but never blocks commit.
# Real errors are caught by `just check` and CI.
set -uo pipefail

docker compose exec -T astro pnpm check || true
