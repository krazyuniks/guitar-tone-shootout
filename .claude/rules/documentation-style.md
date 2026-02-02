# Documentation Style Rules

## Core Principle: Declarative, Not Historical

Documentation describes the **current state** and **prescribed methodology**. It is a reference for what to do NOW, not a changelog.

### What This Means

| Do | Don't |
|----|-------|
| "Use X for this purpose" | "We used to use Y, but now we use X" |
| "Pattern: [code]" | "The old pattern was [code], the new pattern is [code]" |
| "Rationale: [reason]" | "We changed this because the old way had problems with..." |

### Examples

**BAD - Historical narrative:**
```markdown
## Authentication

Previously, we used session-based auth with cookies. However, this caused
issues with mobile clients, so we migrated to JWT tokens in Q3 2024.
The old session code still exists in `legacy/` but is deprecated.

Now we use JWT tokens stored in localStorage...
```

**GOOD - Declarative:**
```markdown
## Authentication

Use JWT tokens for all authentication.

**Storage:** localStorage (web), SecureStorage (mobile)
**Expiry:** 7 days, auto-refresh at 24h remaining

Rationale: Stateless auth enables horizontal scaling and cross-platform consistency.
```

### Rationale Section

It IS appropriate to explain **why** a choice was made. Frame it as:
- "Rationale: [benefit]" - Why this approach is good
- NOT: "We changed because [old problem]" - Why the old way was bad

### When Updating Documentation

1. **Replace** outdated content entirely
2. **Don't** add "Updated:" or "Changed:" annotations
3. **Don't** keep old content "for reference"
4. **Do** use git history if historical context is needed

### Migration Notes Exception

For **active migrations** only, a temporary note is acceptable:

```markdown
> **Migration (remove after 2025-03-01):**
> API v1 endpoints deprecated. Use v2.
```

Remove these notes after the migration completes.

## Structure Principles

### Be Scannable
- Use tables for reference data
- Use headers for navigation
- Lead with the most important information

### Be Complete
- Include working examples (copy-paste ready)
- Cover common use cases
- Provide escape hatches for exceptions

### Be Minimal
- One way to do things (not multiple options)
- No redundant explanations
- Remove outdated content entirely
