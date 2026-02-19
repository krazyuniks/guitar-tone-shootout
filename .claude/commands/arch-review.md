---
description: Architecture review of code changes or specific component.
allowed-tools: Read, Grep, Glob
argument-hint: "[path|--full]"
context: fork
---

# /arch-review - Architecture Review

Perform an architecture review of code changes or a specific component.

**Foundation:** Load `gts-architecture` skill for pattern reference.

---

## Workflow

1. **Identify scope** from argument or recent changes
2. **Load architectural context** from `gts-architecture` skill
3. **Analyze patterns** against project standards
4. **Check for violations**: layer boundaries, SOLID principles, DDD patterns
5. **Generate report** with findings and recommendations

---

## Architecture Principles

### Layer Dependencies (Hex Architecture)

```
API Layer → Service Layer → Domain Layer
                ↓
           Adapter Layer → Domain Layer
```

| Layer | Can Import | Cannot Import |
|-------|------------|---------------|
| **Domain** | Nothing | Services, Adapters, API, Models |
| **Adapters** | Domain | Services, API |
| **Services** | Domain, Adapters (via DI) | API |
| **API** | Services, Schemas | Adapters directly |

### SOLID Verification

| Principle | Check |
|-----------|-------|
| **SRP** | Each class has one reason to change |
| **OCP** | New functionality = new adapter, not modified service |
| **LSP** | All adapters return same domain types |
| **ISP** | Ports have only methods needed by consumers |
| **DIP** | Services depend on Ports (Protocol), not Adapters |

### DDD Patterns

| Pattern | Verification |
|---------|--------------|
| **Aggregate boundaries** | Only root referenced externally |
| **Entity identity** | `__eq__` and `__hash__` by ID |
| **Value object immutability** | `@dataclass(frozen=True)` |
| **Repository abstraction** | Protocol in domain/ports/, implementation in adapters/ |
| **Ubiquitous language** | Domain terms match business vocabulary |

---

## Review Checklist

### Backend (FastAPI + SQLAlchemy)

**Layer Compliance:**
- [ ] Domain has no imports from services, adapters, models, or API
- [ ] Adapters have no imports from services or API
- [ ] Services depend on Ports (Protocol), not concrete Adapters
- [ ] API handlers delegate to services (thin controllers)

**DDD Patterns:**
- [ ] Aggregates have identity equality (`__eq__`, `__hash__`)
- [ ] Repositories return domain entities, not ORM models
- [ ] Mappers convert ORM ↔ Entity in adapter layer
- [ ] Domain events for cross-aggregate communication

**Transaction Ownership:**
- [ ] Services own transactions (`async with session.begin():`)
- [ ] Adapters use `flush()`, not `commit()`
- [ ] One aggregate per transaction

**Code Patterns:**
- [ ] SQLAlchemy 2.0 patterns (`Mapped`, `mapped_column`)
- [ ] Pydantic schemas for request/response
- [ ] Async/await used consistently
- [ ] Type hints on all functions

### Frontend (Astro + Jinja2 + HTMX)

- [ ] Astro pages are pre-built at build time (SSG, no runtime Vite)
- [ ] Jinja2 templates (SSR) extend Astro-built base layout
- [ ] HTMX for small fragment updates (card-sized or smaller, not large page sections)
- [ ] Alpine.js for client-side UI state (toggles, tabs, modals)
- [ ] React islands only for complex stateful components (SignalChainBuilder)
- [ ] `data-testid` on all interactive elements

### Cross-Cutting

- [ ] No secrets in code
- [ ] Error handling with domain exceptions
- [ ] Tests for new functionality
- [ ] Documentation for public APIs

---

## Verification Commands

```bash
# Core isolation (libs/core should have no framework imports)
grep -r "sqlalchemy\|fastapi\|redis" libs/core/

# Import boundary violations (use import-linter for full check)
uv run lint-imports

# Aggregate identity equality
grep -n "__eq__\|__hash__" libs/core/src/core/domain/entities/*.py

# Transaction ownership in webapp services
grep -rn "session.begin()" apps/webapp/src/webapp/services/  # Should exist
grep -rn "\.commit()" apps/webapp/src/webapp/adapters/       # Should be empty
```

---

## Usage

```bash
/arch-review                    # Review recent changes
/arch-review apps/webapp/       # Review specific directory
/arch-review libs/core/         # Review core domain
/arch-review --full             # Full project review
```

---

## Reference

- **Patterns:** `gts-architecture` skill
- **GTS Implementation:** `.planning/codebase/ARCHITECTURE.md`
- **Automated Audit:** `/codebase-review --section=architecture`
