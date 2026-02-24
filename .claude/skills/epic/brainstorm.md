---
name: brainstorm
description: Interactive epic brainstorming — enrich a GitHub issue with observable outcomes, decisions, and regression boundaries before pipeline ingestion.
argument-hint: "<epic-number>"
context: current
---

# Epic Brainstorming (Stage 0)

**Command:** `/epic brainstorm <N>`

Enriches a GitHub issue into the structured format required by the epic pipeline. This is an interactive CC session — the output is the enriched GitHub issue, updated in place.

**IMPORTANT:** This session is exploratory. It consumes CC context for brainstorming. After the issue is updated, the session is disposable — the pipeline runs separately via `just epic N`.

---

## Inputs

Read ALL of these before starting:

1. **GitHub issue:** `gh issue view <N> --repo krazyuniks/guitar-tone-shootout --json title,body,labels`
2. **Architecture:** `../wiki/GTS-Technical-Architecture.md` (via Read tool)
3. **Agent guide:** `AGENTS.md` (via Read tool)
4. **Codebase structure:** `.planning/codebase/STRUCTURE.md` (via Read tool, if exists)
5. **Gap detection guide:** `workflow/references/gap-detection-guide.md` OR `.claude/skills/epic/references/question-bank.md`

---

## Process

### Step 1: Understand the Request

Read the GitHub issue body. Identify what the user wants to build. If the issue is sparse, that's fine — the brainstorming will fill in the gaps.

### Step 1.5: Size Assessment

Evaluate the issue's scope:
- Count the distinct observable outcomes or deliverables
- Identify independent feature areas or bounded contexts involved

**If the issue has >8-10 outcomes or spans multiple independent feature areas**, it needs decomposition into sub-issues before brainstorming. Jump to the **Decomposition Flow** at the bottom of this document.

**If the issue is 4-8 outcomes in a single area**, proceed normally.

### Step 2: Gap Detection

Compare the issue against the architecture and codebase. Identify:
- **Ambiguities:** Terms or requirements that could be interpreted multiple ways
- **Assumptions:** Things the issue takes for granted that might not hold
- **Contradictions:** Requirements that conflict with existing architecture
- **Missing information:** BC ownership, data model, API contracts, frontend patterns, etc.
- **New cross-BC flows:** Any new messaging or data flows between bounded contexts

Present your findings clearly.

### Step 3: Interactive Brainstorming

Resolve each gap through conversation. **Rules:**
- **One question at a time.** Never present a wall of questions.
- **Multiple choice preferred.** Where multiple valid approaches exist, present 2-3 options with your recommendation.
- **Incrementally validate:** After each section, confirm with the user before moving on.
- **Ask until satisfied.** Don't just exhaust a list — confirm coverage of all architecture areas.

Architecture areas to cover (from gap detection guide):
- Bounded context ownership
- Data model (entities, relationships, lifecycle)
- API contract (endpoints, schemas, auth)
- Frontend pattern (page type, navigation, HTMX vs Alpine)
- Job/queue patterns (if applicable)
- Security (auth, ownership, CORS)
- Testing strategy
- Infrastructure (Docker, migrations)

### Step 4: Define Observable Outcomes

These are the core output. Each outcome specifies **what is observable** from any perspective (user, API, database, process).

Good outcomes:
```
- [ ] User can visit /gear and see a list of their gear items
- [ ] Clicking a gear item navigates to a detail page showing model information
- [ ] Submitting the edit form updates the gear name, visible on return to detail page
```

Bad outcomes (too technical):
```
- [ ] GearRepository has a get_by_id method
- [ ] The Pydantic schema validates input
```

Every outcome needs: entry point, success state, and error state.

### Step 5: Draft the Enriched Epic

Produce the full enriched issue body in this exact format:

```markdown
## Summary
One paragraph describing the feature.

## Observable Outcomes
- [ ] Outcome description (entry: ..., success: ...)
- [ ] ...

## Decisions
- BC ownership: ...
- Approach: ...
- Auth: ...
- (all decisions from brainstorming)

## Regression Boundaries
- Existing behaviour that must remain unchanged
- ...
```

### Step 6: Critique

Before updating the issue, review your own work:
- Does every outcome have a clear entry point and success state?
- Are the decisions consistent with the architecture?
- Are there any gaps in the regression boundaries?
- Would an implementation agent be able to build this without ambiguity?

Present the draft to the user for review.

### Step 7: Update the Issue

After human approval:
```bash
gh issue edit <N> --repo krazyuniks/guitar-tone-shootout --body "$(cat <<'BODY'
<enriched issue body>
BODY
)"
```

**Principle:** Everything in the issue ships. No deferral, no MVP subset, no scope reduction.

---

## Completion

After updating the issue, tell the user:
- The issue has been enriched and is ready for the pipeline
- Next step: `just epic <N>` (run from terminal, not CC)
- This CC session can be closed — it served its purpose

---

## Decomposition Flow

Triggered from Step 1.5 when an issue is too large for a single epic run. The goal is to split a large issue into 2-5 child sub-issues, each sized for the orchestrator's sweet spot (4-8 outcomes).

### D1: Identify Groupings

Analyse the outcomes and find natural groupings by:
- **Bounded context** — outcomes that touch the same BC belong together
- **Dependency chain** — outcomes where A must complete before B starts
- **Feature area** — independent functional areas (e.g. API vs frontend vs jobs)

Present the proposed groupings to the user for review.

### D2: Propose Children

For each group, draft a child issue:
- **Title:** concise, scoped to the group
- **Outcomes:** 4-8 observable outcomes (subset of the parent's)
- **Dependencies:** which children must complete before this one can start (`blocked_by`)

Present the full decomposition plan: child titles, outcome assignments, and dependency graph. Get user approval before creating anything.

### D3: Create Sub-Issues

For each approved child:

1. **Create the child issue:**
   ```bash
   gh issue create --repo krazyuniks/guitar-tone-shootout \
     --title "<child title>" \
     --body "$(cat <<'BODY'
   <child issue body — same enriched format as Step 5>
   BODY
   )"
   ```

2. **Get the internal issue ID** (GitHub sub-issues API requires the internal `.id`, NOT the `#number`):
   ```bash
   gh api repos/krazyuniks/guitar-tone-shootout/issues/<child_number> --jq '.id'
   ```

3. **Add as sub-issue of the parent:**
   ```bash
   gh api repos/krazyuniks/guitar-tone-shootout/issues/<parent_number>/sub_issues \
     --method POST --field sub_issue_id=<internal_id>
   ```

4. **Wire blocked_by dependencies** (if this child depends on another):
   ```bash
   gh api repos/krazyuniks/guitar-tone-shootout/issues/<child_number>/dependencies/blocked_by \
     --method POST --field blocked_by_id=<blocker_internal_id>
   ```

**CRITICAL:** The `sub_issue_id` and `blocked_by_id` fields require the internal `.id` (a large integer like `2934857123`), NOT the issue `#number`. Always fetch the ID with `--jq '.id'` before making these API calls.

### D4: Update Parent

Edit the parent issue body to reference the children:

```bash
gh issue edit <parent_number> --repo krazyuniks/guitar-tone-shootout \
  --body "$(cat <<'BODY'
<original parent body>

## Sub-Issues
- #<child_1> — <title> (start here)
- #<child_2> — <title> (blocked by #<child_1>)
- #<child_3> — <title> (blocked by #<child_2>)
BODY
)"
```

### D5: Completion

Tell the user:
- The parent issue has been decomposed into N children
- Dependency chain: `#A → #B → #C`
- Next step: run `/epic brainstorm <first_child>` to enrich the first unblocked child, or `/epic next` to find the next ready issue
- The parent issue cannot be run directly — the pipeline will reject it at ingestion
