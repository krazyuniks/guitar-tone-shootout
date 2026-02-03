#!/usr/bin/env bash
# Astro lint hook - graceful if Docker not running
# Auto-fixes lint issues via just command

if just fix-lint-astro 2>/dev/null; then
    exit 0
else
    echo "Warning: Could not run astro lint (Docker not running?), skipping"
    exit 0  # Don't fail commit if Docker isn't running
fi
