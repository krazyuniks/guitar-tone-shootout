# Second-Order Effects Analysis — Discovery Workflow Design

> **Date:** 2026-04-08
> **Question:** What are the consequences of consequences when building this discovery workflow?
> **Context:** Post via-negativa, first-principles, and inversion. User wants thorough discovery with simple implementation. No shortcuts on research quality.

## Chain 1: Planner reads DISCOVERY.md with locked decisions

**First-order:** Planner receives authoritative constraints. Locked decisions implemented without re-evaluation. Planning is faster — narrower decision space.

**Second-order:** Planner becomes *dependent* on DISCOVERY.md. Epics without discovery have unconstrained planning — quality gap becomes visible between discovered and undiscovered epics.

**Third-order:** User starts running discovery on *every* epic, even without obvious unknowns, because constrained plans are consistently better. Positive feedback loop — more discovery files = more prior knowledge = faster future discoveries.

**Design implication:** Don't fight this tendency. Design the skill so it's fast enough for "light discovery" (mostly prior knowledge, minimal external research) as well as deep investigation. The prior knowledge gate ("this is sufficient") is the natural fast-path.

## Chain 2: Investigation sources can't answer niche questions

**First-order:** Brave returns generic results. WebFetch retrieves docs but they're API references without architectural guidance. Discovery has gaps — questions marked as "Unknowns."

**Second-order:** User provides context directly: specific URLs, maintainer conversations, direct experience. Discovery becomes *collaborative* — part automated, part human knowledge injection. This is the right model.

**Third-order:** Skill needs to handle user-provided context as first-class input. DISCOVERY.md attributes both automated and human sources. More thorough than either alone.

**Design implication:** Skill must explicitly invite user input during investigation. "I couldn't find definitive guidance on X. Do you have a source, a contact, or direct experience?" Make the collaborative path first-class. Consider Perplexity Sonar as a required v1 adapter — its synthesis capability addresses the niche question gap.

## Chain 3: Epic discovery produces knowledge useful beyond the epic

**First-order:** General findings trapped in `.planning/epics/E178/DISCOVERY.md`.

**Second-order:** Future discoveries check prior epic DISCOVERY.md files as prior knowledge. Works but noisy — reading through epic-specific context to extract general knowledge.

**Third-order:** After 10+ epics, substantial knowledge is fragmented across epic-specific files. Prior knowledge step gets slower. Per-epic organisation becomes a retrieval problem.

**Design implication:** Cross-scope promotion (cut in via negativa) needed sooner than expected. Not automated — manual step in enrichment: "These findings about pgmq patterns are general. I'll also write them to `.planning/discovery/messaging-patterns.md`." Skill prompts for this; user confirms.

**Revised position:** Reinstate cross-scope promotion as manual, user-confirmed step.

## Chain 4: Discovery as pre-planning step

**First-order:** Workflow gains a phase: issue → discover → plan → implement. Each epic takes longer to *start* but planning is faster with fewer mid-implementation pivots.

**Second-order:** Total time per epic may *decrease*. Mid-implementation discoveries ("this library doesn't support async") caught earlier. Cost front-loaded; savings distributed across planning and implementation.

**Third-order:** User's relationship with uncertainty changes. "What don't we know?" becomes the default question. Issues written with explicit unknowns. Epics scoped smaller when unknowns are large.

**Delayed consequence:** Risk of *discovery paralysis* — reluctance to start without discovery. Antidote: prior knowledge gate makes fast path genuinely fast (2 minutes when sufficient).

## Chain 5: Quality after 5-10 discovery files

**First-order:** Plans are well-constrained and informed.

**Second-order:** Prior knowledge check now has substantial material. New discoveries start from a richer base.

**Third-order:** Discovery sessions get *shorter over time*. First discovery: 30 minutes. Fifth discovery: 10 minutes. **Compounding returns** — strongest argument for the workflow. Not just per-epic value, but cumulative project-level value.

**Delayed consequence:** Accumulated discovery files become useful project documentation — battle-tested findings, not aspirational docs. Risk of two sources of truth (wiki vs discovery). Need clear boundary: `.planning/discovery/` for investigated findings with decisions; wiki for reference architecture and operational docs.

## Key Insights

1. **Discovery has compounding returns.** Each session makes future sessions cheaper. First 2-3 are most expensive and least impressive — must persist through bootstrap cost.
2. **Cross-scope promotion should be in v1** — manual, user-confirmed, but present from start.
3. **Planner integration is the critical contract** — untested = not working.
4. **User input during investigation is essential** — pure automated research won't cover niche questions.
5. **Fast path must be genuinely fast** — prior knowledge sufficient = done in 2 minutes.
6. **Wiki/discovery boundary needs a convention** — establish before first discovery session.
