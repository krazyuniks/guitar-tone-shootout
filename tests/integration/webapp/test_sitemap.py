"""Integration tests for dynamic sitemap.xml endpoint.

Tests verify:
- GET /sitemap.xml returns valid XML
- Includes static pages (homepage, about, gear browse, shootouts)
- Includes public gear detail pages
- Includes public shootout pages
- Uses PUBLIC_URL env var for absolute URLs
- Includes lastmod, changefreq, priority attributes
- Response has Content-Type: application/xml
- No authentication required
"""

import os
from datetime import datetime
from uuid import uuid4
from xml.etree import ElementTree as ET

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from core.domain.value_objects.signal_chain_enums import GearType, Platform
from webapp.adapters.persistence.models.gear import Gear
from webapp.adapters.persistence.models.shootout import Shootout, ShootoutStatus
from webapp.adapters.persistence.models.user import User
from webapp.auth.dependencies import set_session_override
from webapp.main import create_app


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncClient:
    """Create test client for the FastAPI app."""
    # Override session to use test database
    set_session_override(db_session)

    app = create_app()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        yield client

    # Cleanup
    set_session_override(None)


@pytest.fixture
async def public_gear(db_session: AsyncSession) -> Gear:
    """Create a public gear item for testing."""
    gear = Gear(
        id=uuid4(),
        name="Test Amp",
        slug="test-amp",
        gear_type=GearType.AMP,
        platform=Platform.NAM,
        description="Test amp for sitemap",
        manufacturer="Test Brand",
        is_public=True,
    )
    db_session.add(gear)
    await db_session.commit()
    await db_session.refresh(gear)
    return gear


@pytest.fixture
async def private_gear(db_session: AsyncSession) -> Gear:
    """Create a private gear item for testing."""
    gear = Gear(
        id=uuid4(),
        name="Private Amp",
        slug="private-amp",
        gear_type=GearType.AMP,
        platform=Platform.NAM,
        description="Private amp - should not appear in sitemap",
        manufacturer="Test Brand",
        is_public=False,
    )
    db_session.add(gear)
    await db_session.commit()
    await db_session.refresh(gear)
    return gear


@pytest.fixture
async def completed_shootout(db_session: AsyncSession, test_user: User) -> Shootout:
    """Create a completed shootout for testing."""
    shootout = Shootout(
        id=uuid4(),
        user_id=test_user.id,
        name="Test Shootout",
        status=ShootoutStatus.COMPLETED,
    )
    db_session.add(shootout)
    await db_session.flush()
    return shootout


@pytest.fixture
async def draft_shootout(db_session: AsyncSession, test_user: User) -> Shootout:
    """Create a draft shootout for testing."""
    shootout = Shootout(
        id=uuid4(),
        user_id=test_user.id,
        name="Draft Shootout",
        status=ShootoutStatus.DRAFT,
    )
    db_session.add(shootout)
    await db_session.flush()
    return shootout


@pytest.mark.integration
class TestSitemapEndpoint:
    """Test sitemap.xml endpoint returns valid XML with public content."""

    async def test_sitemap_endpoint_exists(self, client: AsyncClient):
        """Verify /sitemap.xml endpoint responds."""
        response = await client.get("/sitemap.xml")

        # Should return 200 OK (not 404)
        assert response.status_code == 200, "sitemap.xml endpoint should exist"

    async def test_sitemap_returns_xml_content_type(self, client: AsyncClient):
        """Verify response has application/xml content type."""
        response = await client.get("/sitemap.xml")

        assert response.status_code == 200
        assert "application/xml" in response.headers["content-type"], (
            "sitemap.xml should return application/xml content type"
        )

    async def test_sitemap_returns_valid_xml(self, client: AsyncClient):
        """Verify response is valid XML that can be parsed."""
        response = await client.get("/sitemap.xml")

        assert response.status_code == 200

        # Should be parseable XML
        try:
            root = ET.fromstring(response.text)
        except ET.ParseError as e:
            pytest.fail(f"sitemap.xml returned invalid XML: {e}")

        # Root element should be <urlset>
        assert root.tag.endswith("urlset"), "sitemap.xml root element should be <urlset>"

    async def test_sitemap_uses_correct_namespace(self, client: AsyncClient):
        """Verify sitemap uses correct XML namespace."""
        response = await client.get("/sitemap.xml")

        assert response.status_code == 200
        root = ET.fromstring(response.text)

        # Should use sitemap protocol namespace
        assert "http://www.sitemaps.org/schemas/sitemap/0.9" in root.tag, (
            "sitemap.xml should use http://www.sitemaps.org/schemas/sitemap/0.9 namespace"
        )

    async def test_sitemap_requires_no_authentication(self, client: AsyncClient):
        """Verify sitemap.xml does not require authentication."""
        # No Authorization header - should still work
        response = await client.get("/sitemap.xml")

        assert response.status_code == 200, "sitemap.xml should not require authentication"


@pytest.mark.integration
class TestSitemapStaticPages:
    """Test sitemap includes static pages."""

    async def test_sitemap_includes_homepage(self, client: AsyncClient):
        """Verify sitemap includes homepage."""
        response = await client.get("/sitemap.xml")

        assert response.status_code == 200

        public_url = os.getenv("PUBLIC_URL", "http://testserver")
        expected_url = f"{public_url}/"

        assert expected_url in response.text, (
            f"sitemap.xml should include homepage URL: {expected_url}"
        )

    async def test_sitemap_includes_about_page(self, client: AsyncClient):
        """Verify sitemap includes /about page."""
        response = await client.get("/sitemap.xml")

        assert response.status_code == 200

        public_url = os.getenv("PUBLIC_URL", "http://testserver")
        expected_url = f"{public_url}/about"

        assert expected_url in response.text, (
            f"sitemap.xml should include about page URL: {expected_url}"
        )

    async def test_sitemap_includes_gear_browse_page(self, client: AsyncClient):
        """Verify sitemap includes /gear browse page."""
        response = await client.get("/sitemap.xml")

        assert response.status_code == 200

        public_url = os.getenv("PUBLIC_URL", "http://testserver")
        expected_url = f"{public_url}/gear"

        assert expected_url in response.text, (
            f"sitemap.xml should include gear browse page URL: {expected_url}"
        )

    async def test_sitemap_includes_shootouts_page(self, client: AsyncClient):
        """Verify sitemap includes /shootouts page."""
        response = await client.get("/sitemap.xml")

        assert response.status_code == 200

        public_url = os.getenv("PUBLIC_URL", "http://testserver")
        expected_url = f"{public_url}/shootouts"

        assert expected_url in response.text, (
            f"sitemap.xml should include shootouts page URL: {expected_url}"
        )


@pytest.mark.integration
class TestSitemapDynamicContent:
    """Test sitemap includes dynamic content (gear, shootouts)."""

    async def test_sitemap_includes_public_gear_detail_page(
        self, client: AsyncClient, public_gear: Gear
    ):
        """Verify sitemap includes public gear detail pages."""
        response = await client.get("/sitemap.xml")

        assert response.status_code == 200

        public_url = os.getenv("PUBLIC_URL", "http://testserver")
        expected_url = f"{public_url}/gear/{public_gear.slug}"

        assert expected_url in response.text, (
            f"sitemap.xml should include public gear detail URL: {expected_url}"
        )

    async def test_sitemap_excludes_private_gear(
        self, client: AsyncClient, public_gear: Gear, private_gear: Gear
    ):
        """Verify sitemap excludes private (non-public) gear."""
        response = await client.get("/sitemap.xml")

        assert response.status_code == 200

        public_url = os.getenv("PUBLIC_URL", "http://testserver")
        public_gear_url = f"{public_url}/gear/{public_gear.slug}"
        private_gear_url = f"{public_url}/gear/{private_gear.slug}"

        # Public gear should be included
        assert public_gear_url in response.text, "sitemap.xml should include public gear"

        # Private gear should NOT be included
        assert private_gear_url not in response.text, "sitemap.xml should exclude private gear"

    async def test_sitemap_includes_completed_shootout(
        self, client: AsyncClient, completed_shootout: Shootout
    ):
        """Verify sitemap includes completed shootouts."""
        response = await client.get("/sitemap.xml")

        assert response.status_code == 200

        public_url = os.getenv("PUBLIC_URL", "http://testserver")
        expected_url = f"{public_url}/shootouts/{completed_shootout.id}"

        assert expected_url in response.text, (
            f"sitemap.xml should include completed shootout URL: {expected_url}"
        )

    async def test_sitemap_excludes_draft_shootout(
        self, client: AsyncClient, completed_shootout: Shootout, draft_shootout: Shootout
    ):
        """Verify sitemap excludes draft/incomplete shootouts."""
        response = await client.get("/sitemap.xml")

        assert response.status_code == 200

        public_url = os.getenv("PUBLIC_URL", "http://testserver")
        completed_url = f"{public_url}/shootouts/{completed_shootout.id}"
        draft_url = f"{public_url}/shootouts/{draft_shootout.id}"

        # Completed shootout should be included
        assert completed_url in response.text, "sitemap.xml should include completed shootouts"

        # Draft shootout should NOT be included
        assert draft_url not in response.text, "sitemap.xml should exclude draft shootouts"


@pytest.mark.integration
class TestSitemapAttributes:
    """Test sitemap includes required XML attributes."""

    async def test_sitemap_urls_have_lastmod(self, client: AsyncClient):
        """Verify sitemap <url> entries have <lastmod> element."""
        response = await client.get("/sitemap.xml")

        assert response.status_code == 200
        root = ET.fromstring(response.text)

        # Find all <url> elements (accounting for namespace)
        ns = {"sitemap": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        urls = root.findall("sitemap:url", ns)

        assert len(urls) > 0, "sitemap.xml should contain at least one <url>"

        # Check that at least one URL has <lastmod>
        has_lastmod = any(url.find("sitemap:lastmod", ns) is not None for url in urls)
        assert has_lastmod, "sitemap.xml <url> entries should have <lastmod>"

    async def test_sitemap_urls_have_changefreq(self, client: AsyncClient):
        """Verify sitemap <url> entries have <changefreq> element."""
        response = await client.get("/sitemap.xml")

        assert response.status_code == 200
        root = ET.fromstring(response.text)

        ns = {"sitemap": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        urls = root.findall("sitemap:url", ns)

        assert len(urls) > 0, "sitemap.xml should contain at least one <url>"

        # Check that at least one URL has <changefreq>
        has_changefreq = any(url.find("sitemap:changefreq", ns) is not None for url in urls)
        assert has_changefreq, "sitemap.xml <url> entries should have <changefreq>"

    async def test_sitemap_urls_have_priority(self, client: AsyncClient):
        """Verify sitemap <url> entries have <priority> element."""
        response = await client.get("/sitemap.xml")

        assert response.status_code == 200
        root = ET.fromstring(response.text)

        ns = {"sitemap": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        urls = root.findall("sitemap:url", ns)

        assert len(urls) > 0, "sitemap.xml should contain at least one <url>"

        # Check that at least one URL has <priority>
        has_priority = any(url.find("sitemap:priority", ns) is not None for url in urls)
        assert has_priority, "sitemap.xml <url> entries should have <priority>"

    async def test_sitemap_lastmod_uses_valid_format(self, client: AsyncClient):
        """Verify <lastmod> uses W3C Datetime format (ISO 8601)."""
        response = await client.get("/sitemap.xml")

        assert response.status_code == 200
        root = ET.fromstring(response.text)

        ns = {"sitemap": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        lastmod_elements = root.findall(".//sitemap:lastmod", ns)

        assert len(lastmod_elements) > 0, "sitemap.xml should have <lastmod> elements"

        # Check first lastmod uses valid ISO 8601 format
        lastmod_text = lastmod_elements[0].text
        try:
            # Should be parseable as ISO 8601 datetime
            datetime.fromisoformat(lastmod_text.replace("Z", "+00:00"))
        except ValueError as e:
            pytest.fail(f"<lastmod> should use ISO 8601 format, got: {lastmod_text} ({e})")

    async def test_sitemap_changefreq_uses_valid_value(self, client: AsyncClient):
        """Verify <changefreq> uses valid sitemap protocol values."""
        response = await client.get("/sitemap.xml")

        assert response.status_code == 200
        root = ET.fromstring(response.text)

        ns = {"sitemap": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        changefreq_elements = root.findall(".//sitemap:changefreq", ns)

        assert len(changefreq_elements) > 0, "sitemap.xml should have <changefreq> elements"

        valid_values = {"always", "hourly", "daily", "weekly", "monthly", "yearly", "never"}

        for elem in changefreq_elements:
            assert elem.text in valid_values, (
                f"<changefreq> should use valid value, got: {elem.text}"
            )

    async def test_sitemap_priority_uses_valid_range(self, client: AsyncClient):
        """Verify <priority> uses value between 0.0 and 1.0."""
        response = await client.get("/sitemap.xml")

        assert response.status_code == 200
        root = ET.fromstring(response.text)

        ns = {"sitemap": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        priority_elements = root.findall(".//sitemap:priority", ns)

        assert len(priority_elements) > 0, "sitemap.xml should have <priority> elements"

        for elem in priority_elements:
            priority = float(elem.text)
            assert 0.0 <= priority <= 1.0, (
                f"<priority> should be between 0.0 and 1.0, got: {priority}"
            )


@pytest.mark.integration
class TestSitemapPublicUrl:
    """Test sitemap uses PUBLIC_URL environment variable."""

    async def test_sitemap_uses_public_url_env_var(self, client: AsyncClient, monkeypatch):
        """Verify sitemap uses PUBLIC_URL for absolute URLs."""
        # Set a custom PUBLIC_URL
        test_url = "https://example.com"
        monkeypatch.setenv("PUBLIC_URL", test_url)

        # Need to recreate app for env var to take effect
        app = create_app()
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as test_client:
            response = await test_client.get("/sitemap.xml")

        assert response.status_code == 200

        # URLs should use the custom PUBLIC_URL
        assert test_url in response.text, f"sitemap.xml should use PUBLIC_URL env var: {test_url}"

    async def test_sitemap_urls_are_absolute(self, client: AsyncClient):
        """Verify all URLs in sitemap are absolute (not relative)."""
        response = await client.get("/sitemap.xml")

        assert response.status_code == 200
        root = ET.fromstring(response.text)

        ns = {"sitemap": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        loc_elements = root.findall(".//sitemap:loc", ns)

        assert len(loc_elements) > 0, "sitemap.xml should have <loc> elements"

        for elem in loc_elements:
            url = elem.text
            assert url.startswith("http://") or url.startswith("https://"), (
                f"sitemap URLs should be absolute, got: {url}"
            )
