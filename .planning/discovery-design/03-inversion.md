# Inversion Analysis — Discovery Workflow Design

> **Date:** 2026-04-08
> **Question:** What would guarantee this discovery workflow fails or goes unused?
> **Context:** Post via-negativa (16 features cut) and first-principles (7 steps challenged, 6 irreducible truths identified). Surviving design is a Claude Code skill with conversational intake, prior knowledge check, gap identification, investigation, integrated critical thinking, DISCOVERY.md output, and issue enrichment.

## Goal

A discovery workflow that the user actually runs before epics with unknowns, that produces findings the planner actually uses, and that doesn't get abandoned like the previous pipeline.

## Guaranteed Failure Modes

### 1. Make it slower than just winging it
If running `/epic discover 178` takes 20 minutes of interaction before any research happens (intake questions, gap confirmation gates, mode selection), the user will skip it and go straight to planning. The previous pipeline burned ~155k tokens before coding started.
— **Avoid by:** minimal gates (two at most). The skill should produce useful output within 2 minutes of invocation. No mode selection, no configuration. Start working immediately.

### 2. Produce output the planner ignores
If DISCOVERY.md exists but the planner doesn't read it — or reads it and treats it as advisory rather than authoritative — discovery was wasted effort. Most insidious failure mode: user did the work but got no benefit.
— **Avoid by:** the planner skill/prompt MUST explicitly read DISCOVERY.md and commit to locked decisions. This is a contract between skills, not a hope. Test it: run a plan after discovery and verify locked decisions appear unmodified.

### 3. Ask the user questions they can't answer
"What consistency model do you need for your read-heavy workload?" — if the user knew, they wouldn't need discovery. Asking unanswerable questions makes the tool feel useless.
— **Avoid by:** intake asks about goals, constraints, and concerns — not technical specifics. "What are you trying to build? What worries you? What have you tried?" The tool answers the technical questions, not asks them.

### 4. Research things the agent already knows well enough
Claude's training data covers most mainstream technologies adequately. If Claude spends 10 minutes researching Redis basics via WebSearch, that's waste. Discovery should only go external for genuine unknowns or where current/accurate information matters (pricing, compatibility, breaking changes).
— **Avoid by:** honest prior knowledge check. "Here's what I know about Redis caching — likely sufficient from training data. The gap: I don't know the current `redis-py` async API surface or compatibility with SQLAlchemy 2.0. Research that specific question?" Research the delta, not the whole topic.

### 5. Make the output format more important than the content
If the skill spends effort ensuring DISCOVERY.md has perfect YAML frontmatter and numbered decision formats — but findings are shallow — format won over substance. The previous pipeline had perfect JSON schemas and empty insights.
— **Avoid by:** simple output format. A few markdown headers, prose content, a decisions list. If the agent spends more time formatting than thinking, the format is too complex.

### 6. Silently produce inferior results from missing infrastructure
If Brave API key isn't set and the skill silently falls back to WebSearch — producing shallower, less independent search results — the user gets worse findings without knowing why. They make decisions based on thin evidence. Silent degradation IS a workaround, and workarounds are banned.
— **Avoid by:** infrastructure is required, not optional. If Brave Search is part of the workflow, the API key must be configured. If it's missing: STOP, report the error clearly ("Brave API key not configured — discovery requires it"), and tell the user how to fix it. No graceful degradation. No silent fallbacks. Fail fast, fail loud. Same principle applies to any future adapter added to the workflow.

### 7. Try to be comprehensive instead of useful
Researching every possible angle to produce an exhaustive document. The user doesn't need 3000 words on Cassandra. They need: "For our use case, here's what matters, here's the recommendation, here are the 2 risks."
— **Avoid by:** the skill prompt explicitly says "focus on what changes the plan, not what's interesting." Decision-relevant findings only. If a finding doesn't affect a planning decision, cut it.

### 8. Require the user to validate every intermediate step
"Here are the gaps — confirm?" "Here are the search queries — confirm?" "Here are the raw results — confirm?" Each gate is friction. The previous pipeline had validation steps that blocked progress.
— **Avoid by:** two gates maximum. (1) After prior knowledge: "enough, or research?" (2) After findings: "write and update issue?" Everything between those gates is autonomous.

### 9. Build it as infrastructure instead of a skill
The moment there's a Python module, an adapter interface, a registration system, a dispatch layer — you're rebuilding the pipeline that died. A Claude Code skill is a prompt file. The "architecture" is the prompt structure.
— **Avoid by:** v1 is a `.md` skill file. No Python. No scripts. No adapter classes. If the prompt can't express the workflow, the workflow is too complex.

### 10. Design for the general case before solving the specific one
Extractability, portability, "any project can install this" — these dilute focus. Build for GTS first.
— **Avoid by:** use GTS paths, conventions, issue format. Don't abstract. Hardcode what you know.

### 11. Never actually use it
Most likely failure mode. Design complete, implementation done, but the user never reaches for it because going straight to planning is path of least resistance.
— **Avoid by:** make invocation trivial. Make first output appear fast. Make output tangibly better than planning without it. Value must be obvious on first use.

## Anti-Goals (Never Do)

- Never ask the user to configure the tool before using it (config is a prerequisite, not a step)
- Never produce output longer than what the planner needs to read
- Never silently degrade — fail fast if infrastructure is missing
- Never add a step that exists for "completeness" rather than utility
- Never require the user to read or approve raw research results
- Never build Python infrastructure for what a prompt can express
- Never research topics Claude already knows well enough from training data
- Never let the output format dictate the workflow
- Never implement workarounds or fallbacks — fix the real problem

## Success By Avoidance

By not adding ceremony, not gating every transition, not building infrastructure, not degrading silently, and not prioritising comprehensiveness over relevance — the tool becomes fast enough to actually use. The previous pipeline failed because it prioritised rigour over velocity. Discovery succeeds by being lightweight enough that skipping it feels like skipping a useful step, not dodging an obligation.

## Remaining Risk

- **Quality variance.** Brave + WebFetch may produce shallow results for niche technical topics. The user may need to manually provide URLs or context. The skill should handle user-provided context well.
- **Planner integration.** The contract between discovery output and planner input is critical and untested. If the planner doesn't respect locked decisions, the whole system breaks. Test early.
- **Scope creep in the skill prompt.** As edge cases appear, the temptation is to add more instructions, conditions, formatting rules. The skill prompt must stay lean or it'll bloat into the same over-engineering that killed the pipeline.
