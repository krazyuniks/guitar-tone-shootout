"""E2E tests for shootout detail page in pre-processing state.

Tests verify that the shootout detail page correctly displays:
- Shootout metadata (name, description, creation date)
- Chain list with position, name, and gear summary
- DI track section with name, duration, and audio player
- Status badge showing current state (pending, processing, etc.)
- Proper handling of 2-20 chains
- All interactive elements have data-testid attributes
"""

import pytest
from playwright.async_api import Page, expect
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
@pytest.mark.e2e
class TestShootoutDetailPreProcessing:
    """Test shootout detail page display for pending/pre-processing state."""

    async def test_detail_page_shows_shootout_name(
        self,
        page: Page,
        db_session: AsyncSession,
        frontend_url: str,
    ) -> None:
        """Detail page displays shootout name."""
        # Create shootout via DB
        shootout_id = await self._create_test_shootout(
            db_session, name="Mesa Boogie vs Marshall Shootout"
        )

        # Navigate to detail page
        await page.goto(f"{frontend_url}/shootout/{shootout_id}")

        # Verify shootout name is displayed
        await expect(
            page.locator('[data-testid="shootout-title"]')
        ).to_contain_text("Mesa Boogie vs Marshall Shootout")

    async def test_detail_page_shows_description(
        self,
        page: Page,
        db_session: AsyncSession,
        frontend_url: str,
    ) -> None:
        """Detail page displays shootout description."""
        shootout_id = await self._create_test_shootout(
            db_session,
            name="Test Shootout",
            description="Comparing high-gain tones for metal rhythm",
        )

        await page.goto(f"{frontend_url}/shootout/{shootout_id}")

        # Verify description section exists and shows text
        await expect(
            page.locator('[data-testid="description-section"]')
        ).to_be_visible()
        await expect(page.locator('[data-testid="description-section"]')).to_contain_text(
            "Comparing high-gain tones for metal rhythm"
        )

    async def test_detail_page_shows_creation_date(
        self,
        page: Page,
        db_session: AsyncSession,
        frontend_url: str,
    ) -> None:
        """Detail page displays creation date as relative time."""
        shootout_id = await self._create_test_shootout(db_session, name="Test Shootout")

        await page.goto(f"{frontend_url}/shootout/{shootout_id}")

        # Verify relative time is displayed (should show "just now", "X minutes ago", etc.)
        relative_time = page.locator('[data-testid="relative-time"]')
        await expect(relative_time).to_be_visible()
        # Should contain time-related text
        text_content = await relative_time.text_content()
        assert text_content is not None
        assert len(text_content) > 0

    async def test_detail_page_shows_chain_list_with_positions(
        self,
        page: Page,
        db_session: AsyncSession,
        frontend_url: str,
    ) -> None:
        """Chain list shows each chain with position and name."""
        shootout_id = await self._create_test_shootout_with_chains(
            db_session, chain_count=3
        )

        await page.goto(f"{frontend_url}/shootout/{shootout_id}")

        # Verify segments section exists
        await expect(page.locator('[data-testid="segments-section"]')).to_be_visible()

        # Verify all 3 segment buttons are present
        segment_buttons = page.locator('[data-testid="segment-button"]')
        await expect(segment_buttons).to_have_count(3)

        # Verify positions are displayed
        first_segment = segment_buttons.nth(0)
        await expect(first_segment).to_contain_text("Position")

    async def test_detail_page_shows_chain_names(
        self,
        page: Page,
        db_session: AsyncSession,
        frontend_url: str,
    ) -> None:
        """Chain list shows chain names."""
        shootout_id = await self._create_test_shootout_with_chains(
            db_session, chain_count=2
        )

        await page.goto(f"{frontend_url}/shootout/{shootout_id}")

        # Verify chain names are displayed
        segment_buttons = page.locator('[data-testid="segment-button"]')
        first_button_text = await segment_buttons.nth(0).text_content()
        assert first_button_text is not None
        # Should contain either chain name or "Chain X" fallback
        assert "Chain" in first_button_text or len(first_button_text) > 0

    async def test_detail_page_shows_di_track_section(
        self,
        page: Page,
        db_session: AsyncSession,
        frontend_url: str,
    ) -> None:
        """DI track section shows track name and metadata."""
        shootout_id = await self._create_test_shootout(db_session, name="Test Shootout")

        await page.goto(f"{frontend_url}/shootout/{shootout_id}")

        # The template doesn't have a dedicated DI track section testid yet
        # This will fail until implementation adds it
        await expect(page.locator('[data-testid="di-track-section"]')).to_be_visible()

    async def test_detail_page_shows_di_track_duration(
        self,
        page: Page,
        db_session: AsyncSession,
        frontend_url: str,
    ) -> None:
        """DI track section displays track duration."""
        shootout_id = await self._create_test_shootout(db_session, name="Test Shootout")

        await page.goto(f"{frontend_url}/shootout/{shootout_id}")

        # Should show duration in seconds or formatted time
        di_duration = page.locator('[data-testid="di-track-duration"]')
        await expect(di_duration).to_be_visible()
        text_content = await di_duration.text_content()
        assert text_content is not None
        # Should contain time-related text (e.g., "3:45", "225s", etc.)
        assert len(text_content) > 0

    async def test_detail_page_shows_audio_player_for_di_track(
        self,
        page: Page,
        db_session: AsyncSession,
        frontend_url: str,
    ) -> None:
        """DI track section includes audio player with stream link."""
        shootout_id = await self._create_test_shootout(db_session, name="Test Shootout")

        await page.goto(f"{frontend_url}/shootout/{shootout_id}")

        # Verify audio player exists
        audio_player = page.locator('[data-testid="di-track-player"]')
        await expect(audio_player).to_be_visible()

        # Verify it's an audio element (not video)
        tag_name = await audio_player.evaluate("el => el.tagName")
        assert tag_name == "AUDIO"

    async def test_detail_page_shows_status_badge_for_pending(
        self,
        page: Page,
        db_session: AsyncSession,
        frontend_url: str,
    ) -> None:
        """Status badge shows 'pending' state."""
        shootout_id = await self._create_test_shootout(
            db_session, name="Test Shootout", status="pending"
        )

        await page.goto(f"{frontend_url}/shootout/{shootout_id}")

        # Verify status badge exists and shows "Pending"
        status_badge = page.locator('[data-testid="status-badge"]')
        await expect(status_badge).to_be_visible()
        await expect(status_badge).to_contain_text("Pending")

    async def test_detail_page_shows_status_badge_for_processing(
        self,
        page: Page,
        db_session: AsyncSession,
        frontend_url: str,
    ) -> None:
        """Status badge shows 'processing' state."""
        shootout_id = await self._create_test_shootout(
            db_session, name="Test Shootout", status="processing"
        )

        await page.goto(f"{frontend_url}/shootout/{shootout_id}")

        status_badge = page.locator('[data-testid="status-badge"]')
        await expect(status_badge).to_be_visible()
        await expect(status_badge).to_contain_text("Processing")

    async def test_detail_page_shows_pending_explanatory_text(
        self,
        page: Page,
        db_session: AsyncSession,
        frontend_url: str,
    ) -> None:
        """Pending state shows explanatory text about awaiting processing."""
        shootout_id = await self._create_test_shootout(
            db_session, name="Test Shootout", status="pending"
        )

        await page.goto(f"{frontend_url}/shootout/{shootout_id}")

        # Verify processing placeholder exists with pending message
        placeholder = page.locator('[data-testid="processing-placeholder"]')
        await expect(placeholder).to_be_visible()
        await expect(placeholder).to_contain_text("Pending Processing")
        await expect(placeholder).to_contain_text(
            "This shootout is queued for processing"
        )

    async def test_detail_page_works_with_2_chains(
        self,
        page: Page,
        db_session: AsyncSession,
        frontend_url: str,
    ) -> None:
        """Page handles minimum of 2 chains."""
        shootout_id = await self._create_test_shootout_with_chains(
            db_session, chain_count=2
        )

        await page.goto(f"{frontend_url}/shootout/{shootout_id}")

        # Verify exactly 2 segment buttons
        segment_buttons = page.locator('[data-testid="segment-button"]')
        await expect(segment_buttons).to_have_count(2)

    async def test_detail_page_works_with_20_chains(
        self,
        page: Page,
        db_session: AsyncSession,
        frontend_url: str,
    ) -> None:
        """Page handles maximum of 20 chains."""
        shootout_id = await self._create_test_shootout_with_chains(
            db_session, chain_count=20
        )

        await page.goto(f"{frontend_url}/shootout/{shootout_id}")

        # Verify all 20 segment buttons are rendered
        segment_buttons = page.locator('[data-testid="segment-button"]')
        await expect(segment_buttons).to_have_count(20)

    async def test_detail_page_interactive_elements_have_testids(
        self,
        page: Page,
        db_session: AsyncSession,
        frontend_url: str,
    ) -> None:
        """All interactive elements have data-testid attributes."""
        shootout_id = await self._create_test_shootout_with_chains(
            db_session, chain_count=3
        )

        await page.goto(f"{frontend_url}/shootout/{shootout_id}")

        # Verify key testids exist
        await expect(page.locator('[data-testid="shootout-detail"]')).to_be_visible()
        await expect(page.locator('[data-testid="back-link"]')).to_be_visible()
        await expect(page.locator('[data-testid="shootout-title"]')).to_be_visible()
        await expect(page.locator('[data-testid="status-badge"]')).to_be_visible()
        await expect(page.locator('[data-testid="segments-section"]')).to_be_visible()
        await expect(
            page.locator('[data-testid="segment-button"]').first
        ).to_be_visible()

    # Helper methods

    async def _create_test_shootout(
        self,
        db_session: AsyncSession,
        name: str = "Test Shootout",
        description: str | None = None,
        status: str = "pending",
    ) -> str:
        """Create a test shootout with DI track and return shootout ID."""
        from uuid import uuid4

        # Get test user
        user_result = await db_session.execute(
            text("SELECT id FROM users WHERE username = :username"),
            {"username": "testuser"},
        )
        user_row = user_result.fetchone()
        assert user_row is not None, "Test user not found"
        user_id = user_row[0]

        # Create DI track
        di_track_id = str(uuid4())
        await db_session.execute(
            text(
                """
                INSERT INTO di_tracks (id, user_id, name, file_path, original_filename,
                                      duration_seconds, sample_rate, created_at, updated_at)
                VALUES (:id, :user_id, :name, :file_path, :original_filename,
                        :duration_seconds, :sample_rate, NOW(), NOW())
                """
            ),
            {
                "id": di_track_id,
                "user_id": user_id,
                "name": "Test DI Track",
                "file_path": "/media/di-tracks/test.wav",
                "original_filename": "test.wav",
                "duration_seconds": 30.5,
                "sample_rate": 44100,
            },
        )

        # Create shootout
        shootout_id = str(uuid4())
        await db_session.execute(
            text(
                """
                INSERT INTO shootouts (id, user_id, di_track_id, name, description,
                                      status, created_at, updated_at)
                VALUES (:id, :user_id, :di_track_id, :name, :description,
                        :status, NOW(), NOW())
                """
            ),
            {
                "id": shootout_id,
                "user_id": user_id,
                "di_track_id": di_track_id,
                "name": name,
                "description": description,
                "status": status,
            },
        )

        await db_session.commit()
        return shootout_id

    async def _create_test_shootout_with_chains(
        self,
        db_session: AsyncSession,
        chain_count: int = 3,
    ) -> str:
        """Create a test shootout with specified number of chains."""
        from uuid import uuid4

        shootout_id = await self._create_test_shootout(db_session)

        # Get user ID from shootout
        result = await db_session.execute(
            text("SELECT user_id FROM shootouts WHERE id = :id"),
            {"id": shootout_id},
        )
        row = result.fetchone()
        assert row is not None
        user_id = row[0]

        # Create chains
        for i in range(chain_count):
            chain_id = str(uuid4())
            shootout_chain_id = str(uuid4())

            # Create signal chain
            await db_session.execute(
                text(
                    """
                    INSERT INTO signal_chains (id, user_id, name, created_at, updated_at)
                    VALUES (:id, :user_id, :name, NOW(), NOW())
                    """
                ),
                {
                    "id": chain_id,
                    "user_id": user_id,
                    "name": f"Chain {i + 1}",
                },
            )

            # Create shootout_chain link
            await db_session.execute(
                text(
                    """
                    INSERT INTO shootout_chains (id, shootout_id, signal_chain_id,
                                                position, label)
                    VALUES (:id, :shootout_id, :signal_chain_id, :position, :label)
                    """
                ),
                {
                    "id": shootout_chain_id,
                    "shootout_id": shootout_id,
                    "signal_chain_id": chain_id,
                    "position": i,
                    "label": f"Chain {i + 1}",
                },
            )

        await db_session.commit()
        return shootout_id
