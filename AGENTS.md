# Guitar Tone Shootout - Development Operations Guide

**Version:** 2.1 | **Last Updated:** 2025-12-27

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

# GitHub Workflow (ALWAYS use --repo flag)
gh issue list --repo krazyuniks/guitar-tone-shootout
gh issue view 6 --repo krazyuniks/guitar-tone-shootout
gh pr list --repo krazyuniks/guitar-tone-shootout
```

**IMPORTANT:** Always use `--repo krazyuniks/guitar-tone-shootout` with `gh` commands. The SSH alias `github_osx` prevents `gh` from auto-detecting the repository owner.

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

### NEVER Use Git Stash

**CRITICAL: Do NOT use `git stash` for any reason.**

- Stashing causes merge conflicts when resuming work
- If work is incomplete, either:
  - Commit it as a WIP checkpoint (`git commit -m "WIP: description"`)
  - Or discard uncommitted changes and document what was done in session-state.md
- The next session starts fresh from the last commit

### One Issue Per Session

**After a PR is merged:**
1. Sync with main: `git checkout main && git pull --ff-only`
2. Delete the feature branch
3. Update `dev/session-state.md` with progress
4. Commit and push the session-state update
5. **STOP** - Provide resume commands for the next session
6. Do NOT start the next issue in the same session (context degrades)

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

## Git Worktree Development

This project uses git worktrees for isolated parallel development. Each worktree has its own Docker environment with unique ports.

### Structure (After Migration)

Everything is contained in a SINGLE directory:

```
/Users/ryanlauterbach/Work/guitar-tone-shootout-worktrees/
├── guitar-tone-shootout.git/       # Bare repository (INSIDE worktrees folder)
├── .worktree/
│   └── registry.db                 # SQLite registry (ports, volumes)
├── seed.sql                        # Shared database seed
├── main/                           # Main worktree (offset 0)
│   ├── worktree.py → worktree/worktree.py
│   ├── worktree/                   # Worktree management package
│   └── ...
└── 42-feature-audio/               # Feature worktree (offset 1)
```

### Port Allocation

| Service | Main (offset 0) | Feature (offset N) |
|---------|-----------------|-------------------|
| Frontend | 4321 | 4321 + (N × 10) |
| Backend | 8000 | 8000 + (N × 10) |
| Database | 5432 | 5432 + N |
| Redis | 6379 | 6379 + N |

### Volume Strategy

- **Isolated per worktree**: PostgreSQL, Redis, uploads
- **Shared read-only**: Model cache (`gts-model-cache`)

### Initial Setup (One-time)

After cloning or migrating to bare repo structure:

```bash
# Install worktree CLI dependencies (on host, not in Docker)
pip install -e /Users/ryanlauterbach/Work/guitar-tone-shootout-worktrees/main/worktree/

# Register the main worktree
cd /Users/ryanlauterbach/Work/guitar-tone-shootout-worktrees/main
./worktree.py setup main

# Verify
./worktree.py list
```

### Worktree Commands

```bash
# Create new worktree from issue
./worktree.py setup 42

# Create with explicit branch name
./worktree.py setup 42/feature-audio-analysis

# Register existing main worktree
./worktree.py setup main

# List all worktrees with status
./worktree.py list

# Check current worktree health
./worktree.py health

# Show detailed status
./worktree.py status

# Teardown worktree (after PR merged)
./worktree.py teardown 42-feature-audio

# Other utilities
./worktree.py ports      # Show port allocations
./worktree.py prune      # Remove stale entries
./worktree.py start      # Start Docker services
./worktree.py stop       # Stop Docker services
./worktree.py seed       # Re-run database seeding
```

### Worktree Workflow

**Phase 0: Create Worktree**
```bash
cd /path/to/main
./worktree.py setup 42
cd ../42-feature-audio
./worktree.py health
```

**During Development**
- Each worktree is completely isolated
- Use `./worktree.py health` to verify services
- Access frontend at `http://localhost:<frontend-port>`

**After PR Merged**
```bash
./worktree.py teardown 42-feature-audio
# Cleans up: containers, volumes, git worktree, branches
```

### Claude Slash Commands

| Command | Description |
|---------|-------------|
| `/worktree-setup <issue>` | Create new worktree |
| `/worktree-teardown <name>` | Remove worktree and cleanup |
| `/worktree-list` | List all worktrees |
| `/worktree-health` | Check current worktree health |

---

## Parallel Agent Task Planning

When planning epic implementation, **explicitly identify parallel vs serial task blocks**. This enables efficient execution with multiple AI agents working simultaneously.

### Task Block Types

**Serial Block** (must run sequentially):
- Tasks with dependencies on previous task outputs
- Database migrations before queries
- File creation before file editing
- API design before implementation

**Parallel Block** (can run simultaneously):
- Independent feature implementations
- Tests for different modules
- Documentation for separate components
- Frontend and backend work on different endpoints

### Planning Format

When creating execution plans, use this format:

```markdown
## Epic: User Authentication

### Serial Block 1: Database Setup
1. Create User model and migration
2. Run migration
3. Create seed data

### Parallel Block 1: Core Features (3 agents)
- [ ] Agent A: Implement login endpoint
- [ ] Agent B: Implement logout endpoint
- [ ] Agent C: Implement token refresh endpoint

### Serial Block 2: Integration
1. Connect frontend to auth endpoints
2. Add auth middleware to protected routes

### Parallel Block 2: Polish (2 agents)
- [ ] Agent A: Add error handling and validation
- [ ] Agent B: Write integration tests

### Serial Block 3: Finalization
1. End-to-end browser testing
2. Documentation update
3. PR creation
```

### Execution Rules

1. **Complete all tasks in a serial block** before moving to the next block
2. **Launch parallel agents simultaneously** using multiple `Task` tool calls in a single message
3. **Wait for all parallel agents** to complete before the next serial block
4. **Each parallel agent gets its own worktree** for isolation

### Agent Assignment

For parallel blocks with worktrees:

```bash
# Terminal 1 (Agent A)
cd ../42-feature-login
# Work on login endpoint

# Terminal 2 (Agent B)
cd ../43-feature-logout
# Work on logout endpoint

# Terminal 3 (Agent C)
cd ../44-feature-refresh
# Work on refresh endpoint
```

### Identifying Parallelizable Tasks

Ask these questions:
1. Does this task depend on output from another task? → **Serial**
2. Does this task modify the same files as another? → **Serial**
3. Does this task require a database state from another? → **Serial**
4. Can this task run with only the current main branch state? → **Parallel**

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

## Workflow Phases (MANDATORY)

**CRITICAL: This is the ONLY way to develop. No exceptions.**

All development MUST follow this workflow. AI agents are PROHIBITED from:
- Writing code without first creating a GitHub issue
- Working directly on `main` branch
- Skipping worktree setup for any feature/fix
- Executing implementation in the same session as planning
- Making decisions without recording them in GH issue or dev-docs

### Session Discipline

**Planning and execution happen in SEPARATE sessions:**

1. **Planning Session**: Explore, ask questions, create issue, set up worktree, document plan
2. **Execution Session**: Fresh context, implement from documented plan
3. **All outputs recorded**: Every decision, plan, and finding goes in GH issue comments or dev-docs

This separation ensures:
- Fresh context for implementation (no degraded context from long planning)
- Complete documentation trail
- Reproducible work by any agent or human

### Phase 0: GitHub Issue Creation

Every feature, bug fix, or task starts with a GitHub issue. **No issue = No work.**

```bash
gh issue create --repo krazyuniks/guitar-tone-shootout \
  --title "feat: description" \
  --milestone "v2.0 - Web Application Foundation" \
  --label "epic:foundation" \
  --body "$(cat <<'EOF'
## Summary
Brief description of what needs to be done.

## Approach
High-level implementation approach.

## Files to Modify
- file1.py
- file2.ts

## Acceptance Criteria
- [ ] Criterion 1
- [ ] Criterion 2
EOF
)"
```

**Issue Title Conventions:**
- `feat:` - New feature
- `fix:` - Bug fix
- `refactor:` - Code refactoring
- `docs:` - Documentation
- `test:` - Test additions/fixes
- `chore:` - Maintenance tasks

**Record all planning decisions in the issue body or comments.**

### Phase 1: Worktree Setup

**ALWAYS use worktrees. Never work on main.**

```bash
# From main worktree
cd /Users/ryanlauterbach/Work/guitar-tone-shootout-worktrees/main

# Create worktree for issue (creates branch automatically)
./worktree.py setup <issue-number>

# Move to new worktree
cd ../<issue-number>-<description>

# Verify health
./worktree.py health
```

This creates:
- Isolated git worktree with dedicated branch
- Unique Docker ports (no conflicts with other worktrees)
- Isolated database and Redis volumes
- Fresh Docker environment

### Phase 2: Dev-Docs Setup

Create documentation BEFORE writing code:

```bash
mkdir -p dev/active/<task-name>
```

Create `dev/active/<task-name>/plan.md`:
```markdown
# Plan: <Task Name>

**Issue:** #<number>
**Created:** <date>
**Status:** Ready to implement

## Summary
What we're building and why.

## Implementation Steps
1. Step one
2. Step two
3. Step three

## Files to Modify
- path/to/file1.py
- path/to/file2.ts

## Testing Strategy
How we'll verify this works.
```

### Phase 3: End Planning Session

**STOP HERE. Do not implement in the same session.**

1. Commit dev-docs:
   ```bash
   git add dev/active/<task-name>/
   git commit -m "docs: planning for #<issue-number>"
   git push -u origin <branch-name>
   ```

2. Update session-state.md with task reference

3. Provide resume command for execution session:
   ```bash
   cd /path/to/worktree && claude
   # Then: "Implement #<issue-number> - see dev/active/<task-name>/plan.md"
   ```

### Phase 4: Implementation (NEW SESSION)

Start fresh session, read the plan, implement:

```bash
# Read context first
cat dev/active/<task-name>/plan.md
gh issue view <issue-number>

# Implement following the plan
# Run quality gates frequently
just check
```

### Phase 5: Quality Gates

All must pass before PR:

| Check | Command | What it does |
|-------|---------|--------------|
| Backend Lint | `docker compose exec backend ruff check` | Python linting |
| Backend Types | `docker compose exec backend mypy` | Type checking |
| Backend Tests | `docker compose exec backend pytest` | Unit/integration tests |
| Frontend Lint | `docker compose exec frontend pnpm lint` | TypeScript/Astro linting |
| Frontend Build | `docker compose exec frontend pnpm build` | Verify build succeeds |
| **Browser Test** | Chrome DevTools MCP or Playwright | **MANDATORY end-to-end test** |

### Phase 5.5: Browser Testing (MANDATORY)

**CRITICAL: No feature is complete without FULL end-to-end browser testing with screenshot proof.**

This is **non-negotiable**. Unit tests passing does NOT mean the feature works.

#### Required Browser Testing Steps

For **EVERY** feature that has UI or API endpoints:

1. **Start Docker services and verify healthy:**
   ```bash
   docker compose up -d
   docker compose ps  # All services must be healthy
   ```

2. **Navigate to the feature in the browser:**
   ```
   - Use mcp__playwright__browser_navigate or mcp__chrome-devtools__navigate_page
   - Take a snapshot of the initial state
   ```

3. **Execute the FULL user flow:**
   ```
   - Click buttons, fill forms, trigger actions
   - Take snapshots at EACH step
   - Verify the UI updates correctly
   ```

4. **Check for errors:**
   ```
   - Run mcp__playwright__browser_console_messages with level="error"
   - Run mcp__playwright__browser_network_requests to verify API calls succeed
   - ANY console error or failed network request = feature is NOT complete
   ```

5. **Take a FINAL screenshot as proof:**
   ```
   - Use mcp__playwright__browser_take_screenshot
   - This screenshot is REQUIRED before claiming completion
   ```

#### AI Agent Rules (STRICTLY ENFORCED)

You are **PROHIBITED** from:
- Saying "feature complete" without browser testing
- Saying "PR is ready" without screenshot proof
- Claiming "all tests pass" if you only ran unit tests
- Marking a TodoWrite item as "completed" without browser verification
- Assuming code changes work without testing them in the browser

**If you violate these rules, you are producing broken software.**

#### MCP Tools for Browser Testing

| Tool | Purpose |
|------|---------|
| `mcp__playwright__browser_navigate` | Go to a URL |
| `mcp__playwright__browser_snapshot` | Capture page accessibility tree |
| `mcp__playwright__browser_take_screenshot` | Take visual screenshot (REQUIRED for proof) |
| `mcp__playwright__browser_click` | Click elements |
| `mcp__playwright__browser_type` | Type into inputs |
| `mcp__playwright__browser_console_messages` | Check for JS errors |
| `mcp__playwright__browser_network_requests` | Check API calls |

#### Example Browser Test Checklist

```markdown
## Browser Test Results for [Feature Name]

### Environment
- [ ] Docker services running and healthy
- [ ] Backend accessible at localhost:8000
- [ ] Frontend accessible at localhost:4321

### User Flow Tested
- [ ] Step 1: [Description] - Screenshot attached
- [ ] Step 2: [Description] - Screenshot attached
- [ ] Final state verified - Screenshot attached

### Error Checks
- [ ] No console errors (verified with browser_console_messages)
- [ ] All network requests succeeded (verified with browser_network_requests)

### Screenshot Proof
[Attach final screenshot here]
```

### Phase 6: Pull Request

```bash
git push -u origin $(git branch --show-current)

gh pr create --repo krazyuniks/guitar-tone-shootout \
  --title "feat: Docker Compose dev environment" --body "$(cat <<'EOF'
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

**IMPORTANT:** After creating the PR, **STOP and wait for user review**. Do not proceed to Phase 7 until the PR is approved and merged on GitHub.

### Phase 7: Merge and Worktree Teardown

**Merging happens on GitHub, not locally.** The repo is configured for:
- **Squash merge only** - All PR commits are squashed into one
- **Linear history required** - No merge commits allowed
- **Auto-delete branches** - Feature branches deleted after merge

```bash
# User merges PR on GitHub web UI (github.com)
# Then teardown the worktree:

cd /Users/ryanlauterbach/Work/guitar-tone-shootout-worktrees/main
./worktree.py teardown <issue-number>-<description>

# This automatically:
# - Stops Docker containers
# - Removes Docker volumes
# - Deletes the worktree directory
# - Deletes local and remote branches
# - Archives dev-docs to dev/archive/
```

After teardown, sync main:
```bash
git pull --ff-only origin main
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
| 2.1 | 2025-12-27 | Mandatory worktree workflow, session discipline, planning/execution separation |
| 2.0 | 2025-12-26 | Web application pivot, Docker-based workflow |
| 1.0 | 2025-12-25 | Initial CLI-focused workflow |
