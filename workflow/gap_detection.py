"""Stage 2b gap detection — interactive scope refinement.

Identifies implementation gaps between the enriched epic and the current
architecture/codebase, then resolves them through interactive Q&A with
the user. Produces user-decisions.json — the locked-down scope artifact
consumed by the planner.

Reference: wiki/Epic-Workflow.md, Stage 2b Gap Detection.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

import typer
from pydantic import BaseModel, Field
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule

from workflow.dispatch import (
    BUDGET_DEFAULTS,
    dispatch_agent,
    get_tools_for_role,
)

if TYPE_CHECKING:
    from workflow.epic_config import EpicConfig
    from workflow.jsonl_logger import EventLogger

logger = logging.getLogger(__name__)
console = Console()

GAP_DETECTION_GUIDE = Path(__file__).parent / "references" / "gap-detection-guide.md"


class GapDetectionError(Exception):
    """Raised when gap detection fails."""


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class Gap(BaseModel):
    """A single identified gap between epic requirements and codebase."""

    id: str = Field(description="Short unique identifier, e.g. 'gap-auth-1'")
    gap_type: str = Field(
        description="ambiguity | assumption | contradiction | missing | bc_ownership | cross_bc_flow"
    )
    area: str = Field(description="Architecture area: data_model, api, frontend, security, etc.")
    description: str = Field(description="What the gap is")
    question: str = Field(description="Question to resolve this gap")
    options: list[str] = Field(
        default_factory=list, description="Multiple choice options (if applicable)"
    )
    recommendation: str = Field(
        default="", description="Agent's recommended option (if applicable)"
    )


class GapReport(BaseModel):
    """Full gap detection report from the agent."""

    gaps: list[Gap] = Field(default_factory=list)
    coverage_areas_checked: list[str] = Field(default_factory=list)


class GapAnswer(BaseModel):
    """A resolved gap with the user's answer."""

    gap_id: str
    question: str
    answer: str


class UserDecisions(BaseModel):
    """Schema-validated output artifact for user-decisions.json."""

    epic_number: int
    answers: list[GapAnswer] = Field(default_factory=list)
    sufficiency_confirmed: bool = Field(default=False)


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------


def _build_gap_detection_prompt(epic_md: str, context_md: str, guide: str) -> str:
    """Build the prompt for the gap detection agent."""
    return f"""\
# Task: Gap Detection for Epic

You are analysing an enriched epic and its assembled context to identify \
implementation gaps. Read both documents carefully, then compare the epic \
requirements against the architecture and codebase.

## Gap Detection Guide

{guide}

## Epic (EPIC.md)

{epic_md}

## Context (CONTEXT.md)

{context_md}

## Instructions

1. Read the epic and context thoroughly.
2. Identify gaps using the gap types from the guide (ambiguity, assumption, \
contradiction, missing information, BC ownership, cross-BC flow).
3. For each gap, derive a specific question that would resolve it.
4. Where multiple valid approaches exist, provide 2-3 options with your \
recommendation.
5. Confirm which architecture areas you checked for coverage.

Output your analysis as JSON matching this schema:

```json
{{
  "gaps": [
    {{
      "id": "gap-<area>-<n>",
      "gap_type": "ambiguity|assumption|contradiction|missing|bc_ownership|cross_bc_flow",
      "area": "<architecture area>",
      "description": "<what the gap is>",
      "question": "<question to resolve it>",
      "options": ["option 1", "option 2"],
      "recommendation": "<recommended option>"
    }}
  ],
  "coverage_areas_checked": ["bounded_contexts", "data_model", "messaging", ...]
}}
```

Think through your analysis step by step, then emit the JSON inside a \
```json code fence.
"""


def _build_critique_prompt(epic_md: str, context_md: str, gap_report_json: str) -> str:
    """Build the prompt for the gap critique agent."""
    return f"""\
# Task: Critique Gap Detection Report

You are reviewing a gap detection report for an epic. Your job is to find \
problems with the analysis — not to agree with it.

## Epic (EPIC.md)

{epic_md}

## Context (CONTEXT.md)

{context_md}

## Gap Report to Critique

{gap_report_json}

## Instructions

Review the gap report critically:

1. **Missing gaps**: Are there gaps the first agent didn't catch? Check all \
architecture areas: bounded contexts, data model, messaging, API contracts, \
frontend, workers, testing, security, infrastructure.
2. **Badly framed questions**: Are any questions too vague, leading, or \
answerable from the existing context?
3. **False gaps**: Are any "gaps" actually answered by the existing \
architecture or codebase?
4. **Coverage**: Were all architecture areas actually checked?

Output your critique as plain text. Be specific about what's missing or wrong. \
If the report is thorough, say so briefly.
"""


# ---------------------------------------------------------------------------
# Interactive Q&A
# ---------------------------------------------------------------------------


def _ask_gap_questions(gaps: list[Gap]) -> list[GapAnswer]:
    """Present gaps to the user one at a time, collect answers."""
    answers: list[GapAnswer] = []

    for i, gap in enumerate(gaps, 1):
        console.print()
        console.print(Rule(f"Question {i}/{len(gaps)}"))
        console.print(f"[bold]Area:[/bold] {gap.area}")
        console.print(f"[bold]Type:[/bold] {gap.gap_type}")
        console.print(f"[bold]Gap:[/bold] {gap.description}")
        console.print()

        if gap.options:
            console.print("[bold]Options:[/bold]")
            for j, option in enumerate(gap.options, 1):
                rec = " [green](recommended)[/green]" if option == gap.recommendation else ""
                console.print(f"  {j}. {option}{rec}")
            console.print()

        answer = typer.prompt(gap.question)
        answers.append(GapAnswer(gap_id=gap.id, question=gap.question, answer=answer))

    return answers


# ---------------------------------------------------------------------------
# Core flow
# ---------------------------------------------------------------------------


def _parse_json_from_response(text: str) -> dict:
    """Extract JSON from a fenced code block or raw JSON response."""
    # Try extracting from ```json ... ``` fence
    if "```json" in text:
        start = text.index("```json") + len("```json")
        end = text.index("```", start)
        return json.loads(text[start:end])
    # Try raw JSON parse
    return json.loads(text)


def run_gap_detection(
    epic_dir: Path,
    event_logger: EventLogger,
    config: EpicConfig | None = None,
) -> Path:
    """Run the full Stage 2b gap detection flow.

    1. Dispatch gap detection agent
    2. Dispatch critique agent
    3. Display exchange to user
    4. Interactive Q&A
    5. Sufficiency confirmation
    6. Write user-decisions.json

    Args:
        epic_dir: Path to the epic directory (e.g. .planning/epics/E95/).
        event_logger: JSONL event logger for this epic.
        config: Optional epic config for model/budget overrides.

    Returns:
        Path to the written user-decisions.json.

    Raises:
        GapDetectionError: If agent dispatch fails or output is unparseable,
            or if stdin is not interactive (would hang on typer.prompt).
    """
    import sys

    if not sys.stdin.isatty():
        raise GapDetectionError(
            "Gap detection requires interactive input (stdin is not a TTY). "
            "Run the pipeline interactively or provide user-decisions.json manually."
        )

    epic_md_path = epic_dir / "EPIC.md"
    context_md_path = epic_dir / "CONTEXT.md"

    if not epic_md_path.exists():
        raise GapDetectionError(f"EPIC.md not found at {epic_md_path}")
    if not context_md_path.exists():
        raise GapDetectionError(f"CONTEXT.md not found at {context_md_path}")

    epic_md = epic_md_path.read_text(encoding="utf-8")
    context_md = context_md_path.read_text(encoding="utf-8")

    # Read gap detection guide
    if not GAP_DETECTION_GUIDE.exists():
        raise GapDetectionError(f"Gap detection guide not found at {GAP_DETECTION_GUIDE}")
    guide = GAP_DETECTION_GUIDE.read_text(encoding="utf-8")

    # Extract epic number from directory name
    epic_number = int(epic_dir.name.lstrip("E"))

    # Resolve models from config
    gap_model = config.models.planner if config else "opus"
    critique_model = config.models.plan_critic if config else "codex"

    # Resolve budget
    if config and "gap_detection" in config.budgets:
        budget = config.budgets["gap_detection"]
        max_turns = budget.max_turns
        max_budget_usd = budget.max_budget_usd
    else:
        gap_budget = BUDGET_DEFAULTS["gap_detection"]
        max_turns = int(gap_budget["max_turns"])
        max_budget_usd = float(gap_budget["max_budget_usd"])

    # --- Step 1: Gap Detection Agent ---
    console.print("[bold]Step 2b.1:[/bold] Detecting gaps...")
    event_logger.log_event("gap_detection_started", epic=epic_number, model=gap_model)

    gap_prompt = _build_gap_detection_prompt(epic_md, context_md, guide)
    gap_result = dispatch_agent(
        prompt=gap_prompt,
        model=gap_model,
        tools=get_tools_for_role("planning"),
        max_turns=max_turns,
        max_budget_usd=max_budget_usd,
        no_mcp=True,
    )

    if not gap_result.success:
        raise GapDetectionError(f"Gap detection agent failed (exit {gap_result.exit_code})")

    try:
        gap_data = _parse_json_from_response(gap_result.output)
        gap_report = GapReport.model_validate(gap_data)
    except (json.JSONDecodeError, ValueError) as exc:
        raise GapDetectionError(f"Gap detection agent returned unparseable output: {exc}") from exc

    console.print(
        f"  Found [bold]{len(gap_report.gaps)}[/bold] gaps across {len(gap_report.coverage_areas_checked)} areas"
    )

    # --- Step 2: Critique Agent ---
    console.print()
    console.print("[bold]Step 2b.2:[/bold] Critiquing gap report...")
    gap_report_json = gap_report.model_dump_json(indent=2)

    critique_prompt = _build_critique_prompt(epic_md, context_md, gap_report_json)
    if config and "critique_plan" in config.budgets:
        critique_budget = config.budgets["critique_plan"]
        critique_max_turns = critique_budget.max_turns
        critique_max_budget = critique_budget.max_budget_usd
    else:
        critique_defaults = BUDGET_DEFAULTS["critique_plan"]
        critique_max_turns = int(critique_defaults["max_turns"])
        critique_max_budget = float(critique_defaults["max_budget_usd"])

    critique_result = dispatch_agent(
        prompt=critique_prompt,
        model=critique_model,
        tools=get_tools_for_role("critique"),
        max_turns=critique_max_turns,
        max_budget_usd=critique_max_budget,
        no_mcp=True,
    )

    if not critique_result.success:
        raise GapDetectionError(f"Critique agent failed (exit {critique_result.exit_code})")

    event_logger.log_event(
        "gap_critique_complete",
        epic=epic_number,
        critique_model=critique_model,
        findings_count=len(gap_report.gaps),
    )

    # --- Step 3: Display exchange to user ---
    console.print()
    console.print(Panel(critique_result.output, title="Critique", border_style="yellow"))
    console.print()

    # Let user review the exchange and add feedback
    user_feedback = typer.prompt(
        "Review the gaps and critique above. Press Enter to proceed to Q&A, or type feedback",
        default="",
    )
    if user_feedback:
        logger.info("User feedback on gap report: %s", user_feedback)

    # --- Step 4: Interactive Q&A ---
    console.print()
    console.print("[bold]Step 2b.3:[/bold] Interactive Q&A")
    event_logger.log_event(
        "gap_questions_presented",
        epic=epic_number,
        question_count=len(gap_report.gaps),
    )

    answers = _ask_gap_questions(gap_report.gaps)

    for answer in answers:
        event_logger.log_event(
            "gap_answer_received",
            epic=epic_number,
            question_id=answer.gap_id,
            answer=answer.answer,
        )

    # --- Step 5: Sufficiency confirmation ---
    console.print()
    console.print("[bold]Step 2b.4:[/bold] Sufficiency check")
    console.print()
    console.print("[bold]Coverage areas checked:[/bold]")
    for area in gap_report.coverage_areas_checked:
        console.print(f"  - {area}")
    console.print()

    sufficiency = typer.confirm("Are all gaps resolved and scope decisions locked?", default=True)

    # --- Step 6: Write user-decisions.json ---
    decisions = UserDecisions(
        epic_number=epic_number,
        answers=answers,
        sufficiency_confirmed=sufficiency,
    )

    output_path = epic_dir / "user-decisions.json"
    output_path.write_text(decisions.model_dump_json(indent=2) + "\n", encoding="utf-8")

    event_logger.log_event(
        "gap_detection_complete",
        epic=epic_number,
        decisions_count=len(answers),
        sufficiency=sufficiency,
    )

    console.print(f"  [green]Written:[/green] {output_path.name}")
    return output_path
