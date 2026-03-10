# Deprecated

`/epic review-tests` is not part of the current epic workflow.

Do not use or recommend a `tests_approved` gate. The live workflow is:

1. `just epic <N>` for planning and approval
2. `just epic <N>` again for execution
3. `just epic-report <N>` for reporting

See `../wiki/Epic-Workflow.md` and `.agents/skills/epic/SKILL.md` for the
current contract.
