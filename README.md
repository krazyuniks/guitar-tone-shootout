# Guitar Tone Shootout

A web application for creating guitar amp/cab comparison videos, integrated with [Tone 3000](https://tone3000.com) for model management and user authentication.

## What It Does

1. **Authenticate** via Tone 3000 OAuth
2. **Select** NAM amp models, cabinet IRs, and effects from your Tone 3000 library
3. **Upload** DI (direct input) guitar recordings
4. **Build** comparison shootouts via the web interface
5. **Process** through an async job queue with real-time progress
6. **Download** YouTube-ready comparison videos

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     FRONTEND (Astro + React)                    │
│  Landing (Static) │ Comparison Pages │ Pipeline Builder (React) │
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

## Quick Start

### Prerequisites

- **Docker** and **Docker Compose** (all dependencies run in containers)
- **Tone 3000 account** for authentication

### Development Setup

```bash
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

### Production Deployment

```bash
# Build production images
docker compose -f docker-compose.prod.yml build

# Deploy
docker compose -f docker-compose.prod.yml up -d
```

## Project Structure

```
guitar-tone-shootout/
├── backend/                # FastAPI application
│   ├── app/
│   │   ├── api/           # REST endpoints
│   │   ├── core/          # Config, security, Tone 3000 client
│   │   ├── models/        # SQLAlchemy models
│   │   ├── schemas/       # Pydantic schemas
│   │   └── tasks/         # Background job definitions
│   ├── alembic/           # Database migrations
│   └── pyproject.toml
├── frontend/               # Astro + React application
│   ├── src/
│   │   ├── pages/         # Astro pages (static + dynamic)
│   │   ├── components/    # React components
│   │   └── layouts/       # Page layouts
│   └── package.json
├── pipeline/               # Audio/video processing library
│   ├── src/               # NAM, Pedalboard, FFmpeg processing
│   └── tests/
├── dev/                    # Development documentation
│   ├── session-state.md   # Current work tracking
│   ├── EXECUTION-PLAN.md  # Architecture and epics
│   └── active/            # Active task documentation
├── docker-compose.yml      # Development environment
├── docker-compose.prod.yml # Production environment
└── AGENTS.md               # Development workflow guide
```

## Technology Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| Frontend | Astro + React | Static SEO pages + interactive components |
| Backend | FastAPI | REST API, WebSocket, OAuth |
| Database | PostgreSQL | User data, shootouts, job status |
| Cache/Queue | Redis | Job queue, real-time pub/sub |
| Task Queue | TaskIQ | Async pipeline processing |
| Auth | Tone 3000 OAuth | User authentication |
| Audio | NAM + Pedalboard | Amp modeling, effects |
| Video | FFmpeg + Playwright | Video generation |

## Vocabulary

| Term | Definition |
|------|------------|
| **Shootout** | A comparison project with multiple signal chains and DI tracks |
| **DI Track** | Raw, unprocessed guitar recording (Direct Input) |
| **Signal Chain** | Ordered sequence of effects (amp, cab, pedals) |
| **Segment** | One processed audio/video clip (1 DI track × 1 signal chain) |
| **NAM** | Neural Amp Modeler - AI-based amp capture technology |
| **IR** | Impulse Response - Speaker cabinet acoustic snapshot |

## Development

See [AGENTS.md](AGENTS.md) for detailed development workflow, patterns, and conventions.

### Key Commands

```bash
# Start development environment
docker compose up

# Run quality checks (in container)
docker compose exec backend just check
docker compose exec frontend pnpm check

# View logs
docker compose logs -f backend
docker compose logs -f worker

# Database migrations
docker compose exec backend alembic upgrade head
```

## Roadmap

See [GitHub Milestones](https://github.com/krazyuniks/guitar-tone-shootout/milestones) for current progress:

- **v2.0** - Web Application Foundation (Docker, FastAPI, PostgreSQL)
- **v2.1** - Tone 3000 Integration (OAuth, API client)
- **v2.2** - Job Queue System (TaskIQ, Redis, WebSocket)
- **v2.3** - Frontend (Astro, React, Tailwind)
- **v2.4** - Pipeline Web Adapter

## Resources

- [Tone 3000 API Documentation](https://www.tone3000.com/api)
- [Tone 3000 GitHub](https://github.com/tone-3000)
- [Neural Amp Modeler](https://github.com/sdatkinson/neural-amp-modeler)

## License

MIT
