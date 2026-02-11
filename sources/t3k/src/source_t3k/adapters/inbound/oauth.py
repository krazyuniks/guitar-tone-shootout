"""T3K OAuth token management.

Manages OAuth tokens for authenticating with the Tone3000 API. Tokens are
encrypted at rest using Fernet encryption and automatically refreshed when
expired or near expiry.
"""

from datetime import UTC, datetime, timedelta

from cryptography.fernet import Fernet
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from source_t3k.adapters.outbound.models import OAuthToken


class T3KOAuthManager:
    """Manages OAuth token lifecycle for T3K API authentication.

    Responsibilities:
    - Encrypt/decrypt tokens using Fernet
    - Track token expiry
    - Automatically refresh tokens when expired or near expiry
    - Persist tokens to the gts_t3k_source database

    Attributes:
        session: Database session for persisting tokens
        encryption_key: Fernet encryption key (from T3K_TOKEN_ENCRYPTION_KEY env var)
        client_id: OAuth client ID
        client_secret: OAuth client secret
        oauth_base_url: Base URL for T3K OAuth endpoints
    """

    def __init__(
        self,
        session: AsyncSession,
        encryption_key: str,
        client_id: str,
        client_secret: str,
        oauth_base_url: str,
    ) -> None:
        """Initialize OAuth manager.

        Args:
            session: Database session for token persistence
            encryption_key: Fernet encryption key (base64-encoded)
            client_id: OAuth client ID
            client_secret: OAuth client secret
            oauth_base_url: Base URL for OAuth endpoints (e.g., https://oauth.tone3000.com)
        """
        self._session = session
        self._fernet = Fernet(encryption_key.encode())
        self._client_id = client_id
        self._client_secret = client_secret
        self._oauth_base_url = oauth_base_url.rstrip("/")
        self._client = AsyncClient()

    def _encrypt(self, plaintext: str) -> str:
        """Encrypt a plaintext token using Fernet.

        Args:
            plaintext: Plaintext token string

        Returns:
            Encrypted token (base64-encoded)
        """
        return self._fernet.encrypt(plaintext.encode()).decode()

    def _decrypt(self, encrypted: str) -> str:
        """Decrypt an encrypted token using Fernet.

        Args:
            encrypted: Encrypted token (base64-encoded)

        Returns:
            Decrypted plaintext token
        """
        return self._fernet.decrypt(encrypted.encode()).decode()

    def _is_expired(self, token: OAuthToken, buffer_minutes: int = 5) -> bool:
        """Check if a token is expired or near expiry.

        Args:
            token: OAuthToken record
            buffer_minutes: Minutes before expiry to consider token expired (default: 5)

        Returns:
            True if token is expired or within buffer_minutes of expiry
        """
        now = datetime.now(UTC)
        expiry_with_buffer = token.expires_at - timedelta(minutes=buffer_minutes)
        return now >= expiry_with_buffer

    async def get_valid_token(self) -> str:
        """Get a valid (non-expired) access token.

        If the current token is expired or near expiry, automatically refreshes
        it before returning.

        Returns:
            Decrypted access token string

        Raises:
            RuntimeError: If no token exists in database
        """
        # Fetch current token from database
        result = await self._session.execute(select(OAuthToken))
        token = result.scalar_one_or_none()

        if token is None:
            raise RuntimeError("No OAuth token found in database")

        # Refresh if expired or near expiry
        if self._is_expired(token):
            await self.refresh_token()
            # Re-fetch updated token
            result = await self._session.execute(select(OAuthToken))
            token = result.scalar_one()

        return self._decrypt(token.access_token_encrypted)

    async def refresh_token(self) -> None:
        """Refresh the OAuth token using the refresh_token grant.

        Calls the T3K OAuth endpoint with the current refresh token, then
        persists the new tokens (encrypted) to the database.

        Raises:
            RuntimeError: If no token exists in database
            httpx.HTTPError: If OAuth request fails
        """
        # Fetch current token to get refresh_token
        result = await self._session.execute(select(OAuthToken))
        token = result.scalar_one_or_none()

        if token is None:
            raise RuntimeError("No OAuth token found in database")

        # Decrypt refresh token
        refresh_token = self._decrypt(token.refresh_token_encrypted)

        # Call OAuth refresh endpoint
        response = await self._client.post(
            f"{self._oauth_base_url}/token",
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": self._client_id,
                "client_secret": self._client_secret,
            },
        )
        response.raise_for_status()

        # Parse response
        data = response.json()
        new_access_token = data["access_token"]
        new_refresh_token = data["refresh_token"]
        expires_in = data["expires_in"]

        # Calculate expiry time
        now = datetime.now(UTC)
        expires_at = now + timedelta(seconds=expires_in)

        # Update token in database
        token.access_token_encrypted = self._encrypt(new_access_token)
        token.refresh_token_encrypted = self._encrypt(new_refresh_token)
        token.expires_at = expires_at

        await self._session.commit()
