# Guitar Tone Shootout - Development Operations Guide

**Version:** 2.0 | **Last Updated:** 2025-12-26

This document defines the development workflow, patterns, and automation for the Guitar Tone Shootout project. It serves as the primary reference for both human developers and AI agents.

---

## Quick Reference

```bash
# Development (Docker-based)
docker compose up                    # Start all services with hot-reload
docker compose logs -f backend       # View backend logs
docker compose exec backend bash     # Shell into backend container

# Quality Gates (run from host)
just check-backend                    # ruff, mypy, pytest in backend container
just check-frontend                   # pnpm lint, build in frontend container
just check                            # Run all checks

# Database
docker compose exec backend alembic upgrade head    # Run migrations
docker compose exec backend alembic revision -m "description"  # Create migration

# GitHub Workflow
gh issue list --milestone "v2.0 - Web Application Foundation"
gh issue view 6
```

---

## Dependency Version Policy

**Always use the latest stable/mainline versions** of all dependencies:

| Category | Policy |
|----------|--------|
| Python | Latest stable (currently 3.14) |
| Node.js | Latest LTS or current stable |
| npm packages | Latest stable versions |
| Astro, React, Tailwind | Latest stable versions |
| PostgreSQL, Redis | Latest stable Alpine images |
| nginx | Latest stable for reverse proxy |
| Docker base images | Latest stable slim/alpine variants |

**Downgrade only when:**
- Integration problems occur between dependencies
- Stability issues are encountered in production
- Security vulnerabilities require a specific version

**Update strategy:**
- Check for updates when starting new features
- Document any pinned versions and reasons in comments
- Prefer `>=` version constraints over exact pins

---

## Session Checkpoint Rules

**CRITICAL: These rules prevent context loss across Claude Code sessions.**

### Before Ending a Session

1. **Update dev-docs** with current progress:
   ```bash
   # Update session-state.md with current status
   # Update active task context.md with decisions/progress
   ```

2. **Commit and push** all changes:
   ```bash
   git add -A
   git commit -m "checkpoint: description of current state"
   git push
   ```

3. **Never** tell user to start new session without saving state first

### Pre-commit Hook Enforcement

A pre-commit hook validates:
- `dev/session-state.md` exists and is not empty
- Active GitHub issues have corresponding `dev/active/` documentation
- Architecture decisions are documented in `dev/EXECUTION-PLAN.md`

### Resuming Work

1. Read `dev/session-state.md` first
2. Check `dev/EXECUTION-PLAN.md` for architecture context
3. Read active task docs in `dev/active/[task]/`
4. Continue from documented "Next Action"

---

## Project Structure

```
guitar-tone-shootout/
├── backend/                    # FastAPI application
│   ├── app/
│   │   ├── api/               # REST endpoints (auth, shootouts, jobs, ws)
│   │   ├── core/              # Config, security, Tone 3000 client
│   │   ├── models/            # SQLAlchemy models
│   │   ├── schemas/           # Pydantic schemas
│   │   └── tasks/             # TaskIQ background jobs
│   ├── alembic/               # Database migrations
│   ├── Dockerfile.dev         # Development container
│   ├── Dockerfile             # Production container
│   └── pyproject.toml
├── frontend/                   # Astro + React application
│   ├── src/
│   │   ├── pages/             # Astro pages
│   │   ├── components/        # React components (islands)
│   │   └── layouts/
│   ├── Dockerfile.dev
│   ├── Dockerfile
│   └── package.json
├── pipeline/                   # Audio/video processing (preserved)
│   ├── src/guitar_tone_shootout/
│   └── tests/
├── dev/                        # Development documentation
│   ├── README.md              # Dev-docs pattern guide
│   ├── session-state.md       # Current work tracking (SOURCE OF TRUTH)
│   ├── EXECUTION-PLAN.md      # Architecture and epic tracking
│   ├── active/                # Active task documentation
│   └── archive/               # Completed task documentation
├── docker-compose.yml          # Development environment
├── docker-compose.prod.yml     # Production environment
├── .env.example                # Environment template
├── AGENTS.md                   # This file
└── CLAUDE.md                   # Pointer to AGENTS.md
```

**Note:** The `web/` directory (Flask + HTMX) is deprecated and will be removed after `frontend/` is complete.

---

## Workflow Phases

### Phase 0: Issue Creation

Every feature, bug fix, or task starts with a GitHub issue.

```bash
gh issue create --title "feat: description" \
  --milestone "v2.0 - Web Application Foundation" \
  --label "epic:foundation"
```

**Issue Title Conventions:**
- `feat:` - New feature
- `fix:` - Bug fix
- `refactor:` - Code refactoring
- `docs:` - Documentation
- `test:` - Test additions/fixes
- `chore:` - Maintenance tasks

### Phase 1: Branch Creation

```bash
git checkout main
git pull origin main
git checkout -b 6-docker-compose-dev
```

**Branch Naming:** `<issue-number>-<short-description>`

### Phase 2: Development

1. **Create dev-docs** for complex tasks:
   ```bash
   mkdir -p dev/active/docker-compose-dev
   # Create plan.md, context.md, tasks.md
   ```

2. **Update session-state.md** with task mapping

3. **Implement** following patterns in this document

4. **Run quality gates** frequently:
   ```bash
   just check                    # Run all checks from host
   ```

### Phase 3: Quality Gates

All must pass before PR:

| Check | Command | What it does |
|-------|---------|--------------|
| Backend Lint | `docker compose exec backend ruff check` | Python linting |
| Backend Types | `docker compose exec backend mypy` | Type checking |
| Backend Tests | `docker compose exec backend pytest` | Unit/integration tests |
| Frontend Lint | `docker compose exec frontend pnpm lint` | TypeScript/Astro linting |
| Frontend Build | `docker compose exec frontend pnpm build` | Verify build succeeds |

### Phase 4: Pull Request

```bash
git push -u origin $(git branch --show-current)

gh pr create --title "feat: Docker Compose dev environment" --body "$(cat <<'EOF'
## Summary
- Added Docker Compose for development with hot-reload
- PostgreSQL, Redis, backend, frontend, worker services

## Changes
- docker-compose.yml
- backend/Dockerfile.dev
- frontend/Dockerfile.dev

## Related Issues
Closes #6

## Test Plan
- [ ] `docker compose up` starts all services
- [ ] Backend hot-reload works
- [ ] Frontend hot-reload works

---
Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

**IMPORTANT:** After creating the PR, **STOP and wait for user review**. Do not proceed to Phase 5 until the PR is approved and merged on GitHub.

### Phase 5: Merge (on GitHub) and Sync Local

**Merging happens on GitHub, not locally.** The repo is configured for:
- **Squash merge only** - All PR commits are squashed into one
- **Linear history required** - No merge commits allowed
- **Auto-delete branches** - Feature branches deleted after merge

```bash
# User merges PR on GitHub web UI (github.com)
# Then sync locally:

git checkout main
git pull --ff-only origin main   # Will fail if history diverged
git branch -d 6-docker-compose-dev  # Delete local branch (remote already deleted)

# Archive dev-docs if any
mv dev/active/docker-compose-dev dev/archive/ 2>/dev/null || true
# Update session-state.md
```

**If `git pull --ff-only` fails:** The local branch has diverged. Reset to remote:
```bash
git fetch origin
git reset --hard origin/main
```

---

## Git & GitHub Configuration

### Repository Settings (GitHub)

The repository is configured with these merge settings:
- **Squash merge:** Enabled (only option)
- **Merge commits:** Disabled
- **Rebase merge:** Disabled
- **Auto-delete head branches:** Enabled

### Branch Protection (main)

The `main` branch has these protections:
- **Required linear history:** Yes (no merge commits)
- **Allow force pushes:** No
- **Allow deletions:** No

### Local Git Configuration

Configure your local repo for fast-forward only:
```bash
git config --local pull.ff only
git config --local merge.ff only
```

### Workflow Rules

1. **Never commit directly to main** - Always use feature branches
2. **Never merge locally** - All merges happen via GitHub PR squash merge
3. **Always sync with ff-only** - Ensures local matches remote exactly
4. **One PR per issue** - Branch naming: `<issue-number>-<short-description>`

### AI Agent Instructions

**Claude Code must:**
- Create feature branches for all work
- Push branches and create PRs via `gh pr create`
- **STOP after creating PR** - Do not suggest next steps until user confirms merge
- After user confirms merge, sync local with `git pull --ff-only`
- Never use `gh pr merge` - user merges on GitHub

---

## Code Patterns

### Python Style (Backend)

```python
# Type hints required on all functions
from typing import Annotated
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

async def get_shootout(
    shootout_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Shootout:
    """Retrieve a shootout by ID.

    Args:
        shootout_id: The shootout's database ID
        db: Database session
        current_user: Authenticated user

    Returns:
        The shootout if found and owned by user

    Raises:
        HTTPException: If not found or not authorized
    """
    ...
```

**Rules:**
- Type hints on all functions
- Docstrings for public functions
- Use `logging` module (not `print()`)
- `pathlib.Path` over string paths
- Async/await for all database operations
- Pydantic for request/response schemas

### TypeScript Style (Frontend)

```typescript
// Type definitions required
interface ToneModel {
  id: number;
  title: string;
  gear: 'amp' | 'pedal' | 'ir';
  platform: 'nam' | 'ir' | 'aida-x';
}

// React component with props typing
interface PipelineBuilderProps {
  userId: number;
  onSubmit: (shootout: ShootoutConfig) => void;
}

export function PipelineBuilder({ userId, onSubmit }: PipelineBuilderProps) {
  // ...
}
```

### Error Handling

```python
# Custom exceptions
class ShootoutError(Exception):
    """Base exception for shootout errors."""

class Tone3000Error(ShootoutError):
    """Tone 3000 API error."""

class PipelineError(ShootoutError):
    """Pipeline processing error."""

# HTTP exception handling in FastAPI
from fastapi import HTTPException, status

async def get_shootout(shootout_id: int) -> Shootout:
    shootout = await db.get(Shootout, shootout_id)
    if not shootout:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Shootout {shootout_id} not found"
        )
    return shootout
```

---

## Docker Development

### Services

| Service | Port | Purpose |
|---------|------|---------|
| backend | 8000 | FastAPI with uvicorn --reload |
| frontend | 4321 | Astro dev server |
| worker | - | TaskIQ workers |
| db | 5432 | PostgreSQL |
| redis | 6379 | Redis (queue + cache) |

### Common Commands

```bash
# Start all services
docker compose up

# Rebuild after dependency changes
docker compose build backend
docker compose up

# Shell into container
docker compose exec backend bash
docker compose exec frontend sh

# Run one-off commands
docker compose exec backend alembic upgrade head
docker compose exec backend pytest tests/

# View logs
docker compose logs -f backend worker

# Reset database
docker compose down -v  # Removes volumes
docker compose up
```

### Volume Mounts

Development containers mount source code for hot-reload:
- `./backend:/app` - Backend source
- `./frontend:/app` - Frontend source
- `./pipeline:/pipeline` - Pipeline library (read-only in workers)

---

## Database Patterns

### Models (SQLAlchemy 2.0)

```python
from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    tone3000_id: Mapped[int] = mapped_column(unique=True, index=True)
    username: Mapped[str] = mapped_column(String(100))

    shootouts: Mapped[list["Shootout"]] = relationship(back_populates="user")

class Shootout(Base):
    __tablename__ = "shootouts"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(200))

    user: Mapped["User"] = relationship(back_populates="shootouts")
```

### Migrations

```bash
# Create migration
docker compose exec backend alembic revision --autogenerate -m "add shootouts table"

# Apply migrations
docker compose exec backend alembic upgrade head

# Rollback one
docker compose exec backend alembic downgrade -1
```

---

## Tone 3000 Integration

### OAuth Flow

```
1. User clicks Login → Redirect to tone3000.com/api/v1/auth
2. User authenticates on Tone 3000
3. Redirect back to /auth/callback?api_key=xxx
4. Exchange api_key for JWT tokens
5. Store tokens, create local user session
```

### API Client Pattern

```python
from httpx import AsyncClient

class Tone3000Client:
    def __init__(self, access_token: str):
        self.access_token = access_token
        self.base_url = "https://www.tone3000.com/api/v1"

    async def get_user_tones(self) -> list[Tone]:
        async with AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/tones/created",
                headers={"Authorization": f"Bearer {self.access_token}"}
            )
            response.raise_for_status()
            return [Tone(**t) for t in response.json()["data"]]
```

---

## Job Queue Patterns

### Task Definition

```python
from taskiq import TaskiqScheduler
from taskiq_redis import ListQueueBroker, RedisAsyncResultBackend

broker = ListQueueBroker(url="redis://redis:6379")
broker.with_result_backend(RedisAsyncResultBackend(redis_url="redis://redis:6379"))

@broker.task
async def process_shootout(job_id: str, shootout_id: int) -> str:
    """Process a shootout through the pipeline."""
    await update_job_status(job_id, "running", progress=0)

    # Download models, process audio, generate video...
    await update_job_status(job_id, "running", progress=50)

    # Complete
    await update_job_status(job_id, "completed", progress=100)
    return output_path
```

### WebSocket Progress

```python
@router.websocket("/ws/jobs/{job_id}")
async def job_progress(websocket: WebSocket, job_id: str):
    await websocket.accept()
    async for update in subscribe_job_updates(job_id):
        await websocket.send_json({
            "status": update.status,
            "progress": update.progress,
            "message": update.message
        })
```

---

## Claude Code Integration

### Autonomous Execution

Pre-approved commands (no confirmation needed):

```bash
# Docker operations
docker compose up
docker compose logs
docker compose exec backend pytest
docker compose exec frontend pnpm build

# Git (read-only)
git status
git log
git diff

# GitHub CLI (read-only)
gh issue list
gh pr list
gh issue view
```

### Dev-Docs Commands

```bash
# Check session state
cat dev/session-state.md

# Check execution plan
cat dev/EXECUTION-PLAN.md

# View active task
cat dev/active/[task-name]/[task-name]-context.md
```

---

## Troubleshooting

### Docker Issues

**Container won't start:**
```bash
docker compose logs [service]  # Check error logs
docker compose down -v         # Reset volumes
docker compose build --no-cache [service]  # Rebuild
```

**Hot-reload not working:**
- Check volume mounts in docker-compose.yml
- Verify file permissions
- Restart the specific service: `docker compose restart backend`

### Database Issues

**Migration conflicts:**
```bash
docker compose exec backend alembic history  # View history
docker compose exec backend alembic current  # Current state
docker compose exec backend alembic downgrade base  # Reset
docker compose exec backend alembic upgrade head    # Reapply
```

### Tone 3000 API

**Auth failures:**
- Check TONE3000_CLIENT_ID and TONE3000_CLIENT_SECRET in .env
- Verify redirect URL matches registered callback
- Check token expiry and refresh logic

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 2.0 | 2025-12-26 | Web application pivot, Docker-based workflow |
| 1.0 | 2025-12-25 | Initial CLI-focused workflow |
