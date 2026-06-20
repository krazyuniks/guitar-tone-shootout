# Web Application

The webapp workspace member. Depends on gts, NOT on sources.

## Services

| Service | Purpose |
|---------|---------|
| Shootout Service | Shootout CRUD + lifecycle management |
| Signal Chain Service | Chain composition + validation |
| Job Service | Background job lifecycle + retry logic |
| Identity Service | OAuth provider linking (multi-provider per user) |
| Block Type Registry | Built-in processor templates (EQ, compressor, etc.) |
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
- No SPA, no client-side routing

**HTMX Fragment Convention:**

| Backend Route | Template Path |
|---------------|---------------|
| `/api/html/{domain}/{action}` | `fragments/{domain}/{action}.html` |

Examples:
- `POST /api/html/gear/model/{id}/toggle` -> returns updated model row fragment
- `GET /api/html/shootouts/{id}/comments` -> returns comments section fragment
- `GET /api/html/jobs/{id}` -> returns job status polling fragment

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
| `/api/` | JSON API (data operations, auth) |
| `/api/html/` | HTML fragments (HTMX responses) |
| `/` | SSR pages |

**Note:** Admin APIs are split across webapp (port 8000) and t3k-sync (port 8003). See Admin API Architecture below.

## Admin API Architecture

Internal admin API for infrastructure management. Not exposed publicly -- access controlled at network level.

### Design Principles

| Principle | Rationale |
|-----------|-----------|
| **BC ownership** | Each BC serves admin endpoints for its own tables and services |
| **No authentication** | Network-level access control (routes not exposed publicly) |
| **Composite health** | Each service has its own `/health` endpoint |

### Admin API (Webapp -- port 8000, `/api/admin/*`)

Job management and source-agnostic endpoints:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/admin/jobs` | GET | List jobs with status filter |
| `/admin/jobs/{id}` | GET | Get job details |
| `/admin/jobs/dead-lettered` | GET | List dead-lettered jobs |
| `/admin/jobs/{id}/retry` | POST | Retry failed job |
| `/admin/jobs/pending-retries/count` | GET | Pending retry count |
| `/admin/sources/{source}/sync` | POST | Trigger catalog sync |
| `/admin/sources/{source}/errors/summary` | GET | Error aggregation by type |
| `/admin/sources/{source}/sync/unlock` | POST | Release sync lock |
| `/admin/scheduler/unlock` | POST | Release scheduler lock |
| `/admin/enqueue` | POST | Enqueue a job to pgmq |
| `/health` | GET | Composite health check |

### Admin API (T3K Sync -- port 8003, `/api/admin/*`)

T3K-specific sync status, stats, and token management:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/admin/sources/{source}/sync/status` | GET | Current sync state and checkpoint |
| `/admin/sources/{source}/sync/stats` | GET | Total synced counts |
| `/admin/sources/{source}/sync/lag` | GET | Time since last sync |
| `/admin/sources/{source}/sync/api-stats` | GET | API call rate metrics |
| `/admin/auth/refresh-t3k` | POST | Refresh T3K OAuth token |
| `/health` | GET | T3K sync service health |

**Why endpoints are split:** T3K sync endpoints query `SyncCheckpoint` (T3K-owned table) and use T3K-internal services (token manager, API call tracker). Keeping them in t3k-sync respects BC boundaries and eliminates the `webapp-no-sources` import-linter violation.

**Future sources:** When AIDA-X or other sources are added, their admin endpoints will live in their own sync service.

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

> **Note:** A `gts-admin` CLI is planned. Use Chrome DevTools MCP or `just` commands for admin API inspection — never `curl`/`wget`/`httpie`.

Admin API endpoints (`/api/admin/*`) are accessible via the Chrome DevTools MCP browser or through dedicated `just` commands. Do not use `curl` directly — it bypasses test tooling and violates the container-first rule.

For job and sync status: use `just` commands or the Chrome DevTools MCP to inspect the running app at `http://localhost:9000`.

### Port Allocation

| Port | Container | Profile |
|------|-----------|---------|
| 8000 | webapp | default |

Worktree offsets apply: main uses 8000, worktree with offset 10 uses 8010.

### Dependency Flow

```
┌───────────────────┐
│ Chrome DevTools   │
│ MCP / just cmds   │
└────────┬──────────┘
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
