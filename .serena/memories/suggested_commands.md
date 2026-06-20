# Suggested Commands

All project commands run through `just` (which wraps Docker). Never run raw pytest/ruff/mypy on host.

## Essential
- `just up-d` — start all services
- `just down` — stop all services
- `just status` — check service health
- `just logs` — tail service logs

## Development
- `just build-astro` — build Astro frontend
- `just watch-astro` — watch Astro logs (auto-rebuilds)
- `just shell` — open shell in backend container
- `just repl` — Python REPL in backend container
- `just psql` — PostgreSQL shell (gts_core DB)
- `just migrate` — run database migrations

## Quality Checks
- `just check` — run ALL quality checks (lint + types + tests)
- `just check-lint` — lint and formatting only
- `just check-types` — type checking (mypy strict on gts)
- `just check-tests` — unit tests only
- `just check-imports` — import dependency rules
- `just check-astro` — Astro lint + type check

## Testing
- `just tdd PATH` — run single test file (TDD mode, Docker)
- `just test` — all tests except E2E (Docker)
- `just test-unit` — unit tests (Docker)
- `just test-integration` — integration tests (Docker)
- `just test-golden-path` — E2E golden path (host, hits Docker)
- `just test-regression` — regression tests

## Infrastructure
- `./worktree.py setup main` — first-time setup (idempotent)
- `just rebuild` — rebuild and restart containers
- `just db-export` — export database backup
- `just db-import FILE` — import database backup

## Git/GitHub
- Always use `--repo krazyuniks/guitar-tone-shootout` with `gh` commands
- Never commit directly to main
