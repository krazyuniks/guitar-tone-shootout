---
name: brainstorm
description: Interactive issue enrichment before the epic pipeline runs.
argument-hint: "<epic-number>"
context: current
---

# Epic Brainstorming

`/epic brainstorm <N>` enriches a GitHub issue in place so `just epic <N>` can
plan from a clear contract.

## Inputs

Read:

1. `gh issue view <N> --repo krazyuniks/guitar-tone-shootout --json title,body,labels`
2. `AGENTS.md`
3. `../wiki/GTS-Technical-Architecture.md`
4. `.planning/codebase/STRUCTURE.md` if it exists

## Goal

Turn the issue into a small, declarative contract with:

- `## Summary`
- `## Observable Outcomes`
- `## Decisions`
- `## Regression Boundaries`

## Rules

- One question at a time.
- Prefer concrete options with a recommendation.
- Resolve ambiguity against the repo and architecture before drafting.
- Keep the issue outcome-focused, not implementation-plan-heavy.
- Everything written in the issue is intended to ship.

## Process

1. Read the issue and assess scope.
2. If the issue is too large, propose decomposition into child issues first.
3. Clarify missing decisions through conversation.
4. Draft the enriched issue body.
5. Review it with the user.
6. Update the issue with `gh issue edit --repo krazyuniks/guitar-tone-shootout`.

## Completion

After updating the issue:

- confirm the issue is ready for `just epic <N>`
- tell the user this brainstorming session is complete
