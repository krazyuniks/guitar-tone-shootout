# Design Patterns

Persistence and domain patterns used throughout GTS. These implement the patterns defined in the Reference Architecture with GTS-specific technology choices.

## Persistence Pattern Summary

| Pattern | Purpose | Location |
|---------|---------|----------|
| **Repository (DDD)** | Aggregate-oriented data access behind protocol interfaces | `gts/ports/` -> `webapp/adapters/persistence/repositories/` |
| **DataMapper** | Separate ORM models from domain entities; repositories translate between them | `webapp/adapters/persistence/repositories/*` (`_to_entity()` methods) |
| **Unit of Work** | Transaction boundaries managed by session; explicit commit semantics | `webapp/adapters/persistence/unit_of_work.py` |
| **DTO** | Models for data crossing boundaries (sync records, API payloads) | `gts/records/`, `webapp/schemas/` |

## Repository Pattern

Aggregate-oriented data access behind protocol interfaces. Presents collection semantics ("in-memory collection of aggregates"). One repository per aggregate root.

**Ports (Domain Layer):** `model/gts/src/gts/ports/repositories.py`

| Repository | Aggregate | Purpose |
|------------|-----------|---------|
| `UserRepository` | User | User identity and profile operations |
| `GearRepository` | Gear | Unified gear model across all sources |
| `DITrackRepository` | DITrack | DI track persistence |
| `SignalChainRepository` | SignalChain | Signal chain and block persistence |
| `SignalChainGroupRepository` | SignalChainGroup | Chain group persistence |
| `ShootoutRepository` | Shootout | Shootout with chains |
| `JobRepository` | Job | Background job tracking |
| `AuditRepository` | -- | Audit logging |

**Implementations (Adapter Layer):** `apps/webapp/src/webapp/adapters/persistence/repositories/`

**Key Characteristics:**
- Protocol-based (dependency inversion -- domain depends on protocol, not implementation)
- Aggregate-oriented queries (business-focused, not table-oriented)
- **Full aggregate hydration in one query** via `joinedload()` (see `.claude/rules/query-patterns.md`)
- `selectinload`, `subqueryload`, and `lazyload` are **banned** -- they fire separate queries
- All ORM relationships use `lazy="raise"` to prevent implicit loading
- Full CRUD operations with complex queries
- Hides all persistence details from domain layer

## DataMapper Pattern

Domain entities are persistence-ignorant. ORM models and domain entities are **always separate classes**. Repositories handle translation between them.

**Domain entities** (`model/gts/src/gts/domain/entities/`):
- Pure Python dataclasses, no framework imports
- Identity-based equality (`__eq__` compares IDs)
- Business methods that enforce invariants
- No `save()`, `load()`, or any persistence awareness

**ORM models** (`apps/webapp/src/webapp/adapters/persistence/models/`):
- SQLAlchemy 2.0 mapped classes
- Relationships, foreign keys, indexes
- Concern: storage schema only

**Mapping** (`apps/webapp/src/webapp/adapters/persistence/repositories/`):
- Each repository has `_to_entity()` for ORM -> domain conversion
- `save()` methods handle domain -> ORM conversion
- Mapping logic lives in repositories, not in a separate mapper class

```python
# Repository maps between ORM and domain
class SQLAlchemyUserRepository:
    def _to_entity(self, orm_user: UserModel) -> UserEntity:
        """ORM -> Domain: construct domain entity from ORM model."""
        identities = [
            UserIdentityVO(
                provider=identity.provider.name,
                external_id=identity.external_id,
            )
            for identity in orm_user.identities
        ]
        return UserEntity(
            id=orm_user.id,
            username=orm_user.username,
            identities=identities,
        )

    async def save(self, user: UserEntity) -> None:
        """Domain -> ORM: persist domain entity via ORM model."""
        existing = await self.session.get(UserModel, user.id)
        if existing:
            existing.username = user.username
            # ... update fields
        else:
            self.session.add(UserModel(id=user.id, ...))
```

## Unit of Work

Manages database transaction boundaries with explicit commit semantics.

**Location:** `apps/webapp/src/webapp/adapters/persistence/unit_of_work.py`

**Usage:**
```python
async with UnitOfWork(session_factory) as uow:
    user = await user_repository.get_by_id(user_id)
    user.email = "new@example.com"
    await user_repository.save(user)
    await uow.commit()  # Explicit commit required
```

**Key Characteristics:**
- Async context manager protocol (`__aenter__`/`__aexit__`)
- Explicit `commit()` required for changes to persist
- Automatic rollback on exception
- Default rollback if not committed (fail-safe)
- Session lifecycle managed by UoW, not repositories

**Transaction Rule:** Services own transactions. Repositories receive sessions but don't create or commit them.

## DTO (Data Transfer Object)

Models for data crossing system boundaries. Validated at the edge, immutable in transit.

| DTO Type | Location | Purpose |
|----------|----------|---------|
| Sync records | `model/gts/src/gts/records/` | Gear sync messages between source adapters and core consumer |
| API schemas | `apps/webapp/src/webapp/schemas/` | HTTP request/response validation (Pydantic) |
| Value objects | `model/gts/src/gts/domain/value_objects/` | Immutable domain concepts (AudioResult, ToneConfig, etc.) |

**Sync records** are owned by core and imported by source adapters (Conformist pattern). Source adapters must construct valid `GearSyncRecord` instances -- core rejects invalid records.

## Domain Services

Pure business logic with zero framework dependencies.

**Location:** `model/gts/src/gts/services/`

| Service | Purpose |
|---------|---------|
| `SignalChainValidator` | Validates signal chain grammar (amp placement, IR requirements) |
| `PermutationCalculator` | Calculates gear permutations for comparisons |

**Key Characteristics:**
- Stateless services
- No database access -- pure calculations
- Returns value objects, not ORM models
- Testable without infrastructure

## Anti-Patterns to Avoid

These patterns are explicitly prohibited.

| Anti-Pattern | Description | Violation Example |
|--------------|-------------|-------------------|
| **DAO masquerading as Repository** | Table-oriented CRUD instead of aggregate-oriented access | `get_all_rows()`, `find_by_column()` without aggregate context |
| **Active Record** | Domain entities coupled to persistence (`entity.save()`) | Adding SQLAlchemy imports to `model/gts/` |
| **Exposing ORM outside service layer** | ORM models leaked to API routes or templates | Returning `UserModel` from a route handler instead of a schema |
| **Business logic in persistence** | Validation or rules in repository or ORM model | Computing signal chain validity inside a repository query |
| **Multiple queries per aggregate** | Using `selectinload`/`subqueryload` instead of `joinedload` | `.options(selectinload(Gear.models))` fires a second query |
| **Implicit lazy loading** | Missing `lazy="raise"` on relationships | `lazy="selectin"` or default `lazy="select"` fire queries on attribute access |
| **N+1 query pattern** | Accessing unloaded relationships in a loop | `for gear in items: print(gear.make.name)` without eager loading |

## Docker-First Development

All project code executes in Docker containers. The host environment is only for E2E tests and host tooling.

**Execution Matrix:**

| Code Type | Runs In | Command |
|-----------|---------|---------|
| Lint, type check | Docker | `just check` |
| Unit tests | Docker | `just test-unit` |
| Integration tests | Docker | `just test-integration` |
| Migrations | Docker | `just migrate` |
| Python REPL | Docker | `just repl` |
| E2E tests | **Host** | `just test-golden-path` |
| Git, GitHub CLI | Host | `git`, `gh` |
| Worktree management | Host | `./worktree.py` |

**Why Docker-First:**
- Consistent environment across all machines
- Exact dependency versions controlled
- CI parity -- same commands work in GitHub Actions
- No local Python/Node version conflicts

**NEVER run on host:**
```bash
# WRONG
uv run pytest tests/unit/
uv run ruff check
pytest tests/

# RIGHT
just test-unit
just check
just tdd tests/unit/path/test.py
```

The only `uv run` on host is for E2E tests in `tests/e2e/python/`.
