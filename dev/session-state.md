# Session State

**Last Updated:** 2025-12-27
**Branch:** main

---

## Active Work

| Epic | Issue | Status | Next Action |
|------|-------|--------|-------------|
| v2.4 | #24 Tone 3000 model downloader | Ready | Start in new session |

---

## Epic Overview

| Milestone | Epic Issue | Sub-Issues | Status |
|-----------|------------|------------|--------|
| v2.0 - Web Application Foundation | #5 | #6, #7, #8, #9, #10 | **Complete** |
| v2.1 - Tone 3000 Integration | #11 | #12, #13 | **Complete** |
| v2.2 - Job Queue System | #14 | #15, #16, #17 | **Complete** |
| v2.3 - Frontend (Astro) | #18 | #19, #20, #21 | **Complete** |
| v2.4 - Pipeline Web Adapter | #22 | #23, #24, #25 | **In Progress** |
| v2.5 - UI Design System | TBD | TBD | Ready |
| v2.6 - Signal Chain Builder | TBD | TBD | Ready |
| v2.7 - Browse & Discovery | TBD | TBD | Ready |
| v2.8 - Audio Analysis & Reproducibility | #58 | #59, #60, #61, #62, #63, #64, #65 | **New** |

---

## v2.4 Pipeline Web Adapter - IN PROGRESS

| Issue | Title | Status |
|-------|-------|--------|
| #23 | Pipeline service wrapper with progress callbacks | **Merged** (#68) |
| #24 | Tone 3000 model downloader with caching | Open |
| #25 | Shootout database model replacing INI configuration | Open |

**What was built in #23:**
- **PipelineService**: Main service class with async progress callbacks
- **ShootoutConfig/ToneConfig/EffectConfig**: Data classes for web-based configuration
- **process_shootout_task**: TaskIQ task wrapper with Redis progress publishing
- **Pydantic schemas**: ShootoutConfigSchema, ToneSchema, EffectSchema for API validation
- Uses `asyncio.to_thread()` for CPU-intensive pipeline operations
- Full test coverage with 12 new tests

---

## v2.3 Frontend (Astro) - COMPLETE

| Issue | Title | Status |
|-------|-------|--------|
| #19 | Astro project setup with shadcn/ui | **Merged** (#55) |
| #20 | Landing page and layout components | **Merged** (#66) |
| #21 | Pipeline builder React component | **Merged** (#67) |

**What was built in #21:**
- **PipelineBuilder**: Main component with 3-step UX flow
- **ToneSelector**: Browse My Tones, Favorites, Search with gear/platform filters
- **ToneCard**: Display selected tones with NAM/IR/AIDA-X platform badges
- **DITrackUpload**: Drag-and-drop audio upload with format validation
- **Hooks**: TanStack Query hooks for tones, job submission, and auth
- **builder.astro**: Builder page at `/builder` route
- Updated navigation links in Header and Hero

---

## v2.2 Job Queue System - COMPLETE

| Issue | Title | Status |
|-------|-------|--------|
| #15 | TaskIQ setup with Redis broker | **Merged** (#52) |
| #16 | Job model and status endpoints | **Merged** (#53) |
| #17 | WebSocket for real-time progress | **Merged** (#54) |

---

## v2.1 Tone 3000 Integration - COMPLETE

| Issue | Title | Status |
|-------|-------|--------|
| #12 | OAuth login and callback endpoints | Merged |
| #13 | API client with automatic token refresh | Merged |

---

## v2.0 Foundation - COMPLETE

| Issue | Title | Status |
|-------|-------|--------|
| #6 | Docker Compose dev environment | Merged |
| #7 | Docker Compose production environment | Merged |
| #8 | FastAPI project structure | Merged |
| #9 | SQLAlchemy 2.0 async + Alembic | Merged |
| #10 | Update README and AGENTS.md | Merged |

---

## v2.8 Audio Analysis & Reproducibility - NEW

| Issue | Title | Status |
|-------|-------|--------|
| #58 | Epic: Audio Analysis & Reproducibility | Open |
| #59 | Audio metrics extraction library | Open |
| #60 | Database schema for metrics & reproducibility | Open |
| #61 | AI evaluation generation (algorithmic + LLM) | Open |
| #62 | Segment timestamp tracking | Open |
| #63 | Shootout metadata capture | Open |
| #64 | API endpoints for metrics & evaluation | Open |
| #65 | Frontend display of metrics & AI evaluation | Open |

**Dev Docs:** `dev/active/audio-analysis-reproducibility/`

**Key Features:**
- Comprehensive audio metrics (12+ measurements)
- AI evaluation per segment (algorithmic + LLM)
- Full reproducibility metadata (versions, hashes, settings)
- Millisecond-accurate timestamps for deep linking

---

## Recent Activity

- **2025-12-27**: Merged #23 Pipeline service wrapper (#68). v2.4 started.
- **2025-12-27**: Merged #21 Pipeline builder React component (#67). **v2.3 Complete!**
- **2025-12-27**: Merged #20 Landing page and layout components (#66).
- **2025-12-27**: Created v2.8 Audio Analysis & Reproducibility epic (#58) with 7 sub-issues.
- **2025-12-27**: Merged #56 Pedalboard NAM Migration (#57). PyTorch NAM → Pedalboard + VST3.
- **2025-12-26**: Merged #19 Astro project setup (#55). v2.3 Frontend started.
- **2025-12-26**: Merged #17 WebSocket progress endpoint (#54). v2.2 complete.
- **2025-12-26**: Merged #16 Job model and endpoints (#53).
- **2025-12-26**: Merged #15 TaskIQ setup (#52).
- **2025-12-26**: v2.1 Tone 3000 Integration complete (#12, #13).
- **2025-12-26**: v2.0 Foundation complete.

---

## Resume Instructions

After #23 PR is merged:

```bash
# 1. Sync with main
git checkout main && git pull --ff-only

# 2. Start next issue
gh issue view 24
git checkout -b 24-model-downloader
```
