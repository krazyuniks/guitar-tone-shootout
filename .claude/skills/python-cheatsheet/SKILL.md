---
name: python-cheatsheet
description: Quick reference mapping global architecture concepts to Python/FastAPI/SQLAlchemy syntax. For concepts, see the global skills.
---

# Python Cheatsheet

Quick reference for mapping global architecture concepts to Python implementation.

## Global → Python Mapping

| Global Skill | Python Implementation |
|--------------|----------------------|
| service-patterns | Service classes, Depends() |
| repository-patterns | SQLAlchemy 2.0, Protocol classes |
| error-handling | Custom exceptions, HTTPException |
| web-handlers | FastAPI routes, Annotated[T, Depends()] |

---

## Service Patterns (Python)

**See:** `gts-backend-dev` for full details, `service-patterns` (global) for concepts

Quick reference:

```python
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

**Dependency injection (composition root):**

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

## Repository Patterns (Python)

**See:** `gts-backend-dev` for full details, `repository-patterns` (global) for concepts

### Protocol-based ports (preferred):

```python
from typing import Protocol
from uuid import UUID

class ShootoutRepository(Protocol):
    """Port for shootout persistence."""

    async def get_by_id(self, id: UUID) -> Shootout | None:
        """Retrieve shootout by ID."""
        ...

    async def save(self, shootout: Shootout) -> None:
        """Persist shootout."""
        ...
```

### SQLAlchemy 2.0 adapter:

```python
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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

### SQLAlchemy 2.0 models (typed):

```python
from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    tone3000_id: Mapped[int] = mapped_column(unique=True, index=True)
    username: Mapped[str] = mapped_column(String(100))

    # Relationships
    shootouts: Mapped[list["Shootout"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan"
    )

class Shootout(Base):
    __tablename__ = "shootouts"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(200))
    config_json: Mapped[str] = mapped_column(Text)

    user: Mapped["User"] = relationship(back_populates="shootouts")
```

### Queries:

```python
from sqlalchemy import select
from sqlalchemy.orm import selectinload

# Get with eager loading
stmt = (
    select(Shootout)
    .where(Shootout.user_id == user_id)
    .options(selectinload(Shootout.jobs))
    .order_by(Shootout.created_at.desc())
)
result = await db.execute(stmt)
shootouts = result.scalars().all()

# Pagination
stmt = (
    select(Shootout)
    .offset(skip)
    .limit(limit)
)
```

---

## Error Handling (Python)

**See:** `error-handling` (global) for concepts

### Custom exceptions:

```python
class AppError(Exception):
    """Base application error."""

class NotFoundError(AppError):
    """Resource not found."""

class UnauthorizedError(AppError):
    """User not authorised."""
```

### FastAPI error handling:

```python
from fastapi import HTTPException, status

@router.get("/{id}")
async def get_item(id: int, db: AsyncSession = Depends(get_db)):
    item = await db.get(Item, id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Item {id} not found"
        )
    return item
```

---

## Web Handlers (Python)

**See:** `gts-backend-dev` for full details, `web-handlers` (global) for concepts

### FastAPI route pattern:

```python
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/shootouts", tags=["shootouts"])

@router.get("/{shootout_id}", response_model=ShootoutRead)
async def get_shootout(
    shootout_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Shootout:
    """Get a shootout by ID."""
    shootout = await db.get(Shootout, shootout_id)
    if not shootout or shootout.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shootout not found"
        )
    return shootout
```

### Pydantic schemas:

```python
from pydantic import BaseModel, ConfigDict

class ShootoutBase(BaseModel):
    title: str
    config_json: str

class ShootoutCreate(ShootoutBase):
    pass

class ShootoutRead(ShootoutBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
```

---

## Transaction Patterns (CRITICAL)

**See:** `gts-backend-dev` Section "Transactions" for full details

### Service layer transaction ownership:

```python
# In services (gear_item_service.py, signal_chain_service.py, etc.)
context_manager = (
    session.begin_nested() if session.in_transaction() else session.begin()
)
async with context_manager:
    # ... do work, add(), flush() ...
# Savepoint released (if nested) or committed (if begin)
```

**The Contract:**
- `in_transaction()=False` → Service owns commit via `begin()`
- `in_transaction()=True` → **Caller must commit** (service uses savepoint)

**Common Pitfall:** Pre-check queries start implicit transactions:

```python
# API endpoint
@router.post("/items")
async def create_item(db: DbSession, ...):
    # This query starts an implicit transaction!
    existing = await db.execute(select(Item).where(...))

    # Service sees in_transaction()=True, uses begin_nested()
    item = await service.create_item(...)

    # BUG: Without this, changes are never committed!
    await db.commit()  # ← REQUIRED when API queried before service call

    return item
```

**Rules:**
1. If API does ANY query before calling a write service → must `await db.commit()` after
2. If API only calls service (no pre-queries) → service handles commit via `begin()`
3. Service-to-service calls → outer service owns commit, inner uses savepoint

---

## Dependency Injection (FastAPI)

```python
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import async_session_maker

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise

async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Decode JWT and return current user."""
    payload = decode_token(token)
    user = await db.execute(
        select(User).where(User.tone3000_id == payload["sub"])
    )
    user = user.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user
```

---

## Background Tasks (TaskIQ)

```python
from taskiq import TaskiqScheduler
from taskiq_redis import ListQueueBroker, RedisAsyncResultBackend

broker = ListQueueBroker(url="redis://redis:6379")
broker.with_result_backend(RedisAsyncResultBackend(redis_url="redis://redis:6379"))

@broker.task
async def process_shootout(job_id: str, shootout_id: int) -> str:
    """Process a shootout through the pipeline."""
    await update_job_status(job_id, "running", progress=0)

    # Process...
    await update_job_status(job_id, "running", progress=50)

    await update_job_status(job_id, "completed", progress=100)
    return output_path
```

---

## Migrations (Alembic)

```bash
# Create migration
docker compose exec backend alembic revision --autogenerate -m "add jobs table"

# Apply migrations
docker compose exec backend alembic upgrade head

# Rollback
docker compose exec backend alembic downgrade -1
```

---

## Code Quality

### Commands

```bash
# Lint (check only)
docker compose exec backend ruff check app/

# Lint (auto-fix)
docker compose exec backend ruff check --fix app/

# Type check
docker compose exec backend mypy app/

# Test
docker compose exec backend pytest tests/

# All checks
just check-backend
```

### You Must Get Right (can't auto-fix)

| Requirement | Enforced By | Notes |
|-------------|-------------|-------|
| Type hints on all functions | mypy strict | Can't add them for you |
| snake_case functions/variables | ruff N | Can detect but not rename semantically |
| PascalCase for classes | ruff N | Can detect but not rename semantically |
| pytest conventions | ruff PT | `test_` prefix, fixtures via conftest.py |
| ClassVar for mutable class attrs | ruff RUF012 | `ClassVar[dict[...]]` for class-level dicts |

---

## Related Skills

### Project-Specific
- `gts-backend-dev` - Full FastAPI/SQLAlchemy documentation
- `gts-frontend-dev` - Astro frontend patterns
- `gts-testing` - Testing patterns specific to GTS

### Global (Architecture Concepts)
- `service-patterns` - Service layer concepts
- `repository-patterns` - Repository abstraction concepts
- `error-handling` - Error handling concepts
- `web-handlers` - HTTP handler concepts
