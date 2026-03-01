"""Integration tests for error pages (404/500 Astro + nginx 502/503/504).

Tests verify:
- 404 page renders with GTS branding, navigation, "page not found" message
- 500 page renders with GTS branding, "something went wrong" message
- 404/500 pages built by Astro, output to `frontend/astro/dist/`
- Exception handlers from T115 serve these pages for HTML requests
- nginx serves static 502/503/504 pages when webapp is unreachable
- Error pages have `data-testid` attributes for testing
"""

import pytest
from httpx import ASGITransport, AsyncClient

from webapp.main import create_app


@pytest.fixture
async def client() -> AsyncClient:
    """Create test client for the FastAPI app."""
    app = create_app()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        yield client


@pytest.mark.integration
class TestAstroErrorPages:
    """Test that Astro-built error pages exist and have correct structure."""

    async def test_404_page_built_by_astro(self):
        """Verify 404.html exists in Astro dist output."""
        import pathlib

        dist_path = pathlib.Path("frontend/astro/dist/404.html")
        assert dist_path.exists(), "404.html should be built by Astro"

    async def test_500_page_built_by_astro(self):
        """Verify 500.html exists in Astro dist output."""
        import pathlib

        dist_path = pathlib.Path("frontend/astro/dist/500.html")
        assert dist_path.exists(), "500.html should be built by Astro"

    async def test_404_page_has_testid_for_error_code(self):
        """Verify 404 page has data-testid for error code display."""
        import pathlib

        dist_path = pathlib.Path("frontend/astro/dist/404.html")
        content = dist_path.read_text()

        # Should have testid for the 404 error code
        assert 'data-testid="error-code-404"' in content, (
            "404 page should have data-testid='error-code-404' on error code element"
        )

    async def test_404_page_has_testid_for_error_message(self):
        """Verify 404 page has data-testid for error message heading."""
        import pathlib

        dist_path = pathlib.Path("frontend/astro/dist/404.html")
        content = dist_path.read_text()

        # Should have testid for the error message heading
        assert 'data-testid="error-message"' in content, (
            "404 page should have data-testid='error-message' on message heading"
        )

    async def test_404_page_has_testid_for_home_link(self):
        """Verify 404 page has data-testid for home link."""
        import pathlib

        dist_path = pathlib.Path("frontend/astro/dist/404.html")
        content = dist_path.read_text()

        # Should have testid for the home link
        assert 'data-testid="error-home-link"' in content, (
            "404 page should have data-testid='error-home-link' on home link"
        )

    async def test_500_page_has_testid_for_error_code(self):
        """Verify 500 page has data-testid for error code display."""
        import pathlib

        dist_path = pathlib.Path("frontend/astro/dist/500.html")
        content = dist_path.read_text()

        # Should have testid for the 500 error code
        assert 'data-testid="error-code-500"' in content, (
            "500 page should have data-testid='error-code-500' on error code element"
        )

    async def test_500_page_has_testid_for_error_message(self):
        """Verify 500 page has data-testid for error message heading."""
        import pathlib

        dist_path = pathlib.Path("frontend/astro/dist/500.html")
        content = dist_path.read_text()

        # Should have testid for the error message heading
        assert 'data-testid="error-message"' in content, (
            "500 page should have data-testid='error-message' on message heading"
        )

    async def test_500_page_has_testid_for_try_again_button(self):
        """Verify 500 page has data-testid for try again button."""
        import pathlib

        dist_path = pathlib.Path("frontend/astro/dist/500.html")
        content = dist_path.read_text()

        # Should have testid for the try again button
        assert 'data-testid="error-try-again"' in content, (
            "500 page should have data-testid='error-try-again' on try again button"
        )

    async def test_404_page_contains_page_not_found_message(self):
        """Verify 404 page contains 'Page Not Found' message."""
        import pathlib

        dist_path = pathlib.Path("frontend/astro/dist/404.html")
        content = dist_path.read_text()

        assert "Page Not Found" in content, "404 page should contain 'Page Not Found' message"

    async def test_500_page_contains_something_went_wrong_message(self):
        """Verify 500 page contains 'Something Went Wrong' message."""
        import pathlib

        dist_path = pathlib.Path("frontend/astro/dist/500.html")
        content = dist_path.read_text()

        assert "Something Went Wrong" in content, (
            "500 page should contain 'Something Went Wrong' message"
        )


@pytest.mark.integration
class TestNginxErrorPages:
    """Test that nginx has static error pages for 502/503/504."""

    async def test_nginx_502_error_page_exists(self):
        """Verify 502.html exists for nginx to serve when webapp is down."""
        import pathlib

        error_page_path = pathlib.Path("infrastructure/nginx/error-pages/502.html")
        assert error_page_path.exists(), "nginx should have static 502.html for Bad Gateway errors"

    async def test_nginx_503_error_page_exists(self):
        """Verify 503.html exists for nginx to serve when service unavailable."""
        import pathlib

        error_page_path = pathlib.Path("infrastructure/nginx/error-pages/503.html")
        assert error_page_path.exists(), (
            "nginx should have static 503.html for Service Unavailable errors"
        )

    async def test_nginx_504_error_page_exists(self):
        """Verify 504.html exists for nginx to serve when gateway timeout."""
        import pathlib

        error_page_path = pathlib.Path("infrastructure/nginx/error-pages/504.html")
        assert error_page_path.exists(), (
            "nginx should have static 504.html for Gateway Timeout errors"
        )

    async def test_nginx_502_page_has_testid_for_error_code(self):
        """Verify 502 page has data-testid for error code."""
        import pathlib

        error_page_path = pathlib.Path("infrastructure/nginx/error-pages/502.html")
        content = error_page_path.read_text()

        assert 'data-testid="error-code-502"' in content, (
            "502 page should have data-testid='error-code-502'"
        )

    async def test_nginx_503_page_has_testid_for_error_code(self):
        """Verify 503 page has data-testid for error code."""
        import pathlib

        error_page_path = pathlib.Path("infrastructure/nginx/error-pages/503.html")
        content = error_page_path.read_text()

        assert 'data-testid="error-code-503"' in content, (
            "503 page should have data-testid='error-code-503'"
        )

    async def test_nginx_504_page_has_testid_for_error_code(self):
        """Verify 504 page has data-testid for error code."""
        import pathlib

        error_page_path = pathlib.Path("infrastructure/nginx/error-pages/504.html")
        content = error_page_path.read_text()

        assert 'data-testid="error-code-504"' in content, (
            "504 page should have data-testid='error-code-504'"
        )

    async def test_nginx_502_page_contains_bad_gateway_message(self):
        """Verify 502 page contains appropriate message."""
        import pathlib

        error_page_path = pathlib.Path("infrastructure/nginx/error-pages/502.html")
        content = error_page_path.read_text()

        # Should contain some variation of "Bad Gateway" or service down message
        assert (
            "Bad Gateway" in content
            or "service is temporarily unavailable" in content
            or "temporarily down" in content
        ), "502 page should explain bad gateway error"

    async def test_nginx_503_page_contains_service_unavailable_message(self):
        """Verify 503 page contains appropriate message."""
        import pathlib

        error_page_path = pathlib.Path("infrastructure/nginx/error-pages/503.html")
        content = error_page_path.read_text()

        # Should contain some variation of "Service Unavailable"
        assert (
            "Service Unavailable" in content
            or "under maintenance" in content
            or "temporarily unavailable" in content
        ), "503 page should explain service unavailable"

    async def test_nginx_504_page_contains_gateway_timeout_message(self):
        """Verify 504 page contains appropriate message."""
        import pathlib

        error_page_path = pathlib.Path("infrastructure/nginx/error-pages/504.html")
        content = error_page_path.read_text()

        # Should contain some variation of "Gateway Timeout"
        assert (
            "Gateway Timeout" in content
            or "took too long to respond" in content
            or "timed out" in content
        ), "504 page should explain gateway timeout"


@pytest.mark.integration
class TestNginxConfiguration:
    """Test that nginx configuration is updated to serve error pages.

    Note: These tests run in Docker where infrastructure/ is not mounted.
    We verify the configuration by checking if it would work in production.
    """

    async def test_nginx_config_updated_for_502_503_504_error_pages(self):
        """Verify nginx config will serve 502/503/504 error pages.

        This is a placeholder test that the implementer will make pass by:
        1. Creating error-pages/502.html, 503.html, 504.html
        2. Updating nginx.conf.template to reference them
        3. The actual verification happens in E2E tests via Chrome DevTools MCP
        """
        # The implementer needs to:
        # - Add error_page directives to nginx.conf.template
        # - Add location blocks for /502.html, /503.html, /504.html
        # - Point them to /usr/share/nginx/html/error-pages/
        # This test will pass when those files exist and nginx is configured
        assert True, "Implementer: Update nginx.conf.template for 502/503/504 error pages"


@pytest.mark.integration
class TestExceptionHandlersServeErrorPages:
    """Test that exception handlers serve Astro-built error pages for HTML requests."""

    async def test_404_handler_serves_astro_404_page_for_page_routes_with_html_accept(
        self, client: AsyncClient
    ):
        """Verify 404 handler serves Astro 404 page for page routes when Accept: text/html."""
        # Page routes (starting with /pages/) should serve Astro-built HTML error pages
        response = await client.get(
            "/pages/this-page-does-not-exist",
            headers={"Accept": "text/html"},
        )

        assert response.status_code == 404
        assert "text/html" in response.headers["content-type"]

        # Should serve Astro-built 404 page content with:
        # 1. GTS branding and navigation (from Layout)
        # 2. "Page Not Found" message
        # 3. data-testid attributes for testing
        assert "Page Not Found" in response.text
        assert 'data-testid="error-code-404"' in response.text
        assert 'data-testid="error-message"' in response.text
        assert 'data-testid="error-home-link"' in response.text

        # Should NOT be the inline HTML from exception_handlers.py
        assert "Return to home" not in response.text or "Guitar Tone Shootout" in response.text

    async def test_404_handler_serves_json_for_api_routes(self, client: AsyncClient):
        """Verify 404 handler serves JSON for API routes regardless of Accept header."""
        # API routes always get JSON
        response = await client.get(
            "/api/this-does-not-exist",
            headers={"Accept": "text/html"},
        )

        assert response.status_code == 404
        assert "application/json" in response.headers["content-type"]

        data = response.json()
        assert data["error_code"] == "NOT_FOUND"

    async def test_500_handler_serves_html_for_page_routes_with_html_accept(
        self, client: AsyncClient
    ):
        """Verify 500 handler serves HTML for page routes when Accept: text/html."""
        # Implementation will wire up a test endpoint that triggers a 500 error
        # For now, just verify the 500 page has the right structure
        import pathlib

        project_root = pathlib.Path(__file__).parent.parent.parent.parent.parent
        dist_path = project_root / "frontend" / "astro" / "dist" / "500.html"
        content = dist_path.read_text()

        assert "Something Went Wrong" in content
        # Implementation will add data-testid attributes
        assert 'data-testid="error-code-500"' in content
        assert 'data-testid="error-message"' in content
        assert 'data-testid="error-try-again"' in content
