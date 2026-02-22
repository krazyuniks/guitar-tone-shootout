# Gap Detection Guide

Prompt reference for the gap detection agent (Stage 2b). The agent reads the
enriched epic + CONTEXT.md, compares requirements against the codebase, and
produces a **locked decisions document** — the scope contract consumed by the
planner.

**Core principle: ask questions that matter.** The agent resolves mechanical and
deterministic gaps itself. It escalates questions where the user's input
genuinely affects the outcome — whether that's a high-level architectural
decision or a low-level implementation detail the agent can't determine from
the codebase. The bar is relevance, not importance. Don't ask questions you
can answer yourself; do ask questions where the user's knowledge or preference
would change the plan.

---

## 1. Autonomy Tiers

Every identified gap falls into one of two tiers:

### Auto-resolve (agent decides)

The agent resolves these silently and records the decision with rationale.

- **Mechanical consequences** — if the epic says rename X to Y, then renaming X
  everywhere (imports, configs, Dockerfiles, tests) is implementation, not a gap.
- **Deterministic answers** — questions answerable by reading the codebase. "Does
  package A depend on package B?" — read pyproject.toml.
- **Convention-following** — if the codebase has an established pattern, follow it.
  "Should the new endpoint use Pydantic schemas?" — yes, every other endpoint does.
- **Obvious consequences** — if A changes, everything that depends on A must update.
  This is not a question.

### Escalate (user decides)

The agent presents these as interactive questions. Escalate when the answer
cannot be determined from the codebase and the user's input would change
the plan. This can be architectural or low-level — the filter is **relevance**,
not **importance level**. A question is worth asking if:

- The agent genuinely doesn't know the answer, AND
- The user's answer would change what gets built or how

The test for whether to escalate: "Would a different answer from the user
lead to a different plan?" If yes, escalate. If no (i.e. there's really only
one reasonable path), auto-resolve.

Examples of genuine escalations:
- "The MessageBus Protocol is a port (domain layer) but its only consumer is
  moving to the messaging package. Keep it in domain for hexagonal purity, or
  co-locate with its implementation?"
- "The epic adds a new page but doesn't specify auth. The URL pattern suggests
  public, but similar pages require login. Which?"
- "This feature needs cross-BC communication. The wiki specifies pgmq for
  async, but this flow needs synchronous response. Direct import or
  request/reply queue?"
- "GearSyncRecord currently inherits from MessageEnvelope. After the move,
  should it remain a subclass (creating a gts→messaging dependency) or become
  a plain Pydantic model?"

---

## 2. Anti-patterns (never do these)

| Anti-pattern | Why it's wrong | What to do instead |
|---|---|---|
| **Confirm questions** ("Confirm X should happen?") | If the epic says X, then X should happen. | Auto-resolve: "X will happen as specified." |
| **Checklist-walking** (asking about every architecture area) | Wastes the user's time on areas with no gaps. | Only surface areas with genuine ambiguity. |
| **Mechanical consequence questions** ("Should we also update Y?") | Obvious follow-on work is not a decision. | Auto-resolve: "Y will be updated to match." |
| **Two questions in one** ("Should A and also should B?") | User cannot answer cleanly. | One question per gap, always. |
| **Paragraph-length options** (50-word option descriptions) | Unreadable. | Options are 1 sentence max. |
| **Vague open-ended questions** ("How should we handle X?") | Lazy — you should propose approaches. | Present 2–3 concrete options with your recommendation. |

---

## 3. Grey Area Detection (Domain-Aware)

Do not walk a generic checklist. Instead, identify grey areas based on what the
epic is actually doing:

| Epic type | Where grey areas typically live |
|---|---|
| **Structural refactor** (rename, move, reorganise) | Dependency direction, import paths, package boundaries |
| **New feature** | BC ownership, data model, auth requirements, UI interaction patterns |
| **New integration** | Cross-BC flow, queue topology, failure handling, data mapping |
| **Infrastructure change** | Container topology, config management, deployment sequence |
| **Data model change** | Migration strategy, backward compatibility, downstream consumers |

Focus your analysis on the grey areas relevant to THIS epic. Ignore areas that
are clearly specified or have no gaps.

---

## 4. Observable Outcomes

Before gap detection, verify the epic's observable outcomes are concrete:

- What is the observable result? (user sees X, API returns Y, database contains Z)
- What are the entry points? (URLs, endpoints, CLI commands, queue messages)
- What does "it worked" look like from an observer's perspective?
- What existing behaviour must remain unchanged? (regression boundaries)

If outcomes are vague, this is a genuine escalation — the user must clarify what
"done" looks like.

---

## 5. Output Format

The agent produces a structured report with two sections:

### Locked decisions (auto-resolved)

Each entry: what the gap was, what the agent decided, why. These become binding
constraints for the planner — no re-litigation downstream.

### Escalated questions (for user)

Each entry: the gap, 2–4 concrete options (1 sentence each), the agent's
recommendation with brief reasoning. The user picks an option or provides their
own answer. Once answered, these also become locked decisions.

---

## 6. Coverage

The agent confirms it checked these architecture concerns. Not every area will
have gaps — most won't. List which areas were checked and note "no gaps found"
for clean areas:

- Bounded context boundaries and ownership
- Data and behaviour
- Messaging and cross-BC flows
- API contracts
- Frontend
- Workers and background processing
- Testing strategy
- Security
- Infrastructure
