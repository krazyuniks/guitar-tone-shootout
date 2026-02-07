# Output Formats for Each Phase

## ANALYSE Phase Output

```markdown
## Project Analysis Complete

### Worktree State
| Worktree | Issue | Status |
|----------|-------|--------|
| 357-auth-system | #357 | in-progress |
| 361-di-import | #361 | planning |

### GitHub Issue State
- **Total open:** X issues
- **Epics:** Y issues
- **Blocked:** Z issues
- **Blocking others:** W issues

### Ready to Work (Priority Order)

| Pri | # | Title | Blocks | Notes |
|-----|---|-------|--------|-------|
| P1 | #384 | Video Composition | #385 | Core feature |
| P2 | #385 | Progress Tracking | - | Can parallel |

### Blocked Issues

| Pri | # | Title | Blocked By | Status |
|-----|---|-------|------------|--------|
| P1 | #141 | IMPL: Upload API | #140 (TEST) | Waiting |

### Epics Status

| Pri | # | Title | Sub-issues | Progress |
|-----|---|-------|------------|----------|
| P1 | #318 | Test Restructure | 4 | 3/4 done |

### Dependency Graph
(ASCII tree showing blocking relationships)

### Potentially Affected by This Session
| # | Title | Impact |
|---|-------|--------|
| #340 | Old approach | May be superseded |
```

## PROCESS UNPROCESSED Output

```markdown
## Processing Unprocessed Issues

**Found:** 12 unprocessed issues

### Already Handled (Pre-analysis)
| # | Title | Action | Reason |
|---|-------|--------|--------|
| #375 | Old auth | CLOSE | Superseded by #357 |

### Needs Decision
| # | Title | Suggestion |
|---|-------|------------|
| #380 | User prefs | Link to Epic #321? |
```

## SUMMARIZE Output

```markdown
## Epic Summary: [Title]

**Objective:** [One sentence]
**Current State:** [What's defined, what's unclear]
**Test Requirements:** [MISSING / INCOMPLETE / DEFINED]
**Planned Work:** [checklist]
**Success Criteria:** [list]
**Existing Sub-issues:** [table]

**What would you like to do?**
1. Brainstorm
2. Refine
3. Decompose (TDD)
4. View sub-issues
```

## DECOMPOSE Output

```markdown
## TDD Task Decomposition

### Feature: [Name]
| Order | Type | Task | Blocks |
|-------|------|------|--------|
| 1 | TEST | E2E: Upload form | - |
| 2 | TEST | Integration: POST /api | - |
| 3 | IMPL | Create upload API | Tests 1,2 |

**Execution Order:**
1. Write ALL tests first (RED)
2. Implement features (GREEN)
3. Refactor if needed

**Create as sub-issues?**
- "yes" for separate issues
- "combined" for checklist in epic
- "revise" to adjust
```

## RECOMPUTE Output

```markdown
## Issue Graph Recomputation

### From ANALYSE Phase
| # | Title | Flagged Impact | Confirmed Action |
|---|-------|----------------|------------------|
| #340 | Old approach | Superseded | CLOSE |

### Sub-issue Reconciliation
| Action | Issue | Reason |
|--------|-------|--------|
| Keep | #133 | Matches scope |
| Create | new | Task D added |

### Dependency Updates
| From | Relationship | To | Action |
|------|--------------|-----|--------|
| #141 | blocked-by | #140 | ADD |

### Full Change Set for EXECUTE
1. Close #340 (superseded)
2. Create 4 new issues
3. Add 3 dependencies

**Approve?** yes / partial / revise
```

## DISPLAY Output

```markdown
## Planning Session Complete

### Changes Made
| Action | # | Title |
|--------|---|-------|
| Closed | #340 | Old approach |
| Created | #140 | TEST: Upload form |

### Updated Dependency Graph
(ASCII tree)

### Next Steps
1. Start working: `./worktree.py setup 140`
2. Continue planning: `/plan #128`
```
