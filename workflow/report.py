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

# -- Colour palette for event types ------------------------------------------

EVENT_COLOURS: dict[str, tuple[str, str]] = {
    # (bg class, border class) — Tailwind-style but hand-rolled
    "gap_detection_started": ("#dbeafe", "#3b82f6"),
    "gap_critique_complete": ("#dbeafe", "#3b82f6"),
    "gap_questions_presented": ("#dbeafe", "#3b82f6"),
    "gap_detection_complete": ("#dbeafe", "#3b82f6"),
    "planner_dispatched": ("#dbeafe", "#3b82f6"),
    "planner_complete": ("#dbeafe", "#3b82f6"),
    "planner_failed": ("#fee2e2", "#ef4444"),
    "phase_a_pass": ("#d1fae5", "#10b981"),
    "phase_a_fail": ("#fee2e2", "#ef4444"),
    "phase_b_pass": ("#d1fae5", "#10b981"),
    "phase_b_fail": ("#fee2e2", "#ef4444"),
    "phase_c_pass": ("#d1fae5", "#10b981"),
    "phase_c_fail": ("#fee2e2", "#ef4444"),
    "plan_approved": ("#d1fae5", "#10b981"),
    "plan_revised": ("#fef3c7", "#f59e0b"),
    "plan_rejected": ("#fee2e2", "#ef4444"),
    "plan_committed": ("#d1fae5", "#10b981"),
    "epic_started": ("#ede9fe", "#8b5cf6"),
    "story_started": ("#e0e7ff", "#6366f1"),
    "preflight_pass": ("#d1fae5", "#10b981"),
    "preflight_fail": ("#fee2e2", "#ef4444"),
    "agent_dispatched": ("#dbeafe", "#3b82f6"),
    "agent_complete": ("#d1fae5", "#10b981"),
    "agent_failed": ("#fee2e2", "#ef4444"),
    "validation_pass": ("#d1fae5", "#10b981"),
    "validation_fail": ("#fee2e2", "#ef4444"),
    "critique_dispatched": ("#f3e8ff", "#a855f7"),
    "critique_pass": ("#d1fae5", "#10b981"),
    "critique_fail": ("#fee2e2", "#ef4444"),
    "critique_failed": ("#fee2e2", "#ef4444"),
    "epic_critique_dispatched": ("#f3e8ff", "#a855f7"),
    "epic_critique_pass": ("#d1fae5", "#10b981"),
    "epic_critique_fail": ("#fee2e2", "#ef4444"),
    "story_complete": ("#d1fae5", "#10b981"),
    "story_failed": ("#fee2e2", "#ef4444"),
    "exit_to_human": ("#fef3c7", "#f59e0b"),
    "github_comment": ("#f0fdf4", "#86efac"),
    "epic_complete": ("#d1fae5", "#10b981"),
    "epic_failed": ("#fee2e2", "#ef4444"),
}

DEFAULT_COLOUR = ("#f3f4f6", "#9ca3af")


# -- Data collection ----------------------------------------------------------


def collect_all_events(epic_dir: Path) -> list[dict]:
    """Merge epic.jsonl + all story.jsonl files into one sorted timeline."""
    events: list[dict] = []

    # Epic-level events
    epic_log = epic_dir / "epic.jsonl"
    for e in read_log(epic_log):
        e["_source"] = "epic"
        events.append(e)

    # Story-level events
    stories_dir = epic_dir / "stories"
    if stories_dir.is_dir():
        for story_dir in sorted(stories_dir.iterdir()):
            if not story_dir.is_dir():
                continue
            story_log = story_dir / "story.jsonl"
            for e in read_log(story_log):
                e["_source"] = f"story:{story_dir.name}"
                events.append(e)

    # Sort by timestamp
    events.sort(key=lambda e: e.get("ts", ""))
    return events


def match_prompt_file(prompt_hash: str) -> str | None:
    """Find the prompt text file for a given hash."""
    if not prompt_hash or not LOGS_DIR.is_dir():
        return None
    for p in LOGS_DIR.glob(f"dispatch-*-{prompt_hash}-*.txt"):
        return p.read_text(encoding="utf-8")
    return None


def find_story_prompt(epic_dir: Path, story_id: str, attempt: int) -> str | None:
    """Find the prompt file for a specific story attempt."""
    prompt_path = epic_dir / "stories" / story_id / f"prompt-attempt-{attempt}.md"
    if prompt_path.exists():
        return prompt_path.read_text(encoding="utf-8")
    return None


def find_conversation_log(epic_dir: Path, story_id: str, attempt: int) -> list[dict]:
    """Load the conversation JSONL for a specific story attempt."""
    conv_path = epic_dir / "stories" / story_id / f"dispatch-{attempt}.jsonl"
    return read_log(conv_path)


def find_screenshots(epic_dir: Path, story_id: str) -> list[Path]:
    """Find screenshots in a story's screenshots directory."""
    ss_dir = epic_dir / "stories" / story_id / "screenshots"
    if not ss_dir.is_dir():
        return []
    return sorted(
        p for p in ss_dir.iterdir() if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".gif", ".webp")
    )


def compute_duration(events: list[dict], start_event: str, end_event: str, story_id: str | None = None) -> str | None:
    """Compute duration between two event types, optionally filtered by story_id."""
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
    """HTML-escape text."""
    return html.escape(str(text))


def _render_textarea(content: str, rows: int = 12, label: str = "") -> str:
    """Render a scrollable readonly textarea."""
    label_html = f'<div style="font-size:12px;color:#6b7280;margin-bottom:4px;">{_esc(label)}</div>' if label else ""
    return f"""{label_html}<textarea readonly
        style="width:100%;height:{rows * 1.4}em;font-family:monospace;font-size:12px;
        background:#1e1e2e;color:#cdd6f4;border:1px solid #45475a;border-radius:6px;
        padding:8px;resize:vertical;tab-size:2;"
        >{_esc(content)}</textarea>"""


def _render_json_block(data: object, label: str = "") -> str:
    """Render a JSON object in a scrollable textarea."""
    text = json.dumps(data, indent=2, default=str)
    return _render_textarea(text, rows=min(max(text.count("\n") + 1, 4), 20), label=label)


def _format_ts(ts_str: str) -> str:
    """Format an ISO timestamp for display."""
    try:
        dt = datetime.fromisoformat(ts_str)
        return dt.strftime("%H:%M:%S")
    except (ValueError, TypeError):
        return str(ts_str)[:19]


def _format_ts_full(ts_str: str) -> str:
    """Format an ISO timestamp with date for display."""
    try:
        dt = datetime.fromisoformat(ts_str)
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    except (ValueError, TypeError):
        return str(ts_str)


def _render_event_details(event: dict, epic_dir: Path) -> str:
    """Render the expandable details for an event."""
    parts: list[str] = []
    event_type = event.get("event", "")
    story_id = event.get("story_id")
    attempt = event.get("attempt")

    # Show all fields except universal ones and internal ones
    skip_keys = {"schema_v", "run_id", "ts", "event", "_source"}
    extra = {k: v for k, v in event.items() if k not in skip_keys}
    if extra:
        parts.append(_render_json_block(extra, label="Event data"))

    # For dispatched events, show the prompt
    if event_type in ("agent_dispatched", "critique_dispatched", "epic_critique_dispatched"):
        prompt_hash = event.get("prompt_hash")
        # Try story-specific prompt first
        prompt_text = None
        if story_id and attempt:
            prompt_text = find_story_prompt(epic_dir, story_id, attempt)
        if not prompt_text and prompt_hash:
            prompt_text = match_prompt_file(prompt_hash)
        if prompt_text:
            parts.append(_render_textarea(prompt_text, rows=20, label="Prompt"))

    # For agent_complete/agent_failed, show conversation transcript summary
    if event_type in ("agent_complete", "agent_failed") and story_id and attempt:
        conv_events = find_conversation_log(epic_dir, story_id, attempt)
        if conv_events:
            # Extract tool calls and assistant messages for summary
            summary_lines = []
            for ce in conv_events:
                payload = ce.get("payload", {})
                if isinstance(payload, dict):
                    msg_type = payload.get("type", "")
                    if msg_type == "assistant":
                        content = payload.get("message", {}).get("content", [])
                        if isinstance(content, list):
                            for block in content:
                                if isinstance(block, dict):
                                    if block.get("type") == "text":
                                        text = block.get("text", "")
                                        if text.strip():
                                            summary_lines.append(f"[assistant] {text[:200]}")
                                    elif block.get("type") == "tool_use":
                                        tool_name = block.get("name", "?")
                                        summary_lines.append(f"[tool_call] {tool_name}")
                    elif msg_type == "result":
                        # Tool result
                        pass
                elif ce.get("anomaly"):
                    raw = ce.get("raw", "")
                    if raw.strip():
                        summary_lines.append(f"[raw] {raw[:200]}")

            if summary_lines:
                parts.append(
                    _render_textarea(
                        "\n".join(summary_lines),
                        rows=min(len(summary_lines), 30),
                        label=f"Conversation transcript ({len(conv_events)} lines)",
                    )
                )

    # For validation events, show the results detail
    if event_type in ("validation_pass", "validation_fail"):
        results = event.get("results", [])
        if results:
            parts.append(_render_json_block(results, label="Validation results"))

    # For critique events, show findings
    if event_type in ("critique_fail", "epic_critique_fail"):
        findings = event.get("findings", [])
        if findings:
            parts.append(_render_json_block(findings, label="Critique findings"))

    if not parts:
        return ""

    return "\n".join(parts)


def _render_event_card(event: dict, epic_dir: Path, index: int) -> str:
    """Render a single event as a timeline card."""
    event_type = event.get("event", "unknown")
    ts = event.get("ts", "")
    story_id = event.get("story_id", "")
    attempt = event.get("attempt", "")
    source = event.get("_source", "")
    bg, border = EVENT_COLOURS.get(event_type, DEFAULT_COLOUR)

    # Build label
    label_parts = [event_type]
    if story_id:
        label_parts.append(f"story={story_id}")
    if attempt:
        label_parts.append(f"attempt={attempt}")

    label = " | ".join(label_parts)
    details = _render_event_details(event, epic_dir)
    detail_id = f"detail-{index}"

    has_details = bool(details.strip())
    toggle = ""
    details_html = ""
    cursor = ""

    if has_details:
        cursor = "cursor:pointer;"
        toggle = f' onclick="var d=document.getElementById(\'{detail_id}\');d.style.display=d.style.display===\'none\'?\'block\':\'none\';"'
        details_html = f'<div id="{detail_id}" style="display:none;margin-top:8px;">{details}</div>'

    return f"""<div style="display:flex;gap:12px;margin-bottom:2px;">
    <div style="width:70px;flex-shrink:0;text-align:right;font-size:12px;color:#6b7280;padding-top:10px;">
        {_esc(_format_ts(ts))}
    </div>
    <div style="width:3px;background:{border};flex-shrink:0;border-radius:2px;"></div>
    <div style="flex:1;background:{bg};border-left:3px solid {border};border-radius:6px;padding:10px 14px;{cursor}"
         {toggle}>
        <div style="display:flex;justify-content:space-between;align-items:center;">
            <span style="font-weight:600;font-size:13px;">{_esc(label)}</span>
            <span style="font-size:11px;color:#9ca3af;">{_esc(source)}</span>
        </div>
        {details_html}
    </div>
</div>"""


def _render_metadata_header(epic_dir: Path, events: list[dict], plan: dict | None) -> str:
    """Render the report metadata header."""
    epic_name = epic_dir.name
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    # Extract key metadata
    run_ids = sorted({e.get("run_id", "?") for e in events})
    first_ts = _format_ts_full(events[0]["ts"]) if events else "N/A"
    last_ts = _format_ts_full(events[-1]["ts"]) if events else "N/A"

    story_count = len(plan.get("stories", [])) if plan else "?"
    completed = len({e["story_id"] for e in events if e.get("event") == "story_complete"})
    failed = len({e["story_id"] for e in events if e.get("event") == "story_failed"})

    # Determine overall status
    has_complete = any(e.get("event") == "epic_complete" for e in events)
    has_failed = any(e.get("event") == "epic_failed" for e in events)
    has_exit = any(e.get("event") == "exit_to_human" for e in events)

    if has_complete:
        status = '<span style="color:#10b981;font-weight:bold;">COMPLETE</span>'
    elif has_failed:
        status = '<span style="color:#ef4444;font-weight:bold;">FAILED</span>'
    elif has_exit:
        status = '<span style="color:#f59e0b;font-weight:bold;">EXIT TO HUMAN</span>'
    else:
        status = '<span style="color:#3b82f6;font-weight:bold;">IN PROGRESS</span>'

    # Duration
    duration = compute_duration(events, "epic_started", "epic_complete") or compute_duration(
        events, events[0].get("event", ""), events[-1].get("event", "")
    ) if events else "N/A"

    return f"""<div style="background:#1e1e2e;color:#cdd6f4;border-radius:8px;padding:20px;margin-bottom:24px;">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
        <h1 style="margin:0;font-size:24px;">Epic {_esc(epic_name)} Report</h1>
        <div>{status}</div>
    </div>
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:8px;font-size:13px;">
        <div><span style="color:#6b7280;">Generated:</span> {_esc(now)}</div>
        <div><span style="color:#6b7280;">Started:</span> {_esc(first_ts)}</div>
        <div><span style="color:#6b7280;">Last event:</span> {_esc(last_ts)}</div>
        <div><span style="color:#6b7280;">Duration:</span> {_esc(str(duration) if duration else 'N/A')}</div>
        <div><span style="color:#6b7280;">Stories:</span> {completed}/{story_count} complete, {failed} failed</div>
        <div><span style="color:#6b7280;">Events:</span> {len(events)}</div>
        <div><span style="color:#6b7280;">Run IDs:</span> {len(run_ids)}</div>
    </div>
</div>"""


def _render_story_nav(plan: dict | None, events: list[dict]) -> str:
    """Render the story navigation sidebar."""
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
            indicator = '<span style="color:#6b7280;">&#9679;</span>'

        items.append(
            f'<div style="padding:4px 0;font-size:13px;">'
            f'{indicator} <a href="#story-{_esc(sid)}" style="color:#93c5fd;text-decoration:none;">'
            f'{i + 1}. {_esc(sid)}</a>'
            f'<div style="font-size:11px;color:#6b7280;margin-left:20px;">{_esc(name)}</div>'
            f'</div>'
        )

    return f"""<div style="background:#1e1e2e;color:#cdd6f4;border-radius:8px;padding:16px;margin-bottom:24px;">
    <h3 style="margin:0 0 8px 0;font-size:14px;color:#a5b4fc;">Stories</h3>
    {"".join(items)}
</div>"""


def render_report(epic_dir: Path) -> str:
    """Render the full HTML report for an epic."""
    # Load plan if available
    plan_path = epic_dir / "plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8")) if plan_path.exists() else None

    # Collect all events
    events = collect_all_events(epic_dir)

    if not events:
        return f"""<!DOCTYPE html><html><body>
        <h1>Epic {epic_dir.name} Report</h1>
        <p>No events found. The epic has not been started yet.</p>
        </body></html>"""

    # Build timeline cards
    current_story = None
    cards: list[str] = []
    for i, event in enumerate(events):
        story_id = event.get("story_id")
        event_type = event.get("event", "")

        # Insert story anchor when we see a new story
        if event_type == "story_started" and story_id and story_id != current_story:
            current_story = story_id
            story_name = ""
            if plan:
                for s in plan.get("stories", []):
                    if s.get("story_id") == story_id:
                        story_name = s.get("name", "")
                        break
            cards.append(
                f'<div id="story-{_esc(story_id)}" style="margin:24px 0 8px;padding:8px 12px;'
                f'background:#312e81;color:#c7d2fe;border-radius:6px;font-weight:600;">'
                f'Story: {_esc(story_id)}'
                f'{f" &mdash; {_esc(story_name)}" if story_name else ""}'
                f'</div>'
            )

        cards.append(_render_event_card(event, epic_dir, i))

    # Assemble the page
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
            line-height: 1.5;
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
    """Generate the HTML report for an epic and return the output path."""
    epic_dir = PLANNING_DIR / f"E{epic_number}"
    if not epic_dir.is_dir():
        raise FileNotFoundError(f"Epic directory not found: {epic_dir}")

    html_content = render_report(epic_dir)
    output_path = epic_dir / "REPORT.html"
    output_path.write_text(html_content, encoding="utf-8")
    return output_path


def main() -> None:
    """CLI entry point for report generation."""
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
