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
- In zsh scripts, do not use `path` as a scalar variable and do not use post-increment under `set -e`; `path` controls command lookup and a zero-valued post-increment returns failure.

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

The product and technical target are being reconciled. Treat current code as implementation evidence, not as proof of the intended boundary. Durable target state belongs in `docs/`, with reasoning in ADRs and terms in `CONTEXT.md`; do not add target architecture to this instruction file.

The executable current dependency constraints are the `import-linter` contracts in root `pyproject.toml`. Read them before changing package dependencies. Database changes must preserve table ownership and publish pgmq messages in the same transaction as the domain state change.

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

- Tone3000 browser identity and the background catalogue synchroniser use separate credentials.
- Do not extend the legacy shared browser OAuth file, public session-restoration route or saved-identity status route.
- Every user API route requires validated current-user identity unless its public-read contract is explicit and tested.
- Keep administrative operations off public ingress and test that boundary at nginx and application level.

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

The Radian IT project backlog owns scope and order. GitHub issues and pull
requests are execution evidence only. If no external runner is available, work
manually from the exact supplied backlog scope; do not recreate an in-repo
workflow implementation.

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

The project backlog is the source of truth for remaining work. Link GitHub issues and pull requests where they provide execution evidence, but do not derive project order or residual scope from them.

**No branches on the main checkout.** The `main` checkout commits directly to `main`. NEVER create feature branches in it. Each feature worktree IS a branch — create + provision it with `worktree up gts <branch>`. Creating branches within a worktree causes staging area race conditions when multiple sessions commit concurrently.

## Session Context Management

**Separate exploration from execution.** Research sessions should NOT be used for implementation.

1. **Exploration sessions** — research, planning, epic creation, codebase analysis
2. **Execution sessions** — implementation with fresh context
3. **Never mix** — if you've done significant exploration, hand off to fresh session

## Landing the Plane (Session Completion)

**Work is NOT complete until `git push` succeeds.**

1. **Return remaining work to the canonical project backlog and link any GitHub evidence**
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
