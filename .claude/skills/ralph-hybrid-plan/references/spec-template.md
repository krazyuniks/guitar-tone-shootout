# Spec.md Template and Examples

## Template

```markdown
---
created: {ISO-8601 timestamp}
github_issue: {number or null}
---

# {Feature Title}

<!-- If from GitHub issue: -->
> **Source:** GitHub issue #{number} - {issue title}
> **Link:** https://github.com/{owner}/{repo}/issues/{number}

## Problem Statement

{1-2 paragraphs describing the problem this feature solves}
{If from issue, start with that description}

## Success Criteria

- [ ] {High-level criterion 1}
- [ ] {High-level criterion 2}
- [ ] {High-level criterion 3}

## Execution Guidelines

### Test-Driven Development (MANDATORY)

**Every story MUST follow Red-Green-Refactor:**

1. **RED - Write failing tests FIRST**
   - Before writing ANY implementation code, write tests for the story's acceptance criteria
   - Run the tests - they MUST fail (if they pass, you're not testing new behaviour)
   - These tests ARE your feature validation - they prove the feature works

2. **GREEN - Implement to pass**
   - Write the minimum code to make your tests pass
   - Run tests frequently during implementation
   - Stop when tests pass - don't add extras

3. **REFACTOR - Clean up (if needed)**
   - Improve code quality while keeping tests green
   - Run tests after each change

**For UI/browser stories:**
- Write Playwright/E2E tests for UI behaviour
- Tests CAN verify up to external service boundaries (e.g., OAuth redirects to IdP login page)
- You CANNOT test past external login (no real user credentials)
- Manual testing with real accounts happens AFTER ralph completes

**Important distinction:**
- **TDD tests** (you write): Validate the NEW feature works
- **Regression command** (runs automatically): Checks EXISTING tests still pass

### Background Agents

Use the Task tool with `run_in_background: true` for parallel work:

1. **Background agents for independent work:**
   - `Explore` agent - Codebase research, finding related files/patterns
   - `Bash` agent - Running tests, builds, type checks in background
   - `general-purpose` agent - Complex multi-step research tasks

2. **When to use background agents:**
   - Long-running tests while you continue implementing
   - Searching large codebases for patterns
   - Build/typecheck validation while moving to next file
   - Exploring multiple subsystems in parallel

## User Stories

### STORY-001: {Story Title}

**As a** {user type}
**I want to** {goal}
**So that** {benefit}

**Acceptance Criteria:**
- [ ] {Specific, testable criterion}
- [ ] {Specific, testable criterion}
- [ ] Typecheck passes
- [ ] Unit tests pass

**Technical Notes:**
- {Implementation hint}

### STORY-002: {Story Title}
...

## Must-Haves (Derived from Goals)

### Observable Truths
- [User-facing capability 1]
- [User-facing capability 2]

### Required Artifacts
| Artifact | Purpose | Min Lines |
|----------|---------|-----------|
| path/to/file.ext | description | N |

### Key Wiring
| From | To | Via |
|------|----|----|
| Component A | Component B | mechanism |

## Out of Scope

- {Feature/capability explicitly excluded}
- {Related work for future}

## Open Questions

- {Unresolved question needing decision}
```

## Acceptance Criteria Rules

**Required for ALL stories:**
- `Typecheck passes`
- `Unit tests pass` (or specific test file)

**For UI stories, add:**
- `Verify in browser` (manual or E2E test reference)

**Good criteria are:**
- Verifiable: "Email format is validated"
- Measurable: "Response time < 200ms"
- Specific: "GET /api/users returns paginated results"

**Bad criteria:**
- Vague: "Works correctly"
- Subjective: "Looks good"
- Untestable: "Is intuitive"

## Line Count Thresholds by Artifact Type

| Artifact Type | Minimum Lines |
|---------------|---------------|
| Component (React/Vue/Astro) | 15 |
| API route/endpoint | 10 |
| Hook/utility | 10 |
| Model/schema | 5 |
| Test file | 20 |
| Config file | 5 |

## Example Sessions

### With GitHub Issue (typical flow)

```
User: /ralph-hybrid-plan

Claude: I see you're on branch 'feature/42-user-auth'.

[DISCOVER] Fetching GitHub issue #42...

Found issue #42: "Add user authentication"
  Labels: priority:high, type:feature

  Acceptance criteria mentioned:
  - [ ] Users can register with email/password
  - [ ] Users can log in and receive JWT
  - [ ] Protected routes require valid token

I'll use this as the starting point for the spec.
Does this capture the feature correctly? Any additions or changes?
```

### Without External Context

```
User: /ralph-hybrid-plan Add user authentication with JWT

Claude: I see you're on branch 'feature/user-auth'.

[DISCOVER] No GitHub issue detected in branch name.

I'll use your description as the starting point.
Let me ask a few clarifying questions.

1. What user data needs to be stored?
   A) Just email/password
   B) Email/password + profile info
   C) Social login (OAuth)
```
