"""Admin workflow viewer — password-protected epic/story timeline browser.

Serves generated REPORT.html files from .planning/epics/ with a
navigation shell for browsing epics and stories.

Completely separate from the internal /api/admin/* routes.
"""

from __future__ import annotations

import json
import os
import secrets
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials

router = APIRouter(prefix="/admin/workflow", tags=["workflow-admin"])
security = HTTPBasic()

PLANNING_DIR = Path("/app/.planning/epics")


def _verify_credentials(credentials: HTTPBasicCredentials = Depends(security)) -> str:
    """Verify HTTP Basic Auth credentials. Returns username."""
    expected_password = os.getenv("GTS_ADMIN_PASSWORD", "")
    if not expected_password:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin password not configured",
        )
    if not secrets.compare_digest(credentials.password.encode(), expected_password.encode()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


def _scan_epics() -> list[dict]:
    """Scan .planning/epics/ for epic directories and extract metadata."""
    if not PLANNING_DIR.is_dir():
        return []

    epics = []
    for d in sorted(PLANNING_DIR.iterdir(), reverse=True):
        if not d.is_dir() or not d.name.startswith("E"):
            continue

        epic_num = d.name[1:]
        has_report = (d / "REPORT.html").is_file()
        has_plan = (d / "plan.json").is_file()

        stories = []
        if has_plan:
            try:
                plan = json.loads((d / "plan.json").read_text(encoding="utf-8"))
                for s in plan.get("stories", []):
                    stories.append(
                        {
                            "id": s.get("story_id", "?"),
                            "name": s.get("name", "?"),
                        }
                    )
            except (json.JSONDecodeError, OSError):
                pass

        # Check epic status from epic.jsonl last event
        epic_status = "unknown"
        epic_log = d / "epic.jsonl"
        if epic_log.is_file():
            try:
                lines = epic_log.read_text(encoding="utf-8").strip().splitlines()
                if lines:
                    last = json.loads(lines[-1])
                    event = last.get("event", "")
                    if event == "epic_complete":
                        epic_status = "complete"
                    elif event == "epic_failed":
                        epic_status = "failed"
                    elif "exit_to_human" in event:
                        epic_status = "exit_to_human"
                    else:
                        epic_status = "in_progress"
            except (json.JSONDecodeError, OSError):
                pass

        epics.append(
            {
                "number": epic_num,
                "name": d.name,
                "has_report": has_report,
                "stories": stories,
                "status": epic_status,
            }
        )

    return epics


_STATUS_COLOURS = {
    "complete": "#10b981",
    "failed": "#ef4444",
    "exit_to_human": "#f59e0b",
    "in_progress": "#3b82f6",
    "unknown": "#6b7280",
}

_STATUS_LABELS = {
    "complete": "Complete",
    "failed": "Failed",
    "exit_to_human": "Exit to Human",
    "in_progress": "In Progress",
    "unknown": "No Data",
}


def _render_shell(epics: list[dict]) -> str:
    """Render the navigation shell HTML."""
    # Build epic list items
    epic_items = []
    for epic in epics:
        colour = _STATUS_COLOURS.get(epic["status"], "#6b7280")
        label = _STATUS_LABELS.get(epic["status"], "?")
        story_count = len(epic["stories"])

        # Build story sub-items (hidden by default, toggled by Alpine)
        story_items = []
        for story in epic["stories"]:
            sid = story["id"]
            story_items.append(
                f'<a href="{epic["number"]}/report#story-{sid}" '
                f'onclick="loadReport(this.href);return false;"'
                f'style="display:block;padding:4px 8px 4px 24px;font-size:12px;'
                f'color:#93c5fd;text-decoration:none;border-radius:4px;" '
                f"onmouseover=\"this.style.background='#1e293b'\" "
                f"onmouseout=\"this.style.background='transparent'\">"
                f'{sid}<br><span style="color:#6b7280;font-size:11px;">{story["name"]}</span></a>'
            )

        stories_html = "\n".join(story_items) if story_items else ""

        report_link = ""
        if epic["has_report"]:
            report_link = (
                f'<a href="{epic["number"]}/report" onclick="loadReport(this.href);return false;"'
                f'style="font-size:11px;color:#93c5fd;text-decoration:none;">'
                f"View Report</a>"
            )

        epic_items.append(f"""
        <div x-data="{{ open: false }}" style="margin-bottom:2px;">
            <div @click="open = !open"
                 style="padding:8px 12px;cursor:pointer;border-radius:6px;display:flex;
                 justify-content:space-between;align-items:center;"
                 :style="open ? 'background:#1e293b' : ''"
                 onmouseover="if(!this.__x_refs)this.style.background='#1e293b'"
                 onmouseout="if(!this.__x_refs)this.style.background=''">
                <div>
                    <span style="font-weight:600;font-size:14px;">E{epic["number"]}</span>
                    <span style="font-size:11px;color:{colour};margin-left:8px;">{label}</span>
                    <span style="font-size:11px;color:#6b7280;margin-left:4px;">({story_count} stories)</span>
                </div>
                <span x-text="open ? '&#9660;' : '&#9654;'" style="font-size:10px;color:#6b7280;"></span>
            </div>
            <div x-show="open" x-transition style="padding:4px 0 8px;">
                <div style="padding:2px 12px 6px;">{report_link}</div>
                {stories_html}
            </div>
        </div>
        """)

    epic_list = (
        "\n".join(epic_items)
        if epic_items
        else '<p style="color:#6b7280;padding:12px;">No epics found.</p>'
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>GTS Workflow Admin</title>
    <script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3.x.x/dist/cdn.min.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0f172a;
            color: #e2e8f0;
            height: 100vh;
            overflow: hidden;
        }}
        .layout {{
            display: flex;
            height: 100vh;
        }}
        .sidebar {{
            width: 320px;
            flex-shrink: 0;
            background: #0f172a;
            border-right: 1px solid #1e293b;
            overflow-y: auto;
            padding: 16px;
        }}
        .main {{
            flex: 1;
            background: #0f0f23;
        }}
        .main iframe {{
            width: 100%;
            height: 100%;
            border: none;
        }}
        .main .report-content {{
            width: 100%;
            height: 100%;
            overflow-y: auto;
        }}
        h1 {{
            font-size: 18px;
            margin-bottom: 16px;
            padding-bottom: 8px;
            border-bottom: 1px solid #1e293b;
        }}
        .empty-state {{
            display: flex;
            align-items: center;
            justify-content: center;
            height: 100%;
            color: #475569;
            font-size: 16px;
        }}
    </style>
</head>
<body>
    <div class="layout">
        <div class="sidebar">
            <h1>Workflow Epics</h1>
            {epic_list}
        </div>
        <div class="main">
            <iframe id="report-frame" name="report-frame"
                srcdoc="&lt;div style='display:flex;align-items:center;justify-content:center;height:100vh;color:#475569;font-family:sans-serif;'&gt;Select an epic or story to view the report&lt;/div&gt;">
            </iframe>
        </div>
    </div>
    <script>
    function loadReport(url) {{
        var frame = document.getElementById('report-frame');
        var parsed = new URL(url);
        parsed.username = '';
        parsed.password = '';
        url = parsed.toString();
        fetch(url, {{ credentials: 'same-origin' }})
            .then(function(r) {{ return r.ok ? r.text() : Promise.reject(r.status); }})
            .then(function(content) {{
                frame.srcdoc = content;
                var anchor = url.split('#')[1];
                if (anchor) {{
                    frame.onload = function() {{
                        var el = frame.contentDocument.getElementById(anchor);
                        if (el) el.scrollIntoView({{ behavior: 'smooth' }});
                    }};
                }}
            }})
            .catch(function(err) {{
                frame.srcdoc = 'Failed to load report: ' + err;
            }});
    }}
    </script>
</body>
</html>"""


@router.get("/", response_class=HTMLResponse)
async def workflow_index(
    _user: str = Depends(_verify_credentials),
) -> HTMLResponse:
    """Render the workflow admin navigation page."""
    epics = _scan_epics()
    return HTMLResponse(_render_shell(epics))


@router.get("/{epic_number}/report", response_class=HTMLResponse)
async def workflow_report(
    epic_number: int,
    _user: str = Depends(_verify_credentials),
) -> HTMLResponse:
    """Serve the generated REPORT.html for an epic."""
    report_path = PLANNING_DIR / f"E{epic_number}" / "REPORT.html"
    if not report_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No report found for epic E{epic_number}. Run: just epic-report {epic_number}",
        )
    return HTMLResponse(report_path.read_text(encoding="utf-8"))
