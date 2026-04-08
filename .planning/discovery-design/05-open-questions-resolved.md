# Open Questions — Resolved

> **Date:** 2026-04-08
> **Source:** Discovery-Workflow-Design.md "Open Questions" section
> **Resolved by:** Via negativa, first principles, inversion, and second-order analyses

## Q1: Assumptions mode trigger

> Should the tool auto-detect when assumptions mode is appropriate, or always require explicit opt-in?

**Resolution: Question eliminated.** Assumptions mode was cut entirely (via negativa). A good intake step naturally proposes what it knows and asks the user to correct — that IS assumptions mode. No separate mode, no trigger, no opt-in. The skill always works this way: surface existing knowledge, let the user correct.

## Q2: Epic discovery mandatory vs optional

> Should the epic pipeline prompt "Run discovery first?" when it detects unknowns, or remain purely user-triggered?

**Resolution: User-triggered, but practically default.** Second-order analysis (Chain 1) shows discovery tends toward becoming the default over time because constrained plans are consistently better. The prior knowledge fast-path (2 minutes when sufficient) makes it cheap to run even for straightforward epics. No need for the pipeline to auto-detect unknowns — the user runs discovery, and if prior knowledge is sufficient, it terminates quickly.

## Q3: Adapter failure strategy

> Should discovery be strict (all must complete) or resilient (synthesise from whatever succeeded, flag gaps)?

**Resolution: Strict. All required adapters must complete.** User directive: "API keys should always be required. We should not continue if anything in the infrastructure is not available. We do not defer. No technical debt." Silent degradation is a workaround, and workarounds are banned (AGENTS.md). If an adapter fails: STOP, report the error, tell the user how to fix it. No graceful degradation. No silent fallbacks.

## Q4: Session management

> For deep discovery that exceeds one context window, how should handoff work?

**Resolution: Not a v1 design concern.** First-principles analysis concluded project discovery is a conversation (naturally fits one session with user steering). Epic discovery is narrow scope (1-3 focused questions) — should fit in one session. If a session does exceed context, use the existing `/whats-next` handoff mechanism. No custom session management needed. Solve if it becomes a real problem.

## Q5: Adapter quality evaluation framework

> How do we systematically compare adapter output quality over time?

**Resolution: Observation, not framework.** Via negativa cut this as premature infrastructure. You'll know what works by using it. After 5-10 discovery sessions, patterns will be obvious — "Brave consistently finds better technical content than WebSearch" or "Perplexity Sonar answers architectural questions well but misses implementation details." No structured scoring, no A/B infrastructure. Just use the tools and pay attention.
