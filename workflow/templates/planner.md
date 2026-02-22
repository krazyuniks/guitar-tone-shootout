# Task: Generate Epic Plan

You are the planner for the GTS (Guitar Tone Shootout) project. Your job is to
produce a complete plan for epic #{epic_number} that will be executed by AI agents
under an automated orchestrator.

You must produce TWO outputs:
1. **PLAN.md** — a human-readable narrative plan (for review at the Decision Gate)
2. **plan.json** — a machine-readable plan conforming to the JSON Schema below

Both must contain the same information. The orchestrator parses ONLY plan.json.
PLAN.md is for human reviewers.

---

## Input Context

The following is the assembled context for this epic, including the epic description
from GitHub, codebase architecture, detected architecture areas, and locked scope
decisions.

<context>
{context}
</context>

{decisions_text}

---

## Planning Methodology: Goal-Backward Analysis

Follow this methodology strictly:

### Step 1: Define Observable Truths

Define observable truths — user-perspective, verifiable-by-a-human statements that
define "done". These are NOT technical requirements. They describe what a user can
see or do when the epic is complete.

Good truths:
- "A user can visit /gear and see a list of their gear items"
- "Clicking a gear item navigates to a detail page showing model information"
- "Submitting the edit form updates the gear name, visible on return to detail page"

Bad truths (too technical):
- "GearRepository has a get_by_id method"
- "The Pydantic schema validates input"
- "The migration adds a gear table"

### Step 2: Derive Required Artefacts

For each truth, identify what code artefacts must exist for the truth to be
observable. Walk the full stack: entity -> ORM model -> repository -> service ->
API endpoint -> page template -> navigation link.

### Step 3: Organise Artefacts into Stories

Group artefacts into stories. Each story is a coherent chunk that one AI agent
completes in a single invocation.

{STORY_SIZING_GUIDANCE}

### Step 4: Define User Journeys

Create connected, end-to-end narratives that link observable truths into coherent
flows. Not isolated assertions ("GET /gear returns 200") but connected walks
("user clicks Gear in nav, sees list, clicks item, sees detail").

Every truth must appear in at least one journey. Journeys include
critical_transitions with {{from, to, mechanism}}.

### Step 5: Place Validation Checkpoints

{CHECKPOINT_PLACEMENT_GUIDANCE}

### Step 6: Specify Wiki Sections

For each story, specify `wiki_sections` — a list of wiki section header names from
the project wiki indexes (`.planning/wiki-indexes/`). The Stage 4 prompt builder
uses this to load targeted wiki sections into each story's agent prompt, keeping
prompt size manageable.

---

## Agent Configuration Reference

For each story, specify the full agent dispatch configuration.

{SKILL_MAPPING_REFERENCE}

{TOOL_REFERENCE}

{BUDGET_REFERENCE}

---

## Evidence Fields per Check Type

Each validation checkpoint must specify `evidence_fields` per criterion. Use the
correct fields for the check type:

{EVIDENCE_FIELDS_TABLE}

---

## Output Format

### Output 1: PLAN.md

Write the plan in this exact structure:

```
# Plan: {{Epic Title}}

## Goal

{{Outcome-shaped goal statement from goal-backward analysis}}

## Observable Truths

1. {{Truth 1 — user perspective, verifiable by a human}}
2. {{Truth 2}}
...

## User Journeys

### Journey 1: {{Persona}} — {{Summary}}

{{Narrative: connected end-to-end walkthrough in plain English, present tense.
Covers happy path from entry point through all critical transitions.}}

**Truths covered:** 1, 2, 3
**Entry point:** /path
**Critical transitions:**
- {{from}} -> {{to}} ({{mechanism}})

## Stories

### Story 1: {{Name}}

**Purpose:** {{What this story delivers — 1-2 sentences}}

**Agent:**
- model: {{sonnet|opus|haiku}}
- skills: [{{skill1}}, {{skill2}}]
- tools: [Read, Edit, Write, Bash, Glob, Grep]
- max_turns: {{number}}

**Scope:**
- Create: `{{path/to/new/file.py}}`
- Modify: `{{path/to/existing/file.py}}`

**Wiki Sections:** {{section1}}, {{section2}}

**Implementation Notes:**
- {{Domain-specific hint}}

**Truths Addressed:** {{1, 2}}

---

### Validation Checkpoint: After {{Story Name}}

**Type:** {{check_type}}
**Checks:**
- {{criterion}} (evidence: {{field1}}, {{field2}})

---

## Artefact Summary

| Truth | Key Artefacts | Story |
|-------|---------------|-------|
| Truth 1 | {{artefacts}} | Story 1 |
```

### Output 2: plan.json

Emit a valid JSON object conforming to this schema. The schema is a HARD CONSTRAINT.
Every required field must be present with the correct type.

<schema>
{schema_json}
</schema>

---

## Output Delimiters

Emit the two outputs separated by these exact delimiters:

```
===PLAN_MD_START===
(PLAN.md content here)
===PLAN_MD_END===

===PLAN_JSON_START===
(plan.json content here — valid JSON, no markdown fences)
===PLAN_JSON_END===
```

---

## Critical Rules

1. Every observable truth must be addressed by at least one story.
2. Every observable truth must appear in at least one journey's truths_covered.
3. Every checkpoint after_story must reference a valid story_id.
4. Every journey truths_covered ID must exist in observable_truths.
5. Files in scope.modify must be real files that exist in the GTS codebase.
6. Files in scope.create must have parent directories that exist.
7. Stories that use files created by earlier stories must appear after them.
8. state_assumption defaults to "cumulative". Only set "clean" when validation
   criteria depend on known data state.
9. The plan.json epic_number must be {epic_number}.
10. Do NOT invent features not described in the epic. Stay within scope.
11. Include wiki_sections per story for Stage 4 prompt builder consumption.
