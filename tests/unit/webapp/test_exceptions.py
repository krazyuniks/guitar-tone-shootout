"""Unit tests for custom exception hierarchy."""

from webapp.exceptions import (
    AppException,
    AuthorizationError,
    BadRequestError,
    ConflictError,
    NotFoundError,
    ValidationError,
)


class TestAppException:
    """Test the base AppException class."""

    def test_has_status_code_attribute(self) -> None:
        """AppException should have a status_code attribute."""
        exc = AppException(
            status_code=500,
            error_code="INTERNAL_ERROR",
            message="Something went wrong",
        )
        assert exc.status_code == 500

    def test_has_error_code_attribute(self) -> None:
        """AppException should have an error_code attribute."""
        exc = AppException(
            status_code=500,
            error_code="INTERNAL_ERROR",
            message="Something went wrong",
        )
        assert exc.error_code == "INTERNAL_ERROR"

    def test_has_message_attribute(self) -> None:
        """AppException should have a message attribute."""
        exc = AppException(
            status_code=500,
            error_code="INTERNAL_ERROR",
            message="Something went wrong",
        )
        assert exc.message == "Something went wrong"

    def test_has_details_attribute(self) -> None:
        """AppException should have a details attribute."""
        details = {"field": "username", "reason": "already exists"}
        exc = AppException(
            status_code=500,
            error_code="INTERNAL_ERROR",
            message="Something went wrong",
            details=details,
        )
        assert exc.details == details

    def test_details_defaults_to_none(self) -> None:
        """AppException details should default to None if not provided."""
        exc = AppException(
            status_code=500,
            error_code="INTERNAL_ERROR",
            message="Something went wrong",
        )
        assert exc.details is None

    def test_serializes_to_dict(self) -> None:
        """AppException should serialize to a dictionary."""
        exc = AppException(
            status_code=500,
            error_code="INTERNAL_ERROR",
            message="Something went wrong",
            details={"key": "value"},
        )
        serialized = exc.to_dict()
        assert serialized == {
            "error_code": "INTERNAL_ERROR",
            "message": "Something went wrong",
            "details": {"key": "value"},
        }

    def test_serializes_to_dict_without_details(self) -> None:
        """AppException serialization should omit details if None."""
        exc = AppException(
            status_code=500,
            error_code="INTERNAL_ERROR",
            message="Something went wrong",
        )
        serialized = exc.to_dict()
        assert serialized == {
            "error_code": "INTERNAL_ERROR",
            "message": "Something went wrong",
            "details": None,
        }


class TestNotFoundError:
    """Test the NotFoundError exception."""

    def test_inherits_from_app_exception(self) -> None:
        """NotFoundError should inherit from AppException."""
        exc = NotFoundError(message="Resource not found")
        assert isinstance(exc, AppException)

    def test_has_404_status_code(self) -> None:
        """NotFoundError should have status code 404."""
        exc = NotFoundError(message="Resource not found")
        assert exc.status_code == 404

    def test_has_not_found_error_code(self) -> None:
        """NotFoundError should have error code NOT_FOUND."""
        exc = NotFoundError(message="Resource not found")
        assert exc.error_code == "NOT_FOUND"

    def test_accepts_custom_message(self) -> None:
        """NotFoundError should accept a custom message."""
        exc = NotFoundError(message="Gear not found")
        assert exc.message == "Gear not found"

    def test_accepts_details(self) -> None:
        """NotFoundError should accept details."""
        details = {"resource_id": "abc123"}
        exc = NotFoundError(message="Resource not found", details=details)
        assert exc.details == details

    def test_serializes_correctly(self) -> None:
        """NotFoundError should serialize correctly."""
        exc = NotFoundError(
            message="Gear not found",
            details={"gear_id": "abc123"},
        )
        serialized = exc.to_dict()
        assert serialized == {
            "error_code": "NOT_FOUND",
            "message": "Gear not found",
            "details": {"gear_id": "abc123"},
        }


class TestAuthorizationError:
    """Test the AuthorizationError exception."""

    def test_inherits_from_app_exception(self) -> None:
        """AuthorizationError should inherit from AppException."""
        exc = AuthorizationError(message="Access denied")
        assert isinstance(exc, AppException)

    def test_has_403_status_code(self) -> None:
        """AuthorizationError should have status code 403."""
        exc = AuthorizationError(message="Access denied")
        assert exc.status_code == 403

    def test_has_forbidden_error_code(self) -> None:
        """AuthorizationError should have error code FORBIDDEN."""
        exc = AuthorizationError(message="Access denied")
        assert exc.error_code == "FORBIDDEN"

    def test_accepts_custom_message(self) -> None:
        """AuthorizationError should accept a custom message."""
        exc = AuthorizationError(message="You cannot access this resource")
        assert exc.message == "You cannot access this resource"

    def test_accepts_details(self) -> None:
        """AuthorizationError should accept details."""
        details = {"required_permission": "admin"}
        exc = AuthorizationError(message="Access denied", details=details)
        assert exc.details == details

    def test_serializes_correctly(self) -> None:
        """AuthorizationError should serialize correctly."""
        exc = AuthorizationError(
            message="Access denied",
            details={"required_permission": "admin"},
        )
        serialized = exc.to_dict()
        assert serialized == {
            "error_code": "FORBIDDEN",
            "message": "Access denied",
            "details": {"required_permission": "admin"},
        }


class TestConflictError:
    """Test the ConflictError exception."""

    def test_inherits_from_app_exception(self) -> None:
        """ConflictError should inherit from AppException."""
        exc = ConflictError(message="Resource already exists")
        assert isinstance(exc, AppException)

    def test_has_409_status_code(self) -> None:
        """ConflictError should have status code 409."""
        exc = ConflictError(message="Resource already exists")
        assert exc.status_code == 409

    def test_has_conflict_error_code(self) -> None:
        """ConflictError should have error code CONFLICT."""
        exc = ConflictError(message="Resource already exists")
        assert exc.error_code == "CONFLICT"

    def test_accepts_custom_message(self) -> None:
        """ConflictError should accept a custom message."""
        exc = ConflictError(message="Username already taken")
        assert exc.message == "Username already taken"

    def test_accepts_details(self) -> None:
        """ConflictError should accept details."""
        details = {"field": "username", "value": "existing_user"}
        exc = ConflictError(message="Username already taken", details=details)
        assert exc.details == details

    def test_serializes_correctly(self) -> None:
        """ConflictError should serialize correctly."""
        exc = ConflictError(
            message="Username already taken",
            details={"field": "username"},
        )
        serialized = exc.to_dict()
        assert serialized == {
            "error_code": "CONFLICT",
            "message": "Username already taken",
            "details": {"field": "username"},
        }


class TestBadRequestError:
    """Test the BadRequestError exception."""

    def test_inherits_from_app_exception(self) -> None:
        """BadRequestError should inherit from AppException."""
        exc = BadRequestError(message="Invalid request")
        assert isinstance(exc, AppException)

    def test_has_400_status_code(self) -> None:
        """BadRequestError should have status code 400."""
        exc = BadRequestError(message="Invalid request")
        assert exc.status_code == 400

    def test_has_bad_request_error_code(self) -> None:
        """BadRequestError should have error code BAD_REQUEST."""
        exc = BadRequestError(message="Invalid request")
        assert exc.error_code == "BAD_REQUEST"

    def test_accepts_custom_message(self) -> None:
        """BadRequestError should accept a custom message."""
        exc = BadRequestError(message="Missing required parameter")
        assert exc.message == "Missing required parameter"

    def test_accepts_details(self) -> None:
        """BadRequestError should accept details."""
        details = {"parameter": "name"}
        exc = BadRequestError(message="Missing required parameter", details=details)
        assert exc.details == details

    def test_serializes_correctly(self) -> None:
        """BadRequestError should serialize correctly."""
        exc = BadRequestError(
            message="Missing required parameter",
            details={"parameter": "name"},
        )
        serialized = exc.to_dict()
        assert serialized == {
            "error_code": "BAD_REQUEST",
            "message": "Missing required parameter",
            "details": {"parameter": "name"},
        }


class TestValidationError:
    """Test the ValidationError exception."""

    def test_inherits_from_app_exception(self) -> None:
        """ValidationError should inherit from AppException."""
        exc = ValidationError(message="Validation failed")
        assert isinstance(exc, AppException)

    def test_has_422_status_code(self) -> None:
        """ValidationError should have status code 422."""
        exc = ValidationError(message="Validation failed")
        assert exc.status_code == 422

    def test_has_validation_error_code(self) -> None:
        """ValidationError should have error code VALIDATION_ERROR."""
        exc = ValidationError(message="Validation failed")
        assert exc.error_code == "VALIDATION_ERROR"

    def test_accepts_custom_message(self) -> None:
        """ValidationError should accept a custom message."""
        exc = ValidationError(message="Email format is invalid")
        assert exc.message == "Email format is invalid"

    def test_accepts_details(self) -> None:
        """ValidationError should accept details."""
        details = {"field": "email", "reason": "invalid format"}
        exc = ValidationError(message="Email format is invalid", details=details)
        assert exc.details == details

    def test_serializes_correctly(self) -> None:
        """ValidationError should serialize correctly."""
        exc = ValidationError(
            message="Email format is invalid",
            details={"field": "email", "reason": "invalid format"},
        )
        serialized = exc.to_dict()
        assert serialized == {
            "error_code": "VALIDATION_ERROR",
            "message": "Email format is invalid",
            "details": {"field": "email", "reason": "invalid format"},
        }


class TestNoFrameworkDependencies:
    """Test that exceptions module has no framework dependencies."""

    def test_module_imports_only_standard_library(self) -> None:
        """The exceptions module should only import from standard library."""
        import webapp.exceptions as exc_module

        # Check that the module doesn't import FastAPI, Starlette, etc.
        module_dict = vars(exc_module)

        # These would indicate framework dependencies
        forbidden_names = [
            "HTTPException",
            "Request",
            "Response",
            "FastAPI",
            "Starlette",
        ]

        for name in forbidden_names:
            assert name not in module_dict, f"Found forbidden import: {name}"
