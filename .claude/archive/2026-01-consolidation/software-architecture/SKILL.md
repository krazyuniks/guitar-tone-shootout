# Software Architecture

Foundational principles and patterns for maintainable software systems.

---

## 1. Domain-Driven Design (DDD)

> "An approach to software development that centers the development on programming a domain model that has a rich understanding of the processes and rules of a domain."
> — Eric Evans

**Core insight:** Model the business domain, not the database. The domain is the problem space; the model is your solution.

### Ubiquitous Language

A shared vocabulary between developers and domain experts, embedded directly in code.

| Principle | Application |
|-----------|-------------|
| Same terms in code and conversation | `Shootout`, not `ToneComparison` or `comparison_table` |
| Evolve language with understanding | Rename when domain knowledge deepens |
| Reject technical jargon in domain | `SignalChain`, not `AudioProcessingPipeline` |

### Bounded Contexts

A boundary within which a domain model applies. Large systems have multiple contexts, each with its own model.

```
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│   Shootouts     │  │  Signal Chains  │  │   Gear Catalog  │
│                 │  │                 │  │                 │
│  Shootout       │  │  SignalChain    │  │  Gear           │
│  ToneSelection  │  │  SignalBlock    │  │  GearModel      │
│                 │  │  ChainGroup     │  │  GearTag        │
└─────────────────┘  └─────────────────┘  └─────────────────┘
       │                    │                    │
       └────────────────────┼────────────────────┘
                            │
                    Context Mapping
                  (how contexts relate)
```

**Key rule:** Aggregates in different contexts should not directly reference each other. Use IDs or domain events.

### Tactical Patterns

| Pattern | Definition | Example |
|---------|------------|---------|
| **Entity** | Object with identity that persists across state changes | `User` (same user even if name changes) |
| **Value Object** | Immutable object defined by its attributes | `ToneSelection` (amp_id + cab_id) |
| **Aggregate** | Cluster of entities/value objects with a root that owns consistency | `Shootout` owns its `ToneSelections` |
| **Repository** | Abstraction for retrieving and storing aggregates | `ShootoutRepository.get_by_id()` |
| **Domain Event** | Record of something significant that happened | `ShootoutCreated`, `ToneSyncCompleted` |
| **Domain Service** | Stateless operation that doesn't belong to an entity | `GearMatchingService.find_similar()` |

### Aggregate Rules

1. **Single root** — Only the aggregate root is referenced externally
2. **Consistency boundary** — Invariants enforced within the aggregate
3. **Transactional boundary** — One aggregate per transaction
4. **Identity equality** — Aggregates compared by ID, not attributes

```python
# Aggregate root with identity equality
@dataclass
class Shootout:
    id: UUID
    title: str
    selections: list[ToneSelection]  # Owned by this aggregate

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Shootout) and self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)
```

---

## 2. CQRS (Command Query Responsibility Segregation)

> "Use a different model to update information than the model you use to read information."
> — Martin Fowler

**Core insight:** Reads and writes have different needs. Separating them allows optimisation of each.

```
┌──────────────┐         ┌──────────────┐
│   Command    │         │    Query     │
│    Model     │         │    Model     │
│              │         │              │
│  Optimised   │         │  Optimised   │
│  for writes  │         │  for reads   │
└──────┬───────┘         └──────┬───────┘
       │                        │
       │    ┌──────────┐        │
       └───►│   Event  │◄───────┘
            │   Store  │
            └──────────┘
```

### When to Apply CQRS

| Apply When | Avoid When |
|------------|------------|
| Read and write models diverge significantly | Simple CRUD operations |
| Different scaling needs for reads vs writes | Low complexity domain |
| Complex reporting requirements | Small team, rapid iteration |
| Event sourcing is beneficial | Consistency requirements are simple |

**Important:** CQRS applies to specific bounded contexts, not entire systems.

### Relationship to Event Sourcing

CQRS pairs naturally with event-based architectures:
- Write model produces events
- Read models consume events as projections
- Enables temporal queries ("state at time T")

---

## 3. Hexagonal Architecture (Ports and Adapters)

> "Allow an application to equally be driven by users, programs, automated test or batch scripts, and to be developed and tested in isolation from its eventual run-time devices and databases."
> — Alistair Cockburn

**Core insight:** Isolate domain logic from infrastructure. The application has an inside (domain) and outside (infrastructure), connected through ports.

### The Hexagon

```
                    Primary Adapters
                   (drive the application)
                          │
            ┌─────────────┼─────────────┐
            │             ▼             │
            │   ┌─────────────────┐     │
   HTTP ────┼──►│                 │     │
   API      │   │     DOMAIN      │     │
            │   │                 │◄────┼──── Database
   CLI ─────┼──►│   (pure logic)  │     │     Adapter
            │   │                 │◄────┼──── External API
   Tests ───┼──►│                 │     │     Adapter
            │   └─────────────────┘     │
            │             ▲             │
            └─────────────┼─────────────┘
                          │
                  Secondary Adapters
                (driven by the application)
```

### Ports and Adapters

| Concept | Definition | Example |
|---------|------------|---------|
| **Port** | Interface defining how to interact with domain | `ShootoutRepository` protocol |
| **Adapter** | Implementation connecting port to infrastructure | `SQLAlchemyShootoutRepository` |
| **Primary Port** | How external actors drive the application | API endpoints, CLI commands |
| **Secondary Port** | How the application drives external systems | Database, external APIs |

### The Critical Rule: Inside vs Outside

```
INSIDE (Domain)              OUTSIDE (Infrastructure)
────────────────             ────────────────────────
- Business rules             - HTTP frameworks
- Entities                   - ORMs
- Value objects              - External APIs
- Domain services            - Message queues
- Port definitions           - File systems

        │
        │  Ports define the boundary
        │  Adapters implement the connection
        ▼
```

**Import direction:** Outside depends on Inside. Never the reverse.

---

## 4. Pythonic Implementation

Following [Cosmic Python](https://www.cosmicpython.com/) patterns.

### Ports: Protocol vs ABC

**Prefer Protocol** (structural typing) for most cases:

```python
# ports/repository.py
from typing import Protocol
from domain.entities import Shootout

class ShootoutRepository(Protocol):
    """Port for shootout persistence."""

    async def get_by_id(self, id: UUID) -> Shootout | None:
        """Retrieve shootout by ID."""
        ...

    async def save(self, shootout: Shootout) -> None:
        """Persist shootout."""
        ...
```

**Use ABC** when you need runtime enforcement or shared implementation:

```python
from abc import ABC, abstractmethod

class OAuthProvider(ABC):
    """Base for OAuth providers with shared token refresh logic."""

    @abstractmethod
    async def get_user_info(self, token: str) -> UserInfo:
        pass

    async def refresh_if_needed(self, tokens: OAuthTokens) -> OAuthTokens:
        """Shared implementation for all providers."""
        if tokens.is_expired:
            return await self._refresh(tokens)
        return tokens
```

### Adapters: One per Infrastructure Concern

```python
# adapters/persistence/shootout_repository.py
from domain.ports import ShootoutRepository
from domain.entities import Shootout

class SQLAlchemyShootoutRepository:
    """Adapter: implements ShootoutRepository port with SQLAlchemy."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, id: UUID) -> Shootout | None:
        stmt = select(ShootoutModel).where(ShootoutModel.id == id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return ShootoutMapper.to_entity(model) if model else None

    async def save(self, shootout: Shootout) -> None:
        model = ShootoutMapper.to_model(shootout)
        self._session.add(model)
        await self._session.flush()
```

### Repository Pattern

> "A simplifying abstraction over data storage, allowing us to decouple our model layer from the data layer."
> — Cosmic Python

```python
# The illusion of an in-memory collection
class AbstractRepository(Protocol[T]):
    """Minimal interface: add and get."""

    async def add(self, entity: T) -> None: ...
    async def get(self, id: UUID) -> T | None: ...

# Fake for testing (trivial to implement)
class FakeShootoutRepository:
    def __init__(self):
        self._shootouts: dict[UUID, Shootout] = {}

    async def add(self, shootout: Shootout) -> None:
        self._shootouts[shootout.id] = shootout

    async def get(self, id: UUID) -> Shootout | None:
        return self._shootouts.get(id)
```

### Unit of Work Pattern

> "An abstraction over atomic operations... either all changes succeed or none persist."
> — Cosmic Python

```python
# Using Python's context manager protocol
class UnitOfWork:
    def __init__(self, session_factory):
        self._session_factory = session_factory

    async def __aenter__(self):
        self._session = self._session_factory()
        self.shootouts = SQLAlchemyShootoutRepository(self._session)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            await self._session.rollback()
        await self._session.close()

    async def commit(self):
        await self._session.commit()

# Usage in service
async def create_shootout(self, data: CreateShootout) -> Shootout:
    async with self._uow:
        shootout = Shootout.create(data)
        await self._uow.shootouts.add(shootout)
        await self._uow.commit()
        return shootout
```

### Service Layer with Dependency Injection

```python
# services/shootout_service.py
class ShootoutService:
    """Orchestrates domain logic. Depends on ports, not adapters."""

    def __init__(
        self,
        repo: ShootoutRepository,      # Port (Protocol)
        job_queue: JobQueuePort,       # Port (Protocol)
    ):
        self._repo = repo
        self._job_queue = job_queue

    async def create_shootout(
        self,
        user_id: UUID,
        data: CreateShootoutData,
    ) -> Shootout:
        """Domain orchestration - no infrastructure knowledge."""
        shootout = Shootout.create(user_id=user_id, title=data.title)

        for tone in data.tones:
            shootout.add_tone(tone)  # Domain logic in entity

        await self._repo.save(shootout)
        await self._job_queue.enqueue(RenderShootoutJob(shootout.id))

        return shootout
```

### Composition Root (Wiring)

```python
# bootstrap.py or api/deps.py
def create_shootout_service(session: AsyncSession) -> ShootoutService:
    """Wire adapters to ports at the composition root."""
    return ShootoutService(
        repo=SQLAlchemyShootoutRepository(session),
        job_queue=TaskIQJobQueue(broker),
    )

# FastAPI dependency
async def get_shootout_service(
    session: AsyncSession = Depends(get_session),
) -> ShootoutService:
    return create_shootout_service(session)
```

---

## 5. SOLID Principles

| Principle | Definition | Verification |
|-----------|------------|--------------|
| **Single Responsibility** | One reason to change | Each adapter handles one provider/concern |
| **Open/Closed** | Open for extension, closed for modification | New adapter = new file, no changes to service |
| **Liskov Substitution** | Subtypes must be substitutable | All adapters return same domain types |
| **Interface Segregation** | Clients shouldn't depend on unused methods | Ports have only methods they need |
| **Dependency Inversion** | Depend on abstractions, not concretions | Services depend on Ports, not Adapters |

### Verification Commands

```bash
# Single Responsibility: Check adapter file count per concern
ls -la backend/app/adapters/persistence/
ls -la backend/app/adapters/external/

# Open/Closed: Adding new adapter shouldn't touch services
git diff --name-only HEAD~5 | grep -E "adapters.*\.py$"

# Dependency Inversion: Services import from ports, not adapters
grep -r "from app.adapters" backend/app/services/
# Should return empty (violation if not)
```

---

## 6. Layer Dependencies

### Import Rules

```
┌─────────────────────────────────────────────────────────┐
│                         API Layer                        │
│            (routes, schemas, dependencies)              │
└───────────────────────────┬─────────────────────────────┘
                            │ imports
                            ▼
┌─────────────────────────────────────────────────────────┐
│                      Service Layer                       │
│              (orchestration, transactions)              │
└───────────────────────────┬─────────────────────────────┘
                            │ imports
              ┌─────────────┴─────────────┐
              ▼                           ▼
┌─────────────────────────┐   ┌─────────────────────────┐
│      Adapter Layer      │   │      Domain Layer       │
│   (implementations)     │   │   (entities, ports)     │
└─────────────────────────┘   └─────────────────────────┘
              │                           ▲
              │         imports           │
              └───────────────────────────┘
```

| Layer | Can Import | Cannot Import |
|-------|------------|---------------|
| **Domain** | Nothing (pure) | Services, Adapters, API, Models |
| **Adapters** | Domain | Services, API |
| **Services** | Domain, Adapters (via DI) | API |
| **API** | Services, Schemas, Domain types | Adapters directly |

### Verification

```bash
# Domain must not import infrastructure
grep -r "from app.services" backend/app/domain/  # Should be empty
grep -r "from app.adapters" backend/app/domain/  # Should be empty
grep -r "from app.models" backend/app/domain/    # Should be empty

# Adapters must not import services
grep -r "from app.services" backend/app/adapters/  # Should be empty
```

---

## 7. Directory Structure

```
backend/app/
├── domain/                    # INSIDE (pure Python)
│   ├── entities/              # Aggregate roots and entities
│   │   ├── shootout.py        # Shootout aggregate
│   │   ├── signal_chain.py    # SignalChain aggregate
│   │   └── user.py            # User aggregate
│   ├── value_objects/         # Immutable domain concepts
│   │   └── tone_selection.py
│   ├── ports/                 # Interface definitions (Protocols)
│   │   └── repositories.py    # Repository protocols
│   ├── events/                # Domain events
│   └── exceptions.py          # Domain exceptions
│
├── services/                  # Application/Use Case layer
│   ├── shootout_service.py    # Shootout orchestration
│   └── auth_service.py        # Auth orchestration
│
├── adapters/                  # OUTSIDE (infrastructure)
│   ├── persistence/           # Database adapters
│   │   ├── shootout_repo.py   # SQLAlchemy implementation
│   │   └── mappers.py         # ORM ↔ Entity conversion
│   ├── external/              # External API adapters
│   │   └── tone3000.py        # T3K API client
│   └── processing/            # Processing adapters
│       └── ffmpeg.py          # Video processing
│
├── api/                       # Primary adapters (HTTP)
│   └── v1/
│       ├── shootouts.py       # Shootout endpoints
│       └── deps.py            # Dependency injection
│
└── models/                    # ORM models (infrastructure)
    └── shootout.py            # SQLAlchemy model
```

---

## 8. Anti-Patterns

| Anti-Pattern | Problem | Correct Pattern |
|--------------|---------|-----------------|
| Domain imports ORM | Couples domain to database | Use mappers in adapters |
| Service creates adapter | Service knows infrastructure | Inject via constructor |
| Adapter calls another adapter | Adapters become coupled | Coordinate in service layer |
| Aggregate references another aggregate | Violates consistency boundary | Use IDs, domain events |
| Business logic in API handler | Logic scattered, untestable | Move to service/entity |
| Repository returns ORM model | Leaks infrastructure to domain | Return domain entity |

---

## 9. Testing Strategy

### Test Pyramid with Hex Architecture

```
                    ┌───────────┐
                    │   E2E     │  Few: Full system via HTTP
                    ├───────────┤
                    │Integration│  Some: Service + real adapters
                    ├───────────┤
                    │   Unit    │  Many: Domain + fake adapters
                    └───────────┘
```

### Testing Each Layer

| Layer | Test Type | Approach |
|-------|-----------|----------|
| **Domain** | Unit | Pure Python, no mocks needed |
| **Services** | Unit | Inject fake adapters |
| **Adapters** | Integration | Real infrastructure (DB, APIs) |
| **API** | Integration | Real service, real/fake adapters |
| **Full System** | E2E | HTTP requests, real everything |

```python
# Unit test with fake adapter
async def test_create_shootout():
    fake_repo = FakeShootoutRepository()
    fake_queue = FakeJobQueue()
    service = ShootoutService(repo=fake_repo, job_queue=fake_queue)

    shootout = await service.create_shootout(user_id=UUID(...), data=...)

    assert await fake_repo.get(shootout.id) is not None
    assert len(fake_queue.jobs) == 1
```

---

## References

- [Domain-Driven Design](https://martinfowler.com/bliki/DomainDrivenDesign.html) — Martin Fowler
- [CQRS](https://martinfowler.com/bliki/CQRS.html) — Martin Fowler
- [Hexagonal Architecture](https://alistair.cockburn.us/hexagonal-architecture/) — Alistair Cockburn
- [Cosmic Python](https://www.cosmicpython.com/) — Harry Percival & Bob Gregory
- [Architecture Patterns with Python](https://www.oreilly.com/library/view/architecture-patterns-with/9781492052197/) — O'Reilly

---

## GTS-Specific

For GTS implementation details:
- **Aggregates & Contexts:** See `DEVELOPMENT.md` Section "Domain Architecture"
- **Current Structure:** See `.planning/codebase/ARCHITECTURE.md`
- **Verification:** See `/codebase-review --section=architecture`
