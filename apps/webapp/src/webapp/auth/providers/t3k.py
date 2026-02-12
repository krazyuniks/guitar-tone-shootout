"""T3K (Tone3000) authentication provider.

Supports two authentication flows:
1. api_key flow (simplified): T3K redirects with ?api_key=..., exchanged for tokens
2. OAuth2 authorization code flow: standard OAuth2 with authorization_url, token exchange
"""

import os
from typing import Any
from urllib.parse import urlencode

import httpx


class T3KProvider:
    """T3K authentication provider supporting api_key and OAuth2 flows."""

    def __init__(self) -> None:
        self.base_url = os.environ.get("T3K_API_URL", "https://www.tone3000.com")
        self.authorization_url = f"{self.base_url}/oauth/authorize"
        self.token_url = f"{self.base_url}/oauth/token"
        self.user_info_url = f"{self.base_url}/api/v1/user"

    # --- OAuth2 authorization code flow ---

    def build_authorization_url(
        self,
        *,
        client_id: str,
        redirect_uri: str,
        state: str,
        scope: str | None = None,
    ) -> str:
        """Build OAuth2 authorization URL.

        Args:
            client_id: OAuth client ID
            redirect_uri: Callback URL after authorization
            state: Anti-CSRF state token
            scope: Optional OAuth scope string

        Returns:
            Full authorization URL with query parameters
        """
        params: dict[str, str] = {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "state": state,
        }
        if scope:
            params["scope"] = scope
        return f"{self.authorization_url}?{urlencode(params)}"

    async def exchange_code(
        self,
        *,
        code: str,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
    ) -> dict[str, Any]:
        """Exchange authorization code for access/refresh tokens.

        Args:
            code: Authorization code from callback
            client_id: OAuth client ID
            client_secret: OAuth client secret
            redirect_uri: Must match the redirect_uri used in authorization

        Returns:
            Dict with access_token, token_type, refresh_token, expires_in

        Raises:
            httpx.HTTPStatusError: If token exchange fails
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.token_url,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "redirect_uri": redirect_uri,
                },
            )
            response.raise_for_status()
            return response.json()

    # --- api_key flow (T3K simplified) ---

    def build_login_url(self, callback_url: str) -> str:
        """Build T3K login URL that redirects back to our callback.

        Args:
            callback_url: Our callback URL

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
                self.user_info_url,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            response.raise_for_status()
            return response.json()
