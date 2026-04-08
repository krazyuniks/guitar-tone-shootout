# Via Negativa Analysis — Discovery Workflow Design

> **Date:** 2026-04-08
> **Question:** What can we remove from the design and still have a useful v1 discovery workflow?
> **Context:** The previous epic pipeline died from over-engineering and deadlocking. This design has 8 source adapters, 4 interaction modes, 3 investigation depths, evidence quality assessment, two-step synthesis, facet decomposition, 3 deferred capture mechanisms, content hash change detection, raw result immutability, confidence scoring, cross-scope promotion, and more.

## Subtraction Candidates (CUT from v1)

### 4 interaction modes (standard/batch/text/analyse)
Remove because this is designing a preferences system before the tool exists. Every mode is just a prompt variation — if the user wants batch questions, they'll say "give me several at once." Eliminates an entire configuration axis and the code to support it. Just have good conversational intake.

### Assumptions mode as a separate mode
Remove because it's another mode toggle. A good intake step naturally proposes what it knows and asks the user to correct. That IS assumptions mode — it doesn't need a name or a switch. Removes a branching path from Step 1.

### Facet decomposition (obsidian-personal pattern)
Remove because it adds a planning-before-planning step. "Break gaps into facets, dispatch facets to adapters" is the obsidian-personal pipeline's job tracking architecture leaking into a Claude Code skill. Claude can just research the gaps. It doesn't need a formal facet decomposition layer to do targeted searches. Eliminates an entire abstraction layer between "here are the gaps" and "go research them."

### 8 research type heuristics table
Remove because the tool "selects the appropriate type based on the gap" — which means Claude reads the gap and decides how to research it. That's what Claude already does. Labelling it "deep-dive" vs "technical" vs "landscape" adds taxonomy without changing behaviour. Removes a classification system that exists only in the design doc.

### 3 investigation depth levels (quick verify/standard/deep)
Remove because depth is emergent from the question, not a pre-selected tier. "What's Cassandra's consistency model?" naturally gets a quick answer. "Should we replace PostgreSQL with Cassandra?" naturally goes deep. Claude doesn't need a depth selector. Removes a configuration axis that Claude will ignore in practice.

### Evidence quality assessment (richness/agreement/coverage) with confidence scoring
Remove because this is quality infrastructure for a system that doesn't exist yet. You cannot assess "richness" or "agreement" programmatically in v1 — Claude will read the results and judge quality as part of synthesis. Formal scoring adds false precision. Eliminates a scoring framework that would either be hand-waved by the LLM or require substantial tooling to be meaningful.

### Two-step synthesis (per-facet extraction then reconciliation)
Remove because it depends on the facet decomposition you're also cutting. Without formal facets, synthesis is: Claude reads all the research results and writes a coherent summary. That's one step. The two-step pattern is valuable in obsidian-personal where you have database-stored results from 6 independent adapters. In a Claude Code skill where everything is in context, it's overhead. Synthesis becomes "write the output" instead of "extract per facet, then reconcile."

### Raw result immutability + provenance tracking
Remove because flat markdown files in `.planning/` are already immutable-enough (git tracks history). Formal provenance tracking (which adapter produced what, content hashes, re-synthesis without modifying raw results) is database thinking applied to a directory of markdown files. Results are just files. Git is your provenance.

### Content hash change detection (SHA256)
Remove because this is an optimisation for a workflow that runs rarely (the doc says project discovery is "rare" and epic discovery is "ad hoc"). Optimising for cache hits on a rarely-run process is premature. Removes a caching mechanism for something that doesn't need caching.

### Parallel dispatch with 2-second polling and 10-minute timeout
Remove because this is the obsidian-personal job queue architecture. In a Claude Code skill, "parallel" means spawning sub-agents with the Agent tool — Claude Code handles the orchestration. You don't need to build a polling loop. Eliminates process management code that Claude Code already provides.

### Seeds with trigger conditions + Notes (zero-friction capture) as separate mechanisms
Remove because you already have a "Deferred" section in DISCOVERY.md. Seeds with auto-surfacing trigger conditions are a feature for a mature system, not v1. Notes are just text. The user has a text editor. Collapses 3 deferred capture mechanisms into 1 (the Deferred section that already exists in the output format).

### Cross-scope promotion
Remove because it's a v2 convenience. If epic discovery produces generalisable knowledge, the user can move the file. An automated "promote to project level?" prompt is nice-to-have, not essential. Removes a feature that sounds useful but adds a branching path to every epic discovery session.

### `<claude_context>` blocks
Remove because the planner is Claude. Claude can read prose. XML blocks for "machine-readable context" add formatting overhead without changing what the planner actually does — reads the discovery doc and plans accordingly. The planner doesn't parse XML; it reads text. Simplifies output format. Findings are just written clearly.

### Frontmatter schema bloat (confidence/facets/sources fields)
Remove most of it. Keep `epic`, `title`, `discovered` (date). The rest (`confidence`, `facets`, `sources` list) is metadata that nothing consumes. Frontmatter becomes 3 fields instead of 8.

### Extractability constraints ("no GTS-specific imports")
Remove as a design constraint for v1. Build it for GTS. If it's good, extracting it later is trivial — it's a Claude Code skill, not a compiled binary. Designing for extraction now constrains implementation choices without delivering value. Frees you to use GTS conventions, paths, and patterns without worrying about portability.

### Adapter category taxonomy (5 categories)
Remove the taxonomy. You have adapters. Some search, some synthesise, some do both. The 5-category classification is a design doc artefact that doesn't change how they're called. Adapters are just "sources" without a classification hierarchy.

### Staleness detection (90-day flag)
Remove because it's premature UX polish. The user will know if prior knowledge is stale — they're the one who wrote it or read it. Removes a date-checking mechanism for something a human already does.

## Keep (Passed the Test)

- **7-step workflow structure** — this IS the design. The irreducible sequence of knowledge work. Steps can be lighter, but the flow is correct.
- **Two entry points** — "same workflow, different scope" is the core insight.
- **Prior knowledge check (Step 2)** — genuinely novel and valuable. Saves real time and tokens.
- **Gap identification (Step 3)** — "what specifically do we not know?" is the highest-leverage question.
- **Decision categorisation (locked/deferred/discretion)** — directly solves agents re-litigating decisions during planning. High-value, low-complexity.
- **Source adapters (the concept, not 8 of them)** — but 2-3 for v1, not 8.
- **Thinking models in Step 5** — already built (taches `/consider:*`). Zero implementation cost.
- **DISCOVERY.md output format** — good output schema (Domain, Findings, Decisions, Code Context, Unknowns).
- **Hard gate after enrichment** — necessary state transition.
- **Flat markdown storage** — absolutely correct.
- **Deferred section in DISCOVERY.md** — the single deferred capture mechanism.

## After Subtraction — v1 Shape

A 7-step discovery workflow as a Claude Code skill (pure prompt, no scripts). Two entry points. Conversational intake without mode selection. Prior knowledge check against `.planning/` and wiki. Gap identification as specific questions. Investigation using 2-3 adapters (WebSearch + WebFetch as baseline, Brave Search as the one external adapter for v1). Analysis using existing taches thinking models. Single-pass synthesis into DISCOVERY.md. Enrichment of the GitHub issue.

Adapter count: 8 → 3 for v1:
1. **WebSearch** (built-in, zero setup)
2. **WebFetch** (built-in, zero setup)
3. **Brave Search** (one API key, optional)

Perplexity and Gemini adapters are v2 — add when the basic workflow is proven.

## What to Say No To (Future)

- Adapter quality evaluation frameworks
- A/B comparison infrastructure for adapters
- Session management / handoff for long discoveries
- Standalone investigation tool (`/investigate`)
- Any form of job queue, polling loop, or process management
- Programmatic confidence scoring
- Any storage more complex than "write a markdown file"
- Re-synthesis without modifying raw results
- Automated seed surfacing at milestone boundaries
