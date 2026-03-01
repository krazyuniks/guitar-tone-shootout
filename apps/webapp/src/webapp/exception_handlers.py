"""FastAPI exception handlers with content negotiation.

Provides consistent error handling across the application:
- JSON responses for API routes (/api/*)
- HTML error pages for page routes
- Production sanitization (no stack traces, no internal paths)
- Development mode includes full error details
"""

import logging
import os
import traceback
from pathlib import Path
from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from webapp.exceptions import AppException

logger = logging.getLogger(__name__)

# Path to Astro-built error pages
_ERROR_PAGES_DIR = Path(__file__).parent.parent.parent.parent.parent / "frontend" / "astro" / "dist"


def _is_production() -> bool:
    """Check if running in production mode.

    Defaults to production for safety - only development mode when explicitly set.
    """
    return os.getenv("ENVIRONMENT", "production").lower() != "development"


def _is_api_route(request: Request) -> bool:
    """Check if the request is for an API route."""
    return request.url.path.startswith("/api/")


def _is_page_route(request: Request) -> bool:
    """Check if the request is for a page route."""
    return request.url.path.startswith("/pages/")


def _wants_html(request: Request) -> bool:
    """Check if the client prefers HTML based on Accept header."""
    accept = request.headers.get("accept", "")
    return "text/html" in accept


def _sanitize_error_details(details: Any) -> Any:
    """Remove sensitive information from error details in production."""
    if not _is_production():
        return details

    # In production, remove any internal paths or stack traces
    if isinstance(details, dict):
        sanitized = {}
        for key, value in details.items():
            # Skip fields that might contain sensitive information
            if key.lower() in ["traceback", "stack", "exception", "path", "file"]:
                continue
            sanitized[key] = _sanitize_error_details(value)
        return sanitized
    elif isinstance(details, list):
        return [_sanitize_error_details(item) for item in details]
    elif isinstance(details, str):
        # Remove file paths
        if "/apps/" in details or "/libs/" in details or "/home/" in details:
            return None
        return details
    else:
        return details


def _load_error_page(status_code: int) -> str | None:
    """Load Astro-built error page from dist directory.

    Args:
        status_code: HTTP status code (404, 500)

    Returns:
        HTML content of error page, or None if not found
    """
    error_page_path = _ERROR_PAGES_DIR / f"{status_code}.html"
    if error_page_path.exists():
        return error_page_path.read_text()
    return None


def _create_error_response(
    request: Request,
    status_code: int,
    error_code: str,
    message: str,
    details: Any = None,
) -> JSONResponse | HTMLResponse:
    """Create an error response with content negotiation.

    Args:
        request: The request object
        status_code: HTTP status code
        error_code: Machine-readable error code
        message: Human-readable error message
        details: Optional error details

    Returns:
        JSONResponse for API routes and unmapped routes (404s),
        HTMLResponse only when Accept header explicitly requests HTML
    """
    # Sanitize details in production
    if _is_production() and details is not None:
        details = _sanitize_error_details(details)

    # Prepare JSON content
    json_content = {
        "error_code": error_code,
        "message": message,
    }
    if details is not None:
        json_content["details"] = details

    # API routes always get JSON
    if _is_api_route(request):
        return JSONResponse(
            status_code=status_code,
            content=json_content,
        )

    # For non-API routes, check Accept header
    accept = request.headers.get("accept", "")
    wants_json = "application/json" in accept and "text/html" not in accept

    # Return HTML unless JSON is explicitly requested
    if not wants_json:
        # Try to load Astro-built error page
        html_content = _load_error_page(status_code)
        if html_content:
            return HTMLResponse(content=html_content, status_code=status_code)

        # Fallback to inline HTML if Astro page not available
        html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Error {status_code}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            max-width: 600px;
            margin: 100px auto;
            padding: 20px;
            text-align: center;
        }}
        h1 {{
            font-size: 72px;
            margin: 0;
            color: #dc2626;
        }}
        h2 {{
            font-size: 24px;
            margin: 20px 0;
            color: #374151;
        }}
        p {{
            color: #6b7280;
            line-height: 1.6;
        }}
        a {{
            color: #2563eb;
            text-decoration: none;
        }}
        a:hover {{
            text-decoration: underline;
        }}
    </style>
</head>
<body>
    <h1>{status_code}</h1>
    <h2>{message}</h2>
    <p><a href="/">Return to home</a></p>
</body>
</html>
"""
        return HTMLResponse(content=html_content, status_code=status_code)

    # JSON for non-API routes only if explicitly requested
    return JSONResponse(
        status_code=status_code,
        content=json_content,
    )


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse | HTMLResponse:
    """Handle AppException with content negotiation.

    Returns JSON for API routes, HTML error pages for page routes.
    """
    logger.warning(
        "AppException raised: %s",
        exc.message,
        extra={
            "status_code": exc.status_code,
            "error_code": exc.error_code,
            "path": request.url.path,
        },
    )

    return _create_error_response(
        request=request,
        status_code=exc.status_code,
        error_code=exc.error_code,
        message=exc.message,
        details=exc.details,
    )


async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse | HTMLResponse:
    """Handle HTTPException with consistent format.

    Wraps FastAPI/Starlette HTTPException in our standard error format.
    """
    logger.warning(
        "HTTPException raised",
        extra={
            "status_code": exc.status_code,
            "detail": exc.detail,
            "path": request.url.path,
        },
    )

    # Map status code to error code
    error_code_map = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        405: "METHOD_NOT_ALLOWED",
        409: "CONFLICT",
        422: "VALIDATION_ERROR",
        500: "INTERNAL_ERROR",
        502: "BAD_GATEWAY",
        503: "SERVICE_UNAVAILABLE",
        504: "GATEWAY_TIMEOUT",
    }

    error_code = error_code_map.get(exc.status_code, "HTTP_ERROR")
    message = str(exc.detail) if exc.detail else "An error occurred"

    return _create_error_response(
        request=request,
        status_code=exc.status_code,
        error_code=error_code,
        message=message,
    )


async def request_validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Handle Pydantic RequestValidationError with field-level errors.

    Returns 422 with structured validation errors.
    """
    logger.warning(
        "RequestValidationError raised",
        extra={
            "errors": exc.errors(),
            "path": request.url.path,
        },
    )

    # Format validation errors
    errors = exc.errors()
    details = {"errors": errors} if not _is_production() else {"field_count": len(errors)}

    return JSONResponse(
        status_code=422,
        content={
            "error_code": "VALIDATION_ERROR",
            "message": "Request validation failed",
            "details": details,
        },
    )


async def sqlalchemy_error_handler(
    request: Request, exc: SQLAlchemyError
) -> JSONResponse | HTMLResponse:
    """Handle SQLAlchemy errors with sanitized response.

    Logs full error, returns sanitized 500 response.
    """
    logger.error(
        "SQLAlchemyError raised",
        extra={
            "error": str(exc),
            "path": request.url.path,
        },
        exc_info=True,
    )

    # In development, include error details
    details = None
    if not _is_production():
        details = {
            "error_type": type(exc).__name__,
            "error_message": str(exc),
        }

    return _create_error_response(
        request=request,
        status_code=500,
        error_code="DATABASE_ERROR",
        message="A database error occurred",
        details=details,
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unhandled exceptions with sanitized response.

    Logs full error with traceback, returns sanitized 500 response.
    """
    logger.error(
        "Unhandled exception raised",
        extra={
            "error_type": type(exc).__name__,
            "error": str(exc),
            "path": request.url.path,
        },
        exc_info=True,
    )

    # In development, include full traceback
    details = None
    if not _is_production():
        details = {
            "error_type": type(exc).__name__,
            "error_message": str(exc),
            "traceback": traceback.format_exc(),
        }

    # Build JSON content
    json_content: dict[str, Any] = {
        "error_code": "INTERNAL_ERROR",
        "message": "An internal error occurred",
    }
    if details is not None:
        # Sanitize in production
        if _is_production():
            details = _sanitize_error_details(details)
        json_content["details"] = details

    # Always return JSON for unhandled exceptions (even for page routes)
    return JSONResponse(
        status_code=500,
        content=json_content,
    )
