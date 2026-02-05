"""T3K (Tone3000) OAuth provider implementation.

Implements OAuth2 authorization code flow for T3K authentication including:
- Authorization URL generation
- Token exchange with T3K API
- User information retrieval
"""

import os
from typing import Any
from urllib.parse import urlencode

import httpx


class T3KProvider:
    """T3K OAuth provider for Tone3000 authentication.

    Handles OAuth2 flow with T3K's passwordless authentication system.
    T3K uses email magic links for user authentication.
    """

    def __init__(self) -> None:
        """Initialize T3K provider with API endpoints.

        Reads T3K_API_URL from environment or uses default.
        """
        # Read API URL from environment or use default
        self.api_url = os.environ.get("T3K_API_URL", "https://api.tone3000.com")

        # Define OAuth endpoints
        self.authorization_url = f"{self.api_url}/oauth/authorize"
        self.token_url = f"{self.api_url}/oauth/token"
        self.user_info_url = f"{self.api_url}/api/v1/me"

    def build_authorization_url(
        self,
        client_id: str,
        redirect_uri: str,
        state: str,
        scope: str | None = None,
    ) -> str:
        """Build OAuth authorization URL for T3K.

        Args:
            client_id: OAuth client ID
            redirect_uri: Callback URL for OAuth redirect
            state: CSRF protection state token
            scope: OAuth scope (optional)

        Returns:
            Complete authorization URL with parameters
        """
        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "state": state,
        }

        if scope:
            params["scope"] = scope

        return f"{self.authorization_url}?{urlencode(params)}"

    async def exchange_code(
        self,
        code: str,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
    ) -> dict[str, Any]:
        """Exchange authorization code for access token.

        Args:
            code: Authorization code from T3K callback
            client_id: OAuth client ID
            client_secret: OAuth client secret
            redirect_uri: Redirect URI used in authorization request

        Returns:
            Token response with access_token, refresh_token, etc.

        Raises:
            HTTPStatusError: If token exchange fails
        """
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(self.token_url, data=data)
            response.raise_for_status()
            return response.json()

    async def get_user_info(self, access_token: str) -> dict[str, Any]:
        """Retrieve user information from T3K API.

        Args:
            access_token: Valid OAuth access token

        Returns:
            User profile information from T3K

        Raises:
            HTTPStatusError: If user info retrieval fails
        """
        headers = {
            "Authorization": f"Bearer {access_token}",
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(self.user_info_url, headers=headers)
            response.raise_for_status()
            return response.json()
