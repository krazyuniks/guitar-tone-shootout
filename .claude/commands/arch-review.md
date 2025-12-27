# /arch-review - Architecture Review

Perform an architecture review of code changes or a specific component.

## Workflow

1. **Identify scope** from argument or recent changes
2. **Analyze patterns** against project standards
3. **Check for issues**:
   - Architecture violations
   - Security concerns
   - Performance issues
   - Missing error handling
4. **Generate report** with findings and recommendations

## Review Checklist

### Backend (FastAPI + SQLAlchemy)

- [ ] Routes are thin, delegate to services
- [ ] SQLAlchemy 2.0 patterns (Mapped, mapped_column)
- [ ] Pydantic schemas for request/response
- [ ] Proper dependency injection
- [ ] Async/await used consistently
- [ ] Error handling with HTTPException
- [ ] Type hints on all functions
- [ ] No N+1 query issues

### Frontend (Astro + React)

- [ ] Astro pages with minimal client JS
- [ ] React islands with proper hydration directive
- [ ] TypeScript interfaces for props
- [ ] Tailwind utility classes (no custom CSS)
- [ ] API calls in lib/ modules
- [ ] Proper error boundaries

### General

- [ ] No secrets in code
- [ ] Logging instead of print()
- [ ] pathlib.Path for file operations
- [ ] Tests for new functionality
- [ ] Documentation for public APIs

## Report Template

```markdown
## Architecture Review: [Scope]

**Date:** [Date]
**Files Reviewed:** [Count]

### Summary

[Brief overview of findings]

### Issues Found

#### Critical
- [ ] Issue 1 (file:line)

#### Warnings
- [ ] Issue 2 (file:line)

#### Suggestions
- [ ] Improvement 1

### Recommendations

1. [Recommendation]
2. [Recommendation]

### Patterns Verified
- [x] Pattern 1
- [x] Pattern 2
```

## Usage

```
User: /arch-review
Claude: [Reviews recent changes]

User: /arch-review backend/app/api/
Claude: [Reviews specific directory]

User: /arch-review --full
Claude: [Full project review]
```
