"""Stage 2b gap detection — scope refinement with locked decisions.

The agent autonomously resolves most gaps by reading the codebase. Only
genuine architectural decisions — where multiple valid approaches exist and
the user's preference matters — are escalated as interactive questions.

Produces user-decisions.json: locked decisions (agent-resolved) + user
answers (escalated). This is the scope contract consumed by the planner.

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
    dispatch_agent,
    extract_json_from_text,
    get_dispatch_params,
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


class LockedDecision(BaseModel):
    """A gap the agent resolved autonomously by reading the codebase."""

    id: str = Field(description="Short unique identifier, e.g. 'decision-imports-1'")
    area: str = Field(description="Architecture area: data_model, api, infrastructure, etc.")
    description: str = Field(description="What the gap was")
    decision: str = Field(description="What the agent decided")
    rationale: str = Field(description="Why — reference to codebase evidence")


class EscalatedQuestion(BaseModel):
    """A genuine architectural decision requiring user input."""

    id: str = Field(description="Short unique identifier, e.g. 'question-bc-1'")
    area: str = Field(description="Architecture area")
    description: str = Field(description="What the gap is — 1-2 sentences")
    question: str = Field(description="The specific question — 1 sentence")
    options: list[str] = Field(
        min_length=2,
        max_length=4,
        description="2-4 concrete options, each 1 sentence max",
    )
    recommendation: int = Field(
        description="1-indexed option number the agent recommends",
    )
    reasoning: str = Field(
        description="Why the agent recommends this option — 1-2 sentences",
    )


class GapReport(BaseModel):
    """Full gap detection report from the agent."""

    locked_decisions: list[LockedDecision] = Field(default_factory=list)
    escalated_questions: list[EscalatedQuestion] = Field(default_factory=list)
    coverage_areas_checked: list[str] = Field(default_factory=list)


class FalseEscalation(BaseModel):
    """A question the critique agent identified as falsely escalated."""

    question_id: str = Field(description="ID of the escalated question to demote")
    reason: str = Field(description="Why this is a false escalation")
    locked_decision: str = Field(description="The decision to auto-resolve to")


class CritiqueReport(BaseModel):
    """Structured output from the critique agent."""

    false_escalations: list[FalseEscalation] = Field(default_factory=list)
    verdict: str = Field(description="'pass' or 'fail'")


class GapAnswer(BaseModel):
    """A resolved gap with the user's answer."""

    gap_id: str
    question: str
    answer: str


class UserDecisions(BaseModel):
    """Schema-validated output artifact for user-decisions.json."""

    epic_number: int
    locked_decisions: list[LockedDecision] = Field(default_factory=list)
    answers: list[GapAnswer] = Field(default_factory=list)
    sufficiency_confirmed: bool = Field(default=False)


# ---------------------------------------------------------------------------
# Critique application
# ---------------------------------------------------------------------------


def apply_critique(gap_report: GapReport, critique: CritiqueReport) -> GapReport:
    """Demote false escalations to locked decisions. Returns a new GapReport."""
    demote_ids = {fe.question_id for fe in critique.false_escalations}
    fe_lookup = {fe.question_id: fe for fe in critique.false_escalations}

    remaining_questions: list[EscalatedQuestion] = []
    new_locked: list[LockedDecision] = list(gap_report.locked_decisions)

    for q in gap_report.escalated_questions:
        if q.id not in demote_ids:
            remaining_questions.append(q)
            continue

        fe = fe_lookup[q.id]
        decision_id = q.id.replace("question-", "decision-", 1)
        new_locked.append(
            LockedDecision(
                id=decision_id,
                area=q.area,
                description=q.description,
                decision=fe.locked_decision,
                rationale=f"Demoted by critique: {fe.reason}",
            )
        )

    # Warn about unmatched question_ids
    matched_ids = {q.id for q in gap_report.escalated_questions}
    for qid in demote_ids - matched_ids:
        logger.warning("Critique referenced unknown question_id '%s' — skipping", qid)

    return GapReport(
        locked_decisions=new_locked,
        escalated_questions=remaining_questions,
        coverage_areas_checked=list(gap_report.coverage_areas_checked),
    )


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------


def _build_gap_detection_prompt(epic_md: str, context_md: str, guide: str) -> str:
    """Build the prompt for the gap detection agent."""
    return f"""\
# Task: Gap Detection for Epic

You are a senior architect analysing an enriched epic against the codebase. \
Your job is to produce a **locked decisions document** — resolving most gaps \
yourself and escalating only genuine architectural decisions to the user.

## Gap Detection Guide

{guide}

## Epic (EPIC.md)

{epic_md}

## Context (CONTEXT.md)

{context_md}

## Instructions

**You are autonomous.** Resolve everything you can by reading the codebase.

### Step 1: Identify all gaps

Compare the epic requirements against the codebase and architecture. Find \
ambiguities, assumptions, contradictions, missing information, BC ownership \
questions, and cross-BC flow gaps.

### Step 2: Auto-resolve mechanical and deterministic gaps

For each gap, ask yourself:
- Can I answer this by reading the codebase? → Auto-resolve.
- Is this a mechanical consequence of the epic? → Auto-resolve.
- Does the codebase have an established pattern? → Follow it, auto-resolve.
- Is there only one reasonable answer? → Auto-resolve.

Record each auto-resolved gap as a locked decision with your rationale.

### Step 3: Escalate questions where the user's answer changes the plan

The filter is **relevance**, not importance level. A question is worth \
escalating — whether architectural or low-level — if:
- You genuinely don't know the answer from reading the codebase, AND
- A different answer from the user would lead to a different plan

If there's really only one reasonable path, auto-resolve it. If the epic \
already specifies the answer, auto-resolve it. But if the user's knowledge \
or preference would change what gets built, escalate it.

For each escalated question:
- Write 2-4 options, each 1 sentence max
- Pick a recommended option (by number, 1-indexed)
- Give 1-2 sentences of reasoning for your recommendation

### Anti-patterns (NEVER do these)

- "Confirm X should happen?" — if the epic says X, auto-resolve it.
- "Should we also update Y?" — mechanical consequence, auto-resolve.
- Asking about every architecture area — only escalate genuine gaps.
- Paragraph-length options — 1 sentence each, max.
- Two questions in one — 1 question per gap, always.
- Vague open-ended questions — propose concrete options.

### Output format

Think through your analysis step by step, then emit JSON inside a \
```json code fence matching this schema:

```json
{{
  "locked_decisions": [
    {{
      "id": "decision-<area>-<n>",
      "area": "<architecture area>",
      "description": "<what the gap was>",
      "decision": "<what you decided>",
      "rationale": "<why — reference codebase evidence>"
    }}
  ],
  "escalated_questions": [
    {{
      "id": "question-<area>-<n>",
      "area": "<architecture area>",
      "description": "<what the gap is — 1-2 sentences>",
      "question": "<the specific question — 1 sentence>",
      "options": ["option 1", "option 2", "option 3"],
      "recommendation": 1,
      "reasoning": "<why you recommend this — 1-2 sentences>"
    }}
  ],
  "coverage_areas_checked": ["bounded_contexts", "data_model", "messaging", ...]
}}
```
"""


def _build_critique_prompt(epic_md: str, context_md: str, gap_report_json: str) -> str:
    """Build the prompt for the gap critique agent."""
    return f"""\
# Task: Critique Gap Detection Report

You are reviewing a gap detection report. Your primary job is to catch \
**false escalations** — questions that should have been auto-resolved by the \
agent instead of escalated to the user.

## Epic (EPIC.md)

{epic_md}

## Context (CONTEXT.md)

{context_md}

## Gap Report to Critique

{gap_report_json}

## Instructions

Review critically. Focus on these failure modes, in priority order:

1. **False escalations**: Is the agent asking the user about something it \
could answer itself by reading the codebase? Mechanical consequences? \
Confirm questions where the answer is obviously "yes"?

2. **Missing locked decisions**: Did the agent skip obvious gaps instead of \
recording them as locked decisions? Every mechanical consequence should be \
documented, not silently assumed.

3. **Badly framed questions**: Are escalated questions vague, leading, or \
answerable from the context? Do options exceed 1 sentence? Is the \
recommendation missing or unjustified? Are there two questions in one?

4. **Missing escalations**: Are there genuine questions — architectural or \
low-level — that the agent missed? If a different answer from the user \
would change the plan, it should be escalated.

5. **Relevance check**: Does each escalated question pass the test: "Would \
a different answer lead to a different plan?" If not, auto-resolve it.

## Output format

Think through your analysis step by step, then emit JSON inside a \
```json code fence matching this schema:

```json
{{
  "false_escalations": [
    {{
      "question_id": "question-area-N",
      "reason": "Why this should have been auto-resolved",
      "locked_decision": "What the decision should be"
    }}
  ],
  "verdict": "pass or fail — pass means no false escalations found"
}}
```

If there are no false escalations, return an empty list and verdict "pass".
"""


# ---------------------------------------------------------------------------
# Interactive Q&A
# ---------------------------------------------------------------------------


def _ask_escalated_questions(questions: list[EscalatedQuestion]) -> list[GapAnswer]:
    """Present escalated questions to the user, collect answers."""
    if not questions:
        console.print("  [dim]No questions to escalate — all gaps auto-resolved.[/dim]")
        return []

    from workflow.cli import flush_stdin

    answers: list[GapAnswer] = []

    for i, q in enumerate(questions, 1):
        console.print()
        console.print(Rule(f" Question {i}/{len(questions)} ", style="bold cyan"))
        console.print()
        console.print(f"  {q.description}")
        console.print()

        for j, option in enumerate(q.options, 1):
            marker = " [green]← recommended[/green]" if j == q.recommendation else ""
            console.print(f"  [bold]{j}.[/bold] {option}{marker}")

        console.print()
        console.print(f"  [dim]Reasoning: {q.reasoning}[/dim]")
        console.print()

        flush_stdin()
        raw = typer.prompt(f"Select option (1-{len(q.options)}) or type a custom answer")

        # Accept number or free text
        answer: str
        if raw.strip().isdigit():
            idx = int(raw.strip())
            answer = q.options[idx - 1] if 1 <= idx <= len(q.options) else raw
        else:
            answer = raw

        answers.append(GapAnswer(gap_id=q.id, question=q.question, answer=answer))

    return answers


# ---------------------------------------------------------------------------
# Core flow
# ---------------------------------------------------------------------------


def _parse_json_from_response(text: str) -> dict:
    """Extract JSON from agent response text."""
    return extract_json_from_text(text)


def run_gap_detection(
    epic_dir: Path,
    event_logger: EventLogger,
    config: EpicConfig | None = None,
) -> Path:
    """Run the full Stage 2b gap detection flow.

    1. Dispatch gap detection agent (auto-resolves + escalates)
    2. Dispatch critique agent (catches false escalations)
    3. Show locked decisions + critique to user
    4. Interactive Q&A for escalated questions only
    5. Write user-decisions.json (locked + answered)

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

    if not GAP_DETECTION_GUIDE.exists():
        raise GapDetectionError(f"Gap detection guide not found at {GAP_DETECTION_GUIDE}")
    guide = GAP_DETECTION_GUIDE.read_text(encoding="utf-8")

    epic_number = int(epic_dir.name.lstrip("E"))

    # Resolve models from config
    gap_model = config.models.planner if config else "opus"
    critique_model = config.models.plan_critic if config else "opus"

    # --- Step 1: Gap Detection Agent ---
    console.print("[bold]Step 2b.1:[/bold] Analysing gaps...")
    event_logger.log_event("gap_detection_started", epic=epic_number, model=gap_model)

    gap_prompt = _build_gap_detection_prompt(epic_md, context_md, guide)
    mcp_servers_gap, timeout_gap = get_dispatch_params("gap_detection", config)
    gap_result = dispatch_agent(
        prompt=gap_prompt,
        model=gap_model,
        mcp_servers=mcp_servers_gap,
        timeout=timeout_gap,
    )

    if not gap_result.success:
        raise GapDetectionError(f"Gap detection agent failed (exit {gap_result.exit_code})")

    try:
        gap_data = _parse_json_from_response(gap_result.output)
        gap_report = GapReport.model_validate(gap_data)
    except (json.JSONDecodeError, ValueError) as exc:
        raise GapDetectionError(f"Gap detection agent returned unparseable output: {exc}") from exc

    n_locked = len(gap_report.locked_decisions)
    n_escalated = len(gap_report.escalated_questions)
    console.print(
        f"  Agent resolved [bold]{n_locked}[/bold] gaps autonomously, "
        f"escalating [bold]{n_escalated}[/bold] for your input"
    )

    # --- Step 2: Critique Agent ---
    console.print()
    console.print("[bold]Step 2b.2:[/bold] Critiquing gap report...")
    gap_report_json = gap_report.model_dump_json(indent=2)

    critique_prompt = _build_critique_prompt(epic_md, context_md, gap_report_json)
    mcp_servers_crit, timeout_crit = get_dispatch_params("critique", config)
    critique_result = dispatch_agent(
        prompt=critique_prompt,
        model=critique_model,
        mcp_servers=mcp_servers_crit,
        timeout=timeout_crit,
    )

    if not critique_result.success:
        raise GapDetectionError(f"Critique agent failed (exit {critique_result.exit_code})")

    # Parse structured critique
    critique_report: CritiqueReport | None
    try:
        critique_data = _parse_json_from_response(critique_result.output)
        critique_report = CritiqueReport.model_validate(critique_data)
    except (json.JSONDecodeError, ValueError):
        logger.warning("Critique returned unstructured output — skipping demotion")
        critique_report = None

    # Apply false escalation demotions
    if critique_report and critique_report.false_escalations:
        gap_report = apply_critique(gap_report, critique_report)
        n_demoted = n_escalated - len(gap_report.escalated_questions)
        n_escalated = len(gap_report.escalated_questions)
        n_locked = len(gap_report.locked_decisions)
        console.print(f"  Critique demoted [bold]{n_demoted}[/bold] false escalation(s)")

    event_logger.log_event(
        "gap_critique_complete",
        epic=epic_number,
        critique_model=critique_model,
        locked_count=n_locked,
        escalated_count=n_escalated,
        demoted_count=len(critique_report.false_escalations) if critique_report else 0,
    )

    # --- Step 3: Display locked decisions + critique ---
    if gap_report.locked_decisions:
        console.print()
        lines = []
        for d in gap_report.locked_decisions:
            lines.append(f"[bold]{d.id}[/bold] ({d.area})")
            lines.append(f"  {d.decision}")
            lines.append(f"  [dim]{d.rationale}[/dim]")
            lines.append("")
        console.print(
            Panel(
                "\n".join(lines).rstrip(),
                title="Locked Decisions (auto-resolved)",
                border_style="green",
            )
        )

    console.print()
    if critique_report:
        critique_lines = []
        if critique_report.false_escalations:
            critique_lines.append(
                f"[bold]False escalations demoted:[/bold] {len(critique_report.false_escalations)}"
            )
            for fe in critique_report.false_escalations:
                critique_lines.append(f"  • {fe.question_id}: {fe.reason}")
        critique_lines.append(f"\n[bold]Verdict:[/bold] {critique_report.verdict}")
        console.print(Panel("\n".join(critique_lines), title="Critique", border_style="yellow"))
    else:
        console.print(Panel(critique_result.output, title="Critique", border_style="yellow"))
    console.print()

    from workflow.cli import flush_stdin

    flush_stdin()
    user_feedback = typer.prompt(
        "Press Enter to proceed to questions, or type feedback",
        default="",
    )
    if user_feedback:
        logger.info("User feedback on gap report: %s", user_feedback)

    # --- Step 4: Interactive Q&A (escalated questions only) ---
    console.print()
    console.print("[bold]Step 2b.3:[/bold] Architectural decisions")
    event_logger.log_event(
        "gap_questions_presented",
        epic=epic_number,
        question_count=n_escalated,
    )

    answers = _ask_escalated_questions(gap_report.escalated_questions)

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

    flush_stdin()
    sufficiency = typer.confirm("Are all gaps resolved and scope decisions locked?", default=True)

    # --- Step 6: Write user-decisions.json ---
    decisions = UserDecisions(
        epic_number=epic_number,
        locked_decisions=gap_report.locked_decisions,
        answers=answers,
        sufficiency_confirmed=sufficiency,
    )

    output_path = epic_dir / "user-decisions.json"
    output_path.write_text(decisions.model_dump_json(indent=2) + "\n", encoding="utf-8")

    event_logger.log_event(
        "gap_detection_complete",
        epic=epic_number,
        locked_count=n_locked,
        decisions_count=len(answers),
        sufficiency=sufficiency,
    )

    console.print(f"  [green]Written:[/green] {output_path.name}")
    return output_path
