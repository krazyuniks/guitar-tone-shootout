"""Token exchange logic for OAuth flows.

Handles exchanging authorization codes for access tokens from OAuth providers.
"""

from typing import Any

import httpx


class TokenExchanger:
    """Handles token exchange with OAuth providers.

    Exchanges authorization codes for access tokens via POST requests
    to provider token endpoints.
    """

    async def exchange_code(
        self,
        token_url: str,
        client_id: str,
        client_secret: str,
        code: str,
        redirect_uri: str,
    ) -> dict[str, Any]:
        """Exchange authorization code for access token.

        Args:
            token_url: OAuth provider's token endpoint URL
            client_id: OAuth client ID
            client_secret: OAuth client secret
            code: Authorization code from callback
            redirect_uri: Redirect URI used in authorization request

        Returns:
            Token response dictionary containing:
                - access_token: Access token
                - token_type: Token type (usually "Bearer")
                - expires_in: Token expiration time in seconds (optional)
                - refresh_token: Refresh token (optional)
                - scope: Token scope (optional)

        Raises:
            HTTPStatusError: If token exchange request fails
            Exception: For network or other errors
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                token_url,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "redirect_uri": redirect_uri,
                },
            )

            # Raise for HTTP errors (4xx, 5xx)
            response.raise_for_status()

            return response.json()
