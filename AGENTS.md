# Guitar Tone Shootout - Development Guide

Code patterns and quality standards.

---

## Quick Start

```bash
./worktree.py setup main     # First-time: set up main worktree
./worktree.py setup <issue>  # Create feature worktree from issue
```

**Idempotent**: Setup works for fresh checkout, existing worktree, or any state in between. Automatically starts services if not running.

**Entry point**: http://localhost:{port} (9000 on main, 9010/9020/etc. on feature worktrees)

---

## How to Run Commands

**Use `just` for ALL commands. Use `just --list` for discovery.**

Commands change over time - always discover dynamically rather than memorising. Before constructing any ad-hoc Docker, uv, or pnpm command, check if `just` already provides it.

**Quick reference:**
```bash
just --list           # Find ANY command (ALWAYS check here first)
just uv-sync          # Sync uv workspace dependencies
just check            # Quality gates
just fix-lint         # Auto-fix issues
just build-astro      # Build Astro frontend
just verify-astro-sync # Verify dist/ matches src/
```

**Never guess at commands.** If `just --list` doesn't have it, ask.

---

## Stack

| Layer | Technology |
|-------|------------|
| **Package Management** | uv workspaces (monorepo) |
| **Backend** | FastAPI, SQLAlchemy 2.0, PostgreSQL (dual DB), Redis, TaskIQ, pgmq |
| **Frontend** | Astro SSG (pre-bundled), Jinja2 SSR, HTMX, Alpine.js, Tailwind |
| **Testing** | pytest, Playwright |
| **Quality** | ruff, mypy, import-linter |
| **Infrastructure** | Docker (db, redis, backend, nginx, worker, scheduler), worktrees |

**Note:** Astro is pre-bundled (`frontend/astro/dist/` committed to git). No Vite dev server at runtime.

---

## Infrastructure Architecture

**Hard separation between build system and runtime.**

| Concern | What It Is | Runtime Reference |
|---------|------------|-------------------|
| Build system | Astro, Tailwind, `frontend/astro/` dir | **None** - implementation detail |
| Static assets | HTML/CSS/JS in `frontend/astro/dist/` | "static" or "assets" |
| SSR pages | Jinja2 templates via FastAPI | "backend" |

### Dual Database Architecture

| Database | Purpose | Access |
|----------|---------|--------|
| `gts_core` | Application data (users, shootouts, chains) | Webapp, worker |
| `gts_t3k_source` | T3K source data (packs, models, presets) | Worker only |

**Critical**: Webapp has NO direct access to T3K source database. Worker bridges the two databases via pgmq message queues.

### Runtime Stack (ALL environments)
```
db, redis, backend, nginx, worker, scheduler
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
- SSR pages proxied to backend
- API routes proxied to backend

---

## Development Workflow

```bash
just uv-sync            # Sync dependencies (after git pull)
just up-d               # Start services
just build-astro        # Build frontend
just watch-astro        # Auto-rebuild frontend
```

---

## Container-First Execution

**Never run dev commands on host.** Always use Docker via `just` commands.

**Astro Architecture:** `frontend/astro/dist/` is committed to git. Nginx serves static files directly. Astro container is build-only (not in runtime stack).

---

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
│       │   ├── components/     # React islands
│       │   └── lib/            # Utilities, hooks
│       └── dist/               # Build output (COMMITTED TO GIT)
├── infrastructure/
│   ├── docker/                 # Dockerfiles, init scripts
│   ├── migrations/             # Alembic migrations (gts_core)
│   └── nginx/                  # nginx.conf.template
└── tests/
    ├── unit/
    │   ├── core/               # Domain unit tests
    │   ├── audio/              # Audio processing tests
    │   └── worktree/           # Worktree CLI tests
    ├── integration/
    │   ├── webapp/             # Webapp integration tests
    │   └── worker/             # Worker integration tests
    ├── e2e/
    │   ├── python/             # E2E tests (pytest + Playwright)
    │   └── smoke/              # Infrastructure smoke tests
    ├── fixtures/               # Shared test fixtures
    └── data/                   # Test data files
```

**Templates:** Edit `.html.ts` files in `frontend/astro/src/pages/`, build with `just build-astro`. Output to `frontend/astro/dist/` is committed to git.

---

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

### Testing

```bash
just test-regression  # Golden path (< 2 min) - run before commits
just test             # All E2E tests (< 3 min) - run before PRs
just tdd <path>       # Single test during development
```

See `tests/AGENTS.md` for test structure and patterns.

---

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

---

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

---

## Rules

1. **Run in containers** - Not on host
2. **Review auto-fixes after commit** - Pre-commit auto-fixes lint/format
3. **Use `/merge` when done** - Single command: pre-merge checks → PR → auto-merge
4. **Follow existing patterns** - Check skills for examples
5. **Test against real services** - No mocking internal systems
6. **Commit working code** - Don't commit if tests fail
7. **Use provided tooling for infrastructure** - See below
8. **Respect dependency rules** - Webapp never imports from sources

### Infrastructure Management Policy

**Use `worktree.py` and `just` commands. Never run ad-hoc Docker/uv commands.**

| Need | Use This | NOT This |
|------|----------|----------|
| Start services | `just up-d` | `docker compose up -d` |
| Stop services | `just down` | `docker compose down` |
| Sync dependencies | `just uv-sync` | `uv sync` directly |
| Fix issues | `./worktree.py setup <name>` | Ad-hoc docker commands |
| Clean up | `./worktree.py teardown` | `docker volume rm` |
| Reset data | Ask user to run `just reset` | `docker compose down -v` |
| Build Astro | `just build-astro` | `cd frontend/astro && pnpm build` |
| Watch Astro | `just watch-astro` | `cd frontend/astro && pnpm dev` |
| Check Astro | `just check-astro` | `cd frontend/astro && pnpm lint` |
| Verify sync | `just verify-astro-sync` | Manual git diff |

**Why?** The provided tooling has guardrails. Ad-hoc commands don't.

**If tooling is missing:**
1. Ask if the user wants to add it to `worktree.py` or `justfile`
2. Or ask the user to run the raw command manually
3. Do NOT run ad-hoc infrastructure commands yourself

**Destructive commands are blocked** by `.claude/hooks/block-volume-deletion.sh`. Even if you try to run `docker volume rm` or `down -v`, it will be blocked.

See `.claude/rules/infrastructure-protection.md` for details.

---

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

---

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

---

## Git

```bash
# Never commit to main directly
# Always work in feature branches via worktrees

# Before PR
just check
git push
```

For workflow (issue tracking, worktree setup, planning): `./worktree.py start`

---

## GitHub-First Workflow

**GitHub issues are the source of truth.** All work must trace back to a GitHub issue.

### Flow

```
GitHub Issue (source of truth)
    ↓
Worktree (created from GH issue number)
```

### Rules

1. **Create GH issue first** - Before any work, ensure a GitHub issue exists
2. **Setup from GH issue number** - `./worktree.py setup 42`
3. **Use GitHub dependencies** - Use `is:blocked` / `is:blocking` for dependencies

### Commands

```bash
# Setup worktree from GitHub issue
./worktree.py setup 413

# Find available work (unblocked issues)
/next-issue

# View issue dependencies
/issue-deps 413
```

---

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
To execute: /ralph-hybrid-plan XXX (in fresh session)
```

---

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

**Note:** Worktree cleanup is automatic. After PR merge, hooks handle teardown.

**CRITICAL RULES:**
- Work is NOT complete until `git push` succeeds
- NEVER stop before pushing - that leaves work stranded locally
- NEVER say "ready to push when you are" - YOU must push
- If push fails, resolve and retry until it succeeds

---

## Workflow Loops

Development follows two loops:

| Loop | Tool | Scope |
|------|------|-------|
| **Outer** | GitHub Issues | Planning, epics, dependencies |
| **Inner** | Ralph Hybrid | Story execution, TDD |

**Outer loop** (planning): `/next-issue`, `/plan`, `gh-workflow` skill
**Inner loop** (execution): `/ralph-hybrid-plan`, `ralph-hybrid run`

For conceptual overview, see [Workflow Loops](https://github.com/krazyuniks/guitar-tone-shootout/wiki/Workflow-Loops) in the wiki.
For Ralph Hybrid details, see [Ralph Hybrid](https://github.com/krazyuniks/ralph-hybrid).

---

## Ralph Hybrid (Autonomous Development)

For complex features, use Ralph Hybrid to run autonomous development loops.

### Workflow

```
1. Plan:  /ralph-hybrid-plan "description"   (in Claude Code)
2. Run:   ralph-hybrid run                    (in terminal)
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
| `ralph-hybrid run --monitor` | Terminal | Run with tmux dashboard |
| `ralph-hybrid status` | Terminal | Show feature progress |

### Example: GitHub Issue to Implementation

```bash
# 1. Create branch from issue number
git checkout -b 42-user-authentication

# 2. Plan (Claude auto-fetches issue #42 context)
/ralph-hybrid-plan

# 3. Run autonomous loop
ralph-hybrid run --monitor
```

### Key Concepts

- **Fresh context per iteration**: Each loop iteration starts Claude fresh
- **Memory in files**: prd.json tracks story completion, progress.txt logs history
- **Branch = feature folder**: `.ralph-hybrid/{branch-name}/` holds all state

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

GTS-specific skills for specialised tasks. Also uses global skills:

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
