---
epic_id: 181
title: Audit redaction + 256 KB cap (woof dispatch)
observable_outcomes:
  - id: O1
    statement: A dispatched subprocess whose audit output contains a known secret pattern lands on disk with the secret replaced by a [REDACTED:<reason>] marker, and the post-redaction file passes a no-secrets grep.
    verification: automated
  - id: O2
    statement: A dispatched subprocess whose stdout exceeds the configured per-file cap (default 256 KB) lands on disk truncated to the cap with a "... [truncated, full output at .woof/epics/E<N>/audit/raw/]" footer; the raw file is present at the gitignored raw path.
    verification: automated
  - id: O3
    statement: An operator can disable redaction or raise the cap via .woof/agents.toml without re-deploying the woof CLI.
    verification: automated
contract_decisions:
  - id: CD1
    related_outcomes: [O1, O2, O3]
    title: Audit redaction policy schema
    json_schema_ref: woof/schemas/agents.schema.json
    notes: |
      The redaction patterns and per-file cap live under a new
      [audit] block in agents.toml; the agents schema gains an
      optional `audit` property documenting both knobs. CD points
      at the existing schema once that block is added.
acceptance_criteria:
  - "Every dispatched subprocess has a redacted .output (committed) and a raw .output (gitignored under audit/raw/)."
  - "The redaction filter is conservative (false positives leave a [REDACTED] marker; false negatives are an audit failure)."
  - "Per-file cap is configurable via .woof/agents.toml [audit].max_bytes; default 262144."
  - "A unit test feeds a known JWT/AWS-key/bearer-token pattern through the redactor and asserts the output is scrubbed."
  - "A unit test dispatches a stub harness whose stdout exceeds the cap and asserts truncation + raw-file landing."
  - "just test-woof is green on completion."
---

# Audit redaction + 256 KB cap

The first dogfood epic for woof. Task 2 (`woof dispatch`) shipped without
the redaction filter and size cap that Workflow.md §"Audit redaction and
retention" calls non-negotiable for committed audit files. Without it,
codex prompt/output transcripts that land in the repo can leak the
contents of `env.local.sh`, JWT bearer tokens captured during a flow,
and any `.gts-auth.json` token blobs read by a tool the subprocess
invoked.

The fix has two halves: **conservative redaction** of known secret
shapes before the file lands on disk, and a **per-file size cap** with
overflow to a gitignored `audit/raw/` path so the truncation never
loses data.

This is exactly the kind of work woof itself should help build: small
scope, clear contract, deterministic verification. Driving it through
the full Discovery → Definition → Plan → Execute pipeline is the first
real proof that the orchestrator + dispatch + check-cd + driver chain
works end-to-end.
