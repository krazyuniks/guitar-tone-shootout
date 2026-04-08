# First Principles Analysis — Discovery Workflow Design

> **Date:** 2026-04-08
> **Question:** What is the irreducible core of pre-planning knowledge work for a software project?
> **Context:** Post via-negativa pass. 16 features already cut. Examining whether the remaining 7-step structure itself has inherited assumptions from GSD/taches/Superpowers/obsidian-personal.

## Assumptions Challenged

### "Discovery is a 7-step sequential workflow"
**Partially true.** The steps are logical, but the sequence is inherited from GSD's phase model. In practice, research is iterative — read something, realise a gap, search, read more, revise understanding. The 7-step sequence linearises what is actually a loop. Steps are a useful prompting scaffold, not a runtime execution order.

### "There are two distinct scopes (project vs epic)"
**Partially true.** Project discovery is exploratory and divergent ("what should we build?"). Epic discovery is convergent ("how should we build this specific thing?"). Same workflow forces a divergent activity into a convergent structure, or vice versa. Project discovery might just be a conversation; epic discovery is a workflow.

### "You need a prior knowledge check as an explicit step"
**True, but not as a step.** Claude naturally checks context before going external. Making it explicit improves outcomes because it makes the check *visible* to the user and creates a gate ("is this enough?"). It's a gate, not a step.

### "Gap identification must happen before investigation"
**Partially true.** You often don't know what you don't know until you start looking. First search result reveals gaps you couldn't anticipate. Strict "identify all gaps, then investigate" prevents the most common discovery pattern: "I found X, which means I also need to understand Y." Investigation and gap identification are interleaved.

### "Investigation requires dedicated source adapters"
**False for v1.** Claude Code has WebSearch and WebFetch built in. Adding Brave is one more. The "adapter architecture" framing implies pluggable interfaces, registration, dispatch logic. In reality, "use WebSearch, optionally use Brave" is a prompt instruction, not an architecture.

### "Analysis requires thinking models as a separate step"
**Partially true.** Thinking models are valuable, but separating investigation from analysis implies "gather all facts first, then think." In practice, analysis happens *during* investigation. Making it separate risks a mechanical "now apply 3 frameworks" phase instead of integrated critical thinking throughout.

### "Synthesis must produce a specific document format (DISCOVERY.md)"
**True as convention, not fundamental.** The fundamental truth: findings must be *persisted* and *readable by the planner*. The format is a convention. The value is persistence + consumption, not the schema.

### "The user must confirm gaps before investigation begins"
**Partially true.** Gates prevent wasted work, but every gate is a blocking interaction. If the agent identifies 3 obvious gaps, the gate adds latency without value. Gates should exist for *consequential* decisions (spending money on API calls, changing the issue body), not for every step transition.

### "This needs to be a structured workflow at all"
**The deepest assumption.** What if the best pre-planning knowledge work is just a good prompt? "Check what you know. Identify gaps. Research specific questions. Think critically. Write DISCOVERY.md. Update the issue." The "workflow" is Claude's natural reasoning process, guided by a prompt.

## Fundamental Truths (Irreducible)

1. **An agent makes better plans when it knows more about the problem domain.** Discovery is only valuable when there are genuine unknowns.

2. **The agent cannot know what it doesn't know without checking.** The prior knowledge check forces confrontation with the boundary between "I know this" and "I'm guessing."

3. **External research produces better results with specific questions than broad topics.** Gap identification (turning unknowns into specific questions) is the highest-leverage activity in the entire workflow.

4. **Findings must outlive the session.** Persisting to files means the planner (in a different session) can read them.

5. **Decisions made during discovery must constrain planning.** Discovery outputs must be *authoritative* for planning. Locked/deferred/discretion is a mechanism for this truth.

6. **The user is the judge of sufficiency.** No programmatic scoring replaces the user saying "that's enough" or "dig deeper on X."

## Rebuilt Understanding — The Irreducible Core

Six activities, not seven steps. Activities 3 and 4 are interleaved, not sequential:

1. **Confront ignorance.** Force the agent to distinguish what it knows from what it's assuming. Check existing knowledge. Surface the boundary explicitly.

2. **Ask specific questions.** Turn vague unknowns into concrete, searchable questions. The single most valuable activity.

3. **Search and read.** Use whatever tools are available to answer the specific questions. No adapter architecture — just "search for answers."

4. **Think critically.** Challenge assumptions, surface trade-offs, compare options. Integrated into research, not a separate phase. Thinking models are prompting techniques that improve quality, not a phase.

5. **Write it down.** Persist findings + decisions to a file the planner will read. Clearly state what was decided and what was deferred.

6. **Update the issue.** (Epic-level only.) Enrich the GitHub issue so it's accurate and actionable.

## New Possibilities

- **Discovery as a prompt, not a pipeline.** A well-written skill prompt that guides Claude's natural reasoning. No steps, no gates, no modes.

- **Merge investigation and analysis.** "Research each gap, and as you research, apply critical thinking." Better output because analysis is contextual, not mechanical.

- **Two gates only.** (1) "Here's what I know — enough, or research externally?" (prevents unnecessary API spend). (2) "Here are findings and decisions — write DISCOVERY.md and update issue?" (prevents unwanted persistence).

- **7-step model as internal prompt structure, not user-visible workflow.** Ensures Claude covers all bases, but user sees: "Here's what I know. Here are the gaps. [gate] Here's what I found. [gate] Done."

- **Project discovery is a conversation, not a workflow.** Epic discovery benefits from structure. Project discovery is exploratory — forcing it into a structured workflow may make it worse. Consider: project discovery = conversation; epic discovery = skill.
