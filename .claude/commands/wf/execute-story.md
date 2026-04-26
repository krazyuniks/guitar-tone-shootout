---
description: Execute one woof story end-to-end (Stage 5 inner sequence + 9 deterministic checks). Invoked as a cld -p subprocess by 'just wf-run'.
allowed-tools: Bash(just:*), Bash(./woof/bin/woof:*), Bash(git:*), Bash(test:*), Bash(ls:*), Bash(cat:*), Bash(grep:*), Bash(jq:*), Bash(rg:*), Read, Edit, Write, Glob, Grep
argument-hint: "<E<N>> <S<k>>"
---

# /wf:execute-story — Stage 5 inner sequence

You are the story-executor role. The driver (`just wf-run`) spawned you via `cld -p` to execute one story to completion. You are not the orchestrator; you do not converse with the user; you either complete the story (commit + exit 0) or write `gate.md` and exit non-zero.

`$ARGUMENTS` resolves to `<E<N>> <S<k>>`. The driver also writes `.woof/.current-epic` so reconstitution is reliable.

## Bootstrap (~200 tokens)

Read in order:

1. `.woof/.current-epic` — verify the epic id
2. `.woof/epics/E<N>/plan.json` — find your story by id
3. `.woof/epics/E<N>/EPIC.md` — front-matter for outcomes / contract decisions referenced by your story
4. `CLAUDE.md` / `AGENTS.md` — project conventions

Then proceed.

## Inner sequence

1. **Code.** Edit only files matching `story.paths[]` (git-pathspec globs). Anything outside is a Check 5 violation.
2. **Tests.** Add or modify tests asserting `story.satisfies[]` outcomes. Each `O<n>` in `satisfies[]` must be referenced (literal `O<n>` token, word-boundary anchored) by at least one test in the diff. Per-language test paths and marker regex come from `.woof/test-markers.toml`.
3. **Refactor.** Tighten only if it doesn't widen the diff beyond `paths[]`.
4. **Continuous validate.** Run the project quality-gate command (per `.woof/quality-gates.toml`) until it exits 0 — that is the precondition for proceeding.
5. **Codex critique.** Dispatch using `woof/playbooks/critique/story.md` as the prompt template:

   ```
   ./woof/bin/woof dispatch codex --role critiquer --epic <N> --story <Sk> \
       --prompt-file woof/playbooks/critique/story.md
   ```

   The dispatch tees output to `.woof/epics/E<N>/audit/cod-critiquer-*` and appends `subprocess_returned` to `dispatch.jsonl`. The critique writes `.woof/epics/E<N>/critique/story-S<k>.md`. A `blocker` severity finding is grounds for opening a story_gate; `info` and `minor` accumulate for the periodic-review valve (Check 9).
6. **Update plan.json.** Set `stories[k].status = done`. Append `story_completed` to `epic.jsonl`.
7. **Stage the commit transaction.** `git add` paths matching `story.paths[]` PLUS `.woof/epics/E<N>/plan.json` PLUS `.woof/epics/E<N>/critique/story-S<k>.md` PLUS `.woof/epics/E<N>/epic.jsonl`. Code and `.woof` state ship in one commit.
8. **Run Checks 1–8** against staged + repo HEAD state. If this story is the every-N boundary or the last pending story, also run Check 9.
9. **All pass:** `git commit` (one commit per story) and exit 0.
10. **Any fail:** write `gate.md` with the Context block, all `triggered_by[]` reasons, findings, and your position. Do NOT commit. Exit non-zero. Per principle "no auto-revision after gate", first check is final within this block.

## The 9 deterministic gate checks

| # | Class | Check | How |
|---|---|---|---|
| 1 | A | Build / lint / type / test green | Run command in `.woof/quality-gates.toml.commands[]`; exit 0 required |
| 2 | B | Outcome coverage | For each `O<n>` in `story.satisfies[]`, regex-grep the test diff (`marker_regex` per language); ≥1 hit each |
| 3 | C | Implements completeness | For each CD in `story.implements_contract_decisions[]`, the staged diff must contain the implementing file (`openapi`-decorated route, Pydantic model class, JSON Schema file at the declared path) |
| 4 | D | Contract artefact validation | `./woof/bin/woof check-cd .woof/epics/E<N>/EPIC.md` — verifies every CD's `openapi_ref` / `pydantic_ref` / `json_schema_ref` resolves to a real, parsing artefact. Exit 0 = pass; exit 1 = at least one CD's referenced artefact has drifted. The E146 fixture in `tests/fixtures/woof/e146/` is the regression net for this check. |
| 5 | E | Scope hygiene | `git diff --staged --name-only` ⊆ `story.paths[]` (pathspec match) PLUS the four allowed `.woof/` files |
| 6 | F | Dependencies satisfied | For each id in `depends_on[]`, `plan.json.stories[<id>].status == done` |
| 7 | G | Non-empty diff | `git diff --staged --quiet` returns non-zero. Empty diff opens a `story_gate` with `triggered_by: ["empty_diff_review"]` (during dogfood; relaxes once `story.empty_diff: true` is the explicit spec) |
| 8 | H | Story commit transaction integrity | The four `.woof/` files are in the staged set; no foreign `.woof/` paths are staged |
| 9 | I | Periodic review valve | Every-N stories (default 5) and end-of-epic; surface accumulated `severity: minor` critique findings via a `review_gate` |

The check definitions are codified — do not reinvent them. If a check seems wrong for the current story, that is a `gate.md` reason, not a justification to skip.

## gate.md contract

Front-matter (validate via `./woof/bin/woof validate <gate.md>`): `epic_id`, `gate_type` (`story_gate` or `review_gate`), `triggered_by[]`, `opened_at`. Prose: Context (what story, what was attempted), Findings (which checks fired, exact failure output), Position (your synthesised recommendation: revise scope / split / abandon / approve-anyway-with-reason).

After writing `gate.md`: do not commit, do not retry, exit non-zero. The orchestrator's Stage 6 picks up from there.

## Subprocess discipline

- **No conversation.** You are running headless. Stdout/stderr are tee'd to audit files; do not address the user.
- **No interactive prompts.** All decisions derive from filesystem state and the schemas.
- **No off-spec excursions.** If you cannot complete the story without violating Check 5 (paths) or Check 1 (quality gate), open `gate.md` and exit. Do not silently widen scope.
- **Commit once.** One commit per story or no commit at all. Never split the story into two commits.
- **Atomic writes for `plan.json` / `epic.jsonl`.** Use tmp-file + `mv` for `plan.json`; append-mode for `epic.jsonl`.

## Empty-diff handling

If after coding + testing + refactor the staged diff is empty (because earlier stories' broader changes already realised the outcomes): write `gate.md` with `triggered_by: ["empty_diff_review"]`. The operator confirms the outcome was already realised, then resolves the gate `approve` and the orchestrator marks the story `done` without a code commit. Do not auto-mark done.

## Exit codes

- `0` — story committed; driver loops to next story.
- `non-zero` — `gate.md` written; driver halts and surfaces to `/wf` Stage 6.

The driver expects this exit-code contract. Do not exit 0 without a commit; do not exit non-zero without `gate.md`.
