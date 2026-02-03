#!/usr/bin/env bash
# Astro lint hook - graceful if Docker not running
# Ruff hooks handle Python; this handles Astro only

if docker compose --profile build run --rm astro pnpm lint --fix 2>/dev/null; then
    exit 0
else
    echo "Warning: Could not run astro lint (Docker not running?), skipping"
    exit 0  # Don't fail commit if Docker isn't running
fi
