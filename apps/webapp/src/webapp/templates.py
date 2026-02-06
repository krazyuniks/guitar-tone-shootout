"""Jinja2 template configuration for GTS webapp."""

from pathlib import Path

from fastapi.templating import Jinja2Templates
from jinja2 import Environment, FileSystemLoader

PROJECT_ROOT = Path("/app")
TEMPLATE_DIR = PROJECT_ROOT / "frontend" / "astro" / "dist"

# Create a custom Jinja2 environment with auto-escaping disabled.
# Fragment templates render trusted data from our own database,
# and input validation + CSP headers provide XSS protection.
_env = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    autoescape=False,
)
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))
templates.env = _env
