---
description: Run quality gates (lint, types, tests) for backend, frontend, or all.
allowed-tools: Bash(just:*), Bash(docker compose exec:*)
argument-hint: "[backend|frontend|pipeline|all]"
context: fork
model: haiku
---

# /check - Run Quality Gates

Run all quality checks for the specified component or entire project.

## Usage

```
/check              # All checks
/check backend      # Backend only
/check frontend     # Frontend only
/check pipeline     # Pipeline only
```

## Commands

### All Checks
```bash
just check
```

### Backend Only
```bash
docker compose exec backend ruff check app/
docker compose exec backend mypy app/
docker compose exec backend pytest /tests/unit/backend/ /tests/integration/backend/ -v
```

### Frontend Only
```bash
docker compose exec astro pnpm lint
docker compose exec astro pnpm check
just build-astro  # Backend auto-reloads templates
```

### Pipeline Only
```bash
cd pipeline && just check
```

## Error Handling

If checks fail:
1. Report which checks failed
2. Show relevant error messages
3. Offer to fix issues automatically
4. Re-run checks after fixes

## Quality Standards

| Component | Lint | Types | Tests |
|-----------|------|-------|-------|
| Backend | ruff | mypy | pytest |
| Frontend | eslint | tsc | vitest |
| Pipeline | ruff | mypy | pytest |
