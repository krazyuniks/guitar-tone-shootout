---
description: Structured pre-planning discovery for a specific epic. Researches unknowns, writes DISCOVERY.md, enriches the GitHub issue.
allowed-tools: Read, Grep, Glob, Write, Edit, WebSearch, WebFetch, Bash(gh:*), Bash(mkdir:*), Bash(date:*)
argument-hint: "<issue-number>"
---

# /epic-discover — Epic Discovery

You are running structured discovery for epic #$ARGUMENTS. Your job is to build an informed foundation before planning begins — not to plan, not to implement. Discovery only.

## Preflight

Run these checks. If any fail, STOP and report the error. No graceful degradation.

1. **GitHub CLI:** `gh issue view $ARGUMENTS --repo krazyuniks/guitar-tone-shootout` — must succeed and return the issue body.
2. **Web search:** Run a trivial WebSearch query (e.g. `"test"`) to confirm the tool is available and returns results. If it fails: "WebSearch is not available. Discovery requires web search capability."

If both pass, proceed. The issue body from step 1 is the product scope.

## Phase 1: Confront Ignorance

Assemble prior knowledge from these sources (read what exists, skip what doesn't):

- `.planning/discovery/` — project-level findings from previous sessions
- `.planning/codebase/` — codebase mapping (STRUCTURE.md, SCHEMA.md, ENDPOINTS.md, etc.)
- `../wiki/` — architecture docs, technical reference
- `.planning/epics/E*/DISCOVERY.md` — prior epic discoveries
- The codebase itself — grep/glob for relevant code, patterns, existing implementations

Distinguish three categories and present them explicitly:

- **Known** — facts supported by prior discovery files, wiki docs, or code you can read
- **Assumed** — things likely true from training data but not verified against this project
- **Unknown** — genuine gaps where you lack information

Present this to the user. Be honest about the boundary. If you're guessing, say so.

**Gate 1:** Ask the user: "Is prior knowledge sufficient, or should I research externally?"

- If sufficient → skip to Phase 3 (synthesis).
- If research needed → proceed to Phase 2.

## Phase 2: Research

### Ask specific questions

Turn unknowns into concrete, searchable questions. Not "research Redis" but:
- "What is the current async API surface for redis-py 5.x?"
- "Does library X support SQLAlchemy 2.0 async sessions?"

Specific questions produce focused research. Broad topics produce noise.

### Search, read, and think critically

Research each question. Use:
- **WebSearch** — primary search tool
- **WebFetch** — retrieve and read specific URLs

As findings come in, think critically. Do not mechanically apply frameworks — but where they sharpen analysis, use them:

| Model | When it helps |
|-------|---------------|
| First principles | Challenging "how it's always done" assumptions |
| Inversion | "What guarantees this fails?" risk assessment |
| Via negativa | "What can we remove?" scope simplification |
| Second-order effects | "What are the consequences of consequences?" |
| 5-whys | "Why do we actually need this?" root motivation |

**Focus on what changes the plan, not what's interesting.** If a finding doesn't affect a planning decision, skip it.

**Collaborative investigation:** When you can't find a definitive answer, ask the user: "I couldn't find definitive guidance on X. Do you have a source, a contact, or direct experience?" User-provided context is first-class input.

**Progressive disclosure:** Show findings incrementally. Let the user steer — "enough on that, dig deeper on Y."

## Phase 3: Synthesis

Present your findings and recommended decisions to the user.

Categorise every decision:

| Category | Meaning | Downstream effect |
|----------|---------|-------------------|
| **Locked** | Decided. Implement exactly as stated. | Planner commits without re-asking. |
| **Deferred** | Explicitly out of scope. | Planner treats mention as scope creep. |
| **Discretion** | Agent decides during implementation. | Planner has freedom within stated boundaries. |

Number decisions D-01, D-02, etc. Include rationale for each.

**Gate 2:** Ask the user: "Shall I write DISCOVERY.md and update the issue?"

## Phase 4: Write and Enrich

### Write DISCOVERY.md

Create `.planning/epics/E$ARGUMENTS/DISCOVERY.md` (create the directory if needed):

```yaml
---
epic: $ARGUMENTS
title: "<title from issue>"
discovered: YYYY-MM-DD
---
```

Sections (use only what's relevant — empty sections are noise):

- **Domain** — scope boundary: what the epic covers and does not cover
- **Findings** — what we learned, per question, with source attribution
- **Decisions** — locked / deferred / discretion, numbered D-01, D-02... with rationale
- **Code Context** — reusable assets, patterns, integration points discovered in the codebase
- **Canonical Refs** — full paths to specs, docs, ADRs that downstream agents must read
- **Deferred** — out-of-scope ideas captured for later
- **Unknowns** — what we still don't know, flagged for future investigation

### Enrich the GitHub issue

Update the issue body with `gh issue edit`. Add or replace these sections:

- `## Summary` — informed by discovery (replace pre-discovery assumptions)
- `## Observable Outcomes` — grounded in feasibility
- `## Decisions` — locked/deferred/discretion from analysis
- `## Regression Boundaries` — informed by pitfalls discovered
- `## Discovery Reference` — link: `.planning/epics/E$ARGUMENTS/DISCOVERY.md`

**Preserve** existing issue content that is still accurate. Replace what discovery has superseded.

### Precedence

- DISCOVERY.md wins for technical decisions, findings, and implementation approach.
- GitHub issue wins for product scope (what we're building and why).
- If they conflict after enrichment, you have a bug — reconcile before finishing.

## Phase 5: Promote General Findings

If discovery produced knowledge useful beyond this epic (general patterns, technology evaluations, architectural insights), identify these and ask the user:

"These findings about [topic] are general. Should I also save them to `.planning/discovery/[topic].md`?"

Only promote with user confirmation. Do not automate this.

## Completion

Confirm: "Discovery complete for #$ARGUMENTS. DISCOVERY.md written, issue enriched. Ready for planning."

Do NOT proceed to planning. Discovery is done. The user decides what happens next.
