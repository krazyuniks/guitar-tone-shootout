# Guitar Tone Shootout — Agent Guide

> For stack details, project structure, and development setup, see [DEVELOPMENT.md](./DEVELOPMENT.md).

## Quick Start

```bash
./worktree.py setup main     # First-time setup (idempotent)
just up-d                    # Start services
just build-astro             # Build frontend (if changed)
```

**Entry point:** http://localhost:9000

## How to Run Commands

**Use `just` for ALL commands. Use `just --list` for discovery.**

Never guess at commands. Before constructing any ad-hoc Docker, uv, or pnpm command, check if `just` already provides it.

- All project code runs in Docker. Host exceptions: E2E tests, `worktree.py`, git/gh.
- Use `just` commands. Never raw Docker, uv, pytest, ruff, mypy, or pnpm on host.
- Astro runs as a persistent service (chokidar auto-rebuilds). Use `just build-astro` or `just watch-astro`.
- Never restart containers for code changes. Uvicorn `--reload` with WatchFiles detects edits automatically.
- The ONLY `uv run` on host is in `tests/e2e/python/` for E2E tests.

## Stack

FastAPI + SQLAlchemy 2.0 + PostgreSQL | Astro SSG + Jinja2 SSR + HTMX + Alpine.js | Docker. See [DEVELOPMENT.md](./DEVELOPMENT.md).

## Principles

**Error ownership.** You are the sole developer. You own EVERY bug. Fix ALL errors immediately. NEVER say "pre-existing", "not caused by this branch", or "out of scope". If you see it, you own it, you fix it now. If unsure how to fix: stop and ask.

**No workarounds.** NEVER implement workarounds, stopgaps, or deviations from the plan. If the planned approach doesn't work: STOP, explain what isn't working and why, ask how to proceed. NEVER guess at architecture decisions, file locations, build processes, port configurations, or API contracts.

**No defensive parsing.** If the upstream is deterministic, trust it. Read the one field where the data lives. If something fails, fail with a clear error — do not silently try another extraction path. Three lines, not twenty.

**Wait for instructions.** Do ONLY what the user explicitly asks. NEVER chain into the next logical step without being asked.

**Conversation UX.** One question at a time. Context adjacent to question. Build iteratively. Summarise periodically. No scroll-dependent layouts.

**MCP required for UI.** UI work REQUIRES Chrome DevTools MCP. E2E test authoring REQUIRES Playwright MCP. If MCP is unavailable: STOP, report "MCP server required but not available", wait for user to restart with MCP enabled.

## Architecture

| Module | Can depend on | Cannot depend on |
|--------|---------------|------------------|
| `core` | (none) | audio, video, sources, apps |
| `audio` | core | video, sources, apps |
| `video` | core, audio | sources, apps |
| `source_*` | core | audio, video, other sources, apps |
| `webapp` | core, audio, video, messaging | sources |
| `t3k-sync` | core, source_t3k, messaging | audio, video, webapp |
| `audio-worker` | core, audio, messaging | video, sources, webapp |
| `video-worker` | core, video, messaging | audio, sources, webapp |

**Single database:** All BCs share one PostgreSQL instance (`gts_core`). BC separation via `import-linter` + table naming (`core_*`, `t3k_*`).

**BC table isolation:** Each BC's ORM models MUST only reference their own BC's tables.

**Transactional outbox:** All pgmq publishes MUST happen within the same database transaction as the domain state change.

**Enforcement**: `import-linter` contracts in root `pyproject.toml`.

### Query Patterns

- ALWAYS `joinedload` for eager loading. NEVER `selectinload`, `subqueryload`, or `lazyload`.
- ALWAYS `.unique()` on results when `joinedload` with collections (1:N, M:N).
- `lazy="raise"` on ALL model relationships. NEVER `lazy="selectin"`, `lazy="select"`, or `lazy="subquery"`.
- One query per service method. Repositories return fully-hydrated aggregates.
- Paginated lists: use ID subquery for LIMIT/OFFSET, then hydrate with joinedload.

## Security

- SQL injection: never f-string SQL. Use SQLAlchemy ORM or parameterised queries.
- XSS: never bypass auto-escaping. No `|safe` in Jinja2, no `set:html` in Astro.
- Secrets: never commit secrets, API keys, or tokens to code. Use environment variables.
- CORS: never use `allow_origins=["*"]`. Restrict to known origins.
- Resource access: always verify `resource.user_id == current_user.id`. Return 404 not 403.
- Input validation: all API input/output via Pydantic schemas with reasonable limits.

### Authentication

- T3K = passwordless OAuth. No user credentials stored by GTS. Only OAuth access/refresh tokens.
- Token-based auth (stateless). JWT validated per request. No server-side sessions.
- Admin API (Webapp, port 8000, `/api/admin/*`): NO authentication. Network-level access control only.
- User API (Webapp, port 8000): all `/api/v1/*` routes require `CurrentUser` token authentication.

## Testing

- Use `just tdd <path>` for running tests during development.
- Test against real services. No mocking. `unittest.mock` imports are banned (enforced by quality gate).
- `just test-golden-path` is MANDATORY before story completion. Failures BLOCK completion.
- Tests are regression nets written AFTER the product works, not the definition of done.
- NEVER use `curl`/`wget`/`httpie` as validation. Only: `just test-golden-path`, `just tdd`, Chrome DevTools MCP, orchestrator checkpoints.
- E2E tests run on HOST, not Docker. Cannot import internal packages. Use Playwright + raw SQL via `text()`.
- E2E tests MUST: use `page.goto()` for navigation, assert DOM visibility, verify database state.
- NEVER mock internal services or APIs in any test.

## Frontend

- `astro/dist/` is committed to git. Chokidar auto-rebuilds. Commit both `astro/src/` and `astro/dist/`.
- All interactive elements MUST have `data-testid` attributes for Playwright testing.
- No CDN Tailwind. All styles pre-compiled by Astro at `/_astro/*.css`.
- Jinja2 templates extend `layouts/base.html` (built by Astro, provides CSS + scripts).
- No inline styles. Use Tailwind utility classes with design tokens from `astro/src/styles/global.css`.
- No SPA navigation. All links are standard `<a href>`. No ClientRouter, View Transitions, or `data-astro-reload`.
- HTMX for small interactions only (checkboxes, modals, inline updates). Not for page navigation.

## Epic Workflow

- **Principle: "No model marks its own homework."** Opus plans, Codex critiques the plan, agents implement, Opus critiques the implementation.
- Epics run via the stateless orchestrator (`workflow/orchestrator.py`). JSONL log is the only state — enables crash-resume.
- **6 verification gates:** Phase A (deterministic), Phase B (Codex critique), decision gate (human), story validation (checkpoints), story critique (Opus), epic critique (Opus).
- `just epic N` — full pipeline: ingest -> plan -> verify -> gate -> execute -> critique.
- `just epic-status N` — check progress from JSONL logs (read-only).
- `just epic-validate-plan N` — run Phase A deterministic validation only (read-only).
- `just map-codebase` — regenerate .planning/codebase/ files.
- `just index-wiki` — regenerate .planning/wiki-indexes/.
- NEVER read plan files manually, dispatch sub-agents, or use old V1/V2 commands. The orchestrator handles everything.
- See `wiki/Epic-Workflow.md` for full pipeline documentation.

## Infrastructure

- NEVER run ad-hoc Docker commands. Use `just` + `worktree.py`.
- NEVER edit `docker-compose.override.yml` or `.env.local` — they are auto-generated.
- Hook-blocked commands: `docker volume rm`, `docker volume prune`, `down -v`, `docker system prune`, `DROP DATABASE`, `TRUNCATE CASCADE`, `dropdb`.
- For ANY infrastructure problem: `./worktree.py setup <name>` (idempotent).
- **Container topology:** webapp, t3k-sync, audio-worker, video-worker, postgres, nginx.
- **`--profile jobs`:** Activates BC worker containers (t3k-sync, audio-worker, video-worker). Main worktree only.
- **Messaging:** pgmq queues in PostgreSQL. Command queues (point-to-point) and event queues (multi-consumer via offset tracking). See wiki for queue topology.

## Git & GitHub

**GitHub issues are the source of truth.** All work traces back to a GitHub issue.

## Session Context Management

**Separate exploration from execution.** Research sessions should NOT be used for implementation.

1. **Exploration sessions** — research, planning, epic creation, codebase analysis
2. **Execution sessions** — implementation with fresh context
3. **Never mix** — if you've done significant exploration, hand off to fresh session

## Landing the Plane (Session Completion)

**Work is NOT complete until `git push` succeeds.**

1. **File issues for remaining work**
2. **Run quality gates** (if code changed)
3. **Update issue status**
4. **PUSH TO REMOTE** — MANDATORY:
   ```bash
   git pull --rebase
   git push
   git status  # MUST show "up to date with origin"
   ```
5. **Verify** — all changes committed AND pushed
6. **Hand off** — provide context for next session

**NEVER stop before pushing.** NEVER say "ready to push when you are" — YOU must push.

## Architecture Reference

| Topic | Skill Reference |
|-------|----------------|
| Domain model | `gts-architecture/references/domain-model.md` |
| Architecture layers | `gts-architecture/references/architecture-layers.md` |
| Design patterns | `gts-architecture/references/design-patterns.md` |
| Database | `gts-architecture/references/database.md` |
| Data pipeline | `gts-architecture/references/data-pipeline.md` |
| Web application | `gts-architecture/references/web-application.md` |
| Audio & video | `gts-architecture/references/audio-video.md` |
| Job scheduling | `gts-architecture/references/job-scheduling.md` |
| Infrastructure | `gts-architecture/references/infrastructure.md` |
| Security | `gts-architecture/references/security.md` |
| Testing | `gts-architecture/references/testing.md` |
| Operations | `gts-architecture/references/operations.md` |
| Configuration | `gts-architecture/references/configuration.md` |

Wiki deep-dives: `../wiki/GTS-Technical-Architecture.md`, `../wiki/REFERENCE-ARCHITECTURE.md`
