# Web Application Foundation - Tasks

**Epic:** #5
**Last Updated:** 2025-12-26

---

## Phase 1: Docker Dev Environment (#6) - NOT STARTED

- [ ] Create `docker-compose.yml` with all services
  - [ ] PostgreSQL 16 service with volume
  - [ ] Redis 7 service
  - [ ] Backend service with hot-reload
  - [ ] Frontend service with hot-reload
  - [ ] Worker service for TaskIQ
- [ ] Create `backend/Dockerfile.dev`
  - [ ] Python 3.12 base image
  - [ ] Install uv
  - [ ] Configure for hot-reload
- [ ] Create `frontend/Dockerfile.dev`
  - [ ] Node 20 base image
  - [ ] Install pnpm
  - [ ] Configure for dev server
- [ ] Create `.env.example`
  - [ ] Database credentials
  - [ ] Redis URL
  - [ ] Tone 3000 API placeholders
- [ ] Verify `docker compose up` works
- [ ] Verify hot-reload works for backend
- [ ] Verify hot-reload works for frontend

---

## Phase 2: Docker Prod Environment (#7) - NOT STARTED

- [ ] Create `docker-compose.prod.yml`
  - [ ] Production service configurations
  - [ ] Health checks
  - [ ] Resource limits
- [ ] Create `backend/Dockerfile`
  - [ ] Multi-stage build
  - [ ] Gunicorn configuration
  - [ ] Minimal image size
- [ ] Create `frontend/Dockerfile`
  - [ ] Build static assets
  - [ ] Serve with nginx or similar
- [ ] Verify production build works

---

## Phase 3: FastAPI Structure (#8) - NOT STARTED

- [ ] Create `backend/pyproject.toml`
  - [ ] FastAPI and dependencies
  - [ ] Dev dependencies (pytest, mypy, ruff)
- [ ] Create `backend/app/main.py`
  - [ ] FastAPI application
  - [ ] CORS configuration
  - [ ] Lifespan events
- [ ] Create `backend/app/api/health.py`
  - [ ] Health check endpoint
  - [ ] Database connectivity check
- [ ] Create `backend/app/core/config.py`
  - [ ] Pydantic settings
  - [ ] Environment variable loading
- [ ] Verify `/health` endpoint works
- [ ] Verify `/docs` shows OpenAPI

---

## Phase 4: Database Setup (#9) - NOT STARTED

- [ ] Create `backend/app/core/database.py`
  - [ ] Async SQLAlchemy engine
  - [ ] Session factory
  - [ ] Dependency for routes
- [ ] Create `backend/app/models/base.py`
  - [ ] Base class with common fields
- [ ] Create `backend/app/models/user.py`
  - [ ] User model with Tone 3000 ID
- [ ] Initialize Alembic
  - [ ] `alembic init alembic`
  - [ ] Configure for async
- [ ] Create initial migration
- [ ] Verify migrations work

---

## Phase 5: Documentation (#10) - PARTIALLY COMPLETE

- [x] Update README.md for Docker workflow
- [x] Update AGENTS.md for new patterns
- [x] Add session checkpoint rules
- [x] Document architecture in EXECUTION-PLAN.md
- [ ] Remove old `web/` references after frontend complete
- [ ] Update justfile for Docker commands

---

## Summary

| Phase | Issue | Status | Progress |
|-------|-------|--------|----------|
| 1 | #6 | Not Started | 0% |
| 2 | #7 | Not Started | 0% |
| 3 | #8 | Not Started | 0% |
| 4 | #9 | Not Started | 0% |
| 5 | #10 | Partial | 60% |

**Overall Progress:** ~10%
