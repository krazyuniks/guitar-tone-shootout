# Plan Phases -- Detailed Descriptions

## Phase 0: ANALYSE (MANDATORY FIRST STEP)

**Before ANY planning, load complete project state.**

### Actions

1. **Load all worktrees:** `./worktree.py list`

2. **Fetch all open GitHub issues with relationships:**
   ```bash
   gh issue list --repo krazyuniks/guitar-tone-shootout --state open \
     --json number,title,labels,assignees,body --limit 100
   gh issue list --repo krazyuniks/guitar-tone-shootout \
     --search "is:blocking is:open" --json number,title
   gh issue list --repo krazyuniks/guitar-tone-shootout \
     --search "is:blocked is:open" --json number,title
   ```

3. **Determine priority for each issue:**
   - Explicit labels: P0, P1, P2, P3, priority:high, priority:low
   - Inferred from type: bug->P1, epic->P2, enhancement->P2, docs->P3
   - Inferred from blocking count: blocks 3+ issues -> bump up one level

4. **Build dependency graph and identify blockers**

5. **Identify potentially affected issues** (superseded, amended, reprioritised)

### Priority Inference Rules

| Signal | Priority |
|--------|----------|
| Label: P0, priority:critical | P0 |
| Label: P1, priority:high, bug | P1 |
| Label: P2, enhancement, feat | P2 |
| Label: P3, docs, chore | P3 |
| Body contains "PLACEHOLDER" | P4 |
| Blocks 3+ other issues | Bump up 1 level |

---

## Phase 0.5: PROCESS UNPROCESSED (MANDATORY)

**Integrate browser-created issues into the roadmap.**

Issues created directly in GitHub's browser UI lack relationship links. For each:

1. **Pre-analysis:** duplicate? superseded? no longer relevant?
2. **If relevant:** present to user with options (Close, Process, Brainstorm, Skip)
3. **If "Process":** identify parent epic, add relationships, mark processed

Mark as processed: append `<!-- processed: YYYY-MM-DD -->` to issue body.

---

## Phase 1: SUMMARIZE

Show current state of the epic with impact analysis. Present options:
1. Brainstorm
2. Refine
3. Decompose (TDD)
4. View sub-issues

**Wait for user response. Do NOT proceed automatically.**

---

## Phase 2: BRAINSTORM

Open-ended discussion. Ask ONE question at a time:
- "What problem does this solve?"
- "Who benefits?"
- "What does success look like?"
- "What's explicitly out of scope?"
- "Technical constraints?"

Summarise session with new ideas, clarifications, and open questions.

---

## Phase 3: RESEARCH (Optional)

Triggered from Brainstorm when external information needed. Multi-query web search, cross-source compilation, summarise with sources.

---

## Phase 4: REFINE

Draft updated epic content. Show changes from current version. **Do NOT update GitHub until user explicitly approves.**

---

## Phase 5: DECOMPOSE (TDD)

Break refined epic into TEST-first tasks.

**Rules:**
1. Every IMPL task MUST be blocked by at least one TEST task
2. TEST tasks come before their corresponding IMPL tasks
3. E2E tests verify user-facing behaviour (Playwright, real backend)
4. Integration tests verify API contracts (pytest, real DB)
5. "N/A" only valid for docs/config changes

---

## Phase 6: RECOMPUTE (MANDATORY)

Integrate changes into the issue graph BEFORE execution:
- Superseded issues to close
- Existing issues to amend
- Priority changes
- Dependency updates (is:blocked/is:blocking)
- New issues to create

Use native GitHub relationships (REST API), NOT labels.

---

## Phase 7: EXECUTE

**Only runs after explicit user approval of RECOMPUTE change set.**

Execute: close superseded issues, update existing issues, create new issues, add dependencies.

---

## Phase 8: DISPLAY

Show final state: changes made, updated dependency graph, project status, next steps.
