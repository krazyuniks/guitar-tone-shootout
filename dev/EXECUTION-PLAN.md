# Guitar Tone Shootout - Execution Plan

**Created:** 2025-12-26
**Status:** Planning Complete, Implementation Not Started

---

## Executive Summary

The project is pivoting from a CLI-focused audio processing tool to a **full web application** integrated with Tone 3000's OAuth and model library. Users will authenticate via Tone 3000, build shootout comparisons through a web UI, and receive processed videos via an async job queue.

### Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Backend Framework | FastAPI | Best async Python, excellent OAuth/file support |
| Frontend Framework | Astro + React Islands | Static SEO pages + interactive components |
| Database | PostgreSQL + SQLAlchemy 2.0 | Full async, JSONB, built-in FTS |
| Job Queue | TaskIQ + Redis | Async-native, real-time progress |
| Authentication | Authlib → Tone 3000 OAuth | Custom provider support |
| Deployment | Docker Compose | Self-hosted, all services containerized |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         FRONTEND (Astro)                        │
├─────────────────────────────────────────────────────────────────┤
│  Landing Page    │  Comparison Pages   │  Pipeline Builder      │
│  (Static HTML)   │  (Static)           │  (React Island)        │
│  0 KB JS         │  Minimal JS         │  React + Tone 3000 SDK │
└────────────────────────────┬────────────────────────────────────┘
                             │ REST API + WebSocket
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      BACKEND (FastAPI)                          │
├─────────────┬──────────────┬──────────────┬────────────────────┤
│   Auth      │   API        │  WebSocket   │   Background Jobs  │
│  (Authlib)  │  (REST)      │  (Progress)  │    (TaskIQ)        │
│             │              │              │                    │
│  Tone 3000  │  Shootouts   │  Real-time   │  Audio Processing  │
│  OAuth Flow │  Users       │  Updates     │  Video Generation  │
│  Token Mgmt │  Models      │              │  (Pipeline pkg)    │
└─────────────┴──────────────┴──────────────┴────────────────────┘
                             │
         ┌───────────────────┼───────────────────┐
         ▼                   ▼                   ▼
┌─────────────────┐  ┌───────────────┐  ┌────────────────────┐
│   PostgreSQL    │  │  Tone 3000    │  │   Local Storage    │
│                 │  │  API          │  │                    │
│  Users          │  │               │  │  /uploads/{uuid}/  │
│  Shootouts      │  │  Models       │  │    di_tracks/      │
│  Metadata       │  │  Tones        │  │    outputs/        │
│  Tags           │  │  User Data    │  │                    │
└─────────────────┘  └───────────────┘  └────────────────────┘
```

---

## Project Structure (Target)

```
guitar-tone-shootout/
├── backend/                    # FastAPI application (NEW)
│   ├── app/
│   │   ├── api/
│   │   │   ├── auth.py        # Tone 3000 OAuth
│   │   │   ├── shootouts.py   # CRUD for shootouts
│   │   │   ├── jobs.py        # Processing jobs
│   │   │   └── ws.py          # WebSocket handlers
│   │   ├── core/
│   │   │   ├── config.py      # Settings
│   │   │   ├── security.py    # Token handling
│   │   │   └── tone3000.py    # API client
│   │   ├── models/            # SQLAlchemy models
│   │   ├── schemas/           # Pydantic schemas
│   │   └── tasks/             # TaskIQ background jobs
│   ├── alembic/               # Migrations
│   ├── Dockerfile.dev         # Development container
│   ├── Dockerfile             # Production container
│   └── pyproject.toml
├── frontend/                   # Astro application (NEW)
│   ├── src/
│   │   ├── pages/
│   │   │   ├── index.astro    # Landing (static)
│   │   │   ├── login.astro    # Auth redirect
│   │   │   └── builder/       # Pipeline builder
│   │   ├── components/
│   │   │   ├── PipelineBuilder.tsx  # React island
│   │   │   └── ToneSelector.tsx     # React island
│   │   └── layouts/
│   ├── Dockerfile.dev
│   ├── Dockerfile
│   ├── astro.config.mjs
│   └── package.json
├── pipeline/                   # Audio processing (EXISTING - preserved)
│   └── (preserved as-is)
├── web/                        # Flask + HTMX (TO BE REMOVED)
│   └── (will be deleted after frontend/ is ready)
├── docker-compose.yml          # Development environment
├── docker-compose.prod.yml     # Production environment
├── dev/                        # Development documentation
│   ├── README.md
│   ├── session-state.md
│   ├── EXECUTION-PLAN.md
│   └── active/
└── AGENTS.md
```

---

## Tone 3000 Integration

### API Documentation
- URL: https://www.tone3000.com/api
- Rate Limit: 100 requests/minute

### Authentication Flow

```
User clicks "Login" → Redirect to Tone 3000 → User authenticates
                                                      ↓
                              Redirect back with api_key in URL
                                                      ↓
                        Exchange api_key for JWT tokens (access + refresh)
                                                      ↓
                              Store tokens, create local user session
```

### Key Data Models from Tone 3000

| Model | Key Fields |
|-------|------------|
| Tone | id, title, gear (amp/pedal/ir), platform (nam/ir/aida-x), tags[], makes[], license |
| Model | id, name, size (standard/lite/feather/nano), model_url (download) |
| User | id, username, avatar_url, tones_count |

### OAuth Code Example

```python
# Backend: /api/auth/login
@router.get("/auth/login")
async def login():
    redirect_url = quote("https://yourdomain.com/auth/callback")
    return RedirectResponse(
        f"https://www.tone3000.com/api/v1/auth?redirect_url={redirect_url}"
    )

# Backend: /api/auth/callback
@router.get("/auth/callback")
async def callback(api_key: str):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://www.tone3000.com/api/v1/auth/session",
            json={"api_key": api_key}
        )
    session = response.json()
    # Store tokens, create local user, redirect to app
```

---

## Job Queue System

### Components

| Component | Technology | Purpose |
|-----------|------------|---------|
| Message Broker | Redis | Queue jobs, route to workers |
| Task Queue | TaskIQ | Define/execute jobs, track status |
| Result Backend | Redis | Store job status, progress, outputs |
| Workers | TaskIQ workers | Execute pipelines (scalable) |
| Real-time | WebSocket | Push updates to frontend |

### Job Lifecycle

```
1. User submits shootout  →  Job created (PENDING)
2. Job queued to Redis    →  Status: QUEUED  →  WebSocket notify
3. Worker picks up job    →  Status: RUNNING →  WebSocket notify
4. Pipeline processing    →  Progress: 10%, 50%, 90% → WebSocket updates
5. Job completes          →  Status: COMPLETED → WebSocket notify + results
   (or fails)             →  Status: FAILED → WebSocket notify + error
```

### Database Schema

```python
class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    shootout_id: Mapped[int] = mapped_column(ForeignKey("shootouts.id"))

    status: Mapped[str]  # pending, queued, running, completed, failed, cancelled
    progress: Mapped[int] = mapped_column(default=0)  # 0-100
    message: Mapped[str | None]  # Current step description

    created_at: Mapped[datetime]
    started_at: Mapped[datetime | None]
    completed_at: Mapped[datetime | None]

    result_path: Mapped[str | None]  # Path to output files
    error: Mapped[str | None]  # Error message if failed
```

---

## Docker Compose (Development)

```yaml
services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: shootout
      POSTGRES_USER: shootout
      POSTGRES_PASSWORD: ${DB_PASSWORD:-devpassword}
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile.dev
    ports:
      - "8000:8000"
    volumes:
      - ./backend:/app
      - ./pipeline:/pipeline  # Access pipeline code
    environment:
      - DATABASE_URL=postgresql+asyncpg://shootout:${DB_PASSWORD:-devpassword}@db/shootout
      - REDIS_URL=redis://redis:6379
    command: uvicorn app.main:app --host 0.0.0.0 --reload
    depends_on:
      - db
      - redis

  worker:
    build:
      context: ./backend
      dockerfile: Dockerfile.dev
    volumes:
      - ./backend:/app
      - ./pipeline:/pipeline
    environment:
      - DATABASE_URL=postgresql+asyncpg://shootout:${DB_PASSWORD:-devpassword}@db/shootout
      - REDIS_URL=redis://redis:6379
    command: taskiq worker app.tasks.shootout:broker --workers 2
    depends_on:
      - db
      - redis

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile.dev
    ports:
      - "4321:4321"
    volumes:
      - ./frontend:/app
      - /app/node_modules
    command: pnpm dev --host

volumes:
  postgres_data:
  redis_data:
```

---

## Epic Execution Plan

### v2.0 - Web Application Foundation (Start Here)

| Issue | Title | Dependencies |
|-------|-------|--------------|
| #6 | Docker Compose dev environment | None |
| #7 | Docker Compose production environment | #6 |
| #8 | FastAPI project structure | #6 |
| #9 | SQLAlchemy 2.0 async + Alembic | #8 |
| #10 | Update README and AGENTS.md | #6, #8 |

### v2.1 - Tone 3000 Integration

| Issue | Title | Dependencies |
|-------|-------|--------------|
| #12 | OAuth login and callback | v2.0 complete |
| #13 | API client with token refresh | #12 |

### v2.2 - Job Queue System

| Issue | Title | Dependencies |
|-------|-------|--------------|
| #15 | TaskIQ setup with Redis | v2.0 complete |
| #16 | Job model and status endpoints | #15 |
| #17 | WebSocket for real-time progress | #16 |

### v2.3 - Frontend (Astro)

| Issue | Title | Dependencies |
|-------|-------|--------------|
| #19 | Astro project setup | v2.0 complete |
| #20 | Landing page and layouts | #19 |
| #21 | Pipeline builder React component | #19, v2.1, v2.2 |

### v2.4 - Pipeline Web Adapter

| Issue | Title | Dependencies |
|-------|-------|--------------|
| #23 | Pipeline service wrapper | v2.0 complete |
| #24 | Tone 3000 model downloader | #23, v2.1 |
| #25 | Shootout database model | #23, v2.0 |

---

## Technology Research Summary

### Backend: FastAPI (Chosen)

**Why FastAPI over alternatives:**
- Native async support (required for job queue)
- Built-in OpenAPI/Swagger docs
- Excellent OAuth2 support via Authlib
- First-class WebSocket support
- FastAPI-Users for user management

**Alternatives considered:**
- Litestar: Similar but smaller ecosystem
- Django: Sync-first, heavier
- Flask: Would need many extensions

### Frontend: Astro + React (Chosen)

**Why Astro:**
- Static site generation for SEO (landing pages)
- React islands for interactive components
- Zero JS by default on static pages
- Native Tailwind CSS 4 support

**Why React islands (not full SPA):**
- Tone 3000 provides React examples/SDK
- Only pipeline builder needs interactivity
- Better performance for static content

### Database: PostgreSQL + SQLAlchemy 2.0 (Chosen)

**Why PostgreSQL:**
- JSONB for flexible metadata storage
- Built-in full-text search
- Battle-tested for web apps

**Why SQLAlchemy 2.0:**
- Full async support with asyncpg
- Type hints with Mapped[]
- Alembic for migrations

### Job Queue: TaskIQ + Redis (Chosen)

**Why TaskIQ:**
- Native async (unlike Celery)
- Clean integration with FastAPI
- Result backend built-in
- Lightweight

**Why Redis (not PostgreSQL for queue):**
- Faster for job queuing
- Pub/sub for real-time WebSocket updates
- Industry standard for task queues

---

## Constraints and Decisions

1. **Scale:** <100 users initially, local filesystem for uploads
2. **Deployment:** Self-hosted Docker, no cloud dependencies
3. **Real-time:** Essential for job progress (WebSocket required)
4. **SEO:** Landing pages must be static HTML (Astro)
5. **Tone 3000 compatibility:** Must use their React patterns for model selector

---

## Next Steps

1. Begin with Issue #6: Docker Compose development environment
2. Create `backend/` and `frontend/` directory structure
3. Remove `web/` after `frontend/` is functional
