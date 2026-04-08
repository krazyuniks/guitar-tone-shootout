---
description: Guided project-level discovery. Explore the problem space collaboratively, persist findings to .planning/discovery/.
allowed-tools: Read, Grep, Glob, Write, Edit, WebSearch, WebFetch, Bash(gh:*), Bash(mkdir:*), Bash(date:*)
---

# /epic-discover-project — Project Discovery

You are running project-level discovery. This is a conversation, not a rigid workflow. You and the user explore the problem space together. Your role: research, challenge assumptions, write down findings. The user's role: steer direction, judge sufficiency, provide context you can't find.

## Preflight

Run these checks. If any fail, STOP and report the error. No graceful degradation.

1. **GitHub CLI:** `gh issue list --repo krazyuniks/guitar-tone-shootout --limit 1` — must succeed.
2. **Web search:** Run a trivial WebSearch query (e.g. `"test"`) to confirm the tool is available and returns results. If it fails: "WebSearch is not available. Discovery requires web search capability."

## Context Assembly

Read existing project knowledge (skip what doesn't exist):

- `.planning/discovery/` — prior project-level findings
- `.planning/codebase/` — codebase mapping
- `../wiki/` — architecture docs, technical reference
- `.planning/epics/E*/DISCOVERY.md` — prior epic discoveries

Summarise what you know about the project's current state and open questions. Present this as a starting point, not a wall of text.

## Exploration

Follow the user's lead. They may want to:

- Investigate a technology choice
- Evaluate architectural alternatives
- Map a domain they don't fully understand
- Research market/ecosystem context
- Stress-test an assumption about the product

For each direction the user takes:

1. **Check what you know first.** State what you can contribute from existing knowledge and training data. Be explicit about confidence.
2. **Research when needed.** Use WebSearch and WebFetch for external information. Ask specific questions, not broad topics.
3. **Think critically.** Challenge assumptions. Surface trade-offs. Apply thinking models where they sharpen analysis — first principles, inversion, via negativa, second-order effects, 5-whys — but don't force them.
4. **Ask when stuck.** "I couldn't find definitive guidance on X. Do you have a source or direct experience?"

## Writing Findings

When the conversation produces a finding worth persisting, offer to write it:

"This finding about [topic] is worth capturing. Shall I write it to `.planning/discovery/[topic].md`?"

Write only with user confirmation. Each file is a focused topic — not a dump of everything discussed.

Format for discovery files:

```markdown
# [Topic Title]

> Discovered: YYYY-MM-DD

[Findings in clear prose. Source attribution where applicable.]

## Decisions

- **D-01 (locked/deferred/discretion):** [Decision statement] — [Rationale]

## Open Questions

- [Anything still unresolved]
```

Keep files focused. One topic per file. If a topic grows, split it.

## Boundaries

- `.planning/discovery/` is for investigated findings with decisions. `../wiki/` is for reference architecture and operational docs.
- Discovery files cite wiki docs — they don't duplicate them.
- If discovery contradicts the wiki, flag it. The wiki may need updating.

## Completion

Project discovery ends when the user says it does. There is no formal gate. When the user is satisfied, summarise what was written and where.
