#!/usr/bin/env bash
# Update all project dependencies (deterministic + advisory).
# Run periodically to keep deps current. Safe to run at any time.
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

echo "=== Python dependencies (uv) ==="
echo "Updating uv.lock to latest compatible versions..."
uv lock --upgrade
echo "Done. Review changes with: git diff uv.lock"
echo ""

echo "=== Node/pnpm dependencies (Astro) ==="
echo "Updating pnpm lockfile to latest compatible versions..."
docker compose exec -T astro pnpm update
echo "Done. Review changes with: git diff frontend/astro/pnpm-lock.yaml"
echo ""

echo "=== Host tools ==="
echo "Updating uv..."
uv self update
echo ""

echo "=== Docker base image versions (manual) ==="
echo "Current pinned versions:"
grep -h '^FROM' infrastructure/docker/Dockerfile.* frontend/astro/Dockerfile | sort -u
echo ""

PYTHON_LATEST=$(docker run --rm python:3.14-slim python3 --version 2>/dev/null | awk '{print $2}' || echo "unknown")
NODE_LATEST=$(docker run --rm node:24-alpine node --version 2>/dev/null | tr -d 'v' || echo "unknown")

echo "Latest available:"
echo "  Python 3.14.x: ${PYTHON_LATEST}"
echo "  Node 24.x:     ${NODE_LATEST}"
echo ""
echo "If versions differ, ask Claude to update Dockerfiles:"
echo "  'Update Docker base images to python:${PYTHON_LATEST}-slim and node:${NODE_LATEST}-alpine'"
echo ""

echo "=== Post-update checklist ==="
echo "1. Review lockfile diffs"
echo "2. Rebuild Docker: docker compose build"
echo "3. Run quality gates: just check"
echo "4. Commit: git add -A && git commit -m 'build: update dependencies'"
