"""Plan generation — agent-based planner producing JSON.

The planner receives only the enriched epic body (from GitHub) and the
plan.json schema. It explores the codebase itself using tools (Read, Grep,
Glob) rather than receiving pre-assembled context.

Dispatches via dispatch_agent(), parses the output into plan.json via
Pydantic. PLAN.md is rendered deterministically from the model.

Usage:
    python -m workflow.plan_generator <epic_number>
"""

import json
import logging
import re
import sys
from pathlib import Path

from workflow.artifacts import (
    CurationArtifact,
    EpicArtifact,
    PlanArtifact,
    RepoFactsArtifact,
    RevisionRequestArtifact,
    VerifierFeedbackArtifact,
)
from workflow.dispatch import (
    dispatch_agent,
    get_dispatch_params,
)
from workflow.epic_config import EpicConfig
from workflow.models import Plan
from workflow.prompt_compiler import (
    PromptSection,
    make_prompt_artifact,
    render_json_block,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PLANNING_DIR = PROJECT_ROOT / ".planning" / "epics"

logger = logging.getLogger(__name__)


class PlanGenerationError(Exception):
    """Raised when plan generation fails."""


# ---------------------------------------------------------------------------
# Input readers
# ---------------------------------------------------------------------------


def _read_epic_md(epic_dir: Path) -> str:
    """Read EPIC.md from the epic directory."""
    try:
        return EpicArtifact.from_epic_dir(epic_dir).body
    except FileNotFoundError:
        epic_path = epic_dir / "EPIC.md"
        raise PlanGenerationError(
            f"EPIC.md not found at {epic_path}. "
            "Run ingestion first with `just epic <number>`."
        )
    except ValueError as exc:
        raise PlanGenerationError(str(exc)) from exc


def _read_epic_number(epic_dir: Path) -> int:
    """Extract the epic number from the directory name (e.g. E95 -> 95)."""
    try:
        return EpicArtifact.from_epic_dir(epic_dir).epic_number
    except FileNotFoundError:
        match = re.match(r"^E(\d+)$", epic_dir.name)
        if match:
            return int(match.group(1))
        raise PlanGenerationError(f"Cannot extract epic number from directory name: {epic_dir.name}")
    except ValueError as exc:
        raise PlanGenerationError(str(exc)) from exc


def _read_repo_facts(epic_dir: Path) -> RepoFactsArtifact:
    """Read repo_facts.json from the epic directory."""
    try:
        return RepoFactsArtifact.from_epic_dir(epic_dir)
    except FileNotFoundError:
        repo_facts_path = epic_dir / "repo_facts.json"
        raise PlanGenerationError(
            f"repo_facts.json not found at {repo_facts_path}. "
            "Run repo-facts generation after ingestion before planning."
        )
    except ValueError as exc:
        raise PlanGenerationError(str(exc)) from exc


def _read_optional_curation(epic_dir: Path) -> CurationArtifact | None:
    """Read curation.json from the epic directory when present."""
    curation_path = epic_dir / "curation.json"
    if not curation_path.is_file():
        return None
    try:
        return CurationArtifact.from_epic_dir(epic_dir)
    except ValueError as exc:
        raise PlanGenerationError(str(exc)) from exc


# ---------------------------------------------------------------------------
# Planner prompt construction
# ---------------------------------------------------------------------------

CHECKPOINT_PLACEMENT_GUIDANCE = """\
Place validation checkpoints strategically based on story types:
- After scaffolding: pages exist, routes respond, navigation works.
- After CRUD: create/read/update/delete work end-to-end.
- After complex features: feature-specific behaviour verified.
- Before regression tests: full product works (don't waste tokens testing broken product).
- After regression tests: tests pass, quality gates pass (final gate).

Not every story needs a checkpoint. Backend-only stories (entity + repo + service)
may wait for the UI story that exposes them. The key is to catch wiring failures
before building on top of broken scaffolding.

Use explicit `command` values whenever the check maps cleanly to a `just`
recipe or `just tdd <path> -k <test>`. Weak checks like bare 200s, greps, or
"button exists" checks are not enough when the epic requires a real journey."""


def make_planner_prompt(
    epic: EpicArtifact,
    repo_facts: RepoFactsArtifact,
    curation: CurationArtifact | None = None,
):
    """Compile the planner prompt from typed epic workflow artifacts."""
    return make_prompt_artifact(
        role="planner",
        sections=[
            PromptSection(
                "# Task: Generate Epic Plan",
                (
                    f"Produce a complete `plan.json` for epic #{epic.epic_number}. You are a "
                    "tool-equipped planner: inspect the repo live, find the real files and "
                    "routes, and build a plan that matches the epic contract exactly. "
                    "If repo conventions differ, the only valid canonical outcomes are "
                    "`epic` or `bridge`; repo-only substitution is forbidden.\n\n"
                    "Read AGENTS.md and DEVELOPMENT.md first for project conventions and "
                    "structure.\n\n"
                    "Output only a single JSON object matching the provided schema. Do not "
                    "produce markdown, commentary, or `PLAN.md`. Use the StructuredOutput "
                    "tool for the final answer, and pass the plan object itself as the tool "
                    "input. Do NOT wrap it in `result`, `plan`, `output`, or any outer key."
                ),
            ),
            PromptSection("## Epic Contract", epic.prompt_block),
            PromptSection("## Repo Facts", repo_facts.prompt_block),
            *(
                [
                    PromptSection(
                        "## Curated Planning Handoff",
                        (
                            "Use this bounded curation as a shaping input for story "
                            "boundaries, journey framing, missing assumptions, and scope "
                            "tensions. It is advisory and pre-plan, not the final execution "
                            "schema.\n\n"
                            f"{curation.prompt_block}"
                        ),
                    )
                ]
                if curation is not None
                else []
            ),
            PromptSection(
                "## Self-Check Before Emitting JSON",
                """- Count your observable truths and confirm every ID appears in at least one
  story's truths_addressed AND at least one journey's truths_covered.
- Confirm every checkpoint after_story references a real story_id.
- Confirm every scope.modify path points to a file that actually exists (use
  Glob to verify).
- For every user journey, verify the entry point and source page/state either
  exist today or are explicitly created/fixed in story scope.
- For every critical transition, verify the plan proves all 3 parts:
  source page/state renders, transition mechanism works, target page/state
  renders after the transition.
- Reconcile every route/path named in the epic against the actual repo. If the
  current code or tests expect a 404/different path, plan the source-page fix
  explicitly instead of assuming the journey already works.
- For every UI -> API interaction, define one end-to-end transport contract.
  If the UX uses HTMX/Alpine/fetch and the API contract is JSON, spell out the
  exact bridge and add checkpoints that prove it.
- For every redirect or HX-Redirect flow, verify the plan checks both the
  redirect mechanism and the renderability of the destination page.
- If the current codebase suggests a familiar local pattern but the epic
  contract says something else, the epic contract wins.
- If repo conventions differ from the epic contract (route shape, field names,
  transport, or entry point), preserve the epic contract or plan an explicit
  compatibility bridge. Do NOT silently substitute a repo-preferred contract.
- For every epic-vs-repo contract mismatch, record an explicit top-level
  `contract_decisions` entry with: decision_id, epic_contract, repo_convention,
  canonical, bridge, and affected_stories.
- In other words, record an explicit contract decision instead of leaving the
  resolution buried in prose.
- Each contract decision must name the epic contract, the repo convention, the chosen canonical contract, and any compatibility bridge needed.
- `contract_decisions[].canonical` may only be `epic` or `bridge`. There is no
  `repo` option.
- If you choose a compatibility bridge, add checkpoints that prove the canonical
  user-facing/API contract and the bridge behavior end to end.
- Never present a repo-preferred route, field name, or transport as if it were
  the epic contract unless you explicitly mark it as a compatibility decision.
- List any gaps and fix them before writing the JSON object.""",
            ),
            PromptSection(
                "## Planning Methodology: Goal-Backward Analysis",
                f"""Follow this methodology strictly:

### Step 1: Define Observable Truths

Define observable truths — user-perspective, verifiable-by-a-human statements that
define "done". These are NOT technical requirements. They describe what a user can
see or do when the epic is complete.

Good truths:
- "A user can visit /gear and see a list of their gear items"
- "Clicking a gear item navigates to a detail page showing model information"

Bad truths (too technical):
- "GearRepository has a get_by_id method"
- "The Pydantic schema validates input"

### Step 2: Explore the Codebase

Use your tools to understand the current state:
- Read AGENTS.md and DEVELOPMENT.md for conventions
- Grep for existing patterns (repositories, services, API routes, templates)
- Find files that will need modification
- Understand the module structure and dependency rules

### Step 3: Organise Artefacts into Stories

Group artefacts into stories. Each story is a coherent chunk that one AI agent
completes in a single invocation.

Story sizing constraints:
- ONE FEATURE PER STORY. Never bundle unrelated features into one story.
- Each story is a vertical slice: one feature through all layers.
- 3-8 files created/modified per story.
- Each story should produce something checkable.
- Each story builds on the previous but is self-contained.
- More stories is fine. Prefer 5 focused stories over 3 bloated ones.
- state_assumption defaults to "cumulative". Only set "clean" when validation
  criteria depend on known data state.

### Step 3b: Enrich Each Story

For EVERY story, populate these fields with specific, concrete information:

- **acceptance_criteria**: User-perspective, testable statements. Each must be
  independently verifiable.
- **architectural_context**: Patterns, module boundaries, design decisions.
  Reference actual files so the agent knows where to look.
- **navigation_hints**: File paths, symbol names, entry points. Assume the
  agent starts cold with no knowledge of where things live.
- **implementation_notes**: Domain-specific hints.
- **test_spec**: Optional. If you include it, keep it focused on business
  behaviour to verify after implementation, not on frozen test-first scaffolding.

### Step 4: Define User Journeys

Create connected, end-to-end narratives that link observable truths into coherent
flows. Every truth must appear in at least one journey.

When you define a journey:
- Do NOT invent entry points or source pages without tool evidence.
- If the epic references a source page/link path that is currently missing or
  broken, add scope to build or repair that source state.
- Keep route/path names consistent across the epic, journeys, stories, and
  checkpoints. Resolve ambiguities with repo evidence before emitting JSON.
- If a route, field name, or transport contract is disputed, make the
  resolution explicit in the story and in top-level `contract_decisions`
  instead of silently drifting to repo convention.

### Step 5: Place Validation Checkpoints

{CHECKPOINT_PLACEMENT_GUIDANCE}

A transition is only covered when the checkpoint(s) prove:
- the source page/state renders with the expected control,
- the transition mechanism works (click, submit, PATCH, redirect),
- the target page/state renders correctly afterward.

If a story changes an API contract that the frontend consumes, checkpoints must
also prove the transport/wiring end to end, not just the raw endpoint response.""",
            ),
            PromptSection(
                "## Output",
                f"""Return one complete JSON object for epic #{epic.epic_number}.

## Critical Rules

1. Every observable truth must be addressed by at least one story.
2. Every observable truth must appear in at least one journey's truths_covered.
3. Every checkpoint after_story must reference a valid story_id.
4. Every journey truths_covered ID must exist in observable_truths.
5. Files in scope.modify must be real files that exist in the GTS codebase.
   USE GLOB TO VERIFY.
6. Files in scope.create must have parent directories that exist.
7. Stories that use files created by earlier stories must appear after them.
8. state_assumption defaults to "cumulative". Only set "clean" when validation
   criteria depend on known data state.
9. The plan.json epic_number must be {epic.epic_number}.
10. Do NOT invent features not described in the epic. Stay within scope.
11. Every story MUST have non-empty acceptance_criteria.
12. Every story SHOULD include a test_spec with test_type, fixtures, and assertions.
13. Every epic-vs-repo contract mismatch MUST be recorded in top-level
    contract_decisions.
14. Every contract decision MUST use canonical = "epic" or "bridge". There is
    no "repo" option.
15. If canonical == "bridge", bridge must be non-empty and checkpoints must
    prove both the epic contract and the bridge behavior.
16. Never drop the epic contract in favor of the repo convention.

Think through the repo state carefully, then emit the JSON object.""",
            ),
        ],
    )


def _build_planner_prompt(
    epic_md: str,
    repo_facts: dict[str, object],
    epic_number: int,
    curation: dict[str, object] | None = None,
) -> str:
    """Construct the planner prompt.

    The planner is a tool-equipped agent. It receives the epic body,
    repo-facts, and the JSON schema, then explores the codebase using tools
    to verify and extend those grounded inputs.

    PLAN.md is rendered deterministically from the validated model.
    """
    return make_planner_prompt(
        EpicArtifact(epic_number=epic_number, body=epic_md),
        RepoFactsArtifact.from_dict({"epic_number": epic_number, **repo_facts}),
        (
            None
            if curation is None
            else CurationArtifact.from_dict({"epic_number": epic_number, **curation})
        ),
    ).text


# ---------------------------------------------------------------------------
# Revision prompts (legacy — kept for backward compatibility)
# ---------------------------------------------------------------------------


def build_revision_prompt(
    original_prompt: str,
    validation_errors: list[str],
) -> str:
    """Build a revision prompt when Phase A validation fails.

    **Legacy:** No longer called from the revision dispatch path. The
    targeted ``build_targeted_phase_a_revision_prompt`` is used instead.
    """
    error_list = "\n".join(f"- {err}" for err in validation_errors)

    revision_section = f"""

---

## REVISION REQUIRED

Your previous plan.json output failed structural validation. Fix the following
errors and re-emit the plan JSON object:

{error_list}

All other instructions from the original prompt still apply. Produce a single
JSON object and NOTHING ELSE — no markdown, no explanation. Raw JSON only.
"""

    return original_prompt + revision_section


# ---------------------------------------------------------------------------
# Finding extraction helpers (used by both legacy and targeted prompts)
# ---------------------------------------------------------------------------


def _extract_finding_items(dim_data: dict, key: str) -> list:
    """Get finding items from nested dict, flat dict, or array layout."""
    findings = dim_data.get("findings")
    if isinstance(findings, list):
        return [f for f in findings if f.get("severity") == "must_fix"]
    if isinstance(findings, dict):
        items = findings.get(key, [])
        if items:
            return items
    return dim_data.get(key, [])


def _format_finding_item(item: object) -> str:
    """Format a finding item, handling both str and dict."""
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        return json.dumps(item, ensure_ascii=False)
    return str(item)


def build_verifier_revision_prompt(
    original_prompt: str,
    verifier_result: dict,
) -> str:
    """Build a revision prompt when Phase B verification fails.

    **Legacy:** No longer called from the revision dispatch path. The
    targeted ``build_targeted_phase_b_revision_prompt`` is used instead.
    """
    feedback_lines = [
        "",
        "---",
        "",
        "## REVISION REQUIRED (Verifier Feedback)",
        "",
        "Your plan was structurally valid but failed verification. Address the "
        "following issues and re-emit the plan JSON object:",
        "",
    ]

    dims = verifier_result.get("dimensions")
    if not isinstance(dims, dict):
        dims = verifier_result

    jc = dims.get("journey_completeness", {})
    if isinstance(jc, dict) and jc.get("status") == "fail":
        feedback_lines.append("### Journey Completeness Gaps")
        for gap in _extract_finding_items(jc, "gaps"):
            feedback_lines.append(f"- {_format_finding_item(gap)}")
        feedback_lines.append("")

    tc = dims.get("transition_coverage", {})
    if isinstance(tc, dict) and tc.get("status") == "fail":
        feedback_lines.append("### Uncovered Transitions")
        for uc in _extract_finding_items(tc, "uncovered"):
            feedback_lines.append(f"- {_format_finding_item(uc)}")
        feedback_lines.append("")

    ia = dims.get("intent_alignment", {})
    if isinstance(ia, dict) and ia.get("status") == "fail":
        feedback_lines.append("### Intent Alignment Issues")
        for req in _extract_finding_items(ia, "unaddressed_requirements"):
            feedback_lines.append(f"- Unaddressed requirement: {_format_finding_item(req)}")
        for creep in _extract_finding_items(ia, "scope_creep"):
            feedback_lines.append(f"- Scope creep: {_format_finding_item(creep)}")
        feedback_lines.append("")

    gd = dims.get("gap_detection", {})
    if isinstance(gd, dict) and gd.get("status") == "fail":
        feedback_lines.append("### Logical Gaps Between Stories")
        for gap in _extract_finding_items(gd, "gaps"):
            feedback_lines.append(f"- {_format_finding_item(gap)}")
        feedback_lines.append("")

    vs = dims.get("validation_sufficiency", {})
    if isinstance(vs, dict) and vs.get("status") == "fail":
        feedback_lines.append("### Weak Validation Checks")
        for wc in _extract_finding_items(vs, "weak_checks"):
            feedback_lines.append(f"- {_format_finding_item(wc)}")
        feedback_lines.append("")

    gs = dims.get("gap_sufficiency", {})
    if isinstance(gs, dict) and gs.get("status") == "fail":
        feedback_lines.append("### Missed Gaps")
        for mg in _extract_finding_items(gs, "missed_gaps"):
            feedback_lines.append(f"- {_format_finding_item(mg)}")
        feedback_lines.append("")

    feedback_lines.append(
        "Fix all issues above. Produce a single JSON object conforming to "
        "the schema. Output ONLY the raw JSON, no other text."
    )

    return original_prompt + "\n".join(feedback_lines)


# ---------------------------------------------------------------------------
# Targeted revision prompts (send plan.json + feedback, not full context)
# ---------------------------------------------------------------------------


def make_phase_a_revision_prompt(request: RevisionRequestArtifact):
    """Compile a targeted Phase A revision prompt from a typed request."""
    error_list = "\n".join(f"- {err}" for err in request.errors)

    return make_prompt_artifact(
        role="planner_revision_phase_a",
        sections=[
            PromptSection(
                "# Task: Fix Plan Validation Errors (Targeted Revision)",
                (
                    "The current plan.json failed Phase A structural validation. Fix ONLY the "
                    "listed errors. Preserve all other fields exactly as they are."
                ),
            ),
            PromptSection(
                "## Rules",
                """1. Make the MINIMUM changes necessary to fix each error.
2. Do NOT rewrite stories, journeys, or scope unless an error specifically
   requires it.
3. Keep `scope.modify` paths pointing to files that exist on disk RIGHT NOW.
   Use the Glob and Read tools to verify file paths if unsure.
4. Do NOT add new stories or remove existing ones unless an error requires it.
5. If an error mentions contract_fidelity, preserve the epic surface in the
   plan or add/update an explicit top-level `contract_decisions` entry.
6. `contract_decisions[].canonical` may only be `epic` or `bridge`. There is
   no `repo` option.
7. Output only the complete JSON object matching the provided schema.
8. Use the StructuredOutput tool for the final answer.
9. Pass the plan object itself as the StructuredOutput input. Do NOT wrap it
   in `result`, `plan`, `output`, or any outer key.""",
            ),
            PromptSection(
                "## Current Plan",
                f"<current_plan>\n{request.plan.json_text.rstrip()}\n</current_plan>",
            ),
            PromptSection("## Validation Errors to Fix", error_list),
            PromptSection(
                "## Output",
                """Fix the errors above and emit the complete JSON object.
Do NOT omit any existing fields — the output must be a complete, valid plan.""",
            ),
        ],
    )


def build_targeted_phase_a_revision_prompt(
    plan_json_str: str,
    errors: list[str],
) -> str:
    """Build a targeted Phase A revision prompt.

    Sends only the current plan.json + errors + JSON schema (~25K total)
    instead of rebuilding the entire planning prompt.
    """
    request = RevisionRequestArtifact.for_phase_a(
        PlanArtifact.from_json_text(plan_json_str),
        errors,
    )
    return make_phase_a_revision_prompt(request).text


def make_phase_b_revision_prompt(request: RevisionRequestArtifact):
    """Compile a targeted Phase B revision prompt from a typed request."""
    verifier_feedback = request.verifier_feedback
    assert verifier_feedback is not None

    feedback_lines: list[str] = []

    jc = verifier_feedback.dimension("journey_completeness")
    if jc.get("status") == "fail":
        feedback_lines.append("### Journey Completeness Gaps")
        for gap in _extract_finding_items(jc, "gaps"):
            feedback_lines.append(f"- {_format_finding_item(gap)}")
        feedback_lines.append("")

    tc = verifier_feedback.dimension("transition_coverage")
    if tc.get("status") == "fail":
        feedback_lines.append("### Uncovered Transitions")
        for uc in _extract_finding_items(tc, "uncovered"):
            feedback_lines.append(f"- {_format_finding_item(uc)}")
        feedback_lines.append("")

    ia = verifier_feedback.dimension("intent_alignment")
    if ia.get("status") == "fail":
        feedback_lines.append("### Intent Alignment Issues")
        for req in _extract_finding_items(ia, "unaddressed_requirements"):
            feedback_lines.append(f"- Unaddressed requirement: {_format_finding_item(req)}")
        for creep in _extract_finding_items(ia, "scope_creep"):
            feedback_lines.append(f"- Scope creep: {_format_finding_item(creep)}")
        feedback_lines.append("")

    gd = verifier_feedback.dimension("gap_detection")
    if gd.get("status") == "fail":
        feedback_lines.append("### Logical Gaps Between Stories")
        for gap in _extract_finding_items(gd, "gaps"):
            feedback_lines.append(f"- {_format_finding_item(gap)}")
        feedback_lines.append("")

    vs = verifier_feedback.dimension("validation_sufficiency")
    if vs.get("status") == "fail":
        feedback_lines.append("### Weak Validation Checks")
        for wc in _extract_finding_items(vs, "weak_checks"):
            feedback_lines.append(f"- {_format_finding_item(wc)}")
        feedback_lines.append("")

    gs = verifier_feedback.dimension("gap_sufficiency")
    if gs.get("status") == "fail":
        feedback_lines.append("### Missed Gaps")
        for mg in _extract_finding_items(gs, "missed_gaps"):
            feedback_lines.append(f"- {_format_finding_item(mg)}")
        feedback_lines.append("")

    findings_text = "\n".join(feedback_lines) if feedback_lines else "(no specific findings)"
    assert request.epic is not None
    assert request.repo_facts is not None
    curation_sections = (
        [
            PromptSection(
                "## Curated Planning Handoff",
                (
                    "Use this prior curation as a shaping input while you revise the plan. "
                    "It is advisory, not the final story/checkpoint schema.\n\n"
                    f"{request.curation.prompt_block}"
                ),
            )
        ]
        if request.curation is not None
        else []
    )
    return make_prompt_artifact(
        role="planner_revision_phase_b",
        sections=[
            PromptSection(
                "# Task: Address Verifier Feedback (Targeted Revision)",
                (
                    "The current plan.json passed structural validation but failed Phase B "
                    "cross-model verification. Treat the current plan as suspect wherever it "
                    "conflicts with the epic contract or verifier findings."
                ),
            ),
            PromptSection("## Original Epic Contract", request.epic.prompt_block),
            PromptSection("## Repo Facts", request.repo_facts.prompt_block),
            *curation_sections,
            PromptSection(
                "## Rules",
                """1. The epic contract wins over the current plan.
2. You MAY rewrite any affected story, journey, checkpoint, or validation path.
3. Preserve untouched sections only if they still fit the epic and findings.
4. Keep `scope.modify` paths pointing to files that exist on disk RIGHT NOW.
   Use the Glob and Read tools to verify file paths if unsure.
5. If verifier feedback shows the current framing is wrong, fix the framing instead of patching around it.
6. If the verifier flags epic-vs-repo contract drift, you MUST make the
   contract resolution explicit in top-level `contract_decisions`. Each
   decision must include decision_id, epic_contract, repo_convention, the
   chosen canonical contract, bridge, and affected_stories.
7. `contract_decisions[].canonical` may only be `epic` or `bridge`. There is
   no `repo` option.
8. If you keep a repo-shaped bridge for implementation ergonomics, add
   acceptance criteria and checkpoints proving the epic-facing contract too.
9. Never silently replace an epic route, field, or transport with a
   repo-preferred one.
10. Output only the complete JSON object matching the provided schema.
11. Use the StructuredOutput tool for the final answer.
12. Pass the plan object itself as the StructuredOutput input. Do NOT wrap it
   in `result`, `plan`, `output`, or any outer key.""",
            ),
            PromptSection(
                "## Current Plan",
                render_json_block("current_plan", request.plan.review_payload),
            ),
            PromptSection("## Must-Fix Findings", findings_text),
            PromptSection(
                "## Output",
                """Address the findings above and emit the complete JSON object.
Do NOT omit any existing fields unless you are replacing them with corrected content in the revised plan.""",
            ),
        ],
    )


def build_targeted_phase_b_revision_prompt(
    epic_md: str,
    repo_facts_json_str: str,
    plan_json_str: str,
    verifier_feedback: VerifierFeedbackArtifact,
    curation_json_str: str | None = None,
) -> str:
    """Build a targeted Phase B revision prompt.

    Sends the original epic contract + repo_facts.json + current plan.json + must_fix findings.
    """
    plan = PlanArtifact.from_json_text(plan_json_str)
    request = RevisionRequestArtifact.for_phase_b(
        EpicArtifact(epic_number=plan.epic_number, body=epic_md),
        RepoFactsArtifact.from_dict(json.loads(repo_facts_json_str)),
        plan,
        verifier_feedback,
        None if curation_json_str is None else CurationArtifact.from_dict(json.loads(curation_json_str)),
    )
    return make_phase_b_revision_prompt(request).text


# ---------------------------------------------------------------------------
# Structured output parsing
# ---------------------------------------------------------------------------


def _parse_structured_plan(result) -> Plan:
    """Parse a dispatch result into a validated Plan model."""
    text = result.output.strip()

    fence_match = re.search(r"```json\s*\n(.*?)```", text, re.DOTALL)
    json_text = fence_match.group(1).strip() if fence_match else text

    try:
        data = json.loads(json_text)
    except json.JSONDecodeError as exc:
        pos = exc.pos or 0
        context_start = max(0, pos - 200)
        context_end = min(len(json_text), pos + 200)
        error_context = json_text[context_start:context_end]
        marker_pos = pos - context_start
        marker_line = " " * marker_pos + "^ ERROR HERE"
        raise PlanGenerationError(
            f"Planner output is not valid JSON: {exc}\n"
            f"Context around error (char {pos}):\n"
            f"{error_context}\n{marker_line}"
        ) from exc
    try:
        return Plan.model_validate(data)
    except Exception as exc:
        raise PlanGenerationError(f"Plan JSON failed Pydantic validation: {exc}") from exc


# ---------------------------------------------------------------------------
# Core function
# ---------------------------------------------------------------------------


def generate_plan(
    epic_dir: Path,
    config: EpicConfig | None = None,
) -> tuple[Path, Path]:
    """Generate PLAN.md and plan.json from the epic body.

    The planner is dispatched as a tool-equipped agent that explores the
    codebase itself. It receives the epic body, repo_facts, and JSON schema.

    Args:
        epic_dir: Path to the epic directory (e.g. .planning/epics/E95/).
            Must contain EPIC.md from ingestion.
        config: Optional epic config for model/budget overrides.

    Returns:
        Tuple of (plan_md_path, plan_json_path).

    Raises:
        PlanGenerationError: If EPIC.md is missing, dispatch fails, or
            output cannot be parsed.
    """
    try:
        epic = EpicArtifact.from_epic_dir(epic_dir)
        repo_facts = _read_repo_facts(epic_dir)
        curation = _read_optional_curation(epic_dir)
    except FileNotFoundError:
        epic_path = epic_dir / "EPIC.md"
        raise PlanGenerationError(
            f"EPIC.md not found at {epic_path}. "
            "Run ingestion first with `just epic <number>`."
        )
    except ValueError as exc:
        raise PlanGenerationError(str(exc)) from exc
    prompt_artifact = make_planner_prompt(epic, repo_facts, curation)
    prompt = prompt_artifact.text

    prompt_tokens = len(prompt) // 4
    planner_model = config.models.planner if config else "sonnet"

    logger.info(
        "Dispatching %s planner for epic #%d (%d chars, ~%d tokens)",
        planner_model,
        epic.epic_number,
        len(prompt),
        prompt_tokens,
    )

    mcp_servers, timeout = get_dispatch_params("planning", config)
    result = dispatch_agent(
        prompt=prompt,
        model=planner_model,
        json_schema=Plan.model_json_schema(),
        cwd=PROJECT_ROOT,
        mcp_servers=mcp_servers,
        timeout=timeout,
        role="planner",
    )

    if not result.success:
        raise PlanGenerationError(
            f"Planner dispatch failed (exit_code={result.exit_code}). "
            f"Output: {result.output[:500]}"
        )

    logger.info(
        "Planner output length: %d chars, turns: %s",
        len(result.output),
        result.turns or "unknown",
    )

    plan = _parse_structured_plan(result)
    plan_md_path, plan_json_path = PlanArtifact.from_model(plan).write(epic_dir)
    logger.info("Wrote plan.json to %s", plan_json_path)
    logger.info("Wrote PLAN.md to %s", plan_md_path)

    return plan_md_path, plan_json_path


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """CLI entry point: python -m workflow.plan_generator <epic_number>."""
    if len(sys.argv) < 2:
        print(
            f"Usage: {sys.argv[0]} <epic_number>",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        epic_number = int(sys.argv[1])
    except ValueError:
        print(
            f"Error: epic_number must be an integer, got: {sys.argv[1]}",
            file=sys.stderr,
        )
        sys.exit(1)

    epic_dir = PLANNING_DIR / f"E{epic_number}"
    if not epic_dir.is_dir():
        print(
            f"Error: Epic directory not found: {epic_dir}. "
            f"Run ingestion first.",
            file=sys.stderr,
        )
        sys.exit(1)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    try:
        plan_md_path, plan_json_path = generate_plan(epic_dir)
        print(f"Plan generated for epic #{epic_number}:")
        print(f"  PLAN.md:   {plan_md_path.relative_to(PROJECT_ROOT)}")
        print(f"  plan.json: {plan_json_path.relative_to(PROJECT_ROOT)}")
    except PlanGenerationError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
