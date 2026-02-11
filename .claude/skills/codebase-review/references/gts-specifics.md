# GTS-Specific Review Patterns

## GTS Architecture Boundaries

### Import Rules

| Module | Can depend on | Cannot depend on |
|--------|---------------|------------------|
| `core` | (none) | audio, sources, apps |
| `audio` | core | sources, apps |
| `source_*` | core | audio, other sources, apps |
| `webapp` | core, audio | sources |
| `worker` | core, audio | sources |

```bash
# Verify core has no framework imports
grep -r "sqlalchemy\|fastapi\|redis\|httpx" libs/core/ 2>/dev/null

# Verify webapp doesn't import sources
grep -r "from source_" apps/webapp/ 2>/dev/null
```

### Aggregate Roots

| Aggregate | File | Child Entities |
|-----------|------|----------------|
| Shootout | `libs/core/.../entities/shootout.py` | ShootoutChain |
| SignalChain | `libs/core/.../entities/signal_chain.py` | SignalChainBlock |
| User | `libs/core/.../entities/user.py` | UserIdentity |
| Gear | `libs/core/.../entities/gear.py` | GearModel, GearSource |

### Transaction Patterns

```bash
# Services should use session.begin() or begin_nested()
grep -rn "async with.*session.begin" apps/webapp/src/webapp/services/

# API handlers should NOT start transactions
grep -rn "session.begin" apps/webapp/src/webapp/api/

# Adapters should use flush(), not commit()
grep -rn "\.commit()" apps/webapp/src/webapp/adapters/
```

## GTS Frontend Specifics

### Fragment Mapping Convention

`/api/v1/html/{domain}/{action}` maps to `fragments/{domain}/{action}.html`

```bash
# List all HTML fragment endpoints
grep -n '@router\.\(get\|post\|put\|delete\)' apps/webapp/src/webapp/api/v1/html.py

# List all fragment templates
ls -la astro/dist/fragments/
```

### Design Token Usage

Templates should use CSS custom properties from Astro, not hardcoded colours:
- `--color-bg-base`, `--color-bg-surface`, `--color-bg-elevated`
- `--color-text-primary`, `--color-text-secondary`, `--color-text-muted`
- `--color-accent-primary`, `--color-accent-success`
- `--color-block-amp`, `--color-block-pedal`

## GTS Observability Specifics

### Expected Metrics

```bash
# T3K sync metrics
curl -s http://localhost:8000/metrics | grep -E "^t3k_"

# Business metrics
curl -s http://localhost:8000/metrics | grep -E "^(daily_active_users|feature_usage|conversion_funnel)"

# Circuit breaker
curl -s http://localhost:8000/metrics | grep -E "^t3k_circuit_breaker"
```

### Exception Hierarchy

```bash
docker compose exec webapp python -c "
from app.core.exceptions import *
print('AppException subclasses:')
for cls in [NotFoundError, BadRequestError, ValidationError, AuthenticationError,
            AuthorizationError, ConflictError, RateLimitError, ExternalServiceError,
            ServiceUnavailableError]:
    print(f'  {cls.__name__}: {cls.status_code} ({cls.code})')
"
```

## GTS Workflow Specifics

### Required Just Commands

```bash
just check          # Quality gates
just test-unit      # Unit tests (Docker)
just test-integration  # Integration tests (Docker)
just test-golden-path # Golden path tests (host)
just build-astro    # Build frontend
just verify-astro-sync  # Verify frontend sync
```

### Auth Persistence

```bash
./worktree.py auth-status   # Check auth validity
```

## GTS Docker Architecture

Runtime stack: db, redis, webapp, nginx, worker, scheduler
Build-only: astro (starts with `--profile build`)

### Dual Database

| Database | Purpose | Access |
|----------|---------|--------|
| `gts_core` | Application data | Webapp, worker |
| `gts_t3k_source` | T3K source data | Worker only |

**Critical:** Webapp has NO direct access to T3K source database.
