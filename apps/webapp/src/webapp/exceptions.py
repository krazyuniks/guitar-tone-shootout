"""Custom exception hierarchy for GTS webapp.

All application-level errors should raise domain exceptions that map to HTTP status codes.
This module has zero framework dependencies.
"""

from typing import Any


class AppException(Exception):
    """Base exception for all application-level errors.

    All custom exceptions inherit from this base class and provide:
    - HTTP status code mapping
    - Structured error codes
    - Serialization to JSON-compatible dict
    """

    def __init__(
        self,
        status_code: int,
        error_code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize the exception.

        Args:
            status_code: HTTP status code (e.g., 404, 403, 409)
            error_code: Machine-readable error code (e.g., "NOT_FOUND")
            message: Human-readable error message
            details: Optional additional context as a dictionary
        """
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code
        self.message = message
        self.details = details

    def to_dict(self) -> dict[str, Any]:
        """Serialize the exception to a dictionary.

        Returns:
            Dictionary with error_code, message, and details keys.
        """
        return {
            "error_code": self.error_code,
            "message": self.message,
            "details": self.details,
        }


class NotFoundError(AppException):
    """Exception raised when a requested resource is not found (404)."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        """Initialize NotFoundError.

        Args:
            message: Human-readable error message
            details: Optional additional context
        """
        super().__init__(
            status_code=404,
            error_code="NOT_FOUND",
            message=message,
            details=details,
        )


class AuthorizationError(AppException):
    """Exception raised when access is forbidden (403)."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        """Initialize AuthorizationError.

        Args:
            message: Human-readable error message
            details: Optional additional context
        """
        super().__init__(
            status_code=403,
            error_code="FORBIDDEN",
            message=message,
            details=details,
        )


class ConflictError(AppException):
    """Exception raised when a resource conflict occurs (409)."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        """Initialize ConflictError.

        Args:
            message: Human-readable error message
            details: Optional additional context
        """
        super().__init__(
            status_code=409,
            error_code="CONFLICT",
            message=message,
            details=details,
        )


class BadRequestError(AppException):
    """Exception raised when the request is malformed or invalid (400)."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        """Initialize BadRequestError.

        Args:
            message: Human-readable error message
            details: Optional additional context
        """
        super().__init__(
            status_code=400,
            error_code="BAD_REQUEST",
            message=message,
            details=details,
        )


class ValidationError(AppException):
    """Exception raised when input validation fails (422)."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        """Initialize ValidationError.

        Args:
            message: Human-readable error message
            details: Optional additional context
        """
        super().__init__(
            status_code=422,
            error_code="VALIDATION_ERROR",
            message=message,
            details=details,
        )
