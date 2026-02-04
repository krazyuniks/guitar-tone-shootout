# Container-First Execution Rules

## Starting Development

```bash
./worktree.py setup main   # First-time: set up main worktree
just up-d                  # Start services (existing worktree)
```

**Idempotent**: `./worktree.py setup` works for any state - fresh checkout, existing worktree, or already running.

**Entry point**: http://localhost:9000 (nginx routes to static files and webapp API)

**Runtime containers**: db, redis, webapp, nginx, worker, scheduler

**Build-only containers**: astro (starts with `--profile build`)

## Critical Rule

**NEVER run development commands directly on the host.** The host may not have the correct versions of Node, Python, or other tools installed (e.g., Volta errors, missing dependencies).

**ALWAYS use Docker containers** for webapp and astro commands. Use `just` commands when available.

## Execution Matrix

| Component | Run Location | Command Pattern |
|-----------|--------------|-----------------|
| **Webapp** (Python) | Docker | `docker compose exec webapp <command>` |
| **Frontend** (Node/pnpm) | Docker (build profile) | `just build-astro` or `docker compose --profile build exec astro <command>` |
| **Pipeline** | Host | `cd pipeline && uv run <command>` |
| **E2E Tests** (Playwright) | Host | `just tdd tests/e2e/python/...` |
| **Git/GitHub** | Host | `git`, `gh` commands |

## Frontend Commands

Frontend container requires `--profile build` since it's not part of the runtime stack.

```bash
# Use just commands (handles profile automatically)
just build-astro     # Build Astro templates
just watch-astro     # Watch and auto-rebuild
just check-astro     # Lint + type check + build
```

## Exceptions (Run on Host)

### Pipeline
The pipeline uses local GPU resources and specialized audio libraries. Run with `uv`:
```bash
cd pipeline && uv run pytest
cd pipeline && uv run ruff check .
cd pipeline && uv run mypy .
```

### Shell Tools
Git, GitHub CLI, and other shell tools run on host:
```bash
git status
gh pr list --repo krazyuniks/guitar-tone-shootout
just <command>
```

## Why This Matters

1. **Consistency** - Docker provides identical environment across all machines
2. **Dependencies** - Container has exact versions of Python, Node, packages
3. **No Volta/nvm Issues** - Host Node version doesn't matter
4. **CI Parity** - Same commands work in CI pipelines

## Frontend Development Workflow

**Pre-bundled architecture**: `astro/dist/` is committed to git. Frontend container is build-only (not in runtime stack).

```bash
# Build astro (starts astro container with --profile build, runs astro build)
just build-astro

# Watch mode (run in separate terminal) - auto-rebuilds on file changes
just watch-astro
```

**How it works:**
1. Edit source files in `astro/src/`
2. Run `just build-astro` (starts astro container via --profile build)
3. Astro outputs to `astro/dist/`
4. Nginx serves static files directly from bind-mounted `astro/dist/`
5. No container restart needed - nginx serves updated files immediately

**Runtime stack does NOT include astro container.** The astro container only starts when you explicitly run build commands.

**When to commit `astro/dist/`:**
- After any astro source changes
- Commit both `astro/src/` and `astro/dist/` together
- CI uses the pre-committed dist (no build step)
