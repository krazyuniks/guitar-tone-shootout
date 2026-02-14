# Guitar Tone Shootout - Agent Guide

> For stack details, project structure, and development setup, see [DEVELOPMENT.md](./DEVELOPMENT.md).
> For testing workflow, see `.claude/rules/testing-policy.md`.
> For epic workflow, see `.claude/rules/epic-workflow.md`.

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

## Stack

FastAPI + SQLAlchemy 2.0 + PostgreSQL | Astro SSG + Jinja2 SSR + HTMX + Alpine.js | Docker. See [DEVELOPMENT.md](./DEVELOPMENT.md).

## Dependency Rules

| Module | Can depend on | Cannot depend on |
|--------|---------------|------------------|
| `core` | (none) | audio, video, sources, apps |
| `audio` | core | video, sources, apps |
| `video` | core, audio | sources, apps |
| `source_*` | core | audio, video, other sources, apps |
| `webapp` | core, audio, video | sources |
| `worker` | core, audio, video | sources |
| `scheduler` | core | audio, video, sources |

**Critical**: Webapp has NO dependency on sources. Worker bridges gts_core and gts_t3k_source databases.

**Enforcement**: `import-linter` contracts in root `pyproject.toml`.

## Git & GitHub

Never commit to main directly. Feature branches from GitHub issues. Run `just check` before PR.

**GitHub issues are the source of truth.** All work traces back to a GitHub issue.

## Session Context Management

**Separate exploration from execution.** Research sessions should NOT be used for implementation.

1. **Exploration sessions** -- research, planning, epic creation, codebase analysis
2. **Execution sessions** -- implementation with fresh context
3. **Never mix** -- if you've done significant exploration, hand off to fresh session

## Landing the Plane (Session Completion)

**Work is NOT complete until `git push` succeeds.**

1. **File issues for remaining work**
2. **Run quality gates** (if code changed)
3. **Update issue status**
4. **PUSH TO REMOTE** -- MANDATORY:
   ```bash
   git pull --rebase
   git push
   git status  # MUST show "up to date with origin"
   ```
5. **Verify** -- all changes committed AND pushed
6. **Hand off** -- provide context for next session

**NEVER stop before pushing.** NEVER say "ready to push when you are" -- YOU must push.
