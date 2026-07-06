# Guitar Tone Shootout — Agent Guide

> For stack details, project structure, and development setup, see [DEVELOPMENT.md](./DEVELOPMENT.md).

## Quick Start

```bash
./scripts/first-time-setup.sh   # First-time: host deps + mint env.local.sh + just up-d
just up-d                       # Start the main stack (existing checkout)
just build-astro                # Build frontend (if changed)
```

**Entry point:** http://localhost:9000

## How to Run Commands

**Use `just` for ALL commands. Use `just --list` for discovery.**

Never guess at commands. Before constructing any ad-hoc Docker, uv, or pnpm command, check if `just` already provides it.

- All project code runs in Docker. Host exceptions: E2E tests, the `worktree` engine CLI, git/gh.
- Use `just` commands. Never raw Docker, uv, pytest, ruff, mypy, or pnpm on host.
- Astro runs as a persistent service (chokidar auto-rebuilds). Use `just build-astro` or `just watch-astro`.
- Never restart containers for code changes. Uvicorn `--reload` with WatchFiles detects edits automatically.
- Host `uv run` is limited to host-only tooling: `scripts/t3k_auth.py` and `tests/e2e/python/` for E2E tests.

## Stack

FastAPI + SQLAlchemy 2.0 + PostgreSQL | Public frontend: Astro SSG + Jinja2 SSR + HTMX/Alpine for small interactions | App frontend: Vite + React SPA under `/app/*` | Docker. See [DEVELOPMENT.md](./DEVELOPMENT.md).

## Principles

**Error ownership.** You are the sole developer. You own EVERY bug. Fix ALL errors immediately. NEVER say "pre-existing", "not caused by this branch", or "out of scope". If you see it, you own it, you fix it now. If unsure how to fix: stop and ask.

**No workarounds.** NEVER implement workarounds, stopgaps, or deviations from the plan. If the planned approach doesn't work: STOP, explain what isn't working and why, ask how to proceed. NEVER guess at architecture decisions, file locations, build processes, port configurations, or API contracts.

**No defensive parsing.** If the upstream is deterministic, trust it. Read the one field where the data lives. If something fails, fail with a clear error — do not silently try another extraction path. Three lines, not twenty.

**Autonomy boundary.** Execute the user's requested task end to end, but do not chain into unrelated follow-on work without being asked.

**Conversation UX.** One question at a time. Context adjacent to question. Build iteratively. Summarise periodically. No scroll-dependent layouts.

**Browser automation.** Playwright CLI for agent-driven work; Playwright Python or Playwright TypeScript for E2E tests.

## Architecture

| Module | Can depend on | Cannot depend on |
|--------|---------------|------------------|
| `gts` | (none) | audio, video, sources, apps |
| `audio` | gts | video, sources, apps |
| `video` | gts | audio, sources, apps |
| `source_*` | gts | audio, video, other sources, apps |
| `webapp` | gts, audio, video, messaging | sources |
| `t3k-sync` | gts, source_t3k, messaging | audio, video, webapp |
| `audio-worker` | gts, audio, messaging | video, sources, webapp |
| `shootout-orchestrator` | gts, messaging, webapp | audio, video, sources |

**Core bounded context = `gts`.** The domain BC is conceptually "Core" (the DDD core domain) and is realised as the `gts` package (import root `gts`). Prose that says "Core" - the `model/gts/CLAUDE.md` title `# Core Bounded Context`, context-map references like "Sources -> Core", "Core owns the record schemas" - is intentional and correct. Only the package, path, and import root were renamed from `core` to `gts`. Do not flag "Core" references as stale. (`gts_core` is the database name; `core_*` are table names; `core_engine` is a pytest fixture - all unrelated and also correct.)

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
- User API (Webapp, port 8000): all `/api/*` routes require `CurrentUser` token authentication.

## Testing

- Use `just tdd <path>` for running tests during development.
- Test against real services. No mocking. `unittest.mock` imports are banned (enforced by quality gate).
- `just test-golden-path` is MANDATORY before completing feature work. Failures BLOCK completion.
- Tests are regression nets written AFTER the product works, not the definition of done.
- Validate via `just test-golden-path`, `just tdd`, the Playwright CLI, or Playwright E2E tests (Python or TypeScript).
- E2E tests run on HOST, not Docker. Cannot import internal packages. Use Playwright + raw SQL via `text()`.
- E2E tests MUST: use `page.goto()` for navigation, assert DOM visibility, verify database state.
- NEVER mock internal services or APIs in any test.

## Frontend

Two surfaces, one design system (ADR-0001):

- Public surface: Astro SSG/SSR for `/`, `/shootouts`, `/gear/*`, SEO/AdSense content, and public comparison-player embeds. Anyone can read it.
- App surface: Vite + React SPA under `/app/*` for the logged-in workspace (builder, Gear Browser, own shootouts, library). Client-side routing is expected there.
- All interactive elements, including Astro islands and SPA components, MUST have `data-testid` attributes for Playwright testing.

### Public Surface

- `frontend/astro/dist/` is generated and gitignored. Commit source only; `pnpm build` and `just build-astro` build Astro, inject the CSS hash, then build React islands into `dist/islands/`.
- Jinja2 templates extend `layouts/base.html` (built by Astro, provides CSS + scripts).
- No CDN Tailwind. All styles pre-compiled by Astro at `/_astro/*.css`.
- No inline styles. Use Tailwind utility classes with design tokens from `astro/src/styles/global.css`.
- Standard navigation only: links are `<a href>`. No Astro ClientRouter, View Transitions, or `data-astro-reload`. The former blanket "No SPA navigation" rule applies to this surface only.
- HTMX is for small interactions only (checkboxes, modals, inline updates), not page navigation.

### App Surface

- Client-side routing is the norm under `/app/*`, using Vite + React and TanStack Router.
- Build on the design-system Dense family and the vendored `gts` theme tokens. Vendor/copy design-system files into this repo; do not use `file:` dependencies to the design-system checkout.
- Scaffold and build recipes land with the frontend-reshape epic.

## Workflow

Development tooling (workflow runners, orchestrators, review drivers) is
external to GTS. This repository keeps only thin consumer configuration for
such tools (`.woof/*.toml` for the woof runner); it never vendors tool source,
schemas, playbooks, tests, runtime state, audit logs, locks, or generated
codebase maps.

GTS work starts from GitHub issues. If no external runner is available, work
manually from the issue; do not recreate an in-repo workflow implementation.

## Infrastructure

- NEVER run ad-hoc Docker commands. Use `just` + the `worktree` engine.
- NEVER edit `.worktree-run/docker-compose.override.yml` — it is provision-generated.
- Hook-blocked commands: `docker volume rm`, `docker volume prune`, `down -v`, `docker system prune`, `DROP DATABASE`, `TRUNCATE CASCADE`, `dropdb`.
- For ANY infrastructure problem: `worktree up gts <branch>` (feature) or `just up-d` (main).
- Inside a driver-provisioned slice (an external SDLC runner) you are already in a feature worktree the driver provisioned, with its stack up and the webapp serving `/openapi.json`. Use that running stack (codegen runs in-container against `http://webapp:8000/openapi.json`), commit your change, and stop — the driver runs the gate and the review. The driver owns the worktree lifecycle and the stack: do NOT run `worktree up/down/recover` or `just up-d`/`just down`/`just rebuild` from inside a slice. `worktree recover` deletes a dirty checkout (your uncommitted work goes with it), and the plain stack recipes boot with a blank `OAUTH_ENCRYPTION_KEY` (they read the human-only `env.local.sh` a fresh worktree lacks, whereas the gate mints an ephemeral key) so a hand-started stack fails the auth-encryption tests.
- **Container topology:** webapp, t3k-sync, audio-worker, shootout-orchestrator, postgres, nginx.
- **`--profile jobs`:** Activates BC worker containers (t3k-sync, audio-worker, shootout-orchestrator). Main stack only.
- **Messaging:** pgmq queues in PostgreSQL. Four queues today: `audio_commands` (audio-worker), `shootout_commands` (shootout orchestration), `source_events` (t3k-sync), `dead_letter` (DLQ, no consumer yet).

### Env model

| File | State | Owner |
|---|---|---|
| `compose.env` | committed | static non-secret defaults, loaded via `--env-file` |
| `env.local.sh` | gitignored, human-managed | shell-sourced secrets (`DB_PASSWORD`, `OAUTH_ENCRYPTION_KEY`, `SECRET_KEY`, `GTS_ADMIN_PASSWORD`, `T3K_API_KEY`) — seeded once on first-time setup, never overwritten |
| `env.local.sh.example` | committed | template |
| `.envrc` | committed, optional | direnv — sources `env.local.sh`, exports `USER_UID`/`USER_GID` |
| `scripts/dc` | committed | `docker compose` wrapper: sources `env.local.sh`, derives compose project + ports from the engine (`scripts/worktree/current-env`), attaches `--env-file compose.env`, layers provision's override |
| `.worktree-run/` | gitignored, provision-generated | the per-worktree `docker-compose.override.yml` + empty storage trees (written by `scripts/worktree/_derive.sh`) |

All `just` recipes route through `scripts/dc`. The per-worktree project name, ports, and override come from the worktree engine; there is no `.env.worktree`. `USER_UID` / `USER_GID` are derived from `id -u` / `id -g` at runtime.

## Git & GitHub

**GitHub issues are the source of truth.** All work traces back to a GitHub issue.

**No branches on the main checkout.** The `main` checkout commits directly to `main`. NEVER create feature branches in it. Each feature worktree IS a branch — create + provision it with `worktree up gts <branch>`. Creating branches within a worktree causes staging area race conditions when multiple sessions commit concurrently.

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
