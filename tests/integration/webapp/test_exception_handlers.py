"""Integration tests for FastAPI exception handlers with content negotiation.

Tests exception handlers mounted in main.py:
- AppException handler - JSON for API routes, HTML for pages
- HTTPException handler - wrapped in consistent format
- RequestValidationError handler - 422 with field-level errors
- SQLAlchemyError handler - 500 with sanitised response
- Unhandled exception handler - 500 with sanitised response
- Content negotiation based on route prefix and Accept header
- Production vs development mode sanitisation
"""

from collections.abc import AsyncGenerator
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from webapp.adapters.persistence.models.base import Base
from webapp.exceptions import (
    AppException,
    AuthorizationError,
    BadRequestError,
    ConflictError,
    NotFoundError,
    ValidationError,
)


@pytest.fixture
async def db_engine() -> AsyncGenerator[AsyncEngine, None]:
    """Create an in-memory SQLite session for testing."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(db_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """Real database with transaction rollback."""
    connection = await db_engine.connect()
    transaction = await connection.begin()

    async_session_factory = async_sessionmaker(
        bind=connection,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    session = async_session_factory()

    try:
        yield session
    finally:
        await session.close()
        await transaction.rollback()
        await connection.close()


@pytest.fixture
def app_with_handlers() -> FastAPI:
    """Create a FastAPI app with exception handlers mounted.

    This will fail until webapp.exception_handlers module exists.
    """
    from fastapi import HTTPException
    from fastapi.exceptions import RequestValidationError
    from starlette.exceptions import HTTPException as StarletteHTTPException

    from webapp.exception_handlers import (
        app_exception_handler,
        http_exception_handler,
        request_validation_error_handler,
        sqlalchemy_error_handler,
        unhandled_exception_handler,
    )

    app = FastAPI()

    # Mount exception handlers
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, request_validation_error_handler)
    app.add_exception_handler(SQLAlchemyError, sqlalchemy_error_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)

    # Test routes that raise exceptions
    @app.get("/api/v1/test/not-found")
    async def api_not_found():
        raise NotFoundError(message="Resource not found", details={"resource_id": "123"})

    @app.get("/api/v1/test/forbidden")
    async def api_forbidden():
        raise AuthorizationError(message="Access denied")

    @app.get("/api/v1/test/conflict")
    async def api_conflict():
        raise ConflictError(message="Username already exists")

    @app.get("/api/v1/test/bad-request")
    async def api_bad_request():
        raise BadRequestError(message="Invalid input")

    @app.get("/api/v1/test/validation-error")
    async def api_validation():
        raise ValidationError(message="Email is invalid", details={"field": "email"})

    @app.get("/api/v1/test/http-exception")
    async def api_http_exception():
        from fastapi import HTTPException

        raise HTTPException(status_code=503, detail="Service unavailable")

    @app.get("/api/v1/test/sqlalchemy-error")
    async def api_sqlalchemy_error():
        raise SQLAlchemyError("Database connection failed")

    @app.get("/api/v1/test/unhandled")
    async def api_unhandled():
        raise RuntimeError("Something went wrong")

    @app.get("/pages/test/not-found")
    async def page_not_found():
        raise NotFoundError(message="Page not found")

    @app.get("/pages/test/error")
    async def page_error():
        raise RuntimeError("Page error")

    return app


class TestAppExceptionHandler:
    """Test suite for AppException handler with content negotiation."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_not_found_error_returns_404_json(self, app_with_handlers: FastAPI) -> None:
        """Test NotFoundError returns 404 with JSON for API routes."""
        async with AsyncClient(
            transport=ASGITransport(app=app_with_handlers), base_url="http://test"
        ) as client:
            response = await client.get("/api/v1/test/not-found")

            assert response.status_code == 404
            assert response.headers["content-type"] == "application/json"
            data = response.json()
            assert data["error_code"] == "NOT_FOUND"
            assert data["message"] == "Resource not found"
            assert data["details"] == {"resource_id": "123"}

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_authorization_error_returns_403_json(self, app_with_handlers: FastAPI) -> None:
        """Test AuthorizationError returns 403 with JSON for API routes."""
        async with AsyncClient(
            transport=ASGITransport(app=app_with_handlers), base_url="http://test"
        ) as client:
            response = await client.get("/api/v1/test/forbidden")

            assert response.status_code == 403
            assert response.headers["content-type"] == "application/json"
            data = response.json()
            assert data["error_code"] == "FORBIDDEN"
            assert data["message"] == "Access denied"

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_conflict_error_returns_409_json(self, app_with_handlers: FastAPI) -> None:
        """Test ConflictError returns 409 with JSON for API routes."""
        async with AsyncClient(
            transport=ASGITransport(app=app_with_handlers), base_url="http://test"
        ) as client:
            response = await client.get("/api/v1/test/conflict")

            assert response.status_code == 409
            assert response.headers["content-type"] == "application/json"
            data = response.json()
            assert data["error_code"] == "CONFLICT"
            assert data["message"] == "Username already exists"

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_bad_request_error_returns_400_json(self, app_with_handlers: FastAPI) -> None:
        """Test BadRequestError returns 400 with JSON for API routes."""
        async with AsyncClient(
            transport=ASGITransport(app=app_with_handlers), base_url="http://test"
        ) as client:
            response = await client.get("/api/v1/test/bad-request")

            assert response.status_code == 400
            assert response.headers["content-type"] == "application/json"
            data = response.json()
            assert data["error_code"] == "BAD_REQUEST"
            assert data["message"] == "Invalid input"

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_validation_error_returns_422_json(self, app_with_handlers: FastAPI) -> None:
        """Test ValidationError returns 422 with JSON for API routes."""
        async with AsyncClient(
            transport=ASGITransport(app=app_with_handlers), base_url="http://test"
        ) as client:
            response = await client.get("/api/v1/test/validation-error")

            assert response.status_code == 422
            assert response.headers["content-type"] == "application/json"
            data = response.json()
            assert data["error_code"] == "VALIDATION_ERROR"
            assert data["message"] == "Email is invalid"
            assert data["details"] == {"field": "email"}

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_page_route_returns_html_error_page(self, app_with_handlers: FastAPI) -> None:
        """Test page routes return HTML error pages instead of JSON."""
        async with AsyncClient(
            transport=ASGITransport(app=app_with_handlers), base_url="http://test"
        ) as client:
            response = await client.get("/pages/test/not-found")

            assert response.status_code == 404
            assert "text/html" in response.headers["content-type"]
            html = response.text
            assert "<html" in html.lower()
            assert "not found" in html.lower() or "404" in html


class TestHTTPExceptionHandler:
    """Test suite for FastAPI HTTPException handler."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_http_exception_wrapped_in_consistent_format(
        self, app_with_handlers: FastAPI
    ) -> None:
        """Test HTTPException is wrapped in consistent error format."""
        async with AsyncClient(
            transport=ASGITransport(app=app_with_handlers), base_url="http://test"
        ) as client:
            response = await client.get("/api/v1/test/http-exception")

            assert response.status_code == 503
            assert response.headers["content-type"] == "application/json"
            data = response.json()
            assert "error_code" in data
            assert "message" in data
            assert data["message"] == "Service unavailable"


class TestRequestValidationErrorHandler:
    """Test suite for Pydantic RequestValidationError handler."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_validation_error_returns_422_with_field_errors(
        self, app_with_handlers: FastAPI
    ) -> None:
        """Test RequestValidationError returns 422 with field-level errors.

        This test will fail because we need a route with Pydantic validation.
        The implementer will need to add a test route with a Pydantic model.
        """
        from pydantic import BaseModel, Field

        # Add a test route with validation
        class TestModel(BaseModel):
            email: str = Field(..., pattern=r".+@.+\..+")
            age: int = Field(..., gt=0)

        @app_with_handlers.post("/api/v1/test/validate")
        async def validate_input(data: TestModel):
            return {"status": "ok"}

        async with AsyncClient(
            transport=ASGITransport(app=app_with_handlers), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/test/validate", json={"email": "invalid", "age": -1}
            )

            assert response.status_code == 422
            assert response.headers["content-type"] == "application/json"
            data = response.json()
            assert "error_code" in data
            assert data["error_code"] == "VALIDATION_ERROR"
            assert "details" in data
            # Should have field-level error details
            assert isinstance(data["details"], dict | list)


class TestSQLAlchemyErrorHandler:
    """Test suite for SQLAlchemy error handler."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_sqlalchemy_error_returns_500_sanitised(self, app_with_handlers: FastAPI) -> None:
        """Test SQLAlchemyError returns 500 with sanitised response."""
        async with AsyncClient(
            transport=ASGITransport(app=app_with_handlers), base_url="http://test"
        ) as client:
            response = await client.get("/api/v1/test/sqlalchemy-error")

            assert response.status_code == 500
            assert response.headers["content-type"] == "application/json"
            data = response.json()
            assert "error_code" in data
            assert data["error_code"] == "INTERNAL_ERROR" or data["error_code"] == "DATABASE_ERROR"
            # Should NOT contain full database error in production
            assert "Database connection failed" not in str(data) or "details" not in data


class TestUnhandledExceptionHandler:
    """Test suite for unhandled exception handler."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_unhandled_exception_returns_500_sanitised(
        self, app_with_handlers: FastAPI
    ) -> None:
        """Test unhandled exceptions return 500 with sanitised response."""
        async with AsyncClient(
            transport=ASGITransport(app=app_with_handlers, raise_app_exceptions=False),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/v1/test/unhandled")

            assert response.status_code == 500
            assert response.headers["content-type"] == "application/json"
            data = response.json()
            assert "error_code" in data
            assert data["error_code"] == "INTERNAL_ERROR"
            assert "message" in data
            # Should NOT contain exception details in production
            assert "RuntimeError" not in str(data) or "details" not in data


class TestProductionSanitisation:
    """Test suite for production mode error sanitisation."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_production_mode_strips_stack_traces(self, app_with_handlers: FastAPI) -> None:
        """Test production mode strips stack traces from responses."""
        with patch.dict("os.environ", {"ENVIRONMENT": "production"}):
            async with AsyncClient(
                transport=ASGITransport(app=app_with_handlers, raise_app_exceptions=False),
                base_url="http://test",
            ) as client:
                response = await client.get("/api/v1/test/unhandled")

                assert response.status_code == 500
                data = response.json()
                # Should NOT contain stack trace, file paths, or exception types
                response_str = str(data)
                assert "traceback" not in response_str.lower()
                assert "File " not in response_str
                assert "line " not in response_str.lower()
                assert "/apps/" not in response_str
                assert "/libs/" not in response_str

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_production_mode_strips_internal_paths(self, app_with_handlers: FastAPI) -> None:
        """Test production mode strips internal paths from responses."""
        with patch.dict("os.environ", {"ENVIRONMENT": "production"}):
            async with AsyncClient(
                transport=ASGITransport(app=app_with_handlers), base_url="http://test"
            ) as client:
                response = await client.get("/api/v1/test/sqlalchemy-error")

                assert response.status_code == 500
                data = response.json()
                response_str = str(data)
                # Should NOT contain internal file paths
                assert "/home/" not in response_str
                assert "/apps/webapp" not in response_str
                assert "/libs/core" not in response_str


class TestDevelopmentMode:
    """Test suite for development mode error details."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_development_mode_includes_details(self, app_with_handlers: FastAPI) -> None:
        """Test development mode includes error details and stack traces."""
        with patch.dict("os.environ", {"ENVIRONMENT": "development"}):
            async with AsyncClient(
                transport=ASGITransport(app=app_with_handlers, raise_app_exceptions=False),
                base_url="http://test",
            ) as client:
                response = await client.get("/api/v1/test/unhandled")

                assert response.status_code == 500
                data = response.json()
                # Development mode SHOULD include details
                assert "details" in data or "traceback" in str(data).lower()
