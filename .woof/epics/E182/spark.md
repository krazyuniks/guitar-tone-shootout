# Spark — E182

> Source: gh issue #182 — "woof: codify all stage-boundary checks + gate authoring as deterministic subcommands"
> Status: Spark only. Discovery has not started.

## Framing

E181's Stage 5 silently shipped a known-broken commit (`c64066f6`, since reverted in `e5d42c37`) because the `/wf:execute-story` skill body's Check 6 had drifted from canon. Codex correctly returned `severity: blocker` with two real findings against the new `apply_size_cap()`; the executor proceeded anyway because the skill's prose-encoded Check 6 read "Dependencies satisfied" instead of the canonical "Cross-AI critique flags blocker". Nothing told the executor to halt.

The bug is the *pattern*: skill prose claiming to enumerate deterministic checks, executed by a non-deterministic LLM that may quietly diverge from the prose. The same pattern exists at every stage — Stage 5 is just where it failed first.

## Direction (informal — to be challenged in Discovery)

- Each stage gets a `woof check-stageN` subcommand that returns structured pass/fail + `triggered_by[]` enum on stdout.
- Skill bodies (`/wf`, `/wf:plan`, `/wf:execute-story`) collapse to thin caller patterns. They produce artefacts, then call the check binary, then react to its exit code. They do not enumerate checks.
- Gate.md authoring goes through `woof gate write --type ... --triggered-by ... --findings <file>` so YAML field names cannot drift from `gate.schema.json`.
- `/wf` reconstitution uses `check-stageN` in order to determine current stage instead of LLM filesystem inspection.

## Constraints

- E181 sits in a half-finished state (S1 done, S2 reverted to pending). E182's outcomes must be sufficient to enable a clean S2 re-dispatch — particularly the critique-severity check.
- Hot-bootstrap reality: E182's own Stage 5 will execute under the still-broken skill until E182's own early stories land the new check binary + revised skill. Manual operator vigilance applies until then (grep critique severity after every commit).
- Single-epic scope. The dropping of `cld`/`cod` wrapper hard-deps and the `--effort` / reasoning-level controls are tracked separately (#13 in the orchestrator's task notes); they do not bundle into E182 unless Discovery surfaces a hard coupling.

## Open questions for Discovery

- Should each check be a separate subcommand (`woof check-quality-gate`, `woof check-outcome-coverage`, ...) or a single bundled `woof checks-stageN` that runs all relevant checks in one invocation? Bundled is simpler for callers; separate is more composable for ad-hoc checking.
- Where does `gate write` live — same `woof` binary or a sibling? (Probably same.)
- What is the structured-output format for failing checks? (Probably JSON with `triggered_by[]` matching the gate schema enum.)
- Are there checks that are NOT codifiable (require human judgement)? If so, they should be acknowledged explicitly rather than smuggled into the skill prose under the same label.
- How does this epic's own Stage 5 protect itself before its early stories land the binary? Manual operator vigilance, or a temporary prose-Check-6 patch as transitional safety?
- Hot-bootstrap ordering: which check binary does the planner pick first to maximise self-protection?
