"""Golden path regression tests — one test per webapp route.

Fast HTTP-level checks using httpx. Each route tested exactly once.
No browser needed — just verify status codes and key content.
"""

import os

import httpx
import pytest


@pytest.fixture(scope="module")
def app_url() -> str:
    return os.getenv("BASE_URL", os.getenv("FRONTEND_URL", "http://localhost:9000"))


@pytest.fixture(scope="module")
def client(app_url: str) -> httpx.Client:
    return httpx.Client(base_url=app_url, follow_redirects=True, timeout=10)


# --- Public pages (200) ---


class TestPublicPages:
    def test_homepage(self, client: httpx.Client) -> None:
        r = client.get("/")
        assert r.status_code == 200
        assert "Guitar Tone Shootout" in r.text

    def test_about(self, client: httpx.Client) -> None:
        r = client.get("/about")
        assert r.status_code == 200

    def test_login(self, client: httpx.Client) -> None:
        r = client.get("/login")
        assert r.status_code == 200

    def test_gear_browse(self, client: httpx.Client) -> None:
        r = client.get("/gear")
        assert r.status_code == 200
        assert 'data-testid="gear-browse-page"' in r.text

    def test_gear_browse_filtered(self, client: httpx.Client) -> None:
        r = client.get("/gear?gear_type=amp")
        assert r.status_code == 200
        assert 'data-testid="gear-results"' in r.text

    def test_gear_browse_search(self, client: httpx.Client) -> None:
        r = client.get("/gear?search=fender")
        assert r.status_code == 200
        assert 'data-testid="gear-results"' in r.text

    def test_gear_browse_paginated(self, client: httpx.Client) -> None:
        r = client.get("/gear?page=2")
        assert r.status_code == 200

    def test_di_tracks(self, client: httpx.Client) -> None:
        r = client.get("/di-tracks")
        assert r.status_code == 200

    def test_shootouts(self, client: httpx.Client) -> None:
        r = client.get("/shootouts")
        assert r.status_code == 200


# --- Health endpoints (200) ---


class TestHealth:
    def test_health(self, client: httpx.Client) -> None:
        r = client.get("/health")
        assert r.status_code == 200

    def test_api_health(self, client: httpx.Client) -> None:
        r = client.get("/api/v1/health")
        assert r.status_code == 200


# --- HTMX fragment endpoints (200, public) ---


class TestPublicFragments:
    def test_di_tracks_results(self, client: httpx.Client) -> None:
        r = client.get("/api/v1/html/di-tracks/results")
        assert r.status_code == 200

    def test_shootouts_sections(self, client: httpx.Client) -> None:
        r = client.get("/api/v1/html/shootouts/sections")
        assert r.status_code == 200


# --- Protected pages (redirect to login without auth) ---


class TestProtectedPages:
    """Protected pages return 401 for unauthenticated requests."""

    def test_library_my_gear(self, client: httpx.Client) -> None:
        r = client.get("/library/my-gear", follow_redirects=False)
        assert r.status_code == 401

    def test_library_chains(self, client: httpx.Client) -> None:
        r = client.get("/library/chains", follow_redirects=False)
        assert r.status_code == 401

    def test_library_shootouts(self, client: httpx.Client) -> None:
        r = client.get("/library/shootouts", follow_redirects=False)
        assert r.status_code == 401

    def test_library_di_tracks(self, client: httpx.Client) -> None:
        r = client.get("/library/di-tracks", follow_redirects=False)
        assert r.status_code == 401

    def test_shootout_create(self, client: httpx.Client) -> None:
        r = client.get("/shootout/create", follow_redirects=False)
        assert r.status_code == 401


# --- 404 responses ---


class TestNotFound:
    def test_gear_nonexistent_slug(self, client: httpx.Client) -> None:
        r = client.get("/gear/nonexistent-slug-12345")
        assert r.status_code == 404

    def test_nonexistent_page(self, client: httpx.Client) -> None:
        r = client.get("/does-not-exist")
        assert r.status_code == 404


# --- SSR content assertions ---


class TestGearSSRContent:
    def test_gear_browse_has_pack_cards(self, client: httpx.Client) -> None:
        r = client.get("/gear")
        assert r.status_code == 200
        assert 'data-testid="gear-pack-card"' in r.text or 'data-testid="empty-state"' in r.text

    def test_gear_browse_has_pagination_or_empty(self, client: httpx.Client) -> None:
        r = client.get("/gear")
        assert r.status_code == 200
        assert 'data-testid="pagination"' in r.text or 'data-testid="results-count"' in r.text

    def test_gear_browse_no_htmx_loading(self, client: httpx.Client) -> None:
        """Verify no HTMX loading skeleton — content is SSR."""
        r = client.get("/gear")
        assert r.status_code == 200
        assert 'hx-trigger="load"' not in r.text
        assert "animate-pulse" not in r.text
