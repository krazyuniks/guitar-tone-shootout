# Coding Conventions

**Analysis Date:** 2026-02-05

## Naming Patterns

**Files:**
- Python modules: `snake_case.py` (e.g., `signal_chain_validator.py`)
- Test files: `test_{module_name}.py` (e.g., `test_user_model.py`)
- Config files: lowercase with underscores (e.g., `pyproject.toml`)
- Classes: `PascalCase` (e.g., `SignalChainValidator`, `UserRepository`)
- Domain exceptions: `DescriptivePascalCase` (e.g., `InvalidStateTransitionError`, `MaxChainsExceededError`)

**Functions:**
- All functions: `snake_case` (e.g., `validate`, `get_by_id`, `extract_waveform`)
- Private methods: `_snake_case` prefix (e.g., `_to_entity`, `_transition_to`)
- Class methods: `@classmethod def create_with_identity(...)` pattern
- Async functions: `async def function_name(...)` (no special prefix)

**Variables:**
- Module-level constants: `UPPER_CASE` (e.g., `_SUPPORTED_FORMATS`)
- Instance/local variables: `snake_case` (e.g., `user_id`, `db_session`)
- Loop variables: descriptive `snake_case` (e.g., `for identity in user.identities:`)
- Private attributes: prefix with underscore only if truly internal (rare)

**Types:**
- Domain entities: `ClassName` (e.g., `User`, `Job`, `SignalChain`)
- Value objects: `DescriptiveClassName` (e.g., `UserIdentity`, `ValidationError`, `JobStatus`)
- ORM models: `ClassName` (matching domain, e.g., `User` for ORM user model)
- Exception classes: `DescriptiveError` or `DescriptiveException` suffix (e.g., `JobError`, `ProcessingError`)
- Enums: `CapitalizedEnum` (e.g., `JobStatus`, `GearType`, `ValidationRule`)

## Code Style

**Formatting:**
- Tool: `ruff` (formatter and linter combined)
- Line length: 100 characters
- Quotes: Double quotes `"string"` (ruff default)
- Indentation: 4 spaces
- Type hints: Required on all function signatures (enforced by mypy strict mode)

**Linting:**
- Tool: `ruff` (Python linter)
- Config: `pyproject.toml` under `[tool.ruff]`
- Enabled rules: E (errors), W (warnings), F (Pyflakes), I (isort), B (bugbear), C4 (comprehensions), UP (pyupgrade), ARG (unused args), SIM (simplify), TCH (type checking), PTH (pathlib), RUF (ruff-specific)
- Ignored: E501 (handled by formatter), B008 (FastAPI Depends), B904 (raise from), ARG001 (unused args in protocols)

**Type Checking:**
- Tool: `mypy`
- Mode: Strict mode enabled
- Config: `pyproject.toml` under `[tool.mypy]`
- All functions must have explicit return types
- No implicit Optional types
- Untyped library overrides in `[[tool.mypy.overrides]]` for external packages (pedalboard, nam, torch, etc.)

## Import Organization

**Order:**
1. `from __future__ import annotations` (always first for forward references)
2. Standard library (e.g., `from datetime import datetime`, `from pathlib import Path`)
3. Third-party (e.g., `from sqlalchemy import ...`, `from fastapi import ...`)
4. Local first-party (e.g., `from core.domain.entities.user import User`)
5. TYPE_CHECKING block with lazy imports (e.g., `if TYPE_CHECKING: from sqlalchemy.ext.asyncio import AsyncSession`)

**Path Aliases:**
- First-party packages configured in ruff isort: `["core", "audio", "source_t3k", "webapp", "worker", "scheduler"]`
- All imports use absolute paths from workspace root (e.g., `from core.domain.entities.user import User`, never relative imports)

**Example pattern:**
```python
"""Module docstring."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from core.domain.entities.user import User as UserEntity
from core.domain.entities.user import UserIdentity as UserIdentityVO
from webapp.adapters.persistence.models.user import User, UserIdentity

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
```

## Error Handling

**Patterns:**
- Domain exceptions are custom classes inheriting from base domain exception (e.g., `JobError`, `ShootoutError`)
- Custom exceptions include docstring explaining when they're raised
- Domain layer raises domain-specific exceptions (e.g., `InvalidStateTransitionError`)
- Repository/adapter layer propagates or wraps domain exceptions
- FastAPI/webapp layer catches exceptions and converts to HTTP responses
- All exceptions include descriptive messages with context (e.g., `f"Cannot transition from {self.status.value} to {new_status.value}"`)

**Exception hierarchy example:**
```python
class JobError(Exception):
    """Base exception for Job domain errors."""
    pass

class InvalidStateTransitionError(JobError):
    """Raised when an invalid state transition is attempted."""
    pass
```

**State validation pattern:**
```python
def _transition_to(self, new_status: JobStatus) -> None:
    """Validate and execute a status transition.

    Args:
        new_status: The status to transition to

    Raises:
        InvalidStateTransitionError: If the transition is not valid
    """
    if not self.status.can_transition_to(new_status):
        raise InvalidStateTransitionError(
            f"Cannot transition from {self.status.value} to {new_status.value}"
        )
```

## Logging

**Framework:** Standard library `logging` (not explicitly configured in codebase, uses defaults)

**Patterns:**
- Logging not heavily used in domain layer (pure functions preferred)
- Critical errors logged at adapter/application layer
- Structured logging deferred to future expansion
- No logging in unit tests unless debugging

## Comments

**When to Comment:**
- Complex business logic that isn't self-evident
- Grammar rules and validation constraints (e.g., signal chain grammar in `SignalChainValidator`)
- Workarounds or non-obvious decisions
- State machine transitions with validation rules
- Data transformation logic between domain and ORM models

**JSDoc/TSDoc/Docstrings:**
- All public classes: `"""Descriptive docstring with Attributes and usage."""`
- All public functions: `"""What it does. Args: ... Returns: ... Raises: ..."""`
- All methods: Include purpose, parameters, return type, exceptions
- Private methods: Docstring if logic is non-obvious
- Module-level: File-level docstring explaining module purpose
- No docstrings for trivial getters/setters unless adding significant value

**Example docstring:**
```python
class SignalChainValidator:
    """Service for validating signal chain compositions.

    Signal Chain Grammar:
        [PrePedals*] -> AmpBlock -> [IRBlock?] -> [PostEffects*]

    Validation rules:
        - NO_AMP: Chain must have exactly one amp block
        - MULTIPLE_AMPS: Only one amp allowed
        - IR_REQUIRED: Head amp requires IR block
    """

    def validate(self, chain: SignalChain) -> ValidationResult:
        """Validate a signal chain against grammar rules.

        Args:
            chain: The signal chain to validate

        Returns:
            ValidationResult with is_valid and any errors
        """
```

## Function Design

**Size:**
- Prefer functions under 50 lines
- Complex logic broken into helper functions with clear names
- Repository methods often longer due to query building (acceptable)

**Parameters:**
- Prefer explicit parameters over **kwargs
- Type hints required for all parameters
- Default arguments only for optional values
- Use keyword-only arguments for clarity when function has many parameters (`def method(self, required, *, optional=None)`)
- Async functions use same parameter conventions as sync

**Return Values:**
- All functions must declare return type (mypy strict)
- Return `X | None` instead of `Optional[X]`
- Domain methods return domain objects, repositories return entities
- Repository queries return `T | None` for single objects, `list[T]` for collections

**Example pattern:**
```python
async def get_by_id(self, user_id: UUID) -> UserEntity | None:
    """Get a user by their ID.

    Args:
        user_id: The user's UUID

    Returns:
        The User entity if found, None otherwise
    """
    stmt = select(User).where(User.id == user_id)
    result = await self.session.execute(stmt)
    user = result.scalar_one_or_none()
    return self._to_entity(user) if user else None
```

## Module Design

**Exports:**
- Modules export public classes and functions in `__init__.py`
- Private modules (starting with `_`) are implementation details
- Each layer has clear boundary: domain exports entities/value objects, adapters export implementations

**Barrel Files:**
- Use `__init__.py` for public API of packages
- Domain packages export entities: `from core.domain.entities.user import User, UserIdentity`
- Do not use star imports: always explicit `from X import Y`

**Example structure:**
```
libs/core/src/core/
├── domain/
│   ├── entities/
│   │   ├── __init__.py  # exports User, Job, SignalChain, etc.
│   │   ├── user.py
│   │   └── job.py
│   └── value_objects/
│       ├── __init__.py  # exports JobStatus, JobType, etc.
│       └── job_status.py
├── services/
│   ├── __init__.py  # exports validation/processing services
│   └── signal_chain_validator.py
└── ports/
    └── __init__.py  # exports protocols for dependency injection
```

## Dataclasses and Frozen Objects

**Patterns:**
- Domain entities: `@dataclass(eq=False, slots=True)` (identity-based equality, optimized)
- Value objects: `@dataclass(frozen=True, slots=True)` (immutable, hashable)
- ORM models: SQLAlchemy declarative, not dataclasses
- Attributes in dataclasses: declare with type hints and defaults

**Example:**
```python
@dataclass(frozen=True, slots=True)
class UserIdentity:
    """Value object representing an external identity link."""
    provider: str
    external_id: str
    username: str
    avatar_url: str | None = None
```

## Async Conventions

**All async patterns:**
- Repositories: All methods are `async def` even for simple lookups
- Type annotations: Use `AsyncSession`, `AsyncEngine` from `sqlalchemy.ext.asyncio`
- Session management: Use `async with session.begin():` for transactions
- No blocking I/O in async functions
- Fixtures marked with `@pytest.fixture` and return type `AsyncGenerator[T, None]`

**Repository transaction pattern:**
```python
async with session.begin():
    # Multiple operations in transaction
    await repo.save(entity)
    # Auto-rollback on exception, auto-commit on exit
```

## Dependency Injection and Protocols

**Ports/Adapters pattern:**
- Protocols defined in `core.ports` (not yet visible in codebase, follows hexagonal architecture)
- Implementations in `webapp.adapters` (SQLAlchemy, etc.)
- Services accept injected adapters via constructor
- FastAPI uses `Depends()` for injection

**Example (future pattern):**
```python
class UserService:
    def __init__(self, repo: UserRepository):  # Protocol type
        self.repo = repo

    async def create_user(self, identity: UserIdentity) -> User:
        user = User.create_with_identity(identity)
        await self.repo.save(user)
        return user
```

---

*Convention analysis: 2026-02-05*
