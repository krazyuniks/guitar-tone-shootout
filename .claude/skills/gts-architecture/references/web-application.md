# Web Application

The webapp workspace member. Depends on core, NOT on sources.

## Services

| Service | Purpose |
|---------|---------|
| Shootout Service | Shootout CRUD + lifecycle management |
| Signal Chain Service | Chain composition + validation |
| Preset Service | Signal chains with parameter values |
| Job Service | Background job lifecycle + retry logic |
| Identity Service | OAuth provider linking (multi-provider per user) |
| Block Type Registry | Built-in processor templates (EQ, compressor, etc.) |
| IR Upload Service | User IR uploads -> unified Gear model |
| DI Track Service | DI track uploads + validation |

## Authentication

OAuth 2.0 with multiple providers.

| Provider | Status |
|----------|--------|
| T3K (Tone3000) | Implemented |
| Google | Planned |
| GitHub | Planned |
| Facebook | Planned |

**Implementation:**
- Generic OAuth handling in `webapp/auth/`
- Provider-specific configuration (client ID, endpoints)
- Multi-provider linking per user (Identity Service)
- Token encryption at rest (Fernet)
- No provider-specific business logic in domain

## Frontend

**Build System:** Astro
- Compiles Jinja2 templates (`.html.ts` -> `.html`) and Tailwind CSS
- Output committed to `frontend/astro/dist/`
- Bind-mounted to FastAPI container for template access
- No Astro dev server at runtime

**Route Architecture:**

| Route Type | Technology | URL Patterns |
|------------|------------|--------------|
| Static (SSG) | Astro pre-built, nginx serves | `/`, `/about`, `/login` |
| Dynamic (SSR) | Jinja2 + FastAPI | `/gear/{slug}`, `/shootouts`, `/shootout/{id}`, `/library/*`, `/chain/*` |

All templates (static and dynamic) are authored in Astro. Dynamic templates contain Jinja2 syntax evaluated at request time by FastAPI.

**Interactivity:**
- HTMX for partial page updates (HTML-over-the-wire)
- Alpine.js for client-side UI state (tabs, toggles)
- WebSocket for real-time notifications (job completion, alerts)
- No SPA, no client-side routing

**HTMX Fragment Convention:**

| Backend Route | Template Path |
|---------------|---------------|
| `/api/v1/html/{domain}/{action}` | `fragments/{domain}/{action}.html` |

Examples:
- `DELETE /api/v1/html/chains/{id}` -> returns empty (element removed)
- `POST /api/v1/html/chains/{id}/process` -> returns updated status fragment
- `GET /api/v1/html/gear/browse` -> returns gear list fragment for filtering

**React Island: Signal Chain Builder**

Complex interactive UI for composing signal chains. React assets loaded ONLY on builder page.

| Mode | Description | Output |
|------|-------------|--------|
| Permutation | Multiple gear per block (3 amps x 4 IRs) | SignalChainGroup |
| Single Chain | One gear per block | SignalChain (reusable) |

**Signal Chain Library**

SSR page for managing saved chains. HTMX for inline actions (delete, submit processing jobs).

- List user's SignalChains and SignalChainGroups
- Add DI tracks to chains for processing
- Delete chains/groups
- View audio segments generated from chains

Shootouts are optional -- users can build chains, process audio, and manage their library without creating comparisons.

## API Design

| Route Prefix | Purpose |
|--------------|---------|
| `/api/v1/` | JSON API (data operations, auth) |
| `/api/v1/html/` | HTML fragments (HTMX responses) |
| `/` | SSR pages |

**Note:** Admin APIs are served by the webapp at `/api/admin/*` (port 8000). See Admin API Architecture below.

## Admin API Architecture

Internal admin API for infrastructure management. Not exposed publicly -- access controlled at network level.

### Design Principles

| Principle | Rationale |
|-----------|-----------|
| **Centralised in webapp** | Webapp already has all database connections needed (single `gts_core` DB) |
| **No authentication** | Network-level access control (routes not exposed publicly) |
| **Composite health** | Single `/health` endpoint reports all component status |

### Admin API (Webapp -- port 8000, `/api/admin/*`)

All admin endpoints served by the webapp container:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/admin/jobs` | GET | List jobs with status filter |
| `/admin/jobs/{id}` | GET | Get job details |
| `/admin/jobs/dead-lettered` | GET | List dead-lettered jobs |
| `/admin/jobs/{id}/retry` | POST | Retry failed job |
| `/admin/jobs/pending-retries/count` | GET | Pending retry count |
| `/admin/t3k/sync/status` | GET | Current sync state and pagination |
| `/admin/t3k/sync` | POST | Trigger catalog sync |
| `/admin/t3k/sync/stats` | GET | Pack/model counts |
| `/admin/t3k/sync/lag` | GET | Time since last sync |
| `/admin/t3k/auth/status` | GET | OAuth token validity |
| `/admin/t3k/errors/summary` | GET | Error aggregation by type |
| `/health` | GET | Composite health check |

**Why webapp serves admin endpoints:** All BCs share the single `gts_core` database. The webapp already has the database connection needed to query sync status, job state, stats, and checkpoints. No separate admin server required.

**Future sources:** When AIDA-X or other sources are added, their admin endpoints (`/api/admin/aidax/*`) will also be served by the webapp, querying the shared `gts_core` database.

### Composite Health Endpoint

The `/health` endpoint reports on all webapp components:

```json
{
  "status": "healthy",
  "components": {
    "database": "connected",
    "pgmq": "available"
  }
}
```

Docker healthchecks use this endpoint. If any component is unhealthy, the container is marked unhealthy.

### Admin API Access

> **Note:** A `gts-admin` CLI is planned. Currently, use `curl` to access the webapp admin API directly.

```bash
# All requests -> Webapp (port 8000)
curl http://localhost:8000/api/admin/jobs           # List all jobs
curl http://localhost:8000/api/admin/jobs/{id}      # Get job details
curl http://localhost:8000/api/admin/jobs/dead-lettered  # Dead-lettered jobs
curl http://localhost:8000/api/admin/t3k/sync/status     # Sync status
curl -X POST http://localhost:8000/api/admin/t3k/sync    # Trigger sync
curl http://localhost:8000/api/admin/t3k/auth/status     # T3K auth check
curl http://localhost:8000/health                        # Health check
```

### Port Allocation

| Port | Container | Profile |
|------|-----------|---------|
| 8000 | webapp | default |

Worktree offsets apply: main uses 8000, worktree with offset 10 uses 8010.

### Dependency Flow

```
┌─────────────┐
│ curl/CLI    │
│  (client)   │
└──────┬──────┘
       │
       └──── all requests ──▶ Webapp Admin API (:8000/api/admin/*)
                                    │
                              ┌─────▼─────┐
                              │ gts_core  │
                              │  (pgmq)   │
                              └───────────┘
```

## File Storage

Shared bind mount (`../gts-storage/`) — all worktrees share one storage directory on the host, mapped to `/app/storage/` in containers.

### Storage Layout

```
/app/storage/
├── models/              # Core gear models ({uuid}.nam)
├── uploads/
│   ├── di_tracks/       # User-uploaded guitar recordings
│   └── irs/             # User-uploaded impulse responses
├── audio/               # Processed shootout audio segments
├── videos/              # Generated shootout comparison videos
└── source_downloads/    # Raw source adapter downloads
    └── t3k/             # T3K models ({model_id}/{filename}.nam)
```

**Audio segments** are the processed output from running a DI track through a signal chain with a preset. Files are named by UUIDv7 from the audio table.

Audio segments include:
- Standalone processing (signal chain library)
- Individual permutation outputs (shootout processing)
- Full concatenated audio track (for video)

### Upload Handling

- Validate format, size, sample rate
- Compute SHA256 checksum
- Extract waveform visualisation data
- Access controlled via API (not direct HTTP)
