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

Commands change over time - always discover dynamically rather than memorising. Before constructing any ad-hoc Docker, uv, or pnpm command, check if `just` already provides it.

**Quick reference:**
```bash
just --list           # Find ANY command (ALWAYS check here first)
just check            # Quality gates (runs in Docker)
just fix-lint         # Auto-fix issues (runs in Docker)
just test-regression  # Stack tests (runs in Docker)
just test-e2e         # E2E tests (runs on host)
just build-astro      # Build Astro frontend
```

**Never guess at commands.** If `just --list` doesn't have it, ask.

## Stack

| Layer | Technology |
|-------|------------|
| **Package Management** | uv workspaces (monorepo) |
| **Backend** | FastAPI, SQLAlchemy 2.0, PostgreSQL (dual DB), Redis, TaskIQ, pgmq |
| **Frontend** | Astro SSG (pre-bundled), Jinja2 SSR, HTMX, Alpine.js, Tailwind |
| **Testing** | pytest, Playwright |
| **Quality** | ruff, mypy, import-linter |
| **Infrastructure** | Docker (db, redis, webapp, nginx, worker, scheduler) |

**Note:** Astro is pre-bundled (`frontend/astro/dist/` committed to git). No Vite dev server at runtime.

## Infrastructure Architecture

**Hard separation between build system and runtime.**

| Concern | What It Is | Runtime Reference |
|---------|------------|-------------------|
| Build system | Astro, Tailwind, `frontend/astro/` dir | **None** - implementation detail |
| Static assets | HTML/CSS/JS in `frontend/astro/dist/` | "static" or "assets" |
| SSR pages | Jinja2 templates via FastAPI | "webapp" |

### Dual Database Architecture

| Database | Purpose | Access |
|----------|---------|--------|
| `gts_core` | Application data (users, shootouts, chains) | Webapp, worker |
| `gts_t3k_source` | T3K source data (packs, models, presets) | Worker only |

**Critical**: Webapp has NO direct access to T3K source database. Worker bridges the two databases via pgmq message queues.

### Runtime Stack
```
db, redis, webapp, nginx, worker, scheduler
```
No astro container at runtime.

### Build-Only Services
```bash
# Astro container only starts with --profile build
docker compose --profile build up astro
just build-astro        # Starts astro, runs build
just watch-astro        # Starts astro, watches for changes
```

### nginx Configuration
Single `nginx.conf.template` for all environments, processed via envsubst at container startup.
- Static files served from `/static` (bind-mounted `frontend/astro/dist/`)
- SSR pages proxied to webapp
- API routes proxied to webapp

### Docker Compose Architecture

**Overlay pattern for environment-specific configuration.**

| File | Purpose |
|------|---------|
| `docker-compose.yml` | Base config (no ports, no worktree-specific values) |
| `docker-compose.override.yml` | Worktree-specific ports, container names |
| `docker-compose.traefik.yml` | Traefik integration for HTTPS/subdomain routing |
| `docker-compose.ci.yml` | CI ephemeral volumes, isolation |

**Usage:**
```bash
# Local development (auto-loads override)
docker compose up -d

# With Traefik (public deployment)
docker compose -f docker-compose.yml -f docker-compose.override.yml -f docker-compose.traefik.yml up -d

# CI
docker compose -f docker-compose.yml -f docker-compose.ci.yml up -d
```

### Dockerfiles

| File | Purpose | Has uv? |
|------|---------|---------|
| `Dockerfile.dev` | Development with bind mounts, live reload | Yes |
| `Dockerfile.webapp` | Production multi-stage, minimal | No (venv only) |
| `Dockerfile.worker` | Production worker | No |

**Development uses `Dockerfile.dev`** - single stage, uv installed, supports `docker compose exec webapp pytest`.

## Development Workflow

**Single path. No optional steps. Both developers and Claude follow identical workflow.**

```bash
# Start services
just up-d                   # Start all services

# Development cycle
just build-astro            # Build frontend (if changed)
just check                  # Run quality gates (in Docker)
just test-regression        # Run stack tests (in Docker)
just test-e2e               # Run E2E tests (on host)
```

**No host .venv.** All project code executes in Docker. E2E tests are the only exception (they hit Docker containers from the host).

## Container-First Execution

**All project commands run in Docker. The ONLY host execution is E2E tests.**

| Command Type | Runs In | How |
|--------------|---------|-----|
| Lint, type check | Docker | `just check` → `docker compose exec -T webapp ruff/mypy` |
| Unit tests | Docker | `just test-unit` → `docker compose exec -T webapp pytest` |
| Integration tests | Docker | `just test-integration` → `docker compose exec -T webapp pytest` |
| E2E tests | **Host** | `just test-e2e` → `cd tests/e2e/python && uv run pytest` |
| Astro build | Docker | `just build-astro` → `docker compose --profile build run astro` |

**Astro Architecture:** `frontend/astro/dist/` is committed to git. Nginx serves static files directly. Astro container is build-only (not in runtime stack).

### NEVER Run on Host

These commands should NEVER be run directly on the host:

```bash
# FORBIDDEN - always use Docker equivalents via just
uv run pytest tests/unit/     # Use: just test-unit
uv run ruff check             # Use: just check-lint
uv run mypy                   # Use: just check-types
uv sync                       # Not needed - deps managed in Docker
pytest                        # Use: just tdd <path>
```

**The ONLY `uv run` on host is in `tests/e2e/python/` for E2E tests.**

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
│   └── audio/                  # Audio processing
│       └── src/audio/
│           ├── processing/     # NAM, IR, pedalboard processing
│           ├── video/          # Video composition
│           └── analysis/       # Audio analysis (loudness, waveform)
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
| `core` | (none) | audio, sources, apps |
| `audio` | core | sources, apps |
| `source_*` | core | audio, other sources, apps |
| `webapp` | core, audio | sources |
| `worker` | core, audio | sources |
| `scheduler` | core | audio, sources |

**Critical**: Webapp has NO dependency on sources. Worker is the bridge between gts_core and gts_t3k_source databases.

**Enforcement**: `import-linter` contracts in root `pyproject.toml` enforce these rules.

### Backend
- **Services own transactions**: Use `async with session.begin():`
- **Ports/Adapters pattern**: Services use injected adapters (persistence, external, processing)
- **Pydantic for validation**: All API input/output via schemas
- **Domain isolation**: `libs/core/` has zero framework dependencies

### Frontend (Astro Build System)
- **Astro SSG**: Static pages (`/`, `/about`, `/login`) pre-built to `frontend/astro/dist/`, served by nginx
- **Jinja2 SSR**: Dynamic pages (`/shootouts`, `/library/*`, `/shootout/*`) served by FastAPI
- **HTMX + Alpine.js**: Interactivity on SSR pages
- **React island**: SignalChainBuilder only (`/library/chains/build`)
- **Tailwind for styling**: Utility classes, design tokens compiled at build time
- **Pre-bundled**: `frontend/astro/dist/` is committed to git - no Vite dev server at runtime
- **Full docs**: See [Frontend Architecture](https://github.com/krazyuniks/guitar-tone-shootout/wiki/Frontend-Architecture) in the wiki

### Testing Strategy

**Clear boundary: Unit/Integration in Docker, E2E on Host.**

| Test Type | Location | Runs In | Command | Purpose |
|-----------|----------|---------|---------|---------|
| Regression | `tests/regression/` | Docker | `just test-regression` | Stack connectivity (ORM → Repo → DB) |
| Unit | `tests/unit/` | Docker | `just test-unit` | Isolated logic, no I/O |
| Integration | `tests/integration/` | Docker | `just test-integration` | Real DB/Redis |
| E2E (Playwright) | `tests/e2e/python/` | Host | `just test-e2e` | Full user journey |

**Regression tests** validate the ORM → Repository → Database stack works:
- User and Job entity round-trips
- Uses SQLite in-memory for speed (~0.2s)
- Run before commits to catch fundamental breaks

**Commands:**
```bash
just test-regression  # Stack connectivity (< 1s) - run before commits
just test             # Unit + Integration (< 30s) - run before PRs
just tdd <path>       # Single test during development (Docker)
just test-e2e         # E2E only (host, requires running containers)
```

**E2E test isolation:**
- `tests/e2e/python/pyproject.toml` - standalone package with pytest-playwright, httpx
- `cd tests/e2e/python && uv run pytest` - uv creates isolated venv automatically
- No dependency on main workspace `.venv`

See `tests/AGENTS.md` for test structure and patterns.

### Dependency Management

**Three isolation boundaries:**

| Tool | Dependency Source | Where Runs | Notes |
|------|-------------------|------------|-------|
| Project code | uv workspace (`pyproject.toml`) | Docker | `docker compose exec webapp pytest` |
| E2E tests | `tests/e2e/python/pyproject.toml` | Host | Isolated from workspace |
| `worktree.py` | PEP 723 inline deps | Host | Self-contained, no venv needed |

**No host .venv.** There should be no `.venv` directory at project root. All project code executes in Docker.

## Skills Reference

### Global Skills (from ~/.claude/)
| Skill | Purpose |
|-------|---------|
| `/commit` | Create conventional commits |
| `/check` | Run quality gates |
| `/playwright` | Browser testing, screenshots |
| `/htmx` | HTMX patterns |
| `/gh-workflow` | GitHub issue management, dependencies |
| `/security-review` | Security review methodology |

### GTS-Specific Skills
| Skill | Purpose |
|-------|---------|
| `gts-backend-dev` | FastAPI patterns, SQLAlchemy, async Python |
| `gts-frontend-dev` | Jinja2 SSR, HTMX, Tailwind |
| `gts-testing` | pytest fixtures, integration patterns |
| `docker-infra` | Container configuration |
| `chrome-devtools` | Interactive debugging |
| `hot-reload` | Astro rebuild workflow (pre-bundled, no Vite) |

## Agents Reference

### Global Agents (from ~/.claude/)
| Agent | Purpose |
|-------|---------|
| `architect` | Architecture decisions, system design |
| `code-reviewer` | Reviewing code changes, checking conventions |
| `test-runner` | Run tests in isolation, report failures |
| `plan-reviewer` | Validate implementation plans |

### GTS-Specific Agents
| Agent | Purpose |
|-------|---------|
| `gts-lint-checker` | Check GTS code quality without fixing |
| `gts-workflow-verifier` | Verify hot reload infrastructure |
| `gts-quality-reviewer` | Full pre-merge validation report |
| `gts-error-resolver` | Debug and fix build/lint/test errors |
| `gts-log-monitor` | Monitor Docker logs for errors |

## Conversation UX (CLI Environment)

**CRITICAL:** User is in a CLI with limited screen real estate. They cannot see content at the top while reading the bottom.

### Rules

1. **One question at a time** - Never dump pages of content then ask multiple questions at the bottom
2. **Context adjacent to question** - Show ONLY the relevant snippet immediately before the question
3. **Build iteratively** - Synthesize each answer into all the next questions
4. **Summarize periodically** - After 3-5 questions, briefly recap decisions made
5. **No scroll-dependent layouts** - Never assume user can see content from earlier in your response

### Bad Pattern
```
[huge table of 20 items]
...scrolling...
Questions:
1. Is item 3 a duplicate?
2. Should item 7 go under X?
3. What about item 15?
```

### Good Pattern
```
## Item #3: "Fix authentication"
Similar to #42 "Auth refactor"

Is this a **duplicate** of #42, or a **separate issue**?
```
*(wait for answer, then show next item with its context)*

## Rules

### CRITICAL: Do Not Assume - Always Ask

**Never assume. Always ask.** This is the most important rule.

When uncertain about ANY of the following, STOP and ask the user:
- Project conventions or patterns
- Which tool/approach to use
- Whether something should run on host vs Docker
- File locations or naming conventions
- Configuration values or settings
- Whether a feature exists or how it works

**Bad behaviour:**
- "I'll assume this runs on host since it's a Python script"
- "I'll use approach X since it's common"
- "This probably works like Y"

**Good behaviour:**
- "Should this run on host or in Docker?"
- "I see two possible approaches. Which do you prefer?"
- "I'm not sure where this config goes. Can you clarify?"

**The cost of asking is low. The cost of wrong assumptions is high.**

### Other Rules

1. **Run in containers** - Not on host (except explicit host tools like worktree.py)
2. **Review auto-fixes after commit** - Pre-commit auto-fixes lint/format
3. **Use `/merge` when done** - Single command: pre-merge checks → PR → auto-merge
4. **Follow existing patterns** - Check skills for examples
5. **Test against real services** - No mocking internal systems
6. **Commit working code** - Don't commit if tests fail
7. **Use provided tooling for infrastructure** - See below
8. **Respect dependency rules** - Webapp never imports from sources

### Infrastructure Management Policy

**CRITICAL: NEVER run ad-hoc Docker commands or manually edit generated files.**

This project has declarative infrastructure. Generated files (docker-compose.override.yml, .env.local) are output, not input. Manual patches break idempotency - the next `worktree.py setup` will overwrite them.

**The rule is absolute:**
1. **Fix source code** (`worktree/*.py`, `justfile`, templates) - NOT generated output
2. **Use `just` commands** - NOT raw Docker commands
3. **Use `worktree.py`** - NOT manual file edits

| Need | Use This | NOT This |
|------|----------|----------|
| Start services | `just up-d` | `docker compose up -d` |
| Stop services | `just down` | `docker compose down` |
| Fix infra issues | `./worktree.py setup <name>` | Manual file edits |
| Run unit tests | `just test-unit` | `uv run pytest` on host |
| Run E2E tests | `just test-e2e` | - |
| Run lint/types | `just check` | `ruff check` on host |
| TDD single test | `just tdd <path>` | `pytest <path>` on host |
| Reset data | Ask user to run `just reset` | `docker compose down -v` |
| Build Astro | `just build-astro` | `cd frontend/astro && pnpm build` |
| Watch Astro | `just watch-astro` | `cd frontend/astro && pnpm dev` |

**NEVER do these:**
- Edit `docker-compose.override.yml` directly (it's auto-generated)
- Edit `.env.local` directly (it's auto-generated)
- Run `docker compose` commands directly (use `just`)
- Run `uv run pytest` on host (except in `tests/e2e/python/`)
- Manually patch ANY generated file

**If tooling is missing or broken:**
1. **STOP** - Don't work around it
2. **Fix the source** - `worktree/*.py`, `justfile`, templates
3. Or **ask the user** to run a command manually

**Why this matters:**
- Manual patches get overwritten on next setup
- Inconsistent state between worktrees
- Breaks reproducibility
- Creates hidden dependencies on manual steps

**Destructive commands are blocked** by `.claude/hooks/block-volume-deletion.sh`.

See `.claude/rules/infrastructure-protection.md` for details.

## MCP (Browser Tools)

MCP servers enable browser inspection and automation. They're **not installed** - they're loaded dynamically via `npx` when Claude starts.

### How to Enable MCP

```bash
opus              # No MCP servers (default)
opus c            # Chrome DevTools MCP
opus p            # Playwright MCP
opus cp           # Both (recommended for UI work)
sonnet cp         # Both with Sonnet model
```

**What happens:**
- Shell function detects Chromium (`/usr/bin/chromium`) automatically
- Runs MCP servers via `npx chrome-devtools-mcp@latest` and `npx @playwright/mcp@latest`
- Headless mode auto-enabled when no display (servers, SSH)

### Checking MCP Status

If `mcp__chrome-devtools__*` or `mcp__playwright__*` tools are unavailable:
1. MCP was not enabled when Claude started
2. **STOP immediately** - do not attempt workarounds
3. Tell user: "I need MCP for this UI work. Please restart with `opus cp`"
4. **Do NOT try to install anything** - MCP runs via npx, not global install
5. **Do NOT use curl/grep as substitutes** - they cannot see JS errors or DOM state

### When MCP Is Required

MCP required **only for UI/browser work**:
- Debugging UI issues (click doesn't work, page blank)
- Verifying visual changes
- Inspecting console/network errors

MCP **not required** for: planning, backend work, documentation, admin tasks.

### Available MCP Tools

| Tool | Purpose |
|------|---------|
| `mcp__chrome-devtools__navigate_page` | Go to URL |
| `mcp__chrome-devtools__take_snapshot` | DOM/a11y tree (preferred over screenshot) |
| `mcp__chrome-devtools__take_screenshot` | Visual capture |
| `mcp__chrome-devtools__list_console_messages` | JS console output |
| `mcp__chrome-devtools__list_network_requests` | Network activity |
| `mcp__chrome-devtools__click` | Click element by uid |
| `mcp__chrome-devtools__fill` | Type into input |
| `mcp__playwright__browser_snapshot` | Similar to chrome-devtools snapshot |
| `mcp__playwright__browser_click` | Click by ref |

**Prefer `take_snapshot` over `take_screenshot`** - snapshots show element uids for interaction.

## Debugging Workflow

### During Development

1. **Tail docker logs** (in background):
   ```bash
   docker compose logs -f --tail=50
   ```

2. **Use Chrome DevTools MCP** - REQUIRED for UI work:
   - `navigate_page` → `take_snapshot` → inspect DOM
   - `list_console_messages` → see JS errors
   - `list_network_requests` → see failed API calls

3. **Verify behaviour live** - Don't assume code works

### When Something Doesn't Work

1. **Get console logs via MCP** - See actual JS errors
2. **Get network logs via MCP** - See actual failed requests
3. **Check docker logs** - Backend errors
4. **Do NOT guess** - Use the tools
5. **Ask the user** - If tools don't reveal the cause, ASK rather than hypothesise

### After Implementation

1. **Write Playwright tests** - Required for CI validation
2. **Run smoke tests** - `pytest -m smoke`
3. **Capture screenshot evidence** - For PR

### Common Issues

| Symptom | Check via MCP |
|---------|---------------|
| Link click does nothing | Console logs (JS error) |
| Page loads but empty | Network logs (failed API) |
| 404 on route | Network logs, docker logs |
| Styles missing | Console logs, network logs |

## Git

```bash
# Never commit to main directly
# Always work in feature branches

# Before PR
just check
git push
```

## GitHub-First Workflow

**GitHub issues are the source of truth.** All work must trace back to a GitHub issue.

### Flow

```
GitHub Issue (source of truth)
    ↓
Feature Branch (from issue number)
    ↓
Implementation
    ↓
PR (references issue)
```

### Rules

1. **Create GH issue first** - Before any work, ensure a GitHub issue exists
2. **Branch from issue** - `git checkout -b 42-feature-name`
3. **Use GitHub dependencies** - Use `is:blocked` / `is:blocking` for dependencies

## Session Context Management

**Separate exploration from execution.** A session used for research, planning, or exploration should NOT be used for implementation.

### Why

- Exploration consumes significant context (file reads, searches, agent results)
- Starting execution in a depleted session risks hitting context limits mid-task
- Incomplete work due to context limits leaves codebase in broken state

### Rules

1. **Exploration sessions** - Research, planning, epic creation, codebase analysis
2. **Execution sessions** - Implementation, one task at a time, fresh context
3. **Never mix** - If you've done significant exploration, hand off to fresh session

### Handoff Pattern

After exploration/planning, provide:
```
Issue #XXX created with N tasks.
Start fresh session for implementation.
```

## Landing the Plane (Session Completion)

**When ending a work session**, you MUST complete ALL steps below. Work is NOT complete until `git push` succeeds.

**MANDATORY WORKFLOW:**

1. **File issues for remaining work** - Create issues for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **PUSH TO REMOTE** - This is MANDATORY:
   ```bash
   git pull --rebase
   git push
   git status  # MUST show "up to date with origin"
   ```
5. **Verify** - All changes committed AND pushed
6. **Hand off** - Provide context for next session

**CRITICAL RULES:**
- Work is NOT complete until `git push` succeeds
- NEVER stop before pushing - that leaves work stranded locally
- NEVER say "ready to push when you are" - YOU must push
- If push fails, resolve and retry until it succeeds

---

## Ralph Hybrid (Autonomous Development)

For complex features, use Ralph Hybrid to run autonomous development loops.

### Workflow

```
1. Plan:    /ralph-hybrid-plan "description"   (in Claude Code)
2. Run:     ralph-hybrid run                    (in terminal)
3. Verify:  (automatic after stories complete)
4. Archive: ralph-hybrid archive               (or prompted after verify)
```

### When to Use Ralph

- Multi-story features (3+ related tasks)
- Features derived from GitHub issues
- Work that benefits from TDD iteration
- When you want autonomous implementation with human checkpoints

### Commands

| Command | Where | Purpose |
|---------|-------|---------|
| `/ralph-hybrid-plan` | Claude Code | Interactive planning, creates spec.md + prd.json |
| `/ralph-hybrid-plan --regenerate` | Claude Code | Regenerate prd.json from updated spec.md |
| `/ralph-hybrid-amend` | Claude Code | Modify requirements mid-implementation |
| `ralph-hybrid run` | Terminal | Execute autonomous loop |
| `ralph-hybrid run --skip-verification` | Terminal | Run without goal-backward verification |
| `ralph-hybrid verify` | Terminal | Run goal-backward verification manually |
| `ralph-hybrid status` | Terminal | Show feature progress |

### Key Concepts

- **Fresh context per iteration**: Each loop iteration starts Claude fresh
- **Memory in files**: prd.json tracks story completion, progress.txt logs history
- **Branch = feature folder**: `.ralph-hybrid/{branch-name}/` holds all state
- **Fail fast**: Circuit breaker trips after 2 same errors or no progress
- **Goal-backward verification**: After stories complete, verifies feature actually works

### GTS Customizations

GTS has customized Ralph Hybrid with project-specific features:

#### Backpressure Hooks

Post-iteration verification at `.ralph-hybrid/hooks/post_iteration.sh`:
- Runs `ruff check` and `ruff format --check` for linting
- Runs `mypy` for type checking (non-blocking)
- Runs `pytest` for unit and integration tests
- Returns exit code 75 (VERIFICATION_FAILED) on failure
- Auto-detects Docker vs host execution

```bash
# Test the hook
.ralph-hybrid/hooks/post_iteration.sh context.json --dry-run
```

#### Project Memories

Cross-session learning at `.ralph-hybrid/memories.md`:

| Section | Purpose |
|---------|---------|
| **Patterns** | Astro + Jinja2 rendering, transaction handling, testing patterns, container rules |
| **Decisions** | PostgreSQL/SQLAlchemy, pre-bundled Astro, worktrees, Python Playwright |
| **Fixes** | Navigation issues, E2E test fixes, auth centralization |
| **Context** | Domain concepts (shootouts, signal chains, gear, auth patterns) |

Memories are automatically injected into each iteration prompt.

#### Customized Skills

GTS-specific skills for specialised tasks:

| Skill | When to Use | Location |
|-------|-------------|----------|
| `/security-review` | Security audits, pre-merge checks | Global (`~/.claude/skills/`) |
| `/code-archaeology` | Legacy code investigation | Global (`~/.claude/skills/`) |
| `incident-response` | Production issues | `.claude/skills/incident-response/` |

**incident-response** covers:
- GTS Docker Compose architecture
- Diagnostic procedures (health checks, logs)
- Mitigation for DB/Redis/worker/nginx issues
- Rollback procedures (code, migrations, full system)
- GTS-specific incidents (T3K OAuth, job backlog)
