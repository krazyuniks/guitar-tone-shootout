"""V2 plan generation — single Opus invocation producing JSON.

Reads CONTEXT.md (from context assembly), constructs the planner prompt
(with JSON schema embedded in text), dispatches via dispatch_agent(),
and parses the output into plan.json via Pydantic. PLAN.md is rendered
deterministically from the model.

Reference: Research doc Section 8.4 Decisions 1, 3, 4, 5, 6, 7.

Usage:
    python -m workflow.plan_generator <epic_number>
"""

import json
import logging
import re
import sys
from pathlib import Path

from workflow.dispatch import (
    BUDGET_DEFAULTS,
    FALLBACK_MODELS,
    dispatch_with_fallback,
)
from workflow.epic_config import EpicConfig
from workflow.models import Plan, render_plan_md

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PLANNING_DIR = PROJECT_ROOT / ".planning" / "epics"

logger = logging.getLogger(__name__)


class PlanGenerationError(Exception):
    """Raised when plan generation fails."""


# ---------------------------------------------------------------------------
# Context reader
# ---------------------------------------------------------------------------


def _read_context(epic_dir: Path) -> str:
    """Read CONTEXT.md from the epic directory."""
    context_path = epic_dir / "CONTEXT.md"
    if not context_path.is_file():
        raise PlanGenerationError(
            f"CONTEXT.md not found at {context_path}. "
            "Run context assembly first: python -m workflow.context_assembler <number>"
        )
    return context_path.read_text(encoding="utf-8")


def _read_user_decisions(epic_dir: Path) -> str | None:
    """Read user-decisions.json from the epic directory, if it exists."""
    decisions_path = epic_dir / "user-decisions.json"
    if not decisions_path.is_file():
        return None
    return decisions_path.read_text(encoding="utf-8")


def _read_epic_number(epic_dir: Path) -> int:
    """Extract the epic number from the directory name (e.g. E95 -> 95)."""
    match = re.match(r"^E(\d+)$", epic_dir.name)
    if match:
        return int(match.group(1))
    raise PlanGenerationError(f"Cannot extract epic number from directory name: {epic_dir.name}")


# ---------------------------------------------------------------------------
# Planner prompt construction
# ---------------------------------------------------------------------------

# Evidence fields — all types now produce command output (deterministic)
EVIDENCE_FIELDS_TABLE = """\
All check types produce the same evidence fields (command execution output):

| Evidence Field | Description |
|----------------|-------------|
| `command` | The shell command that was executed |
| `exit_code` | Process exit code (0 = pass) |
| `output_tail` | Last 2000 chars of combined stdout + stderr |

The default `evidence_fields` value is `["command", "exit_code", "output_tail"]`.
You may omit `evidence_fields` from criteria — the default is applied automatically."""

# Checkpoint placement guidance (Section 8.4 Decision 5)
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

**Command-based validation:** Every criterion SHOULD include a `command` field with the
shell command to run. Commands should be `just` recipes or `just tdd <path> -k <test>`.
Exit code 0 = pass. The implementation story's scope should include the test file so the
agent writes the test as part of the story.

Examples:
- `"command": "just tdd tests/unit/webapp/test_gear_list.py -k test_gear_list_page"`
- `"command": "just check-lint"`
- `"command": "just test-golden-path"`
- `"command": "just tdd tests/integration/webapp/test_gear_crud.py"`

Criteria without a `command` field fall back to keyword matching (e.g. "quality gates
pass" maps to `just check`), but explicit commands are preferred for precision."""

# Story sizing guidance (Section 8.4 Decision 7)
STORY_SIZING_GUIDANCE = """\
Story sizing constraints:
- Target 2-5 stories per epic. Each story is a coherent chunk an agent completes
  in one invocation.
- 3-8 files created/modified per story.
- Each story should use <50% of the agent context window.
- Full vertical slice OR one layer across multiple entities.
- Each story should produce something checkable.
- Each story builds on the previous but is self-contained.
- State assumption: declare whether the story expects cumulative state (default)
  or clean state (orchestrator runs db-reset before dispatch).

Example story breakdown for a typical GTS epic:
| Story | Scope | Model | Budget |
|-------|-------|-------|--------|
| 1. Architecture | Entity, ORM, repo, service, migration | Codex | $3 |
| 2. API + Schemas | Routes, Pydantic schemas, route registration | Codex | $2 |
| 3. UI Scaffolding | Page templates, fragments, navigation | Codex | $3 |
| 4. CRUD Features | Form handling, HTMX interactions, DB writes | Codex | $4 |
| 5. Regression Tests | E2E tests, regression test updates | Codex | $3 |"""

# Skill mapping per story type (Section 8.5 Decision 3)
SKILL_MAPPING_REFERENCE = """\
Skill mapping per story type (select appropriate skills for each story):
| Story Type | Typical Skills |
|------------|---------------|
| Architecture | `gts-architecture`, `repository-patterns`, `service-patterns` |
| API + Schemas | `gts-backend-dev`, `web-handlers`, `error-handling` |
| UI Scaffolding | `gts-frontend-dev`, `htmx`, `astro-frontend` |
| CRUD Features | `gts-frontend-dev`, `htmx`, `gts-backend-dev` |
| Regression Tests | `gts-testing`, `playwright` |"""

# Tool restrictions per agent role (Section 8.2 Strategy 4)
TOOL_REFERENCE = """\
Tool restrictions per agent role:
| Agent Role | Tools |
|------------|-------|
| Implementation | Read, Edit, Write, Bash, Glob, Grep |
| Regression test | Read, Edit, Write, Bash, Glob, Grep |

Note: Validation checkpoints run commands directly (no agent dispatch).
Validation does not need tool configuration.

Codex agents receive MCP tools (Serena, Pyright, Playwright, Chrome DevTools)
automatically via ~/.codex/config.toml. Do not specify tools in the agent
config for Codex — they are configured globally."""

# Budget defaults (Section 8.2 Strategy 7)
BUDGET_REFERENCE = """\
Budget defaults (starting points):
| Agent Type | Max Turns | Max Budget |
|------------|-----------|------------|
| Architecture (Codex) | 30 | $3.00 |
| Implementation (Codex) | 40 | $4.00 |
| Validation (Haiku) | 15 | $0.50 |
| Regression tests (Codex) | 30 | $3.00 |"""


def _build_decisions_section(user_decisions: str | None) -> str:
    """Build the user decisions section for the planner prompt."""
    if not user_decisions:
        return ""
    return f"""---

## Scope Decisions (from Gap Detection)

The following decisions were made during interactive gap detection (Stage 2b).
These are locked — do not redefine or contradict them.

<user_decisions>
{user_decisions}
</user_decisions>

"""


def _build_planner_prompt(
    context: str,
    epic_number: int,
    user_decisions: str | None = None,
) -> str:
    """Construct the Opus planner prompt.

    The prompt instructs Opus to produce a plan.json structure only.
    PLAN.md is rendered deterministically from the validated model.
    The JSON schema is included inline so the model knows the structure
    without relying on --json-schema constrained decoding.
    """
    # Generate schema for prompt context
    plan_schema_json = json.dumps(Plan.model_json_schema(), indent=2)

    prompt = f"""\
# Task: Generate Epic Plan

You are the planner for the GTS (Guitar Tone Shootout) project. Your job is to
produce a complete plan for epic #{epic_number} that will be executed by AI agents
under an automated orchestrator.

Think through the plan step by step first, then emit the final JSON inside a
```json code fence. The orchestrator extracts JSON from your response
automatically. A separate process renders PLAN.md from the JSON, so you do NOT
produce PLAN.md.

Before emitting the JSON, verify your own work:
- Count your observable truths and confirm every ID appears in at least one
  story's truths_addressed AND at least one journey's truths_covered.
- Confirm every checkpoint after_story references a real story_id.
- List any gaps and fix them before writing the JSON.

---

## JSON Schema

Your output must conform to this schema:

<json_schema>
{plan_schema_json}
</json_schema>

---

## Input Context

The following is the assembled context for this epic, including the epic description
from GitHub and codebase architecture.

<context>
{context}
</context>

{_build_decisions_section(user_decisions)}
---

## Planning Methodology: Goal-Backward Analysis

Follow this methodology strictly:

### Step 1: Define Observable Truths

Define observable truths — user-perspective, verifiable-by-a-human statements that
define "done". These are NOT technical requirements. They describe what a user can
see or do when the epic is complete.

Good truths:
- "A user can visit /gear and see a list of their gear items"
- "Clicking a gear item navigates to a detail page showing model information"
- "Submitting the edit form updates the gear name, visible on return to detail page"

Bad truths (too technical):
- "GearRepository has a get_by_id method"
- "The Pydantic schema validates input"
- "The migration adds a gear table"

### Step 2: Derive Required Artefacts

For each truth, identify what code artefacts must exist for the truth to be
observable. Walk the full stack: entity -> ORM model -> repository -> service ->
API endpoint -> page template -> navigation link.

### Step 3: Organise Artefacts into Stories

Group artefacts into stories. Each story is a coherent chunk that one AI agent
completes in a single invocation.

{STORY_SIZING_GUIDANCE}

### Step 4: Define User Journeys

Create connected, end-to-end narratives that link observable truths into coherent
flows. Not isolated assertions ("GET /gear returns 200") but connected walks
("user clicks Gear in nav, sees list, clicks item, sees detail").

Every truth must appear in at least one journey. Journeys include
critical_transitions with {{from, to, mechanism}}.

### Step 5: Place Validation Checkpoints

{CHECKPOINT_PLACEMENT_GUIDANCE}

### Step 6: Specify Wiki Sections

For each story, specify `wiki_sections` — a list of wiki section header names from
the project wiki indexes (`.planning/wiki-indexes/`). The Stage 4 prompt builder
uses this to load targeted wiki sections into each story's agent prompt, keeping
prompt size manageable.

---

## Agent Configuration Reference

For each story, specify the full agent dispatch configuration.

{SKILL_MAPPING_REFERENCE}

{TOOL_REFERENCE}

{BUDGET_REFERENCE}

---

## Validation Checkpoints: Command-Based

Validation checkpoints run shell commands directly — no LLM agents. Each criterion
should include a `command` field. The `evidence_fields` default to
`["command", "exit_code", "output_tail"]` and can be omitted.

{EVIDENCE_FIELDS_TABLE}

---

## Output

After your analysis, produce the plan JSON inside a ```json code fence.

Key fields:
- `schema_v`: always 1
- `epic_number`: {epic_number}
- `goal`: outcome-shaped goal statement
- `observable_truths`: array of {{id, statement}}
- `user_journeys`: array with journey_id ("J1", "J2", ...), persona,
  narrative, truths_covered, entry_point, critical_transitions
- `stories`: ordered array with story_id ("01-name"), name, purpose,
  agent config, scope, implementation_notes, truths_addressed, wiki_sections
- `validation_checkpoints`: array with after_story, check_type, checks

The critical_transitions use {{source, to, mechanism}}.

---

## Critical Rules

1. Every observable truth must be addressed by at least one story.
2. Every observable truth must appear in at least one journey's truths_covered.
3. Every checkpoint after_story must reference a valid story_id.
4. Every journey truths_covered ID must exist in observable_truths.
5. Files in scope.modify must be real files that exist in the GTS codebase.
6. Files in scope.create must have parent directories that exist.
7. Stories that use files created by earlier stories must appear after them.
8. state_assumption defaults to "cumulative". Only set "clean" when validation
   criteria depend on known data state.
9. The plan.json epic_number must be {epic_number}.
10. Do NOT invent features not described in the epic. Stay within scope.
11. Every story MUST include `wiki_sections` — a list of wiki section header names
    from `.planning/wiki-indexes/` for the Stage 4 prompt builder.

Think step by step, then emit the JSON in a ```json code fence."""

    return prompt


# ---------------------------------------------------------------------------
# Revision prompts
# ---------------------------------------------------------------------------


def build_revision_prompt(
    original_prompt: str,
    validation_errors: list[str],
) -> str:
    """Build a revision prompt when Phase A validation fails.

    Appends the validation errors to the original prompt so the planner
    can fix structural issues in plan.json.
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


def build_verifier_revision_prompt(
    original_prompt: str,
    verifier_result: dict,
) -> str:
    """Build a revision prompt when Phase B verification fails.

    Appends the structured verifier output so the planner can address
    specific gaps: journey incompleteness, uncovered transitions, intent
    misalignment, logical gaps, and weak validations.

    Handles both flat and nested verifier output layouts:
    - Nested: ``{"dimensions": {"journey_completeness": {"findings": {"gaps": [...]}}}}``
    - Flat: ``{"journey_completeness": {"gaps": [...]}}``

    Also handles findings items as either plain strings or dicts with
    structured keys (the verifier is not constrained to one format).
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

    # Resolve dimensions dict (nested under "dimensions" key or flat at top level)
    dims = verifier_result.get("dimensions")
    if not isinstance(dims, dict):
        dims = verifier_result

    def _get_finding_items(dim_data: dict, key: str) -> list:
        """Get finding items from either nested or flat layout."""
        # Nested: dim_data["findings"][key]
        findings = dim_data.get("findings")
        if isinstance(findings, dict):
            items = findings.get(key, [])
            if items:
                return items
        # Flat: dim_data[key]
        return dim_data.get(key, [])

    def _format_item(item) -> str:
        """Format a finding item, handling both str and dict."""
        if isinstance(item, str):
            return item
        if isinstance(item, dict):
            return json.dumps(item, ensure_ascii=False)
        return str(item)

    # Journey completeness
    jc = dims.get("journey_completeness", {})
    if isinstance(jc, dict) and jc.get("status") == "fail":
        feedback_lines.append("### Journey Completeness Gaps")
        for gap in _get_finding_items(jc, "gaps"):
            feedback_lines.append(f"- {_format_item(gap)}")
        feedback_lines.append("")

    # Transition coverage
    tc = dims.get("transition_coverage", {})
    if isinstance(tc, dict) and tc.get("status") == "fail":
        feedback_lines.append("### Uncovered Transitions")
        for uc in _get_finding_items(tc, "uncovered"):
            feedback_lines.append(f"- {_format_item(uc)}")
        feedback_lines.append("")

    # Intent alignment
    ia = dims.get("intent_alignment", {})
    if isinstance(ia, dict) and ia.get("status") == "fail":
        feedback_lines.append("### Intent Alignment Issues")
        for req in _get_finding_items(ia, "unaddressed_requirements"):
            feedback_lines.append(f"- Unaddressed requirement: {_format_item(req)}")
        for creep in _get_finding_items(ia, "scope_creep"):
            feedback_lines.append(f"- Scope creep: {_format_item(creep)}")
        feedback_lines.append("")

    # Gap detection
    gd = dims.get("gap_detection", {})
    if isinstance(gd, dict) and gd.get("status") == "fail":
        feedback_lines.append("### Logical Gaps Between Stories")
        for gap in _get_finding_items(gd, "gaps"):
            feedback_lines.append(f"- {_format_item(gap)}")
        feedback_lines.append("")

    # Validation sufficiency
    vs = dims.get("validation_sufficiency", {})
    if isinstance(vs, dict) and vs.get("status") == "fail":
        feedback_lines.append("### Weak Validation Checks")
        for wc in _get_finding_items(vs, "weak_checks"):
            feedback_lines.append(f"- {_format_item(wc)}")
        feedback_lines.append("")

    feedback_lines.append(
        "Fix all issues above. Produce a single JSON object conforming to "
        "the schema. Output ONLY the raw JSON, no other text."
    )

    return original_prompt + "\n".join(feedback_lines)


# ---------------------------------------------------------------------------
# Structured output parsing
# ---------------------------------------------------------------------------


def _parse_structured_plan(result) -> Plan:
    """Parse a dispatch result into a validated Plan model.

    The model produces reasoning text followed by JSON in a ```json code fence.
    We extract the fenced JSON and validate with Pydantic.
    """
    text = result.output.strip()

    # Dump raw output for debugging
    dump_path = PLANNING_DIR.parent / "logs" / "last-planner-output.txt"
    dump_path.parent.mkdir(parents=True, exist_ok=True)
    dump_path.write_text(text, encoding="utf-8")
    logger.info("Raw planner output dumped to %s (%d chars)", dump_path, len(text))

    # Extract JSON from ```json code fence
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
            f"{error_context}\n{marker_line}\n"
            f"Full output dumped to: {dump_path}"
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
    """Generate PLAN.md and plan.json from assembled context.

    Dispatches a single planner invocation with tools=[] to produce plan JSON.
    The JSON schema is included in the prompt text (not via --json-schema
    constrained decoding, which fails on large outputs). PLAN.md is rendered
    deterministically from the validated Pydantic model.

    Args:
        epic_dir: Path to the epic directory (e.g. .planning/epics/E95/).
            Must contain CONTEXT.md from context assembly.
        config: Optional epic config. If provided, uses config.models.planner
            and config.budgets for dispatch parameters.

    Returns:
        Tuple of (plan_md_path, plan_json_path).

    Raises:
        PlanGenerationError: If context is missing, dispatch fails, or
            output cannot be parsed.
    """
    # Read inputs
    context = _read_context(epic_dir)
    epic_number = _read_epic_number(epic_dir)
    user_decisions = _read_user_decisions(epic_dir)

    # Build the planner prompt (includes JSON schema as context)
    prompt = _build_planner_prompt(
        context=context,
        epic_number=epic_number,
        user_decisions=user_decisions,
    )

    # Resolve model and budget from config or defaults
    planner_model = config.models.planner if config else "opus"
    if config and "planning" in config.budgets:
        budget = config.budgets["planning"]
        max_turns = budget.max_turns
        max_budget_usd = budget.max_budget_usd
    else:
        planning_budget = BUDGET_DEFAULTS["planning"]
        max_turns = int(planning_budget["max_turns"])
        max_budget_usd = float(planning_budget["max_budget_usd"])

    logger.info(
        "Dispatching %s planner for epic #%d (%d chars, ~%d tokens)",
        planner_model,
        epic_number,
        len(prompt),
        len(prompt) // 4,
    )

    # Dispatch with tools=[] — no constrained decoding.
    # The prompt instructs the model to produce raw JSON; we validate
    # with Pydantic after parsing.
    result = dispatch_with_fallback(
        prompt=prompt,
        primary_model=planner_model,
        fallback_model=FALLBACK_MODELS.get(planner_model, planner_model),
        tools=[],
        max_turns=max_turns,
        max_budget_usd=max_budget_usd,
        json_schema=None,
        cwd=PROJECT_ROOT,
        no_mcp=True,
    )

    if not result.success:
        raise PlanGenerationError(
            f"Opus planner dispatch failed (exit_code={result.exit_code}). "
            f"Output: {result.output[:500]}"
        )

    logger.info(
        "Planner output length: %d chars, turns: %s",
        len(result.output),
        result.turns or "unknown",
    )

    # Parse structured output into Pydantic model
    plan = _parse_structured_plan(result)

    # Write plan.json (serialised from validated model)
    plan_json_path = epic_dir / "plan.json"
    plan_json_path.write_text(
        json.dumps(plan.model_dump(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    logger.info("Wrote plan.json to %s", plan_json_path)

    # Render and write PLAN.md deterministically
    plan_md_path = epic_dir / "PLAN.md"
    plan_md_path.write_text(render_plan_md(plan), encoding="utf-8")
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
            f"Run ingestion and context assembly first.",
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
