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
