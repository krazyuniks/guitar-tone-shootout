# Guitar Tone Shootout - Development Guide

Code patterns and quality standards for GTS development.

> **Full technical documentation:** See [DEVELOPMENT.md](./DEVELOPMENT.md) for stack details, architecture, and troubleshooting.

## Quick Start

```bash
./worktree.py setup main     # First-time setup (idempotent)
just up-d                    # Start services
just build-astro             # Build frontend (if changed)
./worktree.py status         # Check current worktree status
```

**Entry point:** http://localhost:9000

## How to Run Commands

**Use `just` for ALL commands. Use `just --list` for discovery.**

Commands change over time — always discover dynamically rather than memorising. Before constructing any ad-hoc Docker, uv, or pnpm command, check if `just` already provides it.

```bash
just --list           # Find ANY command (ALWAYS check here first)
just check            # Quality gates (runs in Docker)
just fix-lint         # Auto-fix issues (runs in Docker)
just test-regression  # Stack tests (runs in Docker)
just test-golden-path # Golden path tests (runs on host)
just build-astro      # Build Astro frontend
```

**Never guess at commands.** If `just --list` doesn't have it, ask.

## Stack

| Layer | Technology |
|-------|------------|
| **Package Management** | uv workspaces (monorepo) |
| **Backend** | FastAPI, SQLAlchemy 2.0, PostgreSQL (dual DB), Redis, TaskIQ, pgmq |
| **Frontend** | Astro SSG (pre-bundled), Jinja2 SSR, HTMX, Alpine.js, Tailwind |
| **Audio Processing** | NAM, IR convolution, pedalboard |
| **Video Processing** | Remotion (React-based video composition) |
| **Testing** | pytest, Playwright |
| **Quality** | ruff, mypy, import-linter |
| **Infrastructure** | Docker (db, redis, webapp, nginx, worker, scheduler) |

**Note:** Astro is pre-bundled (`frontend/astro/dist/` committed to git). No Vite dev server at runtime.

## Project Structure

```
gts/
├── pyproject.toml              # Workspace root (uv workspaces)
├── libs/
│   ├── core/                   # Domain (zero framework deps)
│   │   └── src/core/
│   │       ├── domain/
│   │       │   ├── entities/   # User, Gear, SignalChain, Shootout, Job
│   │       │   └── value_objects/  # Enums, frozen dataclasses
│   │       ├── ports/          # Repository protocols, processor protocols
│   │       ├── records/        # Sync record schemas (GearSyncRecord)
│   │       └── services/       # Domain services (validation, calculation)
│   ├── audio/                  # Audio processing
│   │   └── src/audio/
│   │       ├── processing/     # NAM, IR, pedalboard processing
│   │       └── analysis/       # Audio analysis (loudness, waveform)
│   └── video/                  # Video composition
│       └── src/video/
│           ├── composition/    # Remotion components
│           ├── rendering/      # Video rendering pipeline
│           └── effects/        # Video effects and transitions
├── sources/
│   └── t3k/                    # T3K source adapter
│       └── src/source_t3k/
│           ├── domain/         # T3K-specific entities (Pack, Model)
│           ├── adapters/
│           │   ├── inbound/    # API client, OAuth
│           │   └── outbound/   # pgmq publisher
│           └── services/       # Sync service
├── apps/
│   ├── webapp/                 # FastAPI
│   │   └── src/webapp/
│   │       ├── api/            # REST endpoints, page routes
│   │       ├── auth/           # Session, OAuth
│   │       ├── services/       # Application services
│   │       └── adapters/       # Repository implementations
│   │           └── persistence/
│   │               ├── models/     # SQLAlchemy ORM models
│   │               └── repositories/  # Repository implementations
│   ├── worker/                 # TaskIQ + pgmq consumer
│   │   └── src/worker/
│   │       ├── consumers/      # pgmq message handlers
│   │       └── jobs/           # Background job definitions
│   └── scheduler/              # TaskIQ scheduler
│       └── src/scheduler/
│           └── schedules/      # Cron definitions
├── frontend/
│   └── astro/                  # Build system (pre-bundled)
│       ├── src/
│       │   ├── pages/          # Template sources (.html.ts, .astro)
│       │   ├── layouts/        # Base layout wrapper
│       │   ├── styles/         # Tailwind, design tokens
│       │   └── components/     # React islands
│       └── dist/               # Build output (COMMITTED TO GIT)
├── infrastructure/
│   ├── docker/                 # Dockerfiles, init scripts
│   ├── migrations/             # Alembic migrations (gts_core)
│   └── nginx/                  # nginx.conf.template
└── tests/
    ├── regression/             # Stack connectivity tests (SQLite)
    ├── unit/
    │   ├── core/               # Domain unit tests
    │   ├── audio/              # Audio processing tests
    │   └── webapp/             # ORM and service tests
    ├── integration/
    │   ├── webapp/             # Repository integration tests
    │   └── audio/              # Audio processing integration tests
    ├── e2e/
    │   └── python/             # E2E tests (pytest + Playwright)
    ├── fixtures/               # Shared test fixtures
    └── data/                   # Test data files
```

**Templates:** Edit `.html.ts` files in `frontend/astro/src/pages/`, build with `just build-astro`. Output to `frontend/astro/dist/` is committed to git.

## Key Patterns

### Dependency Rules

| Module | Can depend on | Cannot depend on |
|--------|---------------|------------------|
| `core` | (none) | audio, video, sources, apps |
| `audio` | core | video, sources, apps |
| `video` | core, audio | sources, apps |
| `source_*` | core | audio, video, other sources, apps |
| `webapp` | core, audio, video | sources |
| `worker` | core, audio, video | sources |
| `scheduler` | core | audio, video, sources |

**Critical**: Webapp has NO dependency on sources. Worker is the bridge between gts_core and gts_t3k_source databases.

**Enforcement**: `import-linter` contracts in root `pyproject.toml` enforce these rules.

### Backend
- **Services own transactions**: Use `async with session.begin():`
- **Ports/Adapters pattern**: Services use injected adapters (persistence, external, processing)
- **Pydantic for validation**: All API input/output via schemas
- **Domain isolation**: `libs/core/` has zero framework dependencies

### Frontend
- **Astro SSG**: Static pages pre-built to `frontend/astro/dist/`, served by nginx
- **Jinja2 SSR**: Dynamic pages served by FastAPI
- **HTMX + Alpine.js**: Interactivity on SSR pages
- **React island**: SignalChainBuilder only (`/library/chains/build`)
- **Pre-bundled**: `frontend/astro/dist/` committed to git — no Vite dev server

### Testing
- Unit/Integration in Docker, E2E on Host
- `just test-regression` before commits, `just test` before PRs
- See `tests/AGENTS.md` for structure and patterns

## Conversation UX (CLI Environment)

**CRITICAL:** User is in a CLI with limited screen real estate.

1. **One question at a time** — never dump pages then ask multiple questions
2. **Context adjacent to question** — show ONLY the relevant snippet before asking
3. **Build iteratively** — synthesise each answer into subsequent questions
4. **Summarise periodically** — after 3-5 questions, recap decisions
5. **No scroll-dependent layouts** — never assume user can see earlier content

## Rules

### CRITICAL: Do Not Assume — Always Ask

**Never assume. Always ask.** This is the most important rule.

When uncertain about ANY of the following, STOP and ask the user:
- Project conventions or patterns
- Which tool/approach to use
- Whether something should run on host vs Docker
- File locations or naming conventions
- Configuration values or settings
- Whether a feature exists or how it works

**The cost of asking is low. The cost of wrong assumptions is high.**

### CRITICAL: GTS is Source-Agnostic

**GTS has its own domain model.** Sources (T3K, future providers) are external adapters that sync data INTO GTS.

**Core domain models NEVER contain source-specific fields:**
- NO `t3k_id`, `t3k_username`, `tone3000_*`, etc.
- GTS entities: User, Gear, Pack, Model, SignalChain, Shootout, Job
- Source entities stay in source adapters (`sources/t3k/`)

**The domain model is defined in:**
- `libs/core/src/core/domain/` — Entity definitions
- `../wiki/GTS-Technical-Architecture.md#domain-model` — Authoritative documentation

### CRITICAL: READ Before DERIVE — No Summarisation

**NEVER assume data models exist. ALWAYS read the source file directly.**

Before deriving ANY artifact (model, repository, service, API):
1. Use the **Read tool directly** on the authoritative file
2. **NO Task agents** for domain model exploration — they summarise and lose precision
3. Cite the exact file and line where the entity/field is defined
4. If you cannot cite a source, **STOP and ASK**

### Other Rules

1. **Run in containers** — not on host (except E2E, worktree.py, git/gh)
2. **Review auto-fixes after commit** — pre-commit auto-fixes lint/format
3. **Use `/merge` when done** — pre-merge checks → PR → auto-merge
4. **Follow existing patterns** — check skills for examples
5. **Test against real services** — no mocking internal systems
6. **Commit working code** — don't commit if tests fail
7. **Use provided tooling** — `just` + `worktree.py`, never ad-hoc Docker
8. **Respect dependency rules** — webapp never imports from sources

## Git & GitHub

```bash
# Never commit to main directly. Always work in feature branches.
# Before PR:
just check
git push
```

**GitHub issues are the source of truth.** All work traces back to a GitHub issue.
- Create GH issue first, branch from issue (`42-feature-name`)
- Use GitHub dependencies (`is:blocked` / `is:blocking`)

## Session Context Management

**Separate exploration from execution.** Research sessions should NOT be used for implementation.

1. **Exploration sessions** — research, planning, epic creation, codebase analysis
2. **Execution sessions** — implementation, one task at a time, fresh context
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
