"""Tests for authentication endpoints."""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> TestClient:
    """Create test client."""
    return TestClient(app)


class TestLogin:
    """Tests for the login endpoint."""

    def test_login_redirects_to_tone3000(self, client: TestClient) -> None:
        """Login should redirect to Tone 3000 auth page."""
        response = client.get("/api/v1/auth/login", follow_redirects=False)

        assert response.status_code == 302
        location = response.headers["location"]
        assert "tone3000.com/api/v1/auth" in location
        assert "redirect_url" in location


class TestCallback:
    """Tests for the OAuth callback endpoint."""

    def test_callback_requires_api_key(self, client: TestClient) -> None:
        """Callback should require api_key parameter."""
        response = client.get("/api/v1/auth/callback", follow_redirects=False)

        # FastAPI returns 422 for missing required query parameters
        assert response.status_code == 422
        assert "api_key" in response.text.lower()


class TestMe:
    """Tests for the /me endpoint."""

    def test_me_unauthenticated(self, client: TestClient) -> None:
        """Should return unauthenticated status without session cookie."""
        response = client.get("/api/v1/auth/me")

        assert response.status_code == 200
        data = response.json()
        assert data["authenticated"] is False
        assert data["user"] is None

    def test_me_invalid_session(self, client: TestClient) -> None:
        """Should return unauthenticated with invalid session cookie."""
        response = client.get(
            "/api/v1/auth/me",
            cookies={"session": "invalid_token"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["authenticated"] is False


class TestLogout:
    """Tests for the logout endpoint."""

    def test_logout_clears_cookie(self, client: TestClient) -> None:
        """Logout should clear the session cookie."""
        response = client.post("/api/v1/auth/logout")

        assert response.status_code == 200
        assert response.json()["message"] == "Logged out successfully"
        # Cookie should be deleted (set to empty or with expiry in past)
        assert "session" in response.headers.get("set-cookie", "").lower()
