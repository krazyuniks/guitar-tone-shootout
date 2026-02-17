#!/usr/bin/env bash
# Astro type-check hook — runs inside Docker. Fails if Docker is not running.
set -euo pipefail

docker compose exec -T astro pnpm check
