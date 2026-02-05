# Goal-Backward Analysis: Phase 4 - Web Application Implementation

**Source:** `../wiki/IMPLEMENTATION.md` lines 644-754

## Goal

Users can authenticate via OAuth, browse gear, manage their library, build signal chains, and configure shootouts through a FastAPI backend with Jinja2 SSR pages and HTMX interactivity.

---

## Domain Model Reference

**Source:** `../wiki/GTS-Technical-Architecture.md` lines 245-390

### Entities In Scope for Phase 4

| Entity | Wiki Line | Description |
|--------|-----------|-------------|
| User | 264 | User account |
| UserIdentity | 265 | OAuth provider link (multi-provider per user) |
| OAuthProvider | 266 | OAuth provider configuration |
| Gear | 271 | Equipment item (unified across all sources) |
| GearModel | 272 | Specific model file (NAM, IR, etc.) within gear |
| GearSource | 273 | Source attribution (t3k, community, etc.) |
| UserGear | 276 | User's gear library (references Gear) |
| SignalChain | 281 | Aggregate root - composition of blocks |
| SignalChainBlock | 282 | Single block in chain |
| BlockType | 286 | Built-in processor template |
| Preset | 287 | Parameter values for a signal chain |
| DITrack | 292 | User-uploaded guitar recording |
| Shootout | 293 | A/B comparison configuration |
| ShootoutChain | 294 | Signal chain reference within a shootout |
| Job | 299 | Background job tracking |

### Value Objects (Wiki lines 379-388)

| Value Object | Description |
|--------------|-------------|
| GearType | Enum: AMP, FULL_RIG, PEDAL, OUTBOARD, IR |
| Platform | Enum: NAM, IR, AIDA_X, AA_SNAPSHOT, PROTEUS |
| BlockCategory | Enum of block categories |
| BlockPosition | Enum: pre, loop, post |

---

## Observable Truths

1. User can authenticate via OAuth and access protected pages
2. User can browse public gear and view gear details
3. User can manage their personal gear library (UserGear)
4. User can build signal chains using the React SignalChainBuilder
5. User can create and configure shootouts
6. User can see job status for their jobs
7. Application health can be verified

---

## Required Artifacts (with citations)

### Truth 1: User can authenticate via OAuth

**Entities:** User (wiki:264), UserIdentity (wiki:265), OAuthProvider (wiki:266)

| Artifact | Location | Pattern | Citation |
|----------|----------|---------|----------|
| User ORM model | `apps/webapp/src/webapp/adapters/persistence/models/` | SQLAlchemy | wiki:264 |
| UserIdentity ORM model | `apps/webapp/src/webapp/adapters/persistence/models/` | SQLAlchemy | wiki:265 |
| OAuthProvider ORM model | `apps/webapp/src/webapp/adapters/persistence/models/` | SQLAlchemy | wiki:266 |
| Generic OAuth handler | `apps/webapp/src/webapp/auth/` | OAuth2 | IMPL:661-668 |
| T3K provider | `apps/webapp/src/webapp/auth/providers/` | OAuth2 | IMPL:663 |
| IdentityService | `apps/webapp/src/webapp/services/` | Service | IMPL:678 |
| Auth API routes | `apps/webapp/src/webapp/api/v1/auth.py` | FastAPI | IMPL:681 |

### Truth 2: User can browse public gear

**Entities:** Gear (wiki:271), GearModel (wiki:272), GearSource (wiki:273)

| Artifact | Location | Pattern | Citation |
|----------|----------|---------|----------|
| Gear ORM model | `apps/webapp/src/webapp/adapters/persistence/models/` | SQLAlchemy | wiki:271 |
| GearModel ORM model | `apps/webapp/src/webapp/adapters/persistence/models/` | SQLAlchemy | wiki:272 |
| GearSource ORM model | `apps/webapp/src/webapp/adapters/persistence/models/` | SQLAlchemy | wiki:273 |
| Gear repository | `apps/webapp/src/webapp/adapters/persistence/repositories/` | Protocol impl | - |
| Gear API routes | `apps/webapp/src/webapp/api/v1/gear.py` | FastAPI | IMPL:682 |
| Gear browse page | `frontend/astro/src/pages/` | Jinja2 | IMPL:690 |
| Gear detail page | `frontend/astro/src/pages/` | Jinja2 | IMPL:690 |

### Truth 3: User can manage their gear library

**Entities:** UserGear (wiki:276)

| Artifact | Location | Pattern | Citation |
|----------|----------|---------|----------|
| UserGear ORM model | `apps/webapp/src/webapp/adapters/persistence/models/` | SQLAlchemy | wiki:276 |
| UserGear repository | `apps/webapp/src/webapp/adapters/persistence/repositories/` | Protocol impl | - |
| Library API routes | `apps/webapp/src/webapp/api/v1/` | FastAPI | IMPL:682 |
| My gear page | `frontend/astro/src/pages/` | Jinja2 | IMPL:691 |
| HTMX fragments | `frontend/astro/src/pages/fragments/` | HTML | IMPL:686 |

### Truth 4: User can build signal chains

**Entities:** SignalChain (wiki:281), SignalChainBlock (wiki:282), BlockType (wiki:286), Preset (wiki:287)

| Artifact | Location | Pattern | Citation |
|----------|----------|---------|----------|
| SignalChain ORM model | `apps/webapp/src/webapp/adapters/persistence/models/` | SQLAlchemy | wiki:281 |
| SignalChainBlock ORM model | `apps/webapp/src/webapp/adapters/persistence/models/` | SQLAlchemy | wiki:282 |
| BlockType ORM model | `apps/webapp/src/webapp/adapters/persistence/models/` | SQLAlchemy | wiki:286 |
| Preset ORM model | `apps/webapp/src/webapp/adapters/persistence/models/` | SQLAlchemy | wiki:287 |
| SignalChainService | `apps/webapp/src/webapp/services/` | Service | IMPL:672 |
| PresetService | `apps/webapp/src/webapp/services/` | Service | IMPL:673 |
| BlockTypeRegistry | `apps/webapp/src/webapp/services/` | Registry | IMPL:677 |
| Chain validator | `libs/core/src/core/services/` | Domain service | wiki:360-368 |
| Chain API routes | `apps/webapp/src/webapp/api/v1/signal_chains.py` | FastAPI | IMPL:683 |
| React SignalChainBuilder | `frontend/astro/src/components/SignalChainBuilder/` | React island | IMPL:696-701 |
| Chain builder page | `frontend/astro/src/pages/` | Jinja2 | IMPL:693 |

### Truth 5: User can create and configure shootouts

**Entities:** Shootout (wiki:293), ShootoutChain (wiki:294), DITrack (wiki:292)

| Artifact | Location | Pattern | Citation |
|----------|----------|---------|----------|
| Shootout ORM model | `apps/webapp/src/webapp/adapters/persistence/models/` | SQLAlchemy | wiki:293 |
| ShootoutChain ORM model | `apps/webapp/src/webapp/adapters/persistence/models/` | SQLAlchemy | wiki:294 |
| DITrack ORM model | `apps/webapp/src/webapp/adapters/persistence/models/` | SQLAlchemy | wiki:292 |
| ShootoutService | `apps/webapp/src/webapp/services/` | Service | IMPL:671 |
| DITrackService | `apps/webapp/src/webapp/services/` | Service | IMPL:675 |
| Shootout API routes | `apps/webapp/src/webapp/api/v1/shootouts.py` | FastAPI | IMPL:684 |
| Shootouts page | `frontend/astro/src/pages/` | Jinja2 | IMPL:691 |
| Shootout detail page | `frontend/astro/src/pages/` | Jinja2 | IMPL:692 |

### Truth 6: User can see job status

**Entities:** Job (wiki:299)

| Artifact | Location | Pattern | Citation |
|----------|----------|---------|----------|
| Job ORM model | `apps/webapp/src/webapp/adapters/persistence/models/` | SQLAlchemy | wiki:299 |
| JobService | `apps/webapp/src/webapp/services/` | Service | IMPL:674 |
| Jobs API routes | `apps/webapp/src/webapp/api/v1/jobs.py` | FastAPI | IMPL:685 |

### Truth 7: Application health

| Artifact | Location | Pattern | Citation |
|----------|----------|---------|----------|
| Health endpoints | `apps/webapp/src/webapp/api/v1/health.py` | FastAPI | IMPL:703-705 |

---

## Test Specifications

| Truth | Test Level | Test Name | Location |
|-------|------------|-----------|----------|
| Truth 1 | Unit | `test_identity_service_creates_user_identity` | `tests/unit/webapp/services/` |
| Truth 1 | Integration | `test_oauth_callback_creates_user` | `tests/integration/webapp/auth/` |
| Truth 1 | E2E | `test_login_redirects_to_provider` | `tests/e2e/python/tests/` |
| Truth 2 | Unit | `test_gear_repository_list` | `tests/unit/webapp/repositories/` |
| Truth 2 | Integration | `test_gear_api_returns_list` | `tests/integration/webapp/api/` |
| Truth 2 | E2E | `test_gear_browse_shows_items` | `tests/e2e/python/tests/` |
| Truth 3 | Unit | `test_user_gear_add_remove` | `tests/unit/webapp/repositories/` |
| Truth 3 | Integration | `test_user_gear_api_requires_auth` | `tests/integration/webapp/api/` |
| Truth 3 | E2E | `test_my_gear_page_shows_library` | `tests/e2e/python/tests/` |
| Truth 4 | Unit | `test_chain_validator_rules` | `tests/unit/core/services/` |
| Truth 4 | Integration | `test_signal_chain_crud` | `tests/integration/webapp/api/` |
| Truth 4 | E2E | `test_chain_builder_loads` | `tests/e2e/python/tests/` |
| Truth 5 | Unit | `test_shootout_service_create` | `tests/unit/webapp/services/` |
| Truth 5 | Integration | `test_shootout_api_crud` | `tests/integration/webapp/api/` |
| Truth 5 | E2E | `test_shootout_create_flow` | `tests/e2e/python/tests/` |
| Truth 6 | Unit | `test_job_service_get_user_jobs` | `tests/unit/webapp/services/` |
| Truth 6 | Integration | `test_jobs_api_returns_user_jobs` | `tests/integration/webapp/api/` |
| Truth 7 | Integration | `test_health_endpoint_ok` | `tests/integration/webapp/api/` |
| All | Regression | Update `test_regression.py` | `tests/e2e/python/tests/` |

---

## Three-Layer E2E Validation (MANDATORY)

All E2E tests (including regression) must verify the full code path:

1. **UI Action** - User interaction succeeds (click, submit)
2. **DOM Update** - Page reflects expected state change
3. **Database State** - Data persisted correctly (or page content reflects DB query)

The regression test exercises UI → Domain Model → Database. This ensures the entire stack is wired correctly.

---

## Regression Test Updates (IMPL:742-748)

When Phase 4 completes, update `tests/e2e/python/tests/test_regression.py`:

```python
# Smoke test: App starts, health check passes
# Auth test: Login redirect, callback handling, token received
# Browse test: Gear list loads, detail pages work
# Library test: My gear, chains visible after login
# CRUD test: Create signal chain, delete signal chain
# Builder test: SignalChainBuilder loads and renders
```
