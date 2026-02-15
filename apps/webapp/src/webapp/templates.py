"""Jinja2 template configuration for GTS webapp."""

import re
from datetime import UTC, datetime
from pathlib import Path

from fastapi.templating import Jinja2Templates
from jinja2 import Environment, FileSystemLoader

PROJECT_ROOT = Path("/app")
TEMPLATE_DIR = PROJECT_ROOT / "frontend" / "astro" / "dist"


def _format_number(value: int | float | None) -> str:
    """Format a number with comma separators (e.g. 1,234)."""
    if value is None:
        return "0"
    return f"{int(value):,}"


def _relative_time(dt: datetime | None) -> str:
    """Convert a datetime to a human-readable relative time string."""
    if dt is None:
        return ""
    now = datetime.now(UTC)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    diff = now - dt
    seconds = int(diff.total_seconds())
    if seconds < 60:
        return "just now"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}h ago"
    days = hours // 24
    if days < 30:
        return f"{days}d ago"
    months = days // 30
    if months < 12:
        return f"{months}mo ago"
    years = days // 365
    return f"{years}y ago"


_env = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    autoescape=True,
)


def _extract_youtube_id(url: str) -> str | None:
    """Extract YouTube video ID from URL."""
    if not url:
        return None
    match = re.search(
        r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([a-zA-Z0-9_-]{11})",
        url,
    )
    return match.group(1) if match else None


_env.filters["format_number"] = _format_number
_env.filters["relative_time"] = _relative_time
_env.filters["extract_youtube_id"] = _extract_youtube_id

templates = Jinja2Templates(directory=str(TEMPLATE_DIR))
templates.env = _env
