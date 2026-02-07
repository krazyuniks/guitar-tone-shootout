# Query Pattern Rules

## Hard Constraints

- **NEVER use `selectinload`**, `subqueryload`, or `lazyload` in repository queries. These fire separate queries per relationship.
- **ALWAYS use `joinedload`** for eager loading. Single SQL query via LEFT OUTER JOIN.
- **ALWAYS call `.unique()`** on results when using `joinedload` with collections (1:N, M:N). JOINs produce duplicate parent rows that must be de-duplicated.
- **Model-level `lazy="raise"` on ALL relationships.** Prevents implicit lazy loading; forces explicit `joinedload()` in every repository query.
- **NEVER use `lazy="selectin"`, `lazy="select"`, or `lazy="subquery"`** at the model level.
- **One query per service method.** Each service call (page impression, API request) should execute a single aggregate-loading query via the repository.

## Banned Patterns

```python
# BANNED — model-level eager loading (fires separate queries)
models: Mapped[list[GearModel]] = relationship(..., lazy="selectin")
user: Mapped[User] = relationship(..., lazy="selectin")

# BANNED — default lazy loading (fires query on attribute access)
models: Mapped[list[GearModel]] = relationship(...)  # no lazy= = lazy="select"

# BANNED — repository-level selectinload
from sqlalchemy.orm import selectinload
stmt = select(Gear).options(selectinload(Gear.models))  # separate query
```

## Required Patterns

### ORM Model Relationships

```python
# CORRECT — forces explicit eager loading in repositories
models: Mapped[list[GearModel]] = relationship(
    "GearModel", back_populates="gear",
    cascade="all, delete-orphan",
    lazy="raise",
)
make: Mapped[GearMake | None] = relationship(
    "GearMake", back_populates="gear_items",
    lazy="raise",
)
```

### Repository Queries — Single Entity

```python
from sqlalchemy.orm import joinedload

stmt = (
    select(Gear)
    .where(Gear.id == gear_id)
    .options(
        joinedload(Gear.make),      # scalar (N:1)
        joinedload(Gear.source),    # scalar (1:1)
        joinedload(Gear.models),    # collection (1:N)
        joinedload(Gear.tags),      # collection (M:N)
    )
)
result = await self.session.execute(stmt)
gear = result.unique().scalar_one_or_none()  # .unique() REQUIRED
```

### Repository Queries — Paginated Lists

LIMIT/OFFSET with `joinedload` on collections limits **rows**, not **entities**. Use an ID subquery to paginate correctly:

```python
# Step 1: resolve the correct page of IDs
id_stmt = (
    select(Gear.id)
    .where(Gear.is_public.is_(True))
    .order_by(Gear.name)
    .limit(50)
    .offset(0)
)

# Step 2: hydrate those IDs with full JOINs
stmt = (
    select(Gear)
    .where(Gear.id.in_(id_stmt))
    .options(
        joinedload(Gear.make),
        joinedload(Gear.source),
        joinedload(Gear.models),
        joinedload(Gear.tags),
    )
    .order_by(Gear.name)
)
result = await self.session.execute(stmt)
items = result.unique().scalars().all()
```

### Chained Relationships

For nested relationships, chain `joinedload`:

```python
# User → identities → provider in ONE query
stmt = (
    select(User)
    .where(User.id == user_id)
    .options(
        joinedload(User.identities).joinedload(UserIdentity.provider)
    )
)
result = await self.session.execute(stmt)
user = result.unique().scalar_one_or_none()
```

## Why This Matters

| Strategy | Queries | Mechanism |
|----------|---------|-----------|
| `lazy="select"` (default) | N+1 | Fires query on attribute access |
| `selectinload()` | 1 + R | One extra SELECT per relationship |
| `subqueryload()` | 1 + R | One extra subquery per relationship |
| **`joinedload()`** | **1** | **Single query via LEFT OUTER JOIN** |

For a Gear aggregate with 4 relationships:
- `selectinload` = 5 queries (1 + 4 relationships)
- `joinedload` = 1 query

## Service Layer Responsibility

Services orchestrate use cases. Each service method results in a single aggregate query:

```python
class GearService:
    async def get_by_id(self, gear_id: UUID) -> Gear | None:
        # Repository fires ONE query with all JOINs
        return await self.repository.get_by_id(gear_id)
```

The repository builds the complete JOIN tree. The service trusts the repository to return fully-hydrated aggregates.
