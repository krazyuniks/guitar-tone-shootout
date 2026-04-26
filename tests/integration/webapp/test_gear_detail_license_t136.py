"""Integration tests for license text on gear detail pages (T136).

Tests that the gear detail page correctly renders a collapsible license
section that is gear-specific, has default community text, is hidden
when no license exists, and is keyboard-accessible.

Each test creates its own gear via the ``make_gear`` factory rather than
querying for seed data — see Story 04 of Epic #120 for the migration
rationale (UUID-suffixed fixtures avoid real DB data collisions).
"""

from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from gts.domain.value_objects.signal_chain_enums import GearType, ModelSize, Platform
from webapp.adapters.persistence.models.gear import Gear
from webapp.adapters.persistence.models.gear_model import GearModel
from webapp.main import app


@pytest.mark.asyncio
@pytest.mark.integration
class TestGearDetailLicenseSection:
    """Integration tests for license text on gear detail pages (T136)."""

    async def test_gear_detail_includes_license_section_testid(
        self,
        make_gear,
    ) -> None:
        """Verify gear detail page includes a license section with data-testid."""
        gear = await make_gear(GearType.AMP, Platform.NAM, models=1)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(f"/gear/{gear.slug}")

        html = response.text
        assert response.status_code == 200
        assert 'data-testid="license-section"' in html, (
            "License section must have data-testid='license-section'"
        )

    async def test_license_section_is_collapsible_details_element(
        self,
        make_gear,
    ) -> None:
        """Verify license section uses <details>/<summary> for collapsibility and keyboard access."""
        gear = await make_gear(GearType.AMP, Platform.NAM, models=1)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(f"/gear/{gear.slug}")

        html = response.text
        assert response.status_code == 200
        assert "<details" in html and "<summary" in html, (
            "License section must use <details>/<summary> elements "
            "for collapsibility and keyboard accessibility"
        )

    async def test_license_section_shows_default_community_text(
        self,
        make_gear,
    ) -> None:
        """Verify default community license text shown inside the collapsible section.

        When gear has no specific license_text, the default community-
        contributed text should appear inside the collapsible <details> element.
        """
        gear = await make_gear(GearType.AMP, Platform.NAM, models=1)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(f"/gear/{gear.slug}")

        html = response.text
        assert response.status_code == 200
        assert 'data-testid="license-section"' in html, (
            "License section with data-testid must exist for community gear"
        )
        assert "download and use" in html.lower(), (
            "Default community license text should mention download and use rights"
        )

    async def test_pack_dict_includes_license_text_field(
        self,
        db_session: AsyncSession,
        make_gear,
    ) -> None:
        """Verify _gear_to_detail_pack includes license_text in the pack dict.

        The template needs pack.license_text to conditionally render
        gear-specific license text vs default community text.
        """
        from webapp.api.pages import _gear_to_detail_pack

        gear = await make_gear(GearType.AMP, Platform.NAM, models=1)
        await db_session.refresh(gear, ["models", "source", "tags"])

        pack = _gear_to_detail_pack(gear)
        assert "license_text" in pack, (
            "_gear_to_detail_pack must include 'license_text' in the returned dict"
        )

    async def test_gear_specific_license_text_rendered_when_available(
        self,
        db_session: AsyncSession,
        make_gear,
    ) -> None:
        """Verify gear-specific license text is rendered when the gear has one."""
        gear = await make_gear(GearType.AMP, Platform.NAM, models=1)

        specific_license = "This gear is licensed under Creative Commons BY-NC 4.0."
        gear.license_text = specific_license
        await db_session.commit()

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(f"/gear/{gear.slug}")

        html = response.text
        assert response.status_code == 200
        assert specific_license in html, (
            "Gear-specific license text should be rendered on the detail page"
        )

    async def test_no_license_section_when_no_license_exists(
        self,
        db_session: AsyncSession,
    ) -> None:
        """Verify license section is NOT shown when gear has no license text and no source.

        When license_text is None/empty AND the gear has no source,
        no empty license section should appear.
        """
        suffix = uuid4().hex[:8]
        gear = Gear(
            id=uuid4(),
            name=f"No License Gear Test {suffix}",
            slug=f"no-license-gear-test-{suffix}",
            gear_type=GearType.AMP,
            platform=Platform.NAM,
            description="A gear item with no license",
            manufacturer="TestMfg",
            is_public=True,
            source_id=None,
        )
        db_session.add(gear)
        await db_session.flush()

        model = GearModel(
            id=uuid4(),
            gear_id=gear.id,
            platform=Platform.NAM,
            size=ModelSize.STANDARD,
        )
        db_session.add(model)
        await db_session.commit()

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(f"/gear/{gear.slug}")

        html = response.text
        assert response.status_code == 200
        assert 'data-testid="license-section"' not in html, (
            "License section should not appear when gear has no license text and no source"
        )
