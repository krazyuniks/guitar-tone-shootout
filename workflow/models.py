"""Pydantic models for epic plan data structures.

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

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Leaf models
# ---------------------------------------------------------------------------


class CriticalTransition(BaseModel):
    """Key navigation or state transition in a user journey."""

    from_: str = Field(min_length=1, alias="from", description="Source page or state.")
    to: str = Field(min_length=1, description="Target page or state.")
    mechanism: str = Field(min_length=1, description="How the user transitions.")

    model_config = {"populate_by_name": True}


class ObservableTruth(BaseModel):
    """User-perspective, verifiable-by-a-human assertion that defines 'done'."""

    id: int = Field(ge=1, description="Unique identifier referenced by stories and journeys.")
    statement: str = Field(min_length=1, description="User-perspective assertion.")


class Scope(BaseModel):
    """Files a story creates and modifies."""

    create: list[str] = Field(default_factory=list, description="File paths to create.")
    modify: list[str] = Field(
        default_factory=list, description="File paths to modify (must exist)."
    )


class AgentConfig(BaseModel):
    """Full agent dispatch specification for a story."""

    model: Literal["opus", "sonnet", "haiku"] = Field(description="Claude model tier.")
    skills: list[str] = Field(default_factory=list, description="Skill names to inject.")
    tools: list[str] = Field(default_factory=list, description="Tools available to the agent.")
    mcp: list[str] = Field(default_factory=list, description="MCP server names required.")
    max_turns: int = Field(ge=1, description="Maximum conversation turns.")
    max_budget_usd: float = Field(gt=0, description="Maximum spend in USD.")


class CheckCriterion(BaseModel):
    """Individual criterion to verify at a validation checkpoint."""

    criterion: str = Field(min_length=1, description="Natural-language behaviour to verify.")
    evidence_fields: list[str] = Field(
        min_length=1, description="Required evidence fields for this criterion."
    )


# ---------------------------------------------------------------------------
# Composite models
# ---------------------------------------------------------------------------


class UserJourney(BaseModel):
    """Connected end-to-end narrative linking observable truths."""

    journey_id: str = Field(pattern=r"^J[0-9]+$", description="Journey identifier, e.g. 'J1'.")
    persona: str = Field(min_length=1, description="Who is performing this journey.")
    narrative: str = Field(min_length=1, description="End-to-end walkthrough in plain English.")
    truths_covered: list[int] = Field(
        min_length=1, description="IDs of observable truths exercised."
    )
    entry_point: str = Field(min_length=1, description="URL path where the journey begins.")
    critical_transitions: list[CriticalTransition] = Field(
        min_length=1, description="Key transitions that must work."
    )


class Story(BaseModel):
    """A coherent chunk of work an agent completes in one invocation."""

    story_id: str = Field(
        pattern=r"^[a-z0-9][a-z0-9-]*$",
        description="Unique story identifier, e.g. '01-architecture'.",
    )
    name: str = Field(min_length=1, description="Human-readable story name.")
    purpose: str = Field(min_length=1, description="What this story delivers.")
    agent: AgentConfig
    scope: Scope
    state_assumption: Literal["cumulative", "clean"] = "cumulative"
    implementation_notes: list[str] = Field(
        default_factory=list, description="Domain-specific hints."
    )
    truths_addressed: list[int] = Field(
        min_length=1, description="IDs of observable truths this story contributes to."
    )
    wiki_sections: list[str] = Field(
        default_factory=list, description="Wiki section headers for Stage 4 prompt builder."
    )


class ValidationCheckpoint(BaseModel):
    """Strategic validation checkpoint placed after a story."""

    after_story: str = Field(min_length=1, description="References a story_id.")
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
    checks: list[CheckCriterion] = Field(min_length=1, description="Criteria to verify.")


# ---------------------------------------------------------------------------
# Root model
# ---------------------------------------------------------------------------


class Plan(BaseModel):
    """Machine-readable plan specification for the epic workflow."""

    schema_v: Literal[1] = Field(default=1, description="Schema version.")
    epic_number: int = Field(ge=1, description="GitHub issue number for the epic.")
    goal: str = Field(min_length=1, description="Outcome-shaped goal statement.")
    observable_truths: list[ObservableTruth] = Field(
        min_length=1, description="Truths that define 'done'."
    )
    user_journeys: list[UserJourney] = Field(min_length=1, description="End-to-end narratives.")
    stories: list[Story] = Field(
        min_length=1, description="Ordered sequence of stories to execute."
    )
    validation_checkpoints: list[ValidationCheckpoint] = Field(
        default_factory=list, description="Strategic validation checkpoints."
    )


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
            lines.append(f"- {ct.from_} -> {ct.to} ({ct.mechanism})")
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
        lines.append(f"- mcp: [{', '.join(story.agent.mcp)}]")
        lines.append(f"- max_turns: {story.agent.max_turns}")
        lines.append(f"- max_budget_usd: {story.agent.max_budget_usd}")
        lines.append("")
        lines.append("**Scope:**")
        for fp in story.scope.create:
            lines.append(f"- Create: `{fp}`")
        for fp in story.scope.modify:
            lines.append(f"- Modify: `{fp}`")
        lines.append("")
        if story.wiki_sections:
            lines.append(f"**Wiki Sections:** {', '.join(story.wiki_sections)}")
            lines.append("")
        if story.implementation_notes:
            lines.append("**Implementation Notes:**")
            for note in story.implementation_notes:
                lines.append(f"- {note}")
            lines.append("")
        lines.append(f"**Truths Addressed:** {', '.join(str(t) for t in story.truths_addressed)}")
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
                    lines.append(f"- {check.criterion} (evidence: {evidence})")
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
