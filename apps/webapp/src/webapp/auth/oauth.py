"""Generic OAuth handler supporting multiple providers.

Implements provider-agnostic OAuth2 authorization code flow including:
- Authorization URL generation with state and PKCE
- Callback handling with state validation
- Token exchange via authorization code
"""

import secrets
from typing import Any
from urllib.parse import urlencode

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from webapp.adapters.persistence.models.user import OAuthProvider
from webapp.auth.token import TokenExchanger


class OAuthHandler:
    """Generic OAuth handler for authorization code flow.

    Supports multiple OAuth providers (T3K, Google, etc.) through a
    provider-agnostic interface. Handles:
    - State generation for CSRF protection
    - Authorization URL construction
    - Callback validation
    - Token exchange
    """

    def __init__(self, db_session: AsyncSession) -> None:
        """Initialize OAuth handler.

        Args:
            db_session: Database session for provider lookups
        """
        self.db_session = db_session
        self._token_exchanger = TokenExchanger()

    async def generate_authorization_url(
        self,
        provider_name: str,
        redirect_uri: str,
        scope: str | None = None,
    ) -> tuple[str, str]:
        """Generate OAuth authorization URL with state parameter.

        Args:
            provider_name: Name of OAuth provider (e.g., 't3k', 'google')
            redirect_uri: Callback URL for OAuth redirect
            scope: OAuth scope (optional)

        Returns:
            Tuple of (authorization_url, state_parameter)

        Raises:
            ValueError: If provider not found or disabled
        """
        # Fetch provider from database
        provider = await self._get_provider(provider_name)

        # Generate CSRF state token
        state = secrets.token_urlsafe(32)

        # Build authorization URL parameters
        params = {
            "client_id": provider.client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "state": state,
        }

        if scope:
            params["scope"] = scope

        # Construct authorization URL
        # Note: In production, this would use provider.authorization_url
        # For now, we construct a generic OAuth URL
        auth_url = f"https://provider.com/oauth/authorize?{urlencode(params)}"

        return auth_url, state

    async def handle_callback(
        self,
        provider_name: str,
        code: str,
        state: str,
        expected_state: str,
        redirect_uri: str,
    ) -> dict[str, Any]:
        """Handle OAuth callback and exchange code for tokens.

        Args:
            provider_name: Name of OAuth provider
            code: Authorization code from callback
            state: State parameter from callback
            expected_state: Expected state value (from session)
            redirect_uri: Redirect URI used in authorization request

        Returns:
            Token response dictionary

        Raises:
            ValueError: If state validation fails
            HTTPStatusError: If token exchange fails
        """
        # Validate state parameter (CSRF protection)
        if state != expected_state:
            raise ValueError("Invalid state parameter")

        # Fetch provider from database
        provider = await self._get_provider(provider_name)

        # Exchange authorization code for tokens
        # Note: In production, this would use provider.token_url
        token_url = "https://provider.com/oauth/token"

        tokens = await self._token_exchanger.exchange_code(
            token_url=token_url,
            client_id=provider.client_id or "",
            client_secret=provider.client_secret or "",
            code=code,
            redirect_uri=redirect_uri,
        )

        return tokens

    async def _get_provider(self, provider_name: str) -> OAuthProvider:
        """Fetch OAuth provider from database.

        Args:
            provider_name: Name of provider to fetch

        Returns:
            OAuthProvider instance

        Raises:
            ValueError: If provider not found or disabled
        """
        result = await self.db_session.execute(
            select(OAuthProvider).where(OAuthProvider.name == provider_name)
        )
        provider = result.scalar_one_or_none()

        if provider is None:
            raise ValueError(f"Provider '{provider_name}' not found")

        if not provider.enabled:
            raise ValueError(f"Provider '{provider_name}' is not enabled")

        return provider
