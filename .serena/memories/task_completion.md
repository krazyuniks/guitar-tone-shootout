# Task Completion Checklist

Before considering any task complete:

1. **Run quality gates**: `just check` (lint + types + tests)
2. **Run golden path** (if behaviour changed): `just test-golden-path`
3. **Verify Astro sync** (if frontend changed): `just verify-astro-sync`
4. **Check import rules**: `just check-imports`
5. **Commit with conventional format**: `type(scope): description`
6. **Push to remote**: `git push` (MANDATORY — work isn't done until pushed)
7. **Update GitHub issue status** if applicable

## Commit Types
feat, fix, docs, style, refactor, perf, test, build, ci, chore

## Critical Rules
- Never commit to main directly
- All test/lint commands run in Docker via `just`
- GitHub CLI needs `--repo krazyuniks/guitar-tone-shootout`
- E2E tests run on HOST, not Docker
