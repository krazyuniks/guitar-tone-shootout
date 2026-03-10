"""Epic workflow HTML report generator.

Reads JSONL event logs, prompt files, and conversation transcripts from
an epic directory and renders a self-contained HTML timeline report.

Usage:
    python -m workflow.report 120        # Generate report for epic #120
    just epic-report 120                 # Same via just

Output: .planning/epics/E{N}/REPORT.html
"""

from __future__ import annotations

import html
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from workflow.artifacts import (
    CheckpointRunArtifact,
    CritiqueFindingArtifact,
    CritiqueRunArtifact,
    CurationCompleteArtifact,
    CurationDispatchedArtifact,
    CurationFailedArtifact,
    PhaseAValidationEventArtifact,
    PhaseBVerificationEventArtifact,
    PlannerCompleteArtifact,
    PlannerDispatchedArtifact,
    PlannerFailedArtifact,
    PlanDecisionArtifact,
    PreflightEventArtifact,
    StoryFailureContextArtifact,
    StoryRunArtifact,
    VerifierFeedbackArtifact,
)
from workflow.jsonl_logger import read_log

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PLANNING_DIR = PROJECT_ROOT / ".planning" / "epics"
LOGS_DIR = PROJECT_ROOT / ".planning" / "logs"

# ---------------------------------------------------------------------------
# Strict schema contract: known event types and their expected fields
# ---------------------------------------------------------------------------
# Each entry maps event_type -> list of field names the report understands.
# Universal fields (schema_v, run_id, ts, event) are always present.
# Events not in this dict are rendered as raw JSON.

KNOWN_EVENTS: dict[str, list[str]] = {
    "gap_detection_started": ["epic", "model"],
    "gap_critique_complete": ["locked_count", "escalated_count", "demoted_count"],
    "gap_questions_presented": ["question_count"],
    "gap_detection_complete": ["epic"],
    "curation_dispatched": ["epic", "attempt", "model", "adapter", "prompt_hash", "prompt_tokens"],
    "curation_complete": ["epic", "attempt", "turns", "response_path"],
    "curation_failed": ["epic", "attempt", "error", "turns", "response_path"],
    "planner_dispatched": ["epic", "attempt", "model", "adapter", "prompt_hash", "prompt_tokens"],
    "planner_complete": ["epic", "attempt", "turns", "response_path"],
    "planner_failed": ["epic", "attempt", "error", "turns", "response_path"],
    "phase_a_pass": ["epic", "attempt"],
    "phase_a_fail": ["epic", "attempt", "failures"],
    "phase_b_pass": ["epic", "attempt", "scores", "feedback"],
    "phase_b_fail": ["epic", "attempt", "scores", "feedback"],
    "phase_c_pass": ["epic", "attempt"],
    "phase_c_fail": ["epic", "attempt"],
    "plan_approved": ["epic"],
    "plan_revised": ["epic"],
    "plan_rejected": ["epic", "reason", "details", "feedback"],
    "plan_committed": ["epic", "commit"],
    "tests_approved": ["epic"],
    "tests_generated": ["epic", "stories_count"],
    "test_gen_started": ["story_id"],
    "test_gen_attempt": ["story_id", "attempt", "test_file_path", "error"],
    "test_review_pass": ["story_id", "test_file_path"],
    "test_review_fail": ["story_id", "attempt", "reviewer_feedback"],
    "epic_started": ["epic", "run_id", "stories_total"],
    "story_started": ["story_id", "attempt", "index"],
    "preflight_pass": ["story_id", "attempt", "note", "checks"],
    "preflight_fail": [
        "story_id",
        "attempt",
        "failure_category",
        "description",
        "reason",
        "checks",
    ],
    "agent_dispatched": ["story_id", "attempt", "model", "adapter", "prompt_hash", "prompt_tokens"],
    "agent_complete": ["story_id", "attempt", "commit", "turns"],
    "agent_failed": ["story_id", "attempt", "error", "turns"],
    "validation_pass": ["story_id", "attempt", "check_type", "results"],
    "validation_fail": [
        "story_id",
        "attempt",
        "check_type",
        "results",
        "failure_reason",
        "failure_category",
    ],
    "critique_dispatched": [
        "story_id",
        "attempt",
        "critique_type",
        "critique_model",
        "target_model",
        "adapter",
        "role",
        "prompt_hash",
        "prompt_tokens",
    ],
    "critique_pass": [
        "story_id",
        "attempt",
        "critique_type",
        "critique_model",
        "turns",
        "findings_count",
        "summary",
        "raw_response",
    ],
    "critique_fail": [
        "story_id",
        "attempt",
        "critique_type",
        "critique_model",
        "turns",
        "findings_count",
        "findings",
        "summary",
        "raw_response",
    ],
    "critique_failed": [
        "story_id",
        "attempt",
        "critique_type",
        "critique_model",
        "turns",
        "findings_count",
        "findings",
        "summary",
        "raw_response",
        "error",
    ],
    "critique_skipped": ["story_id", "attempt", "critique_type", "critique_model", "reason"],
    "epic_critique_dispatched": [
        "critique_type",
        "critique_model",
        "adapter",
        "role",
        "prompt_hash",
        "prompt_tokens",
    ],
    "epic_critique_pass": [
        "critique_type",
        "critique_model",
        "turns",
        "findings_count",
        "summary",
        "raw_response",
    ],
    "epic_critique_fail": [
        "critique_type",
        "critique_model",
        "turns",
        "findings_count",
        "findings",
        "summary",
        "raw_response",
        "error",
    ],
    "story_complete": ["story_id", "attempt", "commit"],
    "story_failed": ["story_id", "attempt", "reason", "failure_category"],
    "exit_to_human": ["story_id", "reason", "failure_category", "context"],
    "github_comment": ["epic", "comment_url"],
    "epic_complete": ["epic", "stories_completed"],
    "epic_failed": ["epic", "reason"],
}

# Universal fields present on every event — excluded from details display.
UNIVERSAL_FIELDS = {"schema_v", "run_id", "ts", "event", "_source"}


# ---------------------------------------------------------------------------
# Data collection
# ---------------------------------------------------------------------------


def collect_all_events(epic_dir: Path) -> list[dict]:
    """Merge epic.jsonl + all story.jsonl files into one sorted timeline."""
    events: list[dict] = []

    epic_log = epic_dir / "epic.jsonl"
    for e in read_log(epic_log):
        e["_source"] = "epic"
        events.append(e)

    stories_dir = epic_dir / "stories"
    if stories_dir.is_dir():
        for story_dir in sorted(stories_dir.iterdir()):
            if not story_dir.is_dir():
                continue
            story_log = story_dir / "story.jsonl"
            for e in read_log(story_log):
                e["_source"] = f"story:{story_dir.name}"
                events.append(e)

    events.sort(key=lambda e: e.get("ts", ""))

    # Deduplicate events that appear in both epic.jsonl and story.jsonl.
    # The orchestrator logs story_complete/story_failed to both logs.
    # Use (ts, event, story_id) as dedup key; prefer story-level source.
    seen: set[tuple[str, str, str]] = set()
    deduped: list[dict] = []
    for e in events:
        key = (e.get("ts", ""), e.get("event", ""), e.get("story_id", ""))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(e)

    return deduped


def match_prompt_file(epic_dir: Path, prompt_hash: str) -> str | None:
    if not prompt_hash:
        return None
    prompt_path = epic_dir / "dispatches" / f"{prompt_hash}-prompt.txt"
    if prompt_path.exists():
        return prompt_path.read_text(encoding="utf-8")
    if LOGS_DIR.is_dir():
        for legacy_path in LOGS_DIR.glob(f"dispatch-*-{prompt_hash}-*.txt"):
            return legacy_path.read_text(encoding="utf-8")
    return None


def find_story_prompt(epic_dir: Path, story_id: str, attempt: int) -> str | None:
    prompt_path = epic_dir / "stories" / story_id / f"prompt-attempt-{attempt}.md"
    if prompt_path.exists():
        return prompt_path.read_text(encoding="utf-8")
    return None


def find_conversation_log(epic_dir: Path, story_id: str, attempt: int) -> list[dict]:
    conv_path = epic_dir / "stories" / story_id / f"dispatch-{attempt}.jsonl"
    return read_log(conv_path)


def compute_duration(
    events: list[dict], start_event: str, end_event: str, story_id: str | None = None
) -> str | None:
    start_ts = None
    end_ts = None
    for e in events:
        if story_id and e.get("story_id") != story_id:
            continue
        if e.get("event") == start_event and start_ts is None:
            start_ts = e.get("ts")
        if e.get("event") == end_event:
            end_ts = e.get("ts")

    if not start_ts or not end_ts:
        return None
    try:
        t0 = datetime.fromisoformat(start_ts)
        t1 = datetime.fromisoformat(end_ts)
        delta = t1 - t0
        total_seconds = int(delta.total_seconds())
        if total_seconds < 0:
            return None
        minutes, seconds = divmod(total_seconds, 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f"{hours}h {minutes}m {seconds}s"
        if minutes:
            return f"{minutes}m {seconds}s"
        return f"{seconds}s"
    except (ValueError, TypeError):
        return None


def _build_story_runs(events: list[dict], plan: dict | None = None) -> dict[str, StoryRunArtifact]:
    story_ids: list[str] = []
    seen: set[str] = set()

    if plan:
        for story in plan.get("stories", []):
            story_id = story.get("story_id")
            if story_id and story_id not in seen:
                seen.add(story_id)
                story_ids.append(story_id)

    for event in events:
        story_id = event.get("story_id")
        if story_id and story_id not in seen:
            seen.add(story_id)
            story_ids.append(story_id)

    return {story_id: StoryRunArtifact.from_events(events, story_id) for story_id in story_ids}


# ---------------------------------------------------------------------------
# HTML helpers
# ---------------------------------------------------------------------------


def _esc(text: str) -> str:
    return html.escape(str(text))


def _format_ts(ts_str: str) -> str:
    """Format timestamp as HH:MM:SS for table display."""
    try:
        dt = datetime.fromisoformat(ts_str)
        return dt.strftime("%H:%M:%S")
    except (ValueError, TypeError):
        return str(ts_str)[:19]


def _format_ts_full(ts_str: str) -> str:
    try:
        dt = datetime.fromisoformat(ts_str)
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    except (ValueError, TypeError):
        return str(ts_str)


def _human_label(event_type: str) -> str:
    """Return a plain text label for the event type. No colour-coding."""
    labels = {
        "gap_detection_started": "Gap Detection Started",
        "gap_critique_complete": "Gap Critique Complete",
        "gap_questions_presented": "Gap Questions",
        "gap_detection_complete": "Gap Detection Complete",
        "curation_dispatched": "Curation Dispatched",
        "curation_complete": "Curation Complete",
        "curation_failed": "Curation FAIL",
        "planner_dispatched": "Planner Dispatched",
        "planner_complete": "Plan Generated",
        "planner_failed": "Planner FAIL",
        "phase_a_pass": "Phase A (Deterministic) PASS",
        "phase_a_fail": "Phase A (Deterministic) FAIL",
        "phase_b_pass": "Phase B (Adversarial) PASS",
        "phase_b_fail": "Phase B (Adversarial) FAIL",
        "phase_c_pass": "Phase C PASS",
        "phase_c_fail": "Phase C FAIL",
        "plan_approved": "Plan Approved",
        "plan_revised": "Plan Revised",
        "plan_rejected": "Plan Rejected",
        "plan_committed": "Plan Committed",
        "tests_approved": "Tests Approved",
        "tests_generated": "Tests Generated",
        "test_gen_started": "Test Gen Started",
        "test_gen_attempt": "Test Gen Attempt",
        "test_review_pass": "Test Review PASS",
        "test_review_fail": "Test Review FAIL",
        "epic_started": "Epic Started",
        "story_started": "Story Started",
        "preflight_pass": "Preflight PASS",
        "preflight_fail": "Preflight FAIL",
        "agent_dispatched": "Agent Dispatched",
        "agent_complete": "Agent Complete",
        "agent_failed": "Agent FAIL",
        "validation_pass": "Validation PASS",
        "validation_fail": "Validation FAIL",
        "critique_dispatched": "Story Critique Dispatched",
        "critique_pass": "Story Critique PASS",
        "critique_fail": "Story Critique FAIL",
        "critique_failed": "Story Critique FAIL",
        "critique_skipped": "Story Critique Skipped",
        "epic_critique_dispatched": "Epic Critique Dispatched",
        "epic_critique_pass": "Epic Critique PASS",
        "epic_critique_fail": "Epic Critique FAIL",
        "story_complete": "Story Complete",
        "story_failed": "Story FAIL",
        "exit_to_human": "Exit to Human",
        "github_comment": "GitHub Comment",
        "epic_complete": "Epic Complete",
        "epic_failed": "Epic FAIL",
    }
    return labels.get(event_type, event_type.replace("_", " ").title())


def _render_collapsible(summary: str, content: str) -> str:
    """Render a <details> block for large content."""
    return (
        f'<details><summary style="cursor:pointer;color:#93c5fd;font-size:13px;">'
        f"{_esc(summary)}</summary>"
        f'<pre style="white-space:pre-wrap;word-break:break-word;font-size:12px;'
        f"color:#cbd5e1;background:#0f172a;padding:8px;border-radius:4px;"
        f'margin:4px 0;max-height:30em;overflow-y:auto;line-height:1.4;">'
        f"{_esc(content)}</pre></details>"
    )


def _render_findings(findings: list[CritiqueFindingArtifact] | list) -> str:
    """Render critique findings as a simple list."""
    if not findings:
        return ""
    parts = []
    for f in findings:
        finding = f if isinstance(f, CritiqueFindingArtifact) else None
        if finding is None and isinstance(f, dict):
            try:
                finding = CritiqueFindingArtifact.from_dict(f)
            except (TypeError, ValueError):
                finding = None

        if finding is not None:
            line = f"[{(finding.severity or '?').upper()}] {finding.summary_text}"
            parts.append(
                f'<div style="font-size:12px;color:#cbd5e1;padding:2px 0;">{_esc(line)}</div>'
            )
            continue

        parts.append(
            f'<div style="font-size:12px;color:#cbd5e1;padding:2px 0;">{_esc(str(f))}</div>'
        )
    return "".join(parts)


# ---------------------------------------------------------------------------
# Event details rendering
# ---------------------------------------------------------------------------


def _render_event_details(
    event: dict,
    epic_dir: Path,
    *,
    story_run: StoryRunArtifact | None = None,
) -> str:
    """Render the details column for a single event row.

    Returns HTML content for the details cell. Large content (prompts,
    responses, critique feedback) goes into collapsible <details> blocks.
    """
    parts: list[str] = []
    event_type = event.get("event", "")
    story_id = event.get("story_id")
    attempt = event.get("attempt")
    is_known = event_type in KNOWN_EVENTS

    if not is_known:
        # Unknown event — show all non-universal fields as raw JSON
        extra = {k: v for k, v in event.items() if k not in UNIVERSAL_FIELDS}
        if extra:
            parts.append(
                _render_collapsible("Raw event data", json.dumps(extra, indent=2, default=str))
            )
        return "".join(parts)

    # -- Inline metadata for specific events --

    if event_type == "gap_detection_started":
        model = event.get("model", "?")
        parts.append(f'<span style="color:#94a3b8;">Model: {_esc(model)}</span>')

    elif event_type == "gap_critique_complete":
        parts.append(
            f'<span style="color:#94a3b8;">'
            f"{event.get('locked_count', '?')} locked, "
            f"{event.get('escalated_count', 0)} escalated, "
            f"{event.get('demoted_count', 0)} demoted</span>"
        )

    elif event_type == "gap_questions_presented":
        count = event.get("question_count", 0)
        parts.append(f'<span style="color:#94a3b8;">{count} questions</span>')

    elif event_type in ("curation_dispatched", "planner_dispatched"):
        dispatch = None
        if event_type == "curation_dispatched":
            try:
                dispatch = CurationDispatchedArtifact.from_event(event)
            except (KeyError, TypeError, ValueError):
                dispatch = None
        else:
            try:
                dispatch = PlannerDispatchedArtifact.from_event(event)
            except (KeyError, TypeError, ValueError):
                dispatch = None

        model = (
            dispatch.model
            if dispatch is not None
            else event.get("model") or event.get("planner_model", "?")
        )
        tokens = (
            dispatch.prompt_tokens
            if dispatch is not None and dispatch.prompt_tokens is not None
            else event.get("prompt_tokens", "?")
        )
        parts.append(
            f'<span style="color:#94a3b8;">model={_esc(str(model))}, ~{tokens} tokens</span>'
        )

        prompt_text = None
        if story_id and attempt:
            prompt_text = find_story_prompt(epic_dir, story_id, attempt)
        if not prompt_text:
            prompt_hash = dispatch.prompt_hash if dispatch is not None else event.get("prompt_hash")
            if prompt_hash:
                prompt_text = match_prompt_file(epic_dir, prompt_hash)
        if prompt_text:
            parts.append(_render_collapsible("Show prompt", prompt_text))

    elif event_type in ("curation_complete", "curation_failed", "planner_complete", "planner_failed"):
        result_artifact = None
        try:
            if event_type == "curation_complete":
                result_artifact = CurationCompleteArtifact.from_event(event)
            elif event_type == "curation_failed":
                result_artifact = CurationFailedArtifact.from_event(event)
            elif event_type == "planner_complete":
                result_artifact = PlannerCompleteArtifact.from_event(event)
            else:
                result_artifact = PlannerFailedArtifact.from_event(event)
        except (KeyError, TypeError, ValueError):
            result_artifact = None

        meta: list[str] = []
        if result_artifact is not None:
            if result_artifact.response_path:
                meta.append(result_artifact.response_path)
            if result_artifact.turns is not None:
                meta.append(f"turns={result_artifact.turns}")
            error = getattr(result_artifact, "error", "")
            if error:
                meta.append(f"error: {str(error)[:200]}")
        else:
            response_path = event.get("response_path", "")
            turns = event.get("turns")
            if response_path:
                meta.append(str(response_path))
            if turns is not None:
                meta.append(f"turns={turns}")
            if event_type in ("curation_failed", "planner_failed"):
                error = event.get("error", "")
                if error:
                    meta.append(f"error: {error[:200]}")
        if meta:
            parts.append(f'<span style="color:#94a3b8;">{_esc(", ".join(meta))}</span>')

    elif event_type in ("agent_dispatched", "critique_dispatched", "epic_critique_dispatched"):
        model = event.get("model") or event.get("critique_model", "?")
        tokens = event.get("prompt_tokens", "?")
        parts.append(
            f'<span style="color:#94a3b8;">model={_esc(str(model))}, ~{tokens} tokens</span>'
        )

        prompt_text = None
        if story_id and attempt:
            prompt_text = find_story_prompt(epic_dir, story_id, attempt)
        if not prompt_text:
            prompt_hash = event.get("prompt_hash")
            if prompt_hash:
                prompt_text = match_prompt_file(epic_dir, prompt_hash)
        if prompt_text:
            parts.append(_render_collapsible("Show prompt", prompt_text))

    elif event_type in ("agent_complete", "agent_failed"):
        commit = event.get("commit", "")
        turns = event.get("turns", "")
        meta = []
        if turns:
            meta.append(f"turns={turns}")
        if commit:
            meta.append(f"commit={commit[:8]}")
        if event_type == "agent_failed":
            error = event.get("error", "")
            if error:
                meta.append(f"error: {error[:200]}")
        if meta:
            parts.append(f'<span style="color:#94a3b8;">{_esc(", ".join(meta))}</span>')

        # Show agent response from conversation log
        if story_id and attempt:
            conv_events = find_conversation_log(epic_dir, story_id, attempt)
            for ce in conv_events:
                payload = ce.get("payload", {})
                if isinstance(payload, dict) and payload.get("type") == "result":
                    result_text = payload.get("result", "")
                    if result_text:
                        parts.append(_render_collapsible("Show agent response", result_text))
                    # Cost/usage
                    cost = payload.get("total_cost_usd")
                    num_turns = payload.get("num_turns")
                    duration_ms = payload.get("duration_ms")
                    usage = payload.get("usage", {})
                    cost_parts = []
                    if cost:
                        cost_parts.append(f"${cost:.2f}")
                    if num_turns:
                        cost_parts.append(f"{num_turns} turns")
                    if duration_ms:
                        mins = duration_ms // 60000
                        secs = (duration_ms % 60000) // 1000
                        cost_parts.append(f"{mins}m {secs}s")
                    if usage.get("output_tokens"):
                        cost_parts.append(f"{usage['output_tokens']:,} output tokens")
                    if cost_parts:
                        parts.append(
                            f'<span style="color:#64748b;font-size:11px;">{_esc(" | ".join(cost_parts))}</span>'
                        )
                    break

    elif event_type in ("story_complete", "story_failed"):
        meta = []
        commit = event.get("commit", "")
        attempt_val = event.get("attempt", "")
        if attempt_val:
            meta.append(f"attempt {attempt_val}")
        if commit:
            meta.append(f"commit {commit[:8]}")
        if event_type == "story_failed":
            category = story_run.failure_category if story_run is not None else event.get(
                "failure_category", ""
            )
            if category:
                meta.append(f"[{category}]")
            reason = story_run.failure_reason if story_run is not None else event.get("reason", "")
            if reason:
                meta.append(f"reason: {reason[:200]}")
        if meta:
            parts.append(f'<span style="color:#94a3b8;">{_esc(", ".join(meta))}</span>')

    elif event_type == "plan_committed":
        commit = event.get("commit", "")
        if commit:
            parts.append(f'<span style="color:#94a3b8;">commit {_esc(commit[:8])}</span>')

    elif event_type == "plan_rejected":
        try:
            rejection = PlanDecisionArtifact.from_event(event)
        except (KeyError, TypeError, ValueError):
            rejection = None

        if rejection is not None:
            if rejection.summary_text:
                parts.append(f'<span style="color:#94a3b8;">{_esc(rejection.summary_text[:300])}</span>')
            if rejection.detail_payload is not None:
                parts.append(_render_collapsible("Show rejection details", rejection.detail_json_text))
        else:
            reason = event.get("reason", "")
            if reason:
                parts.append(f'<span style="color:#94a3b8;">{_esc(reason[:300])}</span>')
            details = event.get("details") or event.get("feedback")
            if details:
                parts.append(
                    _render_collapsible(
                        "Show rejection details",
                        json.dumps(details, indent=2, default=str)
                        if not isinstance(details, str)
                        else details,
                    )
                )

    elif event_type in ("preflight_pass", "preflight_fail"):
        try:
            preflight_event = PreflightEventArtifact.from_event(event)
        except (KeyError, TypeError, ValueError):
            preflight_event = None

        if preflight_event is not None:
            if preflight_event.summary_text:
                parts.append(
                    f'<span style="color:#94a3b8;">{_esc(preflight_event.summary_text[:300])}</span>'
                )
            if preflight_event.checks:
                parts.append(
                    _render_collapsible(
                        "Show checks",
                        json.dumps(preflight_event.checks_payload, indent=2, default=str),
                    )
                )
        else:
            note = event.get("note") or event.get("description") or event.get("reason", "")
            if note:
                parts.append(f'<span style="color:#94a3b8;">{_esc(str(note)[:300])}</span>')
            checks = event.get("checks", [])
            if checks:
                parts.append(
                    _render_collapsible("Show checks", json.dumps(checks, indent=2, default=str))
                )

    elif event_type in ("phase_b_pass", "phase_b_fail"):
        try:
            phase_b_event = PhaseBVerificationEventArtifact.from_event(event)
        except (KeyError, TypeError, ValueError):
            phase_b_event = None

        if phase_b_event is not None:
            if phase_b_event.summary_text:
                parts.append(
                    f'<span style="color:#94a3b8;">{_esc(phase_b_event.summary_text[:300])}</span>'
                )
            parts.append(
                _render_collapsible("Show critique feedback", phase_b_event.detail_json_text)
            )
        else:
            feedback = event.get("feedback")
            if feedback:
                if isinstance(feedback, str):
                    try:
                        feedback = json.loads(feedback)
                    except (json.JSONDecodeError, ValueError):
                        pass
                if isinstance(feedback, dict):
                    try:
                        typed_feedback = VerifierFeedbackArtifact.from_dict(feedback)
                    except TypeError:
                        typed_feedback = None
                    if typed_feedback is not None:
                        parts.append(
                            _render_collapsible("Show critique feedback", typed_feedback.json_text)
                        )
                    else:
                        parts.append(
                            _render_collapsible(
                                "Show critique feedback", json.dumps(feedback, indent=2, default=str)
                            )
                        )
                elif isinstance(feedback, list):
                    parts.append(
                        _render_collapsible(
                            "Show critique feedback", json.dumps(feedback, indent=2, default=str)
                        )
                    )
                elif isinstance(feedback, str) and feedback.strip():
                    parts.append(_render_collapsible("Show critique feedback", feedback))

    elif event_type in ("phase_a_pass", "phase_a_fail"):
        try:
            phase_a_event = PhaseAValidationEventArtifact.from_event(event)
        except (KeyError, TypeError, ValueError):
            phase_a_event = None

        if phase_a_event is not None:
            if phase_a_event.summary_text:
                parts.append(
                    f'<span style="color:#94a3b8;">{_esc(phase_a_event.summary_text[:300])}</span>'
                )
            if phase_a_event.failures:
                parts.append(
                    _render_collapsible(
                        "Show failures",
                        json.dumps(phase_a_event.failures_payload, indent=2, default=str),
                    )
                )
        else:
            failures = event.get("failures", [])
            if failures:
                parts.append(
                    _render_collapsible("Show failures", json.dumps(failures, indent=2, default=str))
                )

    elif event_type in ("validation_pass", "validation_fail"):
        checkpoint: CheckpointRunArtifact | None = None
        try:
            checkpoint = CheckpointRunArtifact.from_event(event)
        except (KeyError, TypeError, ValueError):
            checkpoint = None

        if checkpoint is not None:
            if checkpoint.failure_reason:
                parts.append(
                    f'<span style="color:#94a3b8;">{_esc(checkpoint.failure_reason[:200])}</span>'
                )
            if checkpoint.results:
                parts.append(
                    _render_collapsible(
                        "Show results",
                        json.dumps(
                            [result.to_dict() for result in checkpoint.results],
                            indent=2,
                            default=str,
                        ),
                    )
                )
        else:
            results = event.get("results", [])
            reason = event.get("failure_reason", event.get("reason", ""))
            if reason:
                parts.append(f'<span style="color:#94a3b8;">{_esc(str(reason)[:200])}</span>')
            if results:
                parts.append(
                    _render_collapsible("Show results", json.dumps(results, indent=2, default=str))
                )

    elif event_type == "exit_to_human":
        reason = story_run.failure_reason if story_run is not None else event.get("reason", "")
        category = story_run.failure_category if story_run is not None else event.get(
            "failure_category", ""
        )
        if reason:
            parts.append(f'<span style="color:#94a3b8;">{_esc(str(reason)[:300])}</span>')
        if category:
            parts.append(f'<span style="color:#94a3b8;"> [{_esc(str(category))}]</span>')

        failure_context = story_run.failure_context if story_run is not None else None
        if failure_context is None:
            raw_context = event.get("context")
            if isinstance(raw_context, dict):
                try:
                    failure_context = StoryFailureContextArtifact.from_dict(raw_context)
                except (KeyError, TypeError, ValueError):
                    failure_context = None

        context: Any = (
            failure_context.to_dict() if failure_context is not None else event.get("context")
        )
        if context:
            parts.append(
                _render_collapsible("Show context", json.dumps(context, indent=2, default=str))
            )

    elif event_type in (
        "critique_pass",
        "critique_fail",
        "critique_failed",
        "epic_critique_pass",
        "epic_critique_fail",
    ):
        critique_run: CritiqueRunArtifact | None = None
        try:
            critique_run = CritiqueRunArtifact.from_event(event)
        except (KeyError, TypeError, ValueError):
            critique_run = None

        if critique_run is not None:
            model = critique_run.critique_model or "?"
            parts.append(
                f'<span style="color:#94a3b8;">model={_esc(model)}, '
                f'{critique_run.findings_count} findings</span>'
            )
            if critique_run.concise_summary and critique_run.concise_summary != "No findings":
                parts.append(
                    f'<span style="color:#94a3b8;">{_esc(critique_run.concise_summary[:300])}</span>'
                )
            if critique_run.normalized_findings:
                parts.append(_render_findings(list(critique_run.normalized_findings)))
            if critique_run.raw_response:
                parts.append(
                    _render_collapsible("Show raw response", critique_run.raw_response)
                )
            if critique_run.error:
                parts.append(
                    f'<span style="color:#94a3b8;">error: {_esc(critique_run.error[:200])}</span>'
                )
        else:
            model = event.get("critique_model", "?")
            count = event.get("findings_count", 0)
            parts.append(
                f'<span style="color:#94a3b8;">model={_esc(model)}, {count} findings</span>'
            )
            findings = event.get("findings", [])
            if findings:
                parts.append(_render_findings(findings))
            raw_response = event.get("raw_response", "")
            if raw_response:
                parts.append(_render_collapsible("Show raw response", str(raw_response)))
            error = event.get("error", "")
            if error:
                parts.append(f'<span style="color:#94a3b8;">error: {_esc(error[:200])}</span>')

    elif event_type == "critique_skipped":
        reason = event.get("reason", "")
        if reason:
            parts.append(f'<span style="color:#94a3b8;">{_esc(reason[:200])}</span>')

    elif event_type == "github_comment":
        url = event.get("comment_url", "")
        if url:
            parts.append(
                f'<a href="{_esc(url)}" target="_blank" style="color:#93c5fd;font-size:12px;">View on GitHub</a>'
            )

    elif event_type == "epic_complete":
        count = event.get("stories_completed", "?")
        parts.append(f'<span style="color:#94a3b8;">{count} stories completed</span>')

    return " ".join(parts) if len(parts) <= 1 else "<br>".join(parts)


# ---------------------------------------------------------------------------
# HTML structure rendering
# ---------------------------------------------------------------------------


def _render_metadata_header(
    epic_dir: Path,
    events: list[dict],
    plan: dict | None,
    *,
    story_runs: dict[str, StoryRunArtifact] | None = None,
) -> str:
    """Render the metadata summary header at the top of the report."""
    epic_name = epic_dir.name
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")

    run_ids = sorted({e.get("run_id", "?") for e in events})
    first_ts = _format_ts_full(events[0]["ts"]) if events else "N/A"
    last_ts = _format_ts_full(events[-1]["ts"]) if events else "N/A"

    story_runs = _build_story_runs(events, plan) if story_runs is None else story_runs
    story_count = len(plan.get("stories", [])) if plan else len(story_runs)
    completed = len([story_run for story_run in story_runs.values() if story_run.status == "complete"])
    failed = len(
        [
            story_run
            for story_run in story_runs.values()
            if story_run.status in {"failed", "exit_to_human"}
        ]
    )

    has_complete = any(e.get("event") == "epic_complete" for e in events)
    has_failed = any(e.get("event") == "epic_failed" for e in events)
    has_exit = any(e.get("event") == "exit_to_human" for e in events)

    if has_complete:
        status_text = "COMPLETE"
    elif has_failed:
        status_text = "FAILED"
    elif has_exit:
        status_text = "EXIT TO HUMAN"
    else:
        status_text = "IN PROGRESS"

    duration = (
        compute_duration(events, "epic_started", "epic_complete")
        or compute_duration(events, events[0].get("event", ""), events[-1].get("event", ""))
        if events
        else "N/A"
    )

    return f"""<div style="background:#1e293b;border:1px solid #334155;border-radius:8px;padding:20px;margin-bottom:16px;">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
        <h1 style="margin:0;font-size:24px;color:#f1f5f9;">Epic {_esc(epic_name)} Report</h1>
        <div style="font-weight:700;font-size:15px;color:#e2e8f0;">{_esc(status_text)}</div>
    </div>
    <table style="width:100%;font-size:13px;color:#cbd5e1;border-collapse:collapse;">
        <tr>
            <td style="padding:3px 16px 3px 0;color:#64748b;">Generated</td><td style="padding:3px 0;">{_esc(now)}</td>
            <td style="padding:3px 16px 3px 24px;color:#64748b;">Duration</td><td style="padding:3px 0;">{_esc(str(duration) if duration else "N/A")}</td>
        </tr>
        <tr>
            <td style="padding:3px 16px 3px 0;color:#64748b;">Started</td><td style="padding:3px 0;">{_esc(first_ts)}</td>
            <td style="padding:3px 16px 3px 24px;color:#64748b;">Last event</td><td style="padding:3px 0;">{_esc(last_ts)}</td>
        </tr>
        <tr>
            <td style="padding:3px 16px 3px 0;color:#64748b;">Stories</td><td style="padding:3px 0;">{completed}/{story_count} complete, {failed} failed</td>
            <td style="padding:3px 16px 3px 24px;color:#64748b;">Events</td><td style="padding:3px 0;">{len(events)}</td>
        </tr>
        <tr>
            <td style="padding:3px 16px 3px 0;color:#64748b;">Runs</td><td style="padding:3px 0;">{len(run_ids)}</td>
            <td></td><td></td>
        </tr>
    </table>
</div>"""


def _render_token_budget_table(epic_dir: Path) -> str:
    """Render an HTML table of token usage per dispatch role."""
    from workflow.dispatch_log import read_dispatch_log

    entries = read_dispatch_log(epic_dir)
    entries = [e for e in entries if e.get("status", "completed") == "completed"]
    if not entries:
        return ""

    # Aggregate by role
    roles: dict[str, dict] = {}
    for entry in entries:
        role = entry.get("role", "unknown")
        if role not in roles:
            roles[role] = {"dispatches": 0, "input_tokens": 0, "output_tokens": 0, "duration_ms": 0}
        agg = roles[role]
        agg["dispatches"] += 1
        agg["input_tokens"] += entry.get("prompt_tokens", 0)
        agg["output_tokens"] += entry.get("response_tokens", 0)
        agg["duration_ms"] += entry.get("duration_ms", 0)

    rows = ""
    total_d, total_i, total_o, total_dur = 0, 0, 0, 0
    for role, agg in sorted(roles.items()):
        dur_s = agg["duration_ms"] / 1000
        rows += (
            f"<tr><td style='padding:4px 12px;'>{_esc(role)}</td>"
            f"<td style='padding:4px 12px;text-align:right;'>{agg['dispatches']:,}</td>"
            f"<td style='padding:4px 12px;text-align:right;'>{agg['input_tokens']:,}</td>"
            f"<td style='padding:4px 12px;text-align:right;'>{agg['output_tokens']:,}</td>"
            f"<td style='padding:4px 12px;text-align:right;'>{dur_s:.1f}s</td></tr>\n"
        )
        total_d += agg["dispatches"]
        total_i += agg["input_tokens"]
        total_o += agg["output_tokens"]
        total_dur += agg["duration_ms"]

    total_dur_s = total_dur / 1000
    rows += (
        f"<tr style='border-top:1px solid #475569;font-weight:700;'>"
        f"<td style='padding:4px 12px;'>TOTAL</td>"
        f"<td style='padding:4px 12px;text-align:right;'>{total_d:,}</td>"
        f"<td style='padding:4px 12px;text-align:right;'>{total_i:,}</td>"
        f"<td style='padding:4px 12px;text-align:right;'>{total_o:,}</td>"
        f"<td style='padding:4px 12px;text-align:right;'>{total_dur_s:.1f}s</td></tr>"
    )

    return f"""<div style="background:#1e293b;border:1px solid #334155;border-radius:8px;padding:16px;margin-bottom:16px;">
    <h3 style="margin:0 0 8px 0;font-size:15px;color:#e2e8f0;">Token Budget</h3>
    <table style="width:100%;font-size:13px;color:#cbd5e1;border-collapse:collapse;">
        <tr style="color:#64748b;border-bottom:1px solid #334155;">
            <th style="padding:4px 12px;text-align:left;">Role</th>
            <th style="padding:4px 12px;text-align:right;">Dispatches</th>
            <th style="padding:4px 12px;text-align:right;">Input tokens</th>
            <th style="padding:4px 12px;text-align:right;">Output tokens</th>
            <th style="padding:4px 12px;text-align:right;">Duration</th>
        </tr>
        {rows}
    </table>
</div>"""


def _render_story_nav(
    plan: dict | None,
    events: list[dict],
    *,
    story_runs: dict[str, StoryRunArtifact] | None = None,
) -> str:
    """Render horizontal scrollable story navigation bar."""
    if not plan:
        return ""

    stories = plan.get("stories", [])
    if not stories:
        return ""

    story_runs = _build_story_runs(events, plan) if story_runs is None else story_runs

    items = []
    for i, story in enumerate(stories):
        sid = story.get("story_id", "?")
        name = story.get("name", "?")
        story_run = story_runs.get(sid)
        if story_run is not None and story_run.status == "complete":
            indicator = "DONE"
            indicator_style = "color:#10b981;"
        elif story_run is not None and story_run.status in {"failed", "exit_to_human"}:
            indicator = "FAIL"
            indicator_style = "color:#ef4444;"
        elif story_run is not None and story_run.status in {"running", "tests_running", "tests_passed"}:
            indicator = "WIP"
            indicator_style = "color:#f59e0b;"
        else:
            indicator = "..."
            indicator_style = "color:#64748b;"

        items.append(
            f'<a href="javascript:void(0)" '
            f"onclick=\"document.getElementById('story-{_esc(sid)}').scrollIntoView({{behavior:'smooth'}})\" "
            f'style="flex-shrink:0;display:inline-block;padding:6px 12px;'
            f"background:#1e293b;border:1px solid #334155;border-radius:6px;"
            f'text-decoration:none;font-size:12px;white-space:nowrap;cursor:pointer;">'
            f'<span style="{indicator_style}font-weight:600;">{_esc(indicator)}</span> '
            f'<span style="color:#e2e8f0;">{i + 1}. {_esc(sid)}</span>'
            f'<br><span style="color:#64748b;font-size:11px;">{_esc(name)}</span>'
            f"</a>"
        )

    return f"""<div style="background:#0f172a;border:1px solid #1e293b;border-radius:8px;padding:10px;margin-bottom:16px;
    overflow-x:auto;display:flex;gap:8px;align-items:stretch;">
    {"".join(items)}
</div>"""


def _render_event_table(events: list[dict], epic_dir: Path, plan: dict | None) -> str:
    """Render all events as a single HTML table with story section dividers."""
    rows: list[str] = []
    current_story: str | None = None

    for idx, event in enumerate(events):
        event_type = event.get("event", "unknown")
        story_id = event.get("story_id")
        ts = event.get("ts", "")

        # Insert story divider row when a new story starts
        if event_type == "story_started" and story_id and story_id != current_story:
            current_story = story_id
            story_name = ""
            if plan:
                for s in plan.get("stories", []):
                    if s.get("story_id") == story_id:
                        story_name = s.get("name", "")
                        break
            rows.append(
                f'<tr id="story-{_esc(story_id)}">'
                f'<td colspan="3" style="padding:16px 8px 8px;font-weight:700;font-size:15px;'
                f'color:#c7d2fe;border-bottom:2px solid #4338ca;">'
                f"Story: {_esc(story_id)}"
                f"{f' &mdash; {_esc(story_name)}' if story_name else ''}"
                f"</td></tr>"
            )

        # Build label with story_id and attempt context
        label = _human_label(event_type)
        if story_id and event_type not in ("story_started",):
            # Story context already shown in divider
            pass
        attempt = event.get("attempt")
        if attempt and attempt > 1:
            label += f" (attempt {attempt})"

        story_run = (
            StoryRunArtifact.from_events(events[: idx + 1], story_id) if story_id is not None else None
        )
        details = _render_event_details(event, epic_dir, story_run=story_run)

        rows.append(
            f'<tr style="border-bottom:1px solid #1e293b;vertical-align:top;">'
            f'<td style="padding:6px 8px;font-family:monospace;font-size:12px;color:#64748b;'
            f'white-space:nowrap;width:70px;">{_esc(_format_ts(ts))}</td>'
            f'<td style="padding:6px 8px;font-size:13px;color:#e2e8f0;white-space:nowrap;'
            f'width:200px;">{_esc(label)}</td>'
            f'<td style="padding:6px 8px;font-size:13px;color:#cbd5e1;">{details}</td>'
            f"</tr>"
        )

    return f"""<table style="width:100%;border-collapse:collapse;background:#0f172a;">
    <thead>
        <tr style="border-bottom:2px solid #334155;">
            <th style="padding:8px;text-align:left;font-size:12px;color:#64748b;font-weight:600;">Time</th>
            <th style="padding:8px;text-align:left;font-size:12px;color:#64748b;font-weight:600;">Event</th>
            <th style="padding:8px;text-align:left;font-size:12px;color:#64748b;font-weight:600;">Details</th>
        </tr>
    </thead>
    <tbody>
        {"".join(rows)}
    </tbody>
</table>"""


def render_report(epic_dir: Path) -> str:
    """Render the full HTML report for an epic."""
    plan_path = epic_dir / "plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8")) if plan_path.exists() else None

    events = collect_all_events(epic_dir)
    story_runs = _build_story_runs(events, plan)

    if not events:
        return f"""<!DOCTYPE html><html><body style="background:#0f0f23;color:#e2e8f0;font-family:sans-serif;padding:40px;">
        <h1>Epic {epic_dir.name} Report</h1>
        <p>No events found. The epic has not been started yet.</p>
        </body></html>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Epic {_esc(epic_dir.name)} Report</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0f0f23;
            color: #e2e8f0;
            line-height: 1.6;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            padding: 24px;
        }}
        a {{ color: #93c5fd; }}
        a:hover {{ color: #bfdbfe; }}
        details > summary {{ list-style: none; }}
        details > summary::-webkit-details-marker {{ display: none; }}
        pre {{ tab-size: 2; }}
    </style>
</head>
<body>
    <div class="container">
        {_render_metadata_header(epic_dir, events, plan, story_runs=story_runs)}
        {_render_token_budget_table(epic_dir)}
        {_render_story_nav(plan, events, story_runs=story_runs)}
        {_render_event_table(events, epic_dir, plan)}
    </div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def generate_report(epic_number: int) -> Path:
    epic_dir = PLANNING_DIR / f"E{epic_number}"
    if not epic_dir.is_dir():
        raise FileNotFoundError(f"Epic directory not found: {epic_dir}")

    html_content = render_report(epic_dir)
    output_path = epic_dir / "REPORT.html"
    output_path.write_text(html_content, encoding="utf-8")
    return output_path


def main() -> None:
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m workflow.report <epic_number>")
        sys.exit(1)

    try:
        epic_number = int(sys.argv[1])
    except ValueError:
        print(f"Invalid epic number: {sys.argv[1]}")
        sys.exit(1)

    output = generate_report(epic_number)
    print(f"Report generated: {output}")


if __name__ == "__main__":
    main()
