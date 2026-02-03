"""GTS Web Application.

FastAPI backend serving SSR pages and REST API.
"""

__version__ = "0.1.0"

from webapp.main import app, create_app

__all__ = ["app", "create_app"]
