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
from datetime import datetime, timezone
from pathlib import Path

from workflow.jsonl_logger import read_log

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PLANNING_DIR = PROJECT_ROOT / ".planning" / "epics"
LOGS_DIR = PROJECT_ROOT / ".planning" / "logs"

# -- Colour palette for event types (bg, border, text) -------------------------

EVENT_COLOURS: dict[str, tuple[str, str, str]] = {
    "gap_detection_started": ("#1e3a5f", "#3b82f6", "#93c5fd"),
    "gap_critique_complete": ("#1e3a5f", "#3b82f6", "#93c5fd"),
    "gap_questions_presented": ("#1e3a5f", "#3b82f6", "#93c5fd"),
    "gap_detection_complete": ("#1e3a5f", "#3b82f6", "#93c5fd"),
    "planner_dispatched": ("#1e3a5f", "#3b82f6", "#93c5fd"),
    "planner_complete": ("#1e3a5f", "#3b82f6", "#93c5fd"),
    "planner_failed": ("#3b1111", "#ef4444", "#fca5a5"),
    "phase_a_pass": ("#0f3d2c", "#10b981", "#6ee7b7"),
    "phase_a_fail": ("#3b1111", "#ef4444", "#fca5a5"),
    "phase_b_pass": ("#0f3d2c", "#10b981", "#6ee7b7"),
    "phase_b_fail": ("#3b1111", "#ef4444", "#fca5a5"),
    "phase_c_pass": ("#0f3d2c", "#10b981", "#6ee7b7"),
    "phase_c_fail": ("#3b1111", "#ef4444", "#fca5a5"),
    "plan_approved": ("#0f3d2c", "#10b981", "#6ee7b7"),
    "plan_revised": ("#3d2e0f", "#f59e0b", "#fcd34d"),
    "plan_rejected": ("#3b1111", "#ef4444", "#fca5a5"),
    "plan_committed": ("#0f3d2c", "#10b981", "#6ee7b7"),
    "epic_started": ("#2e1065", "#8b5cf6", "#c4b5fd"),
    "story_started": ("#1e1b4b", "#6366f1", "#a5b4fc"),
    "preflight_pass": ("#0f3d2c", "#10b981", "#6ee7b7"),
    "preflight_fail": ("#3b1111", "#ef4444", "#fca5a5"),
    "agent_dispatched": ("#1e3a5f", "#3b82f6", "#93c5fd"),
    "agent_complete": ("#0f3d2c", "#10b981", "#6ee7b7"),
    "agent_failed": ("#3b1111", "#ef4444", "#fca5a5"),
    "validation_pass": ("#0f3d2c", "#10b981", "#6ee7b7"),
    "validation_fail": ("#3b1111", "#ef4444", "#fca5a5"),
    "critique_dispatched": ("#2e1065", "#a855f7", "#d8b4fe"),
    "critique_pass": ("#0f3d2c", "#10b981", "#6ee7b7"),
    "critique_fail": ("#3b1111", "#ef4444", "#fca5a5"),
    "critique_failed": ("#3b1111", "#ef4444", "#fca5a5"),
    "critique_skipped": ("#1e293b", "#64748b", "#94a3b8"),
    "epic_critique_dispatched": ("#2e1065", "#a855f7", "#d8b4fe"),
    "epic_critique_pass": ("#0f3d2c", "#10b981", "#6ee7b7"),
    "epic_critique_fail": ("#3b1111", "#ef4444", "#fca5a5"),
    "story_complete": ("#0f3d2c", "#10b981", "#6ee7b7"),
    "story_failed": ("#3b1111", "#ef4444", "#fca5a5"),
    "exit_to_human": ("#3d2e0f", "#f59e0b", "#fcd34d"),
    "github_comment": ("#0f2922", "#34d399", "#a7f3d0"),
    "epic_complete": ("#0f3d2c", "#10b981", "#6ee7b7"),
    "epic_failed": ("#3b1111", "#ef4444", "#fca5a5"),
}

DEFAULT_COLOUR = ("#1e293b", "#64748b", "#94a3b8")

# Max textarea height in em before it becomes scrollable
MAX_TEXTAREA_HEIGHT = 40


# -- Data collection ----------------------------------------------------------


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
    return events


def match_prompt_file(prompt_hash: str) -> str | None:
    if not prompt_hash or not LOGS_DIR.is_dir():
        return None
    for p in LOGS_DIR.glob(f"dispatch-*-{prompt_hash}-*.txt"):
        return p.read_text(encoding="utf-8")
    return None


def find_story_prompt(epic_dir: Path, story_id: str, attempt: int) -> str | None:
    prompt_path = epic_dir / "stories" / story_id / f"prompt-attempt-{attempt}.md"
    if prompt_path.exists():
        return prompt_path.read_text(encoding="utf-8")
    return None


def find_conversation_log(epic_dir: Path, story_id: str, attempt: int) -> list[dict]:
    conv_path = epic_dir / "stories" / story_id / f"dispatch-{attempt}.jsonl"
    return read_log(conv_path)


def compute_duration(events: list[dict], start_event: str, end_event: str, story_id: str | None = None) -> str | None:
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


# -- HTML rendering -----------------------------------------------------------


def _esc(text: str) -> str:
    return html.escape(str(text))


def _render_textarea(content: str, label: str = "") -> str:
    """Render a scrollable readonly textarea sized to content, max half-page."""
    label_html = f'<div style="font-size:13px;color:#a5b4fc;margin-bottom:4px;font-weight:600;">{_esc(label)}</div>' if label else ""
    line_count = content.count("\n") + 1
    # Size to content, cap at MAX_TEXTAREA_HEIGHT
    height_em = min(line_count * 1.5 + 1, MAX_TEXTAREA_HEIGHT)
    return f"""{label_html}<textarea readonly
        style="width:100%;height:{height_em}em;font-family:'JetBrains Mono',Consolas,monospace;font-size:13px;
        background:#0f172a;color:#e2e8f0;border:1px solid #334155;border-radius:6px;
        padding:10px;resize:vertical;tab-size:2;line-height:1.5;"
        >{_esc(content)}</textarea>"""


def _render_table(data: object, label: str = "") -> str:
    """Render structured data as an HTML table. Falls back to textarea for complex nested data."""
    label_html = f'<div style="font-size:13px;color:#a5b4fc;margin-bottom:4px;font-weight:600;">{_esc(label)}</div>' if label else ""

    if isinstance(data, dict):
        rows = []
        for k, v in data.items():
            val = _esc(str(v)) if not isinstance(v, (dict, list)) else f"<pre style='margin:0;white-space:pre-wrap;'>{_esc(json.dumps(v, indent=2, default=str))}</pre>"
            rows.append(
                f'<tr><td style="padding:6px 12px;color:#94a3b8;white-space:nowrap;vertical-align:top;">{_esc(str(k))}</td>'
                f'<td style="padding:6px 12px;color:#e2e8f0;">{val}</td></tr>'
            )
        return f"""{label_html}<table style="width:100%;border-collapse:collapse;background:#0f172a;border-radius:6px;font-size:13px;margin:4px 0;">
            {"".join(rows)}</table>"""

    if isinstance(data, list):
        if not data:
            return ""
        if isinstance(data[0], dict):
            keys = list(data[0].keys())
            header = "".join(f'<th style="padding:6px 12px;color:#94a3b8;text-align:left;border-bottom:1px solid #334155;">{_esc(k)}</th>' for k in keys)
            rows = []
            for item in data:
                cells = "".join(f'<td style="padding:6px 12px;color:#e2e8f0;">{_esc(str(item.get(k, "")))}</td>' for k in keys)
                rows.append(f'<tr>{cells}</tr>')
            return f"""{label_html}<table style="width:100%;border-collapse:collapse;background:#0f172a;border-radius:6px;font-size:13px;margin:4px 0;">
                <thead><tr>{header}</tr></thead><tbody>{"".join(rows)}</tbody></table>"""
        # Simple list
        items = "".join(f'<li style="padding:2px 0;color:#e2e8f0;">{_esc(str(item))}</li>' for item in data)
        return f'{label_html}<ul style="padding-left:20px;margin:4px 0;font-size:13px;">{items}</ul>'

    # Fallback for other types
    return _render_textarea(json.dumps(data, indent=2, default=str), label=label)


def _format_ts(ts_str: str) -> str:
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
    labels = {
        "gap_detection_started": "Gap Detection Started",
        "gap_critique_complete": "Gap Critique Complete",
        "gap_questions_presented": "Gap Questions",
        "gap_detection_complete": "Gap Detection Complete",
        "planner_dispatched": "Planner Dispatched",
        "planner_complete": "Plan Generated",
        "planner_failed": "Planner Failed",
        "phase_a_pass": "Phase A (Deterministic) — PASS",
        "phase_a_fail": "Phase A (Deterministic) — FAIL",
        "phase_b_pass": "Phase B (Adversarial Critique) — PASS",
        "phase_b_fail": "Phase B (Adversarial Critique) — FAIL",
        "phase_c_pass": "Phase C — PASS",
        "phase_c_fail": "Phase C — FAIL",
        "plan_approved": "Plan Approved",
        "plan_revised": "Plan Revised",
        "plan_rejected": "Plan Rejected",
        "plan_committed": "Plan Committed",
        "epic_started": "Epic Execution Started",
        "story_started": "Story Started",
        "preflight_pass": "Preflight — PASS",
        "preflight_fail": "Preflight — FAIL",
        "agent_dispatched": "Agent Dispatched",
        "agent_complete": "Agent Complete",
        "agent_failed": "Agent Failed",
        "validation_pass": "Validation — PASS",
        "validation_fail": "Validation — FAIL",
        "critique_dispatched": "Story Critique Dispatched",
        "critique_pass": "Story Critique — PASS",
        "critique_fail": "Story Critique — FAIL",
        "critique_failed": "Story Critique — FAIL",
        "critique_skipped": "Story Critique — Skipped",
        "epic_critique_dispatched": "Epic Critique Dispatched",
        "epic_critique_pass": "Epic Critique — PASS",
        "epic_critique_fail": "Epic Critique — FAIL",
        "story_complete": "Story Complete",
        "story_failed": "Story Failed",
        "exit_to_human": "Exit to Human",
        "github_comment": "GitHub Comment",
        "epic_complete": "Epic Complete",
        "epic_failed": "Epic Failed",
    }
    return labels.get(event_type, event_type.replace("_", " ").title())


def _render_event_content(event: dict, epic_dir: Path) -> str:
    """Render all content for an event — always visible, no toggles."""
    parts: list[str] = []
    event_type = event.get("event", "")
    story_id = event.get("story_id")
    attempt = event.get("attempt")

    # -- One-line metadata summaries --

    if event_type == "gap_detection_started":
        model = event.get("model", "?")
        parts.append(f'<div style="color:#cbd5e1;margin-top:4px;">Model: <strong>{_esc(model)}</strong></div>')

    if event_type == "gap_critique_complete":
        locked = event.get("locked_count", "?")
        escalated = event.get("escalated_count", 0)
        demoted = event.get("demoted_count", 0)
        parts.append(f'<div style="color:#cbd5e1;margin-top:4px;">{locked} locked, {escalated} escalated, {demoted} demoted</div>')

    if event_type == "gap_questions_presented":
        count = event.get("question_count", 0)
        parts.append(f'<div style="color:#cbd5e1;margin-top:4px;">{count} questions</div>' if count else
                     '<div style="color:#cbd5e1;margin-top:4px;">No questions needed</div>')

    if event_type == "github_comment":
        url = event.get("comment_url", "")
        if url:
            parts.append(f'<div style="margin-top:4px;"><a href="{_esc(url)}" target="_blank" style="color:#93c5fd;">View on GitHub</a></div>')

    if event_type in ("story_complete", "story_failed"):
        commit = event.get("commit", "")
        attempt_val = event.get("attempt", "")
        meta = []
        if attempt_val:
            meta.append(f"attempt {attempt_val}")
        if commit:
            meta.append(f'commit <code style="background:#1e293b;padding:2px 6px;border-radius:3px;">{_esc(commit[:8])}</code>')
        if meta:
            parts.append(f'<div style="color:#cbd5e1;margin-top:4px;">{" · ".join(meta)}</div>')

    if event_type == "plan_rejected":
        reason = event.get("reason", "")
        if reason:
            parts.append(f'<div style="color:#fca5a5;margin-top:4px;white-space:pre-wrap;">{_esc(reason[:500])}</div>')

    if event_type == "preflight_fail":
        reason = event.get("reason", "")
        if reason:
            parts.append(f'<div style="color:#fca5a5;margin-top:4px;white-space:pre-wrap;">{_esc(reason)}</div>')
        checks = event.get("checks", [])
        if checks:
            parts.append(_render_table(checks, label="Preflight check results"))

    # -- Phase B critique feedback --

    if event_type in ("phase_b_fail", "phase_b_pass"):
        feedback = event.get("feedback")
        # feedback may be: list of dicts, a JSON string, or a Python repr string
        if isinstance(feedback, str) and feedback.strip():
            try:
                feedback = json.loads(feedback)
            except (json.JSONDecodeError, ValueError):
                pass  # leave as string — show in textarea

        if isinstance(feedback, dict):
            # Structured critique with dimensions
            fb_status = feedback.get("status", "")
            if fb_status:
                parts.append(f'<div style="color:#fca5a5;margin-top:4px;font-weight:600;">Status: {_esc(fb_status)}</div>')
            dims = feedback.get("dimensions", {})
            for dim_name, dim_data in dims.items():
                if not isinstance(dim_data, dict):
                    continue
                dim_status = dim_data.get("status", "")
                findings = dim_data.get("findings", [])
                status_colour = "#fca5a5" if dim_status == "fail" else "#6ee7b7"
                parts.append(
                    f'<div style="margin-top:8px;font-size:13px;color:{status_colour};font-weight:600;">'
                    f'{_esc(dim_name.replace("_", " ").title())} — {_esc(dim_status.upper())}</div>'
                )
                for f_item in findings:
                    if isinstance(f_item, dict):
                        sev = f_item.get("severity", "")
                        finding_text = f_item.get("finding", "") or f_item.get("issue", "")
                        fix = f_item.get("fix", "") or f_item.get("recommendation", "")
                        journey = f_item.get("journey_id", "")
                        step = f_item.get("step", "")
                        sev_colour = "#fca5a5" if sev in ("must_fix", "critical", "high") else "#fcd34d" if sev in ("should_fix", "medium") else "#94a3b8"
                        header = f'[{_esc(sev.upper())}]'
                        if journey:
                            header += f' {_esc(journey)}'
                        parts.append(
                            f'<div style="padding:8px 12px;margin:3px 0;background:#0f172a;border-left:3px solid {sev_colour};'
                            f'border-radius:4px;font-size:13px;color:#e2e8f0;">'
                            f'<strong style="color:{sev_colour};">{header}</strong> {_esc(finding_text)}'
                            f'{f"<br><span style=&quot;color:#64748b;font-size:12px;&quot;>Step: {_esc(step)}</span>" if step else ""}'
                            f'{f"<br><span style=&quot;color:#94a3b8;&quot;>Fix: {_esc(fix)}</span>" if fix else ""}'
                            f'</div>'
                        )
        elif isinstance(feedback, list):
            for item in feedback:
                if isinstance(item, dict):
                    severity = item.get("severity", "")
                    finding = item.get("finding", "")
                    recommendation = item.get("recommendation", "")
                    sev_colour = "#fca5a5" if severity in ("critical", "high", "must_fix") else "#fcd34d" if severity in ("medium", "should_fix") else "#94a3b8"
                    parts.append(
                        f'<div style="padding:8px 12px;margin:3px 0;background:#0f172a;border-left:3px solid {sev_colour};'
                        f'border-radius:4px;font-size:13px;color:#e2e8f0;">'
                        f'<strong style="color:{sev_colour};">[{_esc(severity.upper())}]</strong> {_esc(finding)}'
                        f'{f"<br><span style=&quot;color:#94a3b8;&quot;>→ {_esc(recommendation)}</span>" if recommendation else ""}'
                        f'</div>'
                    )
        elif isinstance(feedback, str) and feedback.strip():
            parts.append(_render_textarea(feedback, label="Critique feedback"))

    # -- Prompts (for dispatched events) --

    if event_type in ("agent_dispatched", "critique_dispatched", "epic_critique_dispatched"):
        prompt_text = None
        if story_id and attempt:
            prompt_text = find_story_prompt(epic_dir, story_id, attempt)
        if not prompt_text:
            prompt_hash = event.get("prompt_hash")
            if prompt_hash:
                prompt_text = match_prompt_file(prompt_hash)
        if prompt_text:
            parts.append(_render_textarea(prompt_text, label="Prompt sent to agent"))

    # -- Agent results (for complete/failed events) --

    if event_type in ("agent_complete", "agent_failed") and story_id and attempt:
        conv_events = find_conversation_log(epic_dir, story_id, attempt)
        if conv_events:
            for ce in conv_events:
                payload = ce.get("payload", {})
                if isinstance(payload, dict) and payload.get("type") == "result":
                    result_text = payload.get("result", "")
                    if result_text:
                        parts.append(_render_textarea(result_text, label="Agent result"))
                    # Cost/usage metadata
                    cost = payload.get("total_cost_usd")
                    num_turns = payload.get("num_turns")
                    duration_ms = payload.get("duration_ms")
                    usage = payload.get("usage", {})
                    meta = []
                    if cost:
                        meta.append(f"Cost: ${cost:.2f}")
                    if num_turns:
                        meta.append(f"Turns: {num_turns}")
                    if duration_ms:
                        mins = duration_ms // 60000
                        secs = (duration_ms % 60000) // 1000
                        meta.append(f"Duration: {mins}m {secs}s")
                    if usage.get("output_tokens"):
                        meta.append(f"Output: {usage['output_tokens']:,} tokens")
                    if meta:
                        parts.append(
                            f'<div style="padding:6px 10px;margin:4px 0;background:#0f172a;border-radius:4px;'
                            f'font-size:12px;color:#64748b;">{" · ".join(meta)}</div>'
                        )
                    break

    # -- Validation results --

    if event_type in ("validation_pass", "validation_fail"):
        results = event.get("results", [])
        if results:
            parts.append(_render_table(results, label="Validation results"))
        reason = event.get("reason", "")
        if reason:
            parts.append(f'<div style="padding:8px 10px;margin:4px 0;background:#0f172a;border-radius:4px;'
                         f'font-size:13px;color:#fca5a5;white-space:pre-wrap;">{_esc(reason)}</div>')

    # -- Critique findings --

    if event_type in ("critique_fail", "critique_failed", "epic_critique_fail"):
        findings = event.get("findings", [])
        if findings:
            parts.append(_render_table(findings, label="Critique findings"))
        raw_response = event.get("raw_response", "")
        if raw_response:
            parts.append(_render_textarea(str(raw_response), label="Raw critique response"))

    # -- Plan rejection details --

    if event_type == "plan_rejected":
        details = event.get("details") or event.get("feedback")
        if details:
            if isinstance(details, str):
                parts.append(_render_textarea(details, label="Rejection details"))
            else:
                parts.append(_render_table(details, label="Rejection details"))

    return "\n".join(parts)


def _render_event_card(event: dict, epic_dir: Path) -> str:
    """Render a single event as a timeline card — everything visible."""
    event_type = event.get("event", "unknown")
    ts = event.get("ts", "")
    story_id = event.get("story_id", "")
    attempt = event.get("attempt", "")
    bg, border, text_colour = EVENT_COLOURS.get(event_type, DEFAULT_COLOUR)

    label = _human_label(event_type)
    if story_id:
        label += f' — {story_id}'
    if attempt:
        label += f' (attempt {attempt})'

    content = _render_event_content(event, epic_dir)

    return f"""<div style="display:flex;gap:12px;margin-bottom:3px;">
    <div style="width:70px;flex-shrink:0;text-align:right;font-size:12px;color:#64748b;padding-top:12px;font-family:monospace;">
        {_esc(_format_ts(ts))}
    </div>
    <div style="width:3px;background:{border};flex-shrink:0;border-radius:2px;"></div>
    <div style="flex:1;background:{bg};border-left:3px solid {border};border-radius:6px;padding:12px 16px;">
        <div style="font-weight:600;font-size:14px;color:{text_colour};">{label}</div>
        {content}
    </div>
</div>"""


def _render_metadata_header(epic_dir: Path, events: list[dict], plan: dict | None) -> str:
    epic_name = epic_dir.name
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    run_ids = sorted({e.get("run_id", "?") for e in events})
    first_ts = _format_ts_full(events[0]["ts"]) if events else "N/A"
    last_ts = _format_ts_full(events[-1]["ts"]) if events else "N/A"

    story_count = len(plan.get("stories", [])) if plan else "?"
    completed = len({e["story_id"] for e in events if e.get("event") == "story_complete"})
    failed = len({e["story_id"] for e in events if e.get("event") == "story_failed"})

    has_complete = any(e.get("event") == "epic_complete" for e in events)
    has_failed = any(e.get("event") == "epic_failed" for e in events)
    has_exit = any(e.get("event") == "exit_to_human" for e in events)

    if has_complete:
        status = '<span style="color:#10b981;font-weight:bold;font-size:16px;">COMPLETE</span>'
    elif has_failed:
        status = '<span style="color:#ef4444;font-weight:bold;font-size:16px;">FAILED</span>'
    elif has_exit:
        status = '<span style="color:#f59e0b;font-weight:bold;font-size:16px;">EXIT TO HUMAN</span>'
    else:
        status = '<span style="color:#3b82f6;font-weight:bold;font-size:16px;">IN PROGRESS</span>'

    duration = compute_duration(events, "epic_started", "epic_complete") or compute_duration(
        events, events[0].get("event", ""), events[-1].get("event", "")
    ) if events else "N/A"

    return f"""<div style="background:#1e293b;border:1px solid #334155;border-radius:10px;padding:24px;margin-bottom:24px;">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
        <h1 style="margin:0;font-size:28px;color:#f1f5f9;">Epic {_esc(epic_name)} Report</h1>
        <div>{status}</div>
    </div>
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px;font-size:14px;color:#cbd5e1;">
        <div><span style="color:#64748b;">Generated:</span> {_esc(now)}</div>
        <div><span style="color:#64748b;">Started:</span> {_esc(first_ts)}</div>
        <div><span style="color:#64748b;">Last event:</span> {_esc(last_ts)}</div>
        <div><span style="color:#64748b;">Duration:</span> {_esc(str(duration) if duration else 'N/A')}</div>
        <div><span style="color:#64748b;">Stories:</span> {completed}/{story_count} complete, {failed} failed</div>
        <div><span style="color:#64748b;">Events:</span> {len(events)}</div>
        <div><span style="color:#64748b;">Run IDs:</span> {len(run_ids)}</div>
    </div>
</div>"""


def _render_story_nav(plan: dict | None, events: list[dict]) -> str:
    if not plan:
        return ""

    stories = plan.get("stories", [])
    if not stories:
        return ""

    completed_ids = {e["story_id"] for e in events if e.get("event") == "story_complete"}
    failed_ids = {e["story_id"] for e in events if e.get("event") == "story_failed"}

    items = []
    for i, story in enumerate(stories):
        sid = story.get("story_id", "?")
        name = story.get("name", "?")
        if sid in completed_ids:
            indicator = '<span style="color:#10b981;">&#10003;</span>'
        elif sid in failed_ids:
            indicator = '<span style="color:#ef4444;">&#10007;</span>'
        else:
            indicator = '<span style="color:#64748b;">&#9679;</span>'

        items.append(
            f'<div style="padding:4px 0;font-size:14px;">'
            f'{indicator} <a href="javascript:void(0)" onclick="document.getElementById(\'story-{_esc(sid)}\').scrollIntoView({{behavior:\'smooth\'}})" style="color:#93c5fd;text-decoration:none;cursor:pointer;">'
            f'{i + 1}. {_esc(sid)}</a>'
            f'<div style="font-size:12px;color:#64748b;margin-left:20px;">{_esc(name)}</div>'
            f'</div>'
        )

    return f"""<div style="background:#1e293b;border:1px solid #334155;border-radius:10px;padding:16px;margin-bottom:24px;">
    <h3 style="margin:0 0 12px 0;font-size:15px;color:#a5b4fc;">Stories</h3>
    {"".join(items)}
</div>"""


def render_report(epic_dir: Path) -> str:
    """Render the full HTML report for an epic."""
    plan_path = epic_dir / "plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8")) if plan_path.exists() else None

    events = collect_all_events(epic_dir)

    if not events:
        return f"""<!DOCTYPE html><html><body style="background:#0f0f23;color:#e2e8f0;font-family:sans-serif;padding:40px;">
        <h1>Epic {epic_dir.name} Report</h1>
        <p>No events found. The epic has not been started yet.</p>
        </body></html>"""

    current_story = None
    cards: list[str] = []
    for event in events:
        story_id = event.get("story_id")
        event_type = event.get("event", "")

        if event_type == "story_started" and story_id and story_id != current_story:
            current_story = story_id
            story_name = ""
            if plan:
                for s in plan.get("stories", []):
                    if s.get("story_id") == story_id:
                        story_name = s.get("name", "")
                        break
            cards.append(
                f'<div id="story-{_esc(story_id)}" style="margin:32px 0 12px;padding:12px 16px;'
                f'background:#312e81;border:1px solid #4338ca;color:#c7d2fe;border-radius:8px;font-weight:700;font-size:16px;">'
                f'Story: {_esc(story_id)}'
                f'{f" &mdash; {_esc(story_name)}" if story_name else ""}'
                f'</div>'
            )

        cards.append(_render_event_card(event, epic_dir))

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
            max-width: 1200px;
            margin: 0 auto;
            padding: 24px;
        }}
        .layout {{
            display: flex;
            gap: 24px;
        }}
        .sidebar {{
            width: 280px;
            flex-shrink: 0;
            position: sticky;
            top: 24px;
            align-self: flex-start;
        }}
        .main {{
            flex: 1;
            min-width: 0;
        }}
        a {{ color: #93c5fd; }}
        a:hover {{ color: #bfdbfe; }}
        code {{ background: #1e293b; padding: 2px 6px; border-radius: 3px; font-size: 13px; }}
        textarea:focus {{ outline: 1px solid #6366f1; }}
        @media (max-width: 800px) {{
            .layout {{ flex-direction: column; }}
            .sidebar {{ width: 100%; position: static; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        {_render_metadata_header(epic_dir, events, plan)}
        <div class="layout">
            <div class="sidebar">
                {_render_story_nav(plan, events)}
            </div>
            <div class="main">
                {"".join(cards)}
            </div>
        </div>
    </div>
</body>
</html>"""


# -- CLI entry point ----------------------------------------------------------


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
