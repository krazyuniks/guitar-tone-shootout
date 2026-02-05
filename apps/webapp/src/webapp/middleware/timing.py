"""Timing middleware for tracking request processing time."""

import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class TimingMiddleware(BaseHTTPMiddleware):
    """Adds X-Process-Time header with request processing duration."""

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[override]
        start_time = time.time()
        response = await call_next(request)
        elapsed_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(elapsed_time)

        return response
