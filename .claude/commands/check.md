# /check - Run Quality Gates

Run all quality checks for the specified component or entire project.

## Workflow

1. **Identify target** from argument or detect from recent changes
2. **Run appropriate checks** based on target
3. **Report results** clearly
4. **Suggest fixes** if issues found

## Commands

### All Checks
```bash
just check
```

### Backend Only
```bash
docker compose exec backend ruff check app/
docker compose exec backend mypy app/
docker compose exec backend pytest tests/ -v
```

### Frontend Only
```bash
docker compose exec frontend pnpm lint
docker compose exec frontend pnpm tsc --noEmit
docker compose exec frontend pnpm build
```

### Pipeline Only
```bash
cd pipeline && just check
# Or: uv run ruff check && uv run mypy && uv run pytest
```

## Usage

```
User: /check
Claude: [Runs all checks, reports results]

User: /check backend
Claude: [Runs backend checks only]

User: /check frontend
Claude: [Runs frontend checks only]

User: /check pipeline
Claude: [Runs pipeline checks only]
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
| Frontend | eslint | tsc | (vitest) |
| Pipeline | ruff | mypy | pytest |

## Pre-PR Checklist

Before creating a PR, ensure:
- [ ] All linting passes
- [ ] Type checking passes
- [ ] Tests pass
- [ ] Build succeeds (frontend)
