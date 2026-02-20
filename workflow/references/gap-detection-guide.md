# Gap Detection Guide

Prompt reference for the gap detection agent (Stage 2b). The agent reads the enriched epic + CONTEXT.md and identifies implementation gaps — ambiguities, assumptions, contradictions, and missing information between the epic requirements and the current architecture/codebase. This guide is NOT a static questionnaire. The agent generates context-specific questions from what it actually finds.

---

## 1. Observable Outcomes (Always Asked)

Before detecting gaps, confirm the observable outcomes from the enriched epic are concrete and verifiable:

- For each outcome: what is the observable result? (user sees X, API returns Y, database contains Z, process produces W)
- What are the entry points? (URLs, API endpoints, CLI commands, queue messages, triggers)
- What are the success states? What does "it worked" look like from the observer's perspective?
- What are the error/edge states? What happens when things go wrong?
- What existing behaviour must remain unchanged? (regression boundaries)

Each outcome feeds directly into `plan.json` observable truths and verification criteria.

---

## 2. Gap Detection (Agent-Driven)

Compare the epic requirements against the full architecture and codebase. Look for these gap types:

| Gap Type | What to Look For | Example |
|----------|------------------|---------|
| **Ambiguity** | Requirement could be interpreted multiple ways | "The epic mentions 'processing audio' — this could mean NAM inference, IR convolution, or loudness normalisation. Which?" |
| **Assumption** | Epic assumes something exists or works that doesn't | "The epic assumes gear can be compared, but no comparison UI exists yet" |
| **Contradiction** | Epic conflicts with existing architecture or rules | "The epic wants real-time updates but the architecture is request/response only" |
| **Missing information** | Epic doesn't specify something the planner needs | "The epic describes a new page but doesn't specify whether it needs authentication" |
| **BC ownership** | Unclear which bounded context owns the logic | "This feature touches both core and audio — which BC owns the primary logic?" |
| **New cross-BC flow** | Feature requires communication that doesn't exist | "This requires T3K sync data to trigger audio processing — no message flow connects these today" |

---

## 3. Coverage Checklist

The agent must confirm it has checked for gaps across ALL of these architecture concerns. Not every area will have gaps — but every area must be checked:

- **Bounded context boundaries and ownership** — which BC(s), does this cross boundaries?
- **Data and behaviour** — new entities, lifecycles, inputs/outputs, relationships to existing data
- **Messaging** — new cross-BC flows, queue topology, transactional outbox requirements
- **API contracts** — new endpoints, auth requirements, request/response shapes
- **Frontend** — page types, interaction patterns, navigation
- **Workers and background processing** — which worker(s), processing pipelines, triggers
- **Testing strategy** — critical journeys, test level (unit/integration/E2E)
- **Security** — authentication, ownership checks, input validation
- **Infrastructure** — containers, configuration, MCP server requirements

---

## 4. Sufficiency Confirmation

The agent must confirm:

- All architecture areas have been checked for gaps.
- Every identified gap has been resolved through Q&A.
- The resolved decisions are sufficient to create a robust and thorough plan.
- No remaining ambiguities, assumptions, or contradictions.

The critique agent independently verifies sufficiency before the gap report is presented to the user for acceptance.
