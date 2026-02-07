"""T3K (Tone3000) authentication provider.

Implements T3K's simplified api_key flow:
1. User visits T3K login page with redirect_url
2. T3K redirects back with ?api_key=...
3. We exchange api_key for access/refresh tokens
4. We fetch user profile with the access token
"""

import os
from typing import Any

import httpx


class T3KProvider:
    """T3K authentication provider using api_key flow."""

    def __init__(self) -> None:
        self.base_url = os.environ.get(
            "T3K_API_URL", "https://www.tone3000.com"
        )

    def build_login_url(self, callback_url: str) -> str:
        """Build T3K login URL that redirects back to our callback.

        Args:
            callback_url: Our callback URL (e.g. https://1.tone-shootout.com/api/v1/auth/callback)

        Returns:
            T3K auth URL to redirect the user to
        """
        return f"{self.base_url}/api/v1/auth?redirect_url={callback_url}"

    async def exchange_api_key(self, api_key: str) -> dict[str, Any]:
        """Exchange api_key from callback for access/refresh tokens.

        Args:
            api_key: API key received from T3K callback

        Returns:
            Dict with access_token, refresh_token, expires_at, etc.

        Raises:
            httpx.HTTPStatusError: If exchange fails
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/v1/auth/session",
                json={"api_key": api_key},
            )
            response.raise_for_status()
            return response.json()

    async def get_user_info(self, access_token: str) -> dict[str, Any]:
        """Fetch user profile from T3K API.

        Args:
            access_token: Valid T3K access token

        Returns:
            User profile dict with id, username, email, avatar_url, etc.

        Raises:
            httpx.HTTPStatusError: If request fails
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/v1/user",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            response.raise_for_status()
            return response.json()
