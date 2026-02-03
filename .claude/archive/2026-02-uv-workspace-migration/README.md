# UV Workspace Migration (2026-02)

Completed implementation of uv workspace architecture with dual databases.

## What Was Implemented

1. **AGENTS.md Update** - Updated to reflect new architecture
2. **Phase 1: Infrastructure Foundation**
   - uv workspace configuration (pyproject.toml files)
   - Docker Compose with dual PostgreSQL databases (gts_core + gts_t3k_source)
   - pgmq for inter-service messaging
   - Multi-stage Dockerfile for production builds
   - Directory scaffolds for all workspace members
3. **Phase 2: Core Domain Library**
   - libs/core/ with entities, value objects, ports, records, services
   - Zero framework dependencies (pure Python domain)
   - import-linter contracts for dependency enforcement

## Key Architecture Changes

- `backend/app/` → `apps/webapp/src/webapp/`
- Added `libs/core/` (domain), `libs/audio/` (processing)
- Added `sources/t3k/` (T3K source adapter)
- Dual database: gts_core (webapp) + gts_t3k_source (worker only)
- Worker is the bridge between databases via pgmq

## Archived Files

- `implementation-plan.md` - Original plan from planning session
