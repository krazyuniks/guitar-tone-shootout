# /plan - Iterative Epic Planning

## Quick Reference

**Iterative epic planning with 8 phases.**

| Phase | Purpose |
|-------|---------|
| ANALYSE | Review existing GitHub issue |
| PROCESS | Mark unprocessed issues |
| SUMMARIZE | Create structured summary |
| BRAINSTORM | Generate ideas |
| RESEARCH | Web research for approaches |
| REFINE | User feedback iteration |
| DECOMPOSE | Break into stories (TDD) |
| EXECUTE | Display final plan |

**Mandatory**: ANALYSE, PROCESS UNPROCESSED, and RECOMPUTE phases cannot be skipped.

---

Plan, brainstorm, and refine epics through conversational iteration.

## Usage

```
/plan <issue-url or number>   # Work on existing epic
/plan <topic>                 # Start new epic from scratch
/plan                         # Resume active planning session
```

## Core Philosophy

**The Epic is the source of truth.** Ideas flow through the epic, not directly to sub-issues.

```
Ideas → Epic → Sub-issues
         ↑
      Iterate
```

- User interacts with the EPIC through planning cycles
- Sub-issues are DERIVED from the epic state
- Changes to sub-issues happen by changing the epic first
- Every GitHub mutation requires explicit user approval
- **ANALYSE happens FIRST** - Full project context before any planning
- **RECOMPUTE is mandatory** - New work integrates into the issue graph

---

## Workflow States

```
┌─────────────┐
│   ANALYSE   │ ← FIRST: Full project context (worktrees, all issues, deps)
└──────┬──────┘
       │
       ▼
┌─────────────┐
│   PROCESS   │ ← Integrate unprocessed issues into roadmap
│ UNPROCESSED │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  SUMMARIZE  │ ← Show current state with impact analysis
└──────┬──────┘
       │
       ▼
┌─────────────┐     ┌─────────────┐
│  BRAINSTORM │ ←──→│   RESEARCH  │ (if needed)
└──────┬──────┘     └─────────────┘
       │
       ▼
┌─────────────┐
│   REFINE    │ ← Update epic content (draft)
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  DECOMPOSE  │ ← Break into TEST + IMPL tasks
│   (TDD)     │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  RECOMPUTE  │ ← MANDATORY: Update issue graph (supersedes, deps, priorities)
└──────┬──────┘
       │
       ▼
┌─────────────┐
│   EXECUTE   │ ← GitHub mutations (requires approval)
└──────┬──────┘
       │
       ▼
┌─────────────┐
│   DISPLAY   │ ← Show final state and next steps
└─────────────┘
```

User can exit at any state. Nothing is committed until EXECUTE.

**IMPORTANT:** ANALYSE, PROCESS UNPROCESSED, and RECOMPUTE are NOT optional. Every planning session must:
1. Load full context BEFORE brainstorming (ANALYSE)
2. Integrate unprocessed issues BEFORE summarizing (PROCESS UNPROCESSED)
3. Integrate changes into the issue graph BEFORE execution (RECOMPUTE)

---

## State Details

### 0. ANALYSE (Full Project Context) - MANDATORY FIRST STEP

**Before ANY planning, load complete project state.**

This phase is NOT optional. It runs FIRST to understand the full landscape before brainstorming begins.

**Actions:**

1. **Load all worktrees:**
   ```bash
   ./worktree.py list
   ```

2. **Fetch all open GitHub issues with relationships:**
   ```bash
   # All open issues with labels for priority detection
   gh issue list --repo krazyuniks/guitar-tone-shootout --state open \
     --json number,title,labels,assignees,body --limit 100

   # Issues blocking others (dependencies)
   gh issue list --repo krazyuniks/guitar-tone-shootout \
     --search "is:blocking is:open" --json number,title

   # Blocked issues
   gh issue list --repo krazyuniks/guitar-tone-shootout \
     --search "is:blocked is:open" --json number,title
   ```

3. **Determine priority for each issue:**
   - **Explicit labels:** P0, P1, P2, P3, priority:high, priority:low
   - **Inferred from type:**
     - `bug` / `fix` → P1 (unless labeled otherwise)
     - `epic` → P2 (tracking issues, not direct work)
     - `enhancement` / `feat` → P2
     - `docs` / `chore` → P3
     - `placeholder` in body → P4 (not ready)
   - **Inferred from blocking count:**
     - Blocks 3+ issues → bump priority up one level
     - Blocks critical path → P1

4. **Build dependency graph and identify blockers**

5. **Identify potentially affected issues:**
   - Issues that might be **superseded** by new work
   - Issues that might be **amended** (scope change)
   - Issues that might need **reprioritization**
   - Issues that might become **blocked** or **unblocked**

**Output format:**
```markdown
## Project Analysis Complete

### Worktree State
| Worktree | Issue | Status |
|----------|-------|--------|
| 357-auth-system | #357 | in-progress |
| 361-di-import | #361 | planning |

### GitHub Issue State
- **Total open:** X issues
- **Epics:** Y issues (label: epic)
- **Blocked:** Z issues (waiting on dependencies)
- **Blocking others:** W issues (other work depends on these)

### Ready to Work (Priority Order)

**Non-epic issues that are not blocked, sorted by priority:**

| Pri | # | Title | Blocks | Notes |
|-----|---|-------|--------|-------|
| P1 | #384 | Video Composition | #385 | Core feature, Step 3 |
| P1 | #323 | Test Harness Phase 4-7 | epic #318 | Completes test restructure |
| P2 | #385 | Progress Tracking/WebSocket | - | Can parallel with #384 |
| P2 | #102 | Graceful Shutdown | - | 12-factor compliance |
| P3 | #187 | Grafana Dashboards | - | Observability |

### Blocked Issues

| Pri | # | Title | Blocked By | Status |
|-----|---|-------|------------|--------|
| P1 | #141 | IMPL: Upload API | #140 (TEST) | Waiting on test |
| P2 | #142 | IMPL: Upload UI | #140, #141 | Waiting on 2 issues |

### Epics Status

| Pri | # | Title | Sub-issues | Progress |
|-----|---|-------|------------|----------|
| P1 | #318 | Test Harness Restructure | 4 | 3/4 done |
| P2 | #428 | Job Processing Pipeline | 3 | 1/3 done |
| P2 | #185 | Infrastructure Excellence | 8 | 4/8 done |
| P4 | #191 | CI/CD Pipeline | 0 | Placeholder |

### Dependency Graph
```
#350 (core API)
├── blocks #357 (auth)
├── blocks #361 (DI import)
└── blocks #365 (player)

#357 (auth)
└── blocks #370 (user profiles)
```

### Potentially Affected by This Planning Session
| # | Title | Impact |
|---|-------|--------|
| #340 | Old DI approach | May be superseded |
| #355 | Audio upload | Scope may change |
| #360 | Track listing | Priority may increase |

---
**What would you like to work on?**
- Pick a number from "Ready to Work" to start planning
- Or specify an epic to break down further
```

**Priority Inference Rules:**

| Signal | Priority |
|--------|----------|
| Label: P0, priority:critical | P0 |
| Label: P1, priority:high, bug | P1 |
| Label: P2, enhancement, feat | P2 |
| Label: P3, docs, chore | P3 |
| Body contains "PLACEHOLDER" | P4 |
| Blocks 3+ other issues | Bump up 1 level |
| Part of critical user path | P1 |
| Epic (tracking issue) | Same as highest sub-issue |

**Why ANALYSE is mandatory:**
- Prevents duplicate work
- Identifies superseded issues BEFORE creating new ones
- Ensures dependencies are updated, not forgotten
- Keeps the issue graph consistent
- **Shows prioritized "Ready to Work" list for easy selection**

### 0.5. PROCESS UNPROCESSED (Issue Integration) - MANDATORY

**Integrate browser-created issues into the roadmap.**

Issues created directly in GitHub's browser UI are "unprocessed" - they lack relationship links and haven't been integrated. This phase handles them BEFORE proceeding to planning.

**Detecting unprocessed issues:**
```bash
# Get all open issues
gh issue list --repo krazyuniks/guitar-tone-shootout --state open \
  --json number,title,body --limit 100 > /tmp/all-issues.json

# Check each issue body for processed marker
# Unprocessed = no "<!-- processed:" in body AND no relationships
```

**For each unprocessed issue, determine action:**

1. **Pre-analysis** - Before queuing for processing:
   - Is this a **duplicate** of existing work? → Close as duplicate
   - Has this been **superseded** by newer work? → Close as superseded
   - Is this **no longer relevant**? → Close with reason

2. **If potentially relevant**, present to user:
   ```markdown
   ## Unprocessed Issue: #380 "Add user preferences"

   **Created:** 2026-01-05 (6 days ago)
   **Body:** [summary]

   **Analysis:**
   - Similar to #342 (Design Showcase) - 65% title similarity
   - No parent epic identified
   - No dependencies detected

   **Action?**
   1. **Close** - Duplicate of #342
   2. **Close** - No longer relevant
   3. **Process** - Add relationships, mark processed
   4. **Brainstorm** - Need to discuss this one
   5. **Skip** - Handle later
   ```

3. **If user chooses "Process":**
   - Identify parent epic (or create standalone)
   - Add blocked-by/blocking relationships
   - Add sub-issue relationship if applicable
   - Add processed marker to issue body

**Marking as processed:**
```bash
# Get current body and append marker
CURRENT_BODY=$(gh issue view 380 --repo krazyuniks/guitar-tone-shootout --json body --jq '.body')

gh issue edit 380 --repo krazyuniks/guitar-tone-shootout \
  --body "$CURRENT_BODY

<!-- processed: $(date +%Y-%m-%d) -->"
```

**Output format:**
```markdown
## Processing Unprocessed Issues

**Found:** 12 unprocessed issues

### Already Handled (Pre-analysis)
| # | Title | Action | Reason |
|---|-------|--------|--------|
| #375 | Old auth approach | CLOSE | Superseded by #357 |
| #372 | Fix typo | CLOSE | Already fixed in #380 |

### Needs Decision
| # | Title | Suggestion |
|---|-------|------------|
| #380 | Add user preferences | Link to Epic #321? |
| #378 | Mobile layout fix | Standalone P2? |

---

**Process these issues now?**
- Type "yes" to go through each one
- Type "skip" to proceed to SUMMARIZE (handle later)
- Type "auto" to apply suggested actions
```

**Feedback loop:** When ANY issue is updated during processing, context has changed. The RECOMPUTE phase will account for this.

**Why PROCESS UNPROCESSED is mandatory:**
- Keeps roadmap accurate and complete
- Prevents "blind spots" in project planning
- Ensures all work is tracked with proper relationships
- First run may have significant backlog - this is expected

### 1. SUMMARIZE (Entry Point)

**When given an existing issue**, ALWAYS start here:

```markdown
## Epic Summary: [Title]

**Objective:** [One sentence goal]

**Current State:**
- [What's defined]
- [What's unclear]

**Test Requirements:** [MISSING / INCOMPLETE / DEFINED]
- E2E Tests: [count] defined
- Integration Tests: [count] defined

**Planned Work:**
- [ ] Task 1 (issue #X or planned)
- [ ] Task 2 (issue #Y or planned)

**Success Criteria:**
- [Criterion 1]
- [Criterion 2]

**Existing Sub-issues:**
| # | Title | Type | Status |
|---|-------|------|--------|
| 133 | TEST: Upload flow works | TEST | open |
| 134 | IMPL: Create upload API | IMPL | blocked |

---

**What would you like to do?**
1. **Brainstorm** - Explore ideas, add context, discuss
2. **Refine** - Update the epic content directly
3. **Decompose (TDD)** - Break into TEST + IMPL tasks (recommended)
4. **View sub-issues** - See detailed sub-issue status
```

**CRITICAL:** Wait for user response. Do NOT proceed automatically.

### 2. BRAINSTORM (Conversational Mode)

Open-ended discussion to capture ideas:

**Behavior:**
- Ask open questions, one at a time
- Capture ideas without judging feasibility yet
- Explore alternatives and tradeoffs
- Take notes on what the user says

**Questions to explore:**
- "What problem does this solve?"
- "Who benefits from this change?"
- "What does success look like?"
- "What are you unsure about?"
- "What should definitely NOT be in scope?"
- "Any technical constraints I should know about?"

**Output:** Summarize the brainstorm session:
```markdown
## Brainstorm Summary

**New ideas captured:**
- [Idea 1]
- [Idea 2]

**Clarifications:**
- [Clarification 1]

**Open questions:**
- [Question still unresolved]

**Next:** Would you like to continue brainstorming, or refine the epic with these ideas?
```

### 3. RESEARCH (Optional, triggered from Brainstorm)

When external information is needed:

**Triggers:**
- Unknown technology or API
- Need to find existing patterns
- User asks "how do others do X?"

**Approach:**
- Multi-query web search
- Cross-source compilation (docs, GitHub, forums)
- Summarize findings, cite sources

**Output:** Research summary integrated into brainstorm

### 4. REFINE (Update Epic Content)

Draft updated epic content based on brainstorm:

**Output format:**
```markdown
## Proposed Epic Update

**Changes from current version:**
- Added: [new content]
- Removed: [removed content]
- Changed: [modified content]

---

### Updated Epic Content

[Full updated epic body in GitHub markdown]

---

**Approve this update?**
- Type "yes" to update the epic on GitHub
- Type "no" or suggest changes to revise
```

**CRITICAL:** Do NOT update GitHub until user explicitly approves.

### 5. DECOMPOSE (TDD Task Breakdown)

**Break the refined epic into TEST-first tasks.**

This is the critical step that makes TDD mandatory: every feature becomes explicit TEST tasks that block IMPL tasks.

**Output format:**
```markdown
## TDD Task Decomposition

For each feature/behavior in the epic, I've created paired TEST + IMPL tasks:

### Feature: User can upload DI tracks
| Order | Type | Task | Blocks |
|-------|------|------|--------|
| 1 | TEST | E2E: Upload form accepts file + metadata | - |
| 2 | TEST | E2E: Uploaded track appears in list | - |
| 3 | TEST | Integration: POST /di-tracks returns 201 | - |
| 4 | IMPL | Create DI track upload API endpoint | Tests 1,2,3 |
| 5 | IMPL | Create upload form component | Tests 1,2 |

### Feature: Filter DI tracks
| Order | Type | Task | Blocks |
|-------|------|------|--------|
| 6 | TEST | E2E: Filter by guitar shows matching tracks | - |
| 7 | TEST | Integration: GET /di-tracks?guitar=X filters correctly | - |
| 8 | IMPL | Add filter parameters to API | Test 7 |
| 9 | IMPL | Add filter UI to track list | Tests 6,7 |

---

**Execution Order:**
1. Write ALL tests first (they will fail - RED)
2. Implement features to make tests pass (GREEN)
3. Refactor if needed

**Create these as sub-issues?**
- Type "yes" to create separate issues for each task
- Type "combined" to keep as checklist in epic
- Type "revise" to adjust the breakdown
```

**Rules for TDD decomposition:**
1. Every IMPL task MUST be blocked by at least one TEST task
2. TEST tasks come before their corresponding IMPL tasks
3. E2E tests verify user-facing behavior (Playwright, real backend)
4. Integration tests verify API contracts (pytest, real DB)
5. "N/A" is only valid for docs/config changes with no behavior

### 6. RECOMPUTE (Issue Graph Integration) - MANDATORY

**Integrate brainstorm results into the issue graph BEFORE execution.**

This is NOT optional. Every planning session must compute the full set of changes to the issue graph, including:
- Superseded issues to close (identified in ANALYSE)
- Existing issues to amend
- Priority changes
- Dependency updates (`is:blocked`/`is:blocking`)
- New issues to create

**Actions:**

1. **Review ANALYSE findings** - What issues were flagged as potentially affected?

2. **Compare epic tasks to existing issues:**
   - Which existing issues match new tasks?
   - Which existing issues are now out of scope?
   - Which new tasks need issues created?

3. **Compute dependency graph changes:**
   ```bash
   # See /gh-workflow skill for full dependency commands
   # Use native GitHub relationships (REST API), NOT labels
   # Example: Make issue #358 blocked by issue #357
   BLOCKING_ID=$(gh issue view 357 --repo krazyuniks/guitar-tone-shootout --json id --jq '.id')
   gh api repos/krazyuniks/guitar-tone-shootout/issues/358/dependencies/blocked_by \
     --method POST -f issue_id="$BLOCKING_ID"
   ```

4. **Compute priority changes** based on new work

**Output format:**
```markdown
## Issue Graph Recomputation

### From ANALYSE Phase
These issues were flagged as potentially affected:
| # | Title | Flagged Impact | Confirmed Action |
|---|-------|----------------|------------------|
| #340 | Old DI approach | Superseded | **CLOSE** - replaced by this epic |
| #355 | Audio upload | Scope change | **AMEND** - update description |
| #360 | Track listing | Priority change | **REPRIORITIZE** - P3 → P2 |

### Sub-issue Reconciliation
| Action | Issue | Reason |
|--------|-------|--------|
| Keep | #133 | Matches current scope |
| Update | #134 | Description needs update |
| Close | #135 | Removed from scope |
| Create | new | Task D added to scope |

### Dependency Updates
| From | Relationship | To | Action |
|------|--------------|-----|--------|
| #141 (IMPL) | blocked-by | #140 (TEST) | ADD |
| #142 (IMPL) | blocked-by | #140 (TEST) | ADD |
| #340 | blocked-by | #128 | REMOVE (closing #340) |

### Priority Changes
| # | Title | Old | New | Reason |
|---|-------|-----|-----|--------|
| #360 | Track listing | P3 | P2 | Needed sooner for DI feature |

---

**Full Change Set for EXECUTE:**
1. Close #340 (superseded)
2. Update #355 description
3. Update #360 priority: P3 → P2
4. Update #134 description
5. Close #135 (out of scope)
6. Create 4 new issues (TEST + IMPL tasks)
7. Add 3 dependency relationships

**Approve this change set?**
- Type "yes" to execute all changes
- Type "partial" to select specific changes
- Type "revise" to go back and adjust
```

**Why RECOMPUTE is mandatory:**
- Ensures issue graph stays consistent
- Closes superseded work (no orphan issues)
- Updates dependencies (nothing falls through cracks)
- Adjusts priorities (project stays coherent)

### 7. EXECUTE (GitHub Mutations)

**Only runs after explicit user approval of RECOMPUTE change set.**

```markdown
## Executing Changes

### Closing Superseded Issues
- [ ] Closing #340 with reason "Superseded by #128"...

### Updating Existing Issues
- [ ] Updating #355 description...
- [ ] Updating #360 priority: P3 → P2...
- [ ] Updating #134 description...
- [ ] Closing #135 with reason "Out of scope"...

### Creating New Issues
- [ ] Creating TEST: Upload form validation...
- [ ] Creating IMPL: Upload API endpoint...

### Adding Dependencies
- [ ] Adding #141 blocked-by #140...
- [ ] Adding #142 blocked-by #140...

## Complete

| Action | Issue | Result |
|--------|-------|--------|
| Closed | #340 | ✓ Superseded |
| Updated | #355 | ✓ Scope clarified |
| Updated | #360 | ✓ Priority P2 |
| Closed | #135 | ✓ Out of scope |
| Created | #140 | ✓ TEST: Upload form |
| Created | #141 | ✓ IMPL: Upload API (blocked by #140) |
```

### 8. DISPLAY (Show Final State)

**After executing changes, show the updated project state.**

**Output format:**
```markdown
## Planning Session Complete

### Changes Made
| Action | # | Title |
|--------|---|-------|
| Closed | #340 | Old DI approach (superseded) |
| Created | #140 | TEST: Upload form validation |
| Created | #141 | IMPL: Upload API endpoint |
| Updated | #128 | Epic: User Uploads |

### Updated Dependency Graph
```
Epic #128
├── #140 TEST: Upload form (ready)
├── #141 IMPL: Upload API (blocked by #140)
└── #142 IMPL: Upload UI (blocked by #140)
```

### Project Status
- **Ready to start:** 2 tasks (#140, #143)
- **Blocked:** 3 tasks (waiting on tests)
- **Issues closed this session:** 2 (#340, #135)
- **Dependencies added:** 3

### Next Steps
1. **Start working:** `./worktree.py setup 140` (first TEST task)
2. **Continue planning:** `/plan #128` to refine further
3. **View all ready work:** `/next-issue`
```

---

## Key Principles

### 1. Never Auto-Execute

The following actions ALWAYS require explicit "yes" from the user:
- Creating GitHub issues
- Updating GitHub issues
- Closing GitHub issues
- Any mutation to the repository

### 2. Epic-First Thinking

- Don't create sub-issues directly
- Update the epic, then derive sub-issues
- This keeps the epic as single source of truth

### 3. TDD is Mandatory (Not Optional)

**Every feature must have explicit TEST tasks that block IMPL tasks.**

- TEST tasks are created during DECOMPOSE phase
- TEST tasks must be completed (tests written, failing) BEFORE implementation
- IMPL tasks cannot start until their blocking tests exist
- "N/A" is only valid for docs/config with no behavior

**Why this matters:** If tests aren't explicit tasks, they get skipped under time pressure. Making them tasks with dependencies ensures they happen first.

### 4. Iteration is Expected

- User may run `/plan #128` multiple times
- Each session picks up where the last left off
- Changing your mind is normal and supported

### 5. Quick Capture

- Brainstorm mode is lightweight
- Just capture ideas, don't over-structure
- Refinement and decomposition come later

### 6. Explicit State Transitions

Always tell the user what state you're in:
```
[ANALYSE] Loading full project context...
[PROCESS UNPROCESSED] Found X unprocessed issues...
[SUMMARIZE] Here's the current state with impact analysis...
[BRAINSTORM] Let's explore this idea...
[REFINE] Here's the proposed update...
[DECOMPOSE] Breaking into TEST + IMPL tasks...
[RECOMPUTE] Computing issue graph changes...
[EXECUTE] Making changes now...
[DISPLAY] Here's the final state...
```

### 7. Use /gh-workflow Skill

Reference the global `/gh-workflow` skill for GitHub commands:
- Finding unblocked issues
- Adding/removing dependencies
- Priority label management
- Issue state queries

---

## Reminders for Claude

### CLI UX: One Question at a Time

**CRITICAL:** The user is in a CLI environment with limited screen real estate. They cannot see content at the top of the screen while answering questions at the bottom.

**Rules:**
1. **Ask ONE question at a time** - Never dump a page of content then ask multiple questions
2. **Show only relevant context** - Display the specific issue/content being asked about, not a full table
3. **Context ABOVE the question** - Put the relevant snippet immediately before the question
4. **Build understanding iteratively** - Synthesize answers into the next question
5. **Summarize progress periodically** - After several questions, provide a brief summary of decisions made

**BAD (don't do this):**
```
[20 issues in a table]
[scroll scroll scroll]
Questions:
1. Is #356 a duplicate?
2. Should #345 be under #192?
3. Is there a pipeline epic?
```

**GOOD (do this):**
```
## Issue #356: Test infrastructure improvements

This issue covers test organization and markers.

**Potential overlap:** Epic #318 also covers test restructuring.

Is #356 a **duplicate** of #318, or should it be a **sub-issue**?
```

Then after user answers, move to the next question with its relevant context.

### GitHub Mutations

**BEFORE any GitHub mutation, you MUST:**
1. Show the user exactly what will change
2. Ask "Approve?" or similar
3. Wait for explicit "yes" response
4. Only then execute

**NEVER:**
- Auto-approve your own work
- Skip ANALYSE - ALWAYS load full project context first
- Skip PROCESS UNPROCESSED - ALWAYS check for and handle unprocessed issues
- Skip SUMMARIZE when given an existing issue
- Skip RECOMPUTE - ALWAYS compute issue graph changes before EXECUTE
- Create issues without showing the user first
- Assume an epic is "well-planned" without asking
- Execute without showing the full change set from RECOMPUTE
- Forget to close superseded issues
- Forget to update dependencies
- Forget to mark processed issues with `<!-- processed: date -->` marker
