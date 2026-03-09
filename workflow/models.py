"""Pydantic models for epic plan and curation data structures.

These models are the single source of truth for plan.json structure.
They replace plan.schema.json for both validation and structured output.

Usage:
    from workflow.models import Plan, render_plan_md

    # Parse from dict (e.g. Claude structured output)
    plan = Plan.model_validate(data)

    # Generate JSON Schema for --json-schema
    schema = Plan.model_json_schema()

    # Render deterministic PLAN.md
    md = render_plan_md(plan)
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

# ---------------------------------------------------------------------------
# Leaf models
# ---------------------------------------------------------------------------


class CriticalTransition(BaseModel):
    """Key navigation or state transition in a user journey."""

    source: str = Field(description="Source page or state.")
    to: str = Field(description="Target page or state.")
    mechanism: str = Field(description="How the user transitions.")


class ObservableTruth(BaseModel):
    """User-perspective, verifiable-by-a-human assertion that defines 'done'."""

    id: int = Field(description="Unique identifier referenced by stories and journeys.")
    statement: str = Field(description="User-perspective assertion.")


class Scope(BaseModel):
    """Files a story creates and modifies."""

    create: list[str] = Field(default_factory=list, description="File paths to create.")
    modify: list[str] = Field(
        default_factory=list, description="File paths to modify (must exist)."
    )


class AgentConfig(BaseModel):
    """Full agent dispatch specification for a story."""

    model: Literal["opus", "sonnet", "haiku", "codex"] = Field(description="Model tier.")
    skills: list[str] = Field(default_factory=list, description="Skill names to inject.")
    tools: list[str] = Field(default_factory=list, description="Tools available to the agent.")


class TestAssertion(BaseModel):
    """Individual assertion within a test spec.

    Accepts both flat and nested formats:
      Flat:   {"type": "http_status", "route": "/foo", "expected_status": 200}
      Nested: {"type": "http_status", "details": {"route": "/foo", "expected_status": 200}}

    In both cases, type-specific fields end up in ``details``.
    """

    type: str = Field(
        description="Assertion type: http_status, dom_element, dom_absent, db_state, api_response."
    )
    details: dict = Field(
        default_factory=dict,
        description="Type-specific fields (e.g. route, selector, query).",
    )

    @model_validator(mode="before")
    @classmethod
    def _collect_flat_fields(cls, data: object) -> object:
        """Move non-schema keys into details (supports flat assertion format)."""
        if not isinstance(data, dict):
            return data
        known_keys = {"type", "details"}
        extra = {k: v for k, v in data.items() if k not in known_keys}
        if extra:
            details = dict(data.get("details", {}))
            details.update(extra)
            return {"type": data["type"], "details": details}
        return data


class TestSpec(BaseModel):
    """Machine-readable test specification for a story."""

    test_type: str = Field(
        description="Test type: 'integration' or 'e2e'."
    )
    fixtures: list[str] = Field(
        default_factory=list,
        description="Fixture names to use (e.g. 'make_user', 'make_shootout(chains=2)').",
    )
    assertions: list[TestAssertion] = Field(
        default_factory=list,
        description="Ordered list of assertions to verify.",
    )


class CheckCriterion(BaseModel):
    """Individual criterion to verify at a validation checkpoint."""

    criterion: str = Field(description="Natural-language behaviour to verify.")
    command: str | None = Field(
        default=None,
        description="Shell command to run (e.g. 'just tdd tests/... -k test_name'). "
        "Exit 0 = pass. If omitted, falls back to keyword matching.",
    )
    evidence_fields: list[str] = Field(
        default_factory=lambda: ["command", "exit_code", "output_tail"],
        description="Evidence fields (default: command output).",
    )


# ---------------------------------------------------------------------------
# Composite models
# ---------------------------------------------------------------------------


class UserJourney(BaseModel):
    """Connected end-to-end narrative linking observable truths."""

    journey_id: str = Field(description="Journey identifier, e.g. 'J1'.")
    persona: str = Field(description="Who is performing this journey.")
    narrative: str = Field(description="End-to-end walkthrough in plain English.")
    truths_covered: list[int] = Field(description="IDs of observable truths exercised.")
    entry_point: str = Field(description="URL path where the journey begins.")
    critical_transitions: list[CriticalTransition] = Field(
        description="Key transitions that must work."
    )


class Story(BaseModel):
    """A coherent chunk of work an agent completes in one invocation."""

    story_id: str = Field(description="Unique story identifier, e.g. '01-architecture'.")
    name: str = Field(description="Human-readable story name.")
    purpose: str = Field(description="What this story delivers.")
    agent: AgentConfig
    scope: Scope
    state_assumption: Literal["cumulative", "clean"] = "cumulative"
    acceptance_criteria: list[str] = Field(
        description="User-perspective, verifiable criteria that must all pass for this story to be done. Required non-empty."
    )
    architectural_context: list[str] = Field(
        default_factory=list,
        description="Architecture patterns, module boundaries, and design decisions relevant to this story.",
    )
    navigation_hints: list[str] = Field(
        default_factory=list,
        description="File paths, symbol names, and entry points to orient the agent in the codebase.",
    )
    implementation_notes: list[str] = Field(
        default_factory=list, description="Domain-specific hints."
    )
    truths_addressed: list[int] = Field(
        description="IDs of observable truths this story contributes to."
    )
    test_spec: TestSpec | None = Field(
        default=None,
        description="Machine-readable test specification for automated validation.",
    )


class ValidationCheckpoint(BaseModel):
    """Strategic validation checkpoint placed after a story."""

    after_story: str = Field(description="References a story_id.")
    check_type: Literal[
        "http",
        "http+dom",
        "browser+db",
        "api+response",
        "process",
        "screenshot",
        "regression",
        "quality",
    ] = Field(description="Type of validation check.")
    checks: list[CheckCriterion] = Field(description="Criteria to verify.")


class ContractDecision(BaseModel):
    """Explicit resolution for an epic-vs-repo contract mismatch."""

    decision_id: str = Field(description="Stable contract decision identifier, e.g. CD1.")
    epic_contract: str = Field(description="Canonical user-facing/API contract from the epic.")
    repo_convention: str = Field(description="Conflicting route, field, or transport already in repo.")
    canonical: Literal["epic", "bridge"] = Field(
        description="Whether the epic contract stands alone or ships with a compatibility bridge."
    )
    bridge: str | None = Field(
        default=None,
        description="Compatibility bridge details. Required when canonical is 'bridge'.",
    )
    affected_stories: list[str] = Field(
        default_factory=list,
        description="Story IDs that implement or validate this decision.",
    )

    @model_validator(mode="after")
    def _validate_bridge_requirements(self) -> "ContractDecision":
        if self.canonical == "bridge" and not (self.bridge and self.bridge.strip()):
            raise ValueError("ContractDecision.bridge is required when canonical == 'bridge'.")
        if self.canonical == "epic" and self.bridge is not None:
            raise ValueError("ContractDecision.bridge must be omitted when canonical == 'epic'.")
        return self


# ---------------------------------------------------------------------------
# Curation models
# ---------------------------------------------------------------------------


class CandidateJourney(BaseModel):
    """Bounded journey candidate used to shape the planner handoff."""

    journey_id: str = Field(description="Stable candidate identifier, e.g. CJ1.")
    title: str = Field(description="Short label for the journey candidate.")
    entry_point: str = Field(description="Observed or required entry point for this journey.")
    desired_outcome: str = Field(description="What the user should achieve by the end.")
    key_steps: list[str] = Field(
        default_factory=list,
        description="Ordered steps or transitions that planning must preserve.",
    )


class StorySlice(BaseModel):
    """Candidate vertical slice boundary proposed before final plan generation."""

    slice_id: str = Field(description="Stable slice identifier, e.g. SL1.")
    title: str = Field(description="Short label for the slice.")
    objective: str = Field(description="What the slice should deliver.")
    likely_surfaces: list[str] = Field(
        default_factory=list,
        description="Files, routes, or components likely involved in this slice.",
    )
    dependencies: list[str] = Field(
        default_factory=list,
        description="Preconditions or earlier slices this slice depends on.",
    )


class MissingAssumption(BaseModel):
    """Epic ambiguity or repo gap the planner should resolve explicitly."""

    assumption: str = Field(description="The missing or ambiguous assumption.")
    why_it_matters: str = Field(description="Why this assumption affects plan correctness.")
    planner_action: str = Field(description="What the planner should do about it.")


class ScopeTension(BaseModel):
    """Scope boundary or design tension that needs explicit handling."""

    tension: str = Field(description="The scope tension or conflict.")
    tradeoff: str = Field(description="Why the tension matters.")
    planner_guidance: str = Field(description="How the planner should resolve or balance it.")


class PlannerHandoff(BaseModel):
    """Compact bounded handoff from curation into planning."""

    priority_order: list[str] = Field(
        default_factory=list,
        description="Ordered priorities the planner should preserve.",
    )
    watchouts: list[str] = Field(
        default_factory=list,
        description="Pitfalls the planner should avoid.",
    )
    recommended_story_shape: str = Field(
        description="Concise guidance on the intended story framing.",
    )


# ---------------------------------------------------------------------------
# Root model
# ---------------------------------------------------------------------------


class Plan(BaseModel):
    """Machine-readable plan specification for the epic workflow."""

    schema_v: Literal[1] = Field(default=1, description="Schema version.")
    epic_number: int = Field(description="GitHub issue number for the epic.")
    goal: str = Field(description="Outcome-shaped goal statement.")
    observable_truths: list[ObservableTruth] = Field(description="Truths that define 'done'.")
    user_journeys: list[UserJourney] = Field(description="End-to-end narratives.")
    contract_decisions: list[ContractDecision] = Field(
        default_factory=list,
        description="Explicit epic-vs-repo contract resolutions. Canonical may be 'epic' or 'bridge' only.",
    )
    stories: list[Story] = Field(description="Ordered sequence of stories to execute.")
    validation_checkpoints: list[ValidationCheckpoint] = Field(
        default_factory=list, description="Strategic validation checkpoints."
    )

    @model_validator(mode="after")
    def _validate_unique_contract_decision_ids(self) -> "Plan":
        seen: set[str] = set()
        duplicates: set[str] = set()
        for decision in self.contract_decisions:
            if decision.decision_id in seen:
                duplicates.add(decision.decision_id)
            seen.add(decision.decision_id)
        if duplicates:
            duplicate_list = ", ".join(sorted(duplicates))
            raise ValueError(f"Duplicate contract decision IDs are not allowed: {duplicate_list}")
        return self


class Curation(BaseModel):
    """Machine-readable curation handoff between repo-facts and planning."""

    schema_v: Literal[1] = Field(default=1, description="Schema version.")
    epic_number: int = Field(description="GitHub issue number for the epic.")
    candidate_journeys: list[CandidateJourney] = Field(
        default_factory=list,
        description="Candidate end-to-end journeys that should shape planning.",
    )
    story_slices: list[StorySlice] = Field(
        default_factory=list,
        description="Candidate story boundaries and sequencing hints.",
    )
    missing_assumptions: list[MissingAssumption] = Field(
        default_factory=list,
        description="Assumptions or ambiguities the planner must resolve.",
    )
    scope_tensions: list[ScopeTension] = Field(
        default_factory=list,
        description="Scope tensions to balance explicitly during planning.",
    )
    planner_handoff: PlannerHandoff


# ---------------------------------------------------------------------------
# Deterministic PLAN.md renderer
# ---------------------------------------------------------------------------


def render_plan_md(plan: Plan) -> str:
    """Render a Plan model to deterministic PLAN.md markdown.

    PLAN.md is never emitted by Claude — it is always rendered from
    the validated Plan model to ensure consistency with plan.json.
    """
    lines: list[str] = []

    # Header
    lines.append(f"# Plan: Epic #{plan.epic_number}")
    lines.append("")
    lines.append("## Goal")
    lines.append("")
    lines.append(plan.goal)
    lines.append("")

    # Observable Truths
    lines.append("## Observable Truths")
    lines.append("")
    for truth in plan.observable_truths:
        lines.append(f"{truth.id}. {truth.statement}")
    lines.append("")

    # User Journeys
    lines.append("## User Journeys")
    lines.append("")
    for journey in plan.user_journeys:
        lines.append(f"### Journey {journey.journey_id}: {journey.persona}")
        lines.append("")
        lines.append(journey.narrative)
        lines.append("")
        lines.append(f"**Truths covered:** {', '.join(str(t) for t in journey.truths_covered)}")
        lines.append(f"**Entry point:** {journey.entry_point}")
        lines.append("**Critical transitions:**")
        for ct in journey.critical_transitions:
            lines.append(f"- {ct.source} -> {ct.to} ({ct.mechanism})")
    lines.append("")

    # Contract Decisions
    lines.append("## Contract Decisions")
    lines.append("")
    if plan.contract_decisions:
        lines.append("| ID | Epic Contract | Repo Convention | Resolution | Affected Stories |")
        lines.append("|---|---|---|---|---|")
        for decision in plan.contract_decisions:
            resolution = decision.canonical
            if decision.bridge:
                resolution = f"{resolution}: {decision.bridge}"
            affected = ", ".join(f"`{story_id}`" for story_id in decision.affected_stories) or "-"
            lines.append(
                "| "
                f"{decision.decision_id} | "
                f"{_escape_markdown_table_cell(decision.epic_contract)} | "
                f"{_escape_markdown_table_cell(decision.repo_convention)} | "
                f"{_escape_markdown_table_cell(resolution)} | "
                f"{affected} |"
            )
    else:
        lines.append("(none)")
    lines.append("")

    # Stories
    lines.append("## Stories")
    lines.append("")
    for story in plan.stories:
        lines.append(f"### Story: {story.name} (`{story.story_id}`)")
        lines.append("")
        lines.append(f"**Purpose:** {story.purpose}")
        lines.append("")
        lines.append("**Agent:**")
        lines.append(f"- model: {story.agent.model}")
        lines.append(f"- skills: [{', '.join(story.agent.skills)}]")
        lines.append(f"- tools: [{', '.join(story.agent.tools)}]")
        lines.append("")
        lines.append("**Scope:**")
        for fp in story.scope.create:
            lines.append(f"- Create: `{fp}`")
        for fp in story.scope.modify:
            lines.append(f"- Modify: `{fp}`")
        lines.append("")
        lines.append("### Acceptance Criteria")
        lines.append("")
        for criterion in story.acceptance_criteria:
            lines.append(f"- {criterion}")
        lines.append("")
        lines.append("### Architectural Context")
        lines.append("")
        for item in story.architectural_context:
            lines.append(f"- {item}")
        lines.append("")
        lines.append("### Navigation Guide")
        lines.append("")
        for hint in story.navigation_hints:
            lines.append(f"- {hint}")
        lines.append("")
        if story.implementation_notes:
            lines.append("**Implementation Notes:**")
            for note in story.implementation_notes:
                lines.append(f"- {note}")
            lines.append("")
        lines.append(f"**Truths Addressed:** {', '.join(str(t) for t in story.truths_addressed)}")
        lines.append("")
        if story.test_spec:
            lines.append("### Test Spec")
            lines.append("")
            lines.append(f"**Type:** {story.test_spec.test_type}")
            if story.test_spec.fixtures:
                lines.append(f"**Fixtures:** {', '.join(story.test_spec.fixtures)}")
            if story.test_spec.assertions:
                lines.append("**Assertions:**")
                for assertion in story.test_spec.assertions:
                    detail_str = ", ".join(f"{k}={v}" for k, v in assertion.details.items())
                    lines.append(f"- [{assertion.type}] {detail_str}")
            lines.append("")
        lines.append("---")
        lines.append("")

        # Validation checkpoint after this story (if any)
        for cp in plan.validation_checkpoints:
            if cp.after_story == story.story_id:
                lines.append(f"### Validation Checkpoint: After {story.name}")
                lines.append("")
                lines.append(f"**Type:** {cp.check_type}")
                lines.append("**Checks:**")
                for check in cp.checks:
                    evidence = ", ".join(check.evidence_fields)
                    cmd_suffix = f" [cmd: `{check.command}`]" if check.command else ""
                    lines.append(f"- {check.criterion} (evidence: {evidence}){cmd_suffix}")
                lines.append("")
                lines.append("---")
                lines.append("")

    # Artefact Summary
    lines.append("## Artefact Summary")
    lines.append("")
    lines.append("| Truth | Key Artefacts | Story |")
    lines.append("|-------|---------------|-------|")
    for truth in plan.observable_truths:
        # Find stories addressing this truth
        addressing = [s for s in plan.stories if truth.id in s.truths_addressed]
        story_names = ", ".join(s.name for s in addressing)
        # Collect files from those stories
        files = []
        for s in addressing:
            files.extend(s.scope.create)
            files.extend(s.scope.modify)
        artefacts = ", ".join(f"`{f}`" for f in files[:3])
        if len(files) > 3:
            artefacts += f" (+{len(files) - 3} more)"
        lines.append(f"| {truth.id}. {truth.statement} | {artefacts} | {story_names} |")
    lines.append("")

    return "\n".join(lines)


def render_curation_md(curation: Curation) -> str:
    """Render a Curation model to deterministic CURATION.md markdown."""
    lines: list[str] = []

    lines.append(f"# Curation: Epic #{curation.epic_number}")
    lines.append("")

    lines.append("## Candidate Journeys")
    lines.append("")
    if curation.candidate_journeys:
        for journey in curation.candidate_journeys:
            lines.append(f"### {journey.title} (`{journey.journey_id}`)")
            lines.append("")
            lines.append(f"**Entry point:** {journey.entry_point}")
            lines.append(f"**Desired outcome:** {journey.desired_outcome}")
            if journey.key_steps:
                lines.append("**Key steps:**")
                for step in journey.key_steps:
                    lines.append(f"- {step}")
            lines.append("")
    else:
        lines.append("(none)")
        lines.append("")

    lines.append("## Story Slices")
    lines.append("")
    if curation.story_slices:
        for story_slice in curation.story_slices:
            lines.append(f"### {story_slice.title} (`{story_slice.slice_id}`)")
            lines.append("")
            lines.append(story_slice.objective)
            if story_slice.likely_surfaces:
                lines.append("")
                lines.append("**Likely surfaces:**")
                for surface in story_slice.likely_surfaces:
                    lines.append(f"- {surface}")
            if story_slice.dependencies:
                lines.append("")
                lines.append("**Dependencies:**")
                for dependency in story_slice.dependencies:
                    lines.append(f"- {dependency}")
            lines.append("")
    else:
        lines.append("(none)")
        lines.append("")

    lines.append("## Missing Assumptions")
    lines.append("")
    if curation.missing_assumptions:
        for item in curation.missing_assumptions:
            lines.append(f"- **Assumption:** {item.assumption}")
            lines.append(f"  **Why it matters:** {item.why_it_matters}")
            lines.append(f"  **Planner action:** {item.planner_action}")
    else:
        lines.append("(none)")
    lines.append("")

    lines.append("## Scope Tensions")
    lines.append("")
    if curation.scope_tensions:
        for item in curation.scope_tensions:
            lines.append(f"- **Tension:** {item.tension}")
            lines.append(f"  **Tradeoff:** {item.tradeoff}")
            lines.append(f"  **Planner guidance:** {item.planner_guidance}")
    else:
        lines.append("(none)")
    lines.append("")

    lines.append("## Planner Handoff")
    lines.append("")
    lines.append(f"**Recommended story shape:** {curation.planner_handoff.recommended_story_shape}")
    lines.append("")
    lines.append("**Priority order:**")
    if curation.planner_handoff.priority_order:
        for item in curation.planner_handoff.priority_order:
            lines.append(f"- {item}")
    else:
        lines.append("- (none)")
    lines.append("")
    lines.append("**Watchouts:**")
    if curation.planner_handoff.watchouts:
        for item in curation.planner_handoff.watchouts:
            lines.append(f"- {item}")
    else:
        lines.append("- (none)")
    lines.append("")

    return "\n".join(lines)


def _escape_markdown_table_cell(value: str) -> str:
    """Keep deterministic markdown table cells on one line."""
    return value.replace("|", "\\|").replace("\n", " ")
