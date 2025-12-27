# Development Guide

Technical documentation for developing and deploying Guitar Tone Shootout.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     FRONTEND (Astro + React)                    │
│  Landing (Static) │ Dashboard │ Pipeline Builder (React Island) │
└────────────────────────────┬────────────────────────────────────┘
                             │ REST API + WebSocket
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      BACKEND (FastAPI)                          │
│   Auth (Tone 3000 OAuth) │ API │ WebSocket │ Background Jobs    │
└────────────────────────────┬────────────────────────────────────┘
                             │
         ┌───────────────────┼───────────────────┐
         ▼                   ▼                   ▼
┌─────────────────┐  ┌───────────────┐  ┌────────────────────┐
│   PostgreSQL    │  │  Tone 3000    │  │   Pipeline         │
│   + Redis       │  │  API          │  │   (Audio/Video)    │
└─────────────────┘  └───────────────┘  └────────────────────┘
```

## Technology Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| Frontend | Astro + React | Static SEO pages + interactive islands |
| Data Fetching | TanStack Query | Server state management |
| Forms | TanStack Form | Type-safe form handling |
| Tables | TanStack Table | Data grid components |
| Styling | Tailwind CSS | Utility-first CSS |
| Backend | FastAPI | REST API, WebSocket, OAuth |
| Database | PostgreSQL | User data, shootouts, jobs |
| ORM | SQLAlchemy 2.0 | Async database operations |
| Cache/Queue | Redis | Job queue, real-time pub/sub |
| Task Queue | TaskIQ | Async pipeline processing |
| Auth | Tone 3000 OAuth | User authentication |
| Audio | NAM + Pedalboard | Amp modeling, effects |
| Video | FFmpeg + Playwright | Video generation |

## Project Structure

```
guitar-tone-shootout/
├── backend/                    # FastAPI application
│   ├── app/
│   │   ├── api/               # REST endpoints
│   │   │   ├── auth.py        # Tone 3000 OAuth
│   │   │   ├── shootouts.py   # CRUD operations
│   │   │   ├── jobs.py        # Processing jobs
│   │   │   └── ws.py          # WebSocket handlers
│   │   ├── core/              # Configuration & shared
│   │   │   ├── config.py      # Settings
│   │   │   ├── database.py    # SQLAlchemy setup
│   │   │   ├── security.py    # Token handling
│   │   │   └── tone3000.py    # API client
│   │   ├── models/            # SQLAlchemy models
│   │   ├── schemas/           # Pydantic schemas
│   │   └── tasks/             # TaskIQ background jobs
│   ├── alembic/               # Database migrations
│   ├── tests/
│   ├── Dockerfile.dev
│   ├── Dockerfile
│   └── pyproject.toml
├── frontend/                   # Astro application
│   ├── src/
│   │   ├── pages/             # Astro pages (routing)
│   │   ├── layouts/           # Page layouts
│   │   ├── components/        # React islands
│   │   │   ├── ui/           # Reusable UI
│   │   │   └── features/     # Feature components
│   │   └── lib/              # Utilities, hooks
│   ├── Dockerfile.dev
│   ├── Dockerfile
│   └── package.json
├── pipeline/                   # Audio/video processing
│   ├── src/guitar_tone_shootout/
│   └── tests/
├── dev/                        # Development documentation
│   ├── session-state.md       # Current work tracking
│   ├── EXECUTION-PLAN.md      # Architecture and epics
│   └── active/                # Active task documentation
├── .claude/                    # Claude Code configuration
│   ├── skills/                # Domain knowledge
│   ├── agents/                # Specialized agents
│   ├── commands/              # Slash commands
│   └── hooks/                 # Lifecycle hooks
├── docker-compose.yml          # Development environment
├── docker-compose.prod.yml     # Production environment
├── justfile                    # Task runner
├── AGENTS.md                   # Development workflow
└── README.md                   # User documentation
```

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Git

### Development Setup

```bash
# Clone repository
git clone https://github.com/krazyuniks/guitar-tone-shootout.git
cd guitar-tone-shootout

# Copy environment template
cp .env.example .env
# Edit .env with your Tone 3000 API credentials

# Start all services with hot-reload
docker compose up

# Access the app
# Frontend: http://localhost:4321
# Backend API: http://localhost:8000/docs
```

### Services

| Service | Port | Purpose |
|---------|------|---------|
| frontend | 4321 | Astro dev server |
| backend | 8000 | FastAPI with hot-reload |
| worker | - | TaskIQ background workers |
| db | 5432 | PostgreSQL |
| redis | 6379 | Queue and cache |

## Development Workflow

See [AGENTS.md](AGENTS.md) for the complete development workflow, including:
- Git branching strategy
- PR process
- Quality gates
- Session checkpoints

### Git Worktree Development (Parallel Development)

This project supports git worktrees for isolated parallel development. Each worktree has its own Docker environment with unique ports.

**After bare repo migration (single directory):**
```
/Work/guitar-tone-shootout-worktrees/
├── guitar-tone-shootout.git/     # Bare repository (INSIDE worktrees folder)
├── .worktree/registry.db         # SQLite registry
├── seed.sql                      # Shared database seed
├── main/                         # Main worktree
└── 42-feature-audio/             # Feature worktree
```

**Quick Start:**
```bash
# Create worktree from issue number
./worktree.py setup 42

# Navigate to new worktree
cd ../42-feature-audio

# Check health
./worktree.py health

# After PR merged, teardown
./worktree.py teardown 42-feature-audio
```

**Port Allocation:**
| Service | Main | Feature (offset N) |
|---------|------|-------------------|
| Frontend | 4321 | 4321 + (N × 10) |
| Backend | 8000 | 8000 + (N × 10) |
| Database | 5432 | 5432 + N |
| Redis | 6379 | 6379 + N |

See [AGENTS.md](AGENTS.md#git-worktree-development) for complete worktree documentation.

### Git Rules

**Never use `git stash`**. If you need to switch context or pause work:
1. Commit your changes with a `wip:` prefix: `git commit -m "wip: description"`
2. If unsure what the changes are, run `git status` and `git diff` first
3. Ask for guidance if the changes are unclear

This ensures work is never lost and progress is always visible in the git log.

### Key Commands

```bash
# Start development environment
docker compose up

# Run quality checks
just check                        # All checks
just check-backend               # Backend only
just check-frontend              # Frontend only

# View logs
docker compose logs -f backend worker

# Database migrations
docker compose exec backend alembic upgrade head
docker compose exec backend alembic revision -m "description"

# Shell access
docker compose exec backend bash
docker compose exec frontend sh
```

## Environment Variables

```bash
# .env.example

# Database
DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/shootout

# Redis
REDIS_URL=redis://redis:6379

# Tone 3000 OAuth
TONE3000_CLIENT_ID=your_client_id
TONE3000_CLIENT_SECRET=your_client_secret
TONE3000_REDIRECT_URI=http://localhost:8000/auth/callback

# Frontend
PUBLIC_API_URL=http://localhost:8000
```

## Production Deployment

```bash
# Build production images
docker compose -f docker-compose.prod.yml build

# Deploy
docker compose -f docker-compose.prod.yml up -d

# View logs
docker compose -f docker-compose.prod.yml logs -f
```

### Production Checklist

- [ ] Set secure `SECRET_KEY`
- [ ] Configure HTTPS (reverse proxy)
- [ ] Set proper `CORS_ORIGINS`
- [ ] Configure Tone 3000 production credentials
- [ ] Set up database backups
- [ ] Configure log aggregation

## Frontend Architecture

### Astro + React Islands

Static pages for SEO, React for interactivity:

```astro
---
// Static Astro page
import Layout from '../layouts/Layout.astro';
import PipelineBuilder from '../components/PipelineBuilder';
---

<Layout title="Build Pipeline">
  <!-- React island with hydration -->
  <PipelineBuilder client:load />
</Layout>
```

### TanStack Stack

| Library | Usage |
|---------|-------|
| TanStack Query | API data fetching, caching, mutations |
| TanStack Form | Pipeline builder form with validation |
| TanStack Table | Shootout and job listings |

See `.claude/skills/frontend-dev/SKILL.md` for patterns.

## Backend Architecture

### FastAPI Structure

- **Routes** (`api/`) - Thin handlers, delegate to services
- **Models** (`models/`) - SQLAlchemy 2.0 with `Mapped[]`
- **Schemas** (`schemas/`) - Pydantic v2 for validation
- **Tasks** (`tasks/`) - TaskIQ background jobs

See `.claude/skills/backend-dev/SKILL.md` for patterns.

### Authentication Flow

```
User → Login → Redirect to Tone 3000 → OAuth
                                         ↓
                     Callback with api_key → Exchange for JWT
                                         ↓
                           Store tokens → Create session
```

## Job Processing

### Pipeline Flow

```
1. User submits shootout  →  Job created (PENDING)
2. Job queued to Redis    →  Status: QUEUED  →  WebSocket notify
3. Worker picks up job    →  Status: RUNNING →  WebSocket notify
4. Pipeline processing    →  Progress updates → WebSocket updates
5. Job completes          →  Status: COMPLETED → Download ready
```

### Worker Scaling

```bash
# Scale workers
docker compose up -d --scale worker=4
```

## Testing

```bash
# Backend tests
docker compose exec backend pytest tests/ -v

# With coverage
docker compose exec backend pytest tests/ --cov=app

# Frontend build test
docker compose exec frontend pnpm build

# E2E tests (when implemented)
docker compose exec backend pytest tests/e2e/ -v
```

## Claude Code Integration

This project includes Claude Code customizations in `.claude/`:

### Skills
Domain-specific knowledge for backend, frontend, testing, etc.

### Commands
- `/dev-docs` - Create task documentation
- `/check` - Run quality gates
- `/resume` - Resume from session state

### Agents
- `code-reviewer` - Code quality review
- `error-resolver` - Fix build errors
- `plan-reviewer` - Validate plans

See `.claude/README.md` for details.

## Roadmap

Track progress via [GitHub Milestones](https://github.com/krazyuniks/guitar-tone-shootout/milestones):

- **v2.0** - Web Application Foundation
- **v2.1** - Tone 3000 Integration
- **v2.2** - Job Queue System
- **v2.3** - Frontend
- **v2.4** - Pipeline Web Adapter

## Contributing

1. Create issue describing the change
2. Create feature branch: `git checkout -b 123-feature-name`
3. Follow patterns in AGENTS.md
4. Run quality gates: `just check`
5. Create PR via GitHub

## Resources

- [AGENTS.md](AGENTS.md) - Development workflow
- [dev/EXECUTION-PLAN.md](dev/EXECUTION-PLAN.md) - Architecture decisions
- [.claude/README.md](.claude/README.md) - Claude Code setup
- [Tone 3000 API](https://www.tone3000.com/api) - API documentation
