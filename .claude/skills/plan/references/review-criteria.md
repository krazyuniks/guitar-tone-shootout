# Plan Review Checklist and GitHub Mutation Rules

## GitHub Mutation Rules

**BEFORE any GitHub mutation:**
1. Show the user exactly what will change
2. Ask "Approve?" or similar
3. Wait for explicit "yes" response
4. Only then execute

**NEVER:**
- Auto-approve your own work
- Skip ANALYSE -- ALWAYS load full project context first
- Skip PROCESS UNPROCESSED -- ALWAYS check for unprocessed issues
- Skip SUMMARIZE when given an existing issue
- Skip RECOMPUTE -- ALWAYS compute issue graph changes before EXECUTE
- Create issues without showing the user first
- Assume an epic is "well-planned" without asking
- Execute without showing the full change set from RECOMPUTE
- Forget to close superseded issues
- Forget to update dependencies
- Forget to mark processed issues with `<!-- processed: date -->` marker

## TDD Decomposition Review

1. Every IMPL task MUST be blocked by at least one TEST task
2. TEST tasks come before their corresponding IMPL tasks
3. E2E tests verify user-facing behaviour
4. Integration tests verify API contracts
5. "N/A" only valid for docs/config changes with no behaviour

## Issue Quality Criteria

- Clear objective (1-2 sentences)
- Specific acceptance criteria (checkboxes)
- Dependencies noted
- Labels applied

## CLI UX Review

1. **ONE question at a time** -- never dump content then ask multiple questions
2. **Context ABOVE the question** -- relevant snippet immediately before
3. **Build iteratively** -- synthesise answers into next question
4. **Summarise periodically** -- after 3-5 questions, recap decisions

## Recompute Review

Before approving EXECUTE, verify:

- [ ] All superseded issues identified and marked for closure
- [ ] All dependency relationships correct (blocked-by / blocking)
- [ ] Priority changes justified
- [ ] New issues have proper labels
- [ ] No orphaned issues created
- [ ] Existing sub-issues reconciled (keep/update/close/create)

## GitHub CLI Requirement

**ALWAYS** include `--repo krazyuniks/guitar-tone-shootout` with ALL `gh` commands.

## Dependency Commands

```bash
# Use native GitHub relationships (REST API), NOT labels
BLOCKING_ID=$(gh issue view 357 --repo krazyuniks/guitar-tone-shootout --json id --jq '.id')
gh api repos/krazyuniks/guitar-tone-shootout/issues/358/dependencies/blocked_by \
  --method POST -f issue_id="$BLOCKING_ID"
```

Reference the `/gh-workflow` skill for full dependency command reference.
