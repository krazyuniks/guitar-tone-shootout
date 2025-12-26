"""Logging configuration for the application.

Provides structured logging with different formatters for development
and production environments.
"""

import logging
import sys
from collections.abc import MutableMapping
from typing import Any

from app.core.config import settings


def setup_logging() -> None:
    """Configure logging for the application.

    In debug mode: Human-readable format with colors
    In production: JSON-structured format for log aggregation
    """
    log_level = logging.DEBUG if settings.debug else logging.INFO

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)

    if settings.debug:
        # Development: readable format
        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    else:
        # Production: JSON-like structured format
        formatter = logging.Formatter(
            fmt='{"time":"%(asctime)s","level":"%(levelname)s",'
            '"logger":"%(name)s","line":%(lineno)d,"message":"%(message)s"}',
            datefmt="%Y-%m-%dT%H:%M:%S",
        )

    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # Configure specific loggers
    # Reduce noise from uvicorn access logs in production
    if not settings.debug:
        logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    # SQLAlchemy engine logs
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.INFO if settings.debug else logging.WARNING
    )

    # httpx logs (for Tone 3000 API calls)
    logging.getLogger("httpx").setLevel(
        logging.DEBUG if settings.debug else logging.WARNING
    )


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance for a module.

    Args:
        name: The logger name, typically __name__ from the calling module.

    Returns:
        A configured logger instance.

    Example:
        >>> from app.core.logging import get_logger
        >>> logger = get_logger(__name__)
        >>> logger.info("Processing shootout", extra={"shootout_id": 123})
    """
    return logging.getLogger(name)


class LoggerAdapter(logging.LoggerAdapter[logging.Logger]):
    """Logger adapter that adds context to log messages.

    Useful for adding request-specific context like user_id or request_id.

    Example:
        >>> logger = LoggerAdapter(get_logger(__name__), {"user_id": 42})
        >>> logger.info("User action")  # Includes user_id in output
    """

    def process(
        self, msg: str, kwargs: MutableMapping[str, Any]
    ) -> tuple[str, MutableMapping[str, Any]]:
        """Process the log message to include extra context."""
        extra = dict(kwargs.get("extra", {}))
        if self.extra:
            extra.update(self.extra)
        kwargs["extra"] = extra
        return msg, kwargs
