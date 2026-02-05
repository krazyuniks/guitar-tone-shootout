"""Jinja2 template configuration for GTS webapp."""

from pathlib import Path

from fastapi.templating import Jinja2Templates

PROJECT_ROOT = Path("/app")
TEMPLATE_DIR = PROJECT_ROOT / "frontend" / "astro" / "dist"

templates = Jinja2Templates(directory=str(TEMPLATE_DIR))
