"""Tone 3000 API client with automatic token refresh.

This module provides a client for interacting with the Tone 3000 API,
handling authentication, token refresh, and rate limiting.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.user import User
from app.schemas.auth import TokenResponse
from app.schemas.tone3000 import Model, PaginatedResponse, Tone

logger = get_logger(__name__)

BASE_URL = "https://www.tone3000.com/api/v1"
TOKEN_REFRESH_BUFFER = timedelta(seconds=30)


class Tone3000Error(Exception):
    """Base exception for Tone 3000 API errors."""


class AuthenticationExpired(Tone3000Error):
    """Raised when refresh token is expired and user needs to re-authenticate."""


class RateLimitExceeded(Tone3000Error):
    """Raised when rate limit is exceeded."""


class Tone3000Client:
    """Client for interacting with the Tone 3000 API.

    Handles authentication, automatic token refresh, and rate limiting.

    Usage:
        client = Tone3000Client(user, db)
        tones = await client.get_user_tones()
    """

    def __init__(self, user: User, db: AsyncSession):
        """Initialize the client.

        Args:
            user: The authenticated user with Tone 3000 tokens
            db: Database session for persisting token updates
        """
        self.user = user
        self.db = db
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "Tone3000Client":
        """Enter async context manager."""
        self._client = httpx.AsyncClient(
            base_url=BASE_URL,
            timeout=30.0,
        )
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit async context manager."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _ensure_valid_token(self) -> str:
        """Ensure the access token is valid, refreshing if needed.

        Returns:
            Valid access token

        Raises:
            AuthenticationExpired: If refresh fails
        """
        if self.user.token_expires_at is None:
            raise AuthenticationExpired("No token expiry set")

        # Check if token is expired or expiring soon
        if self.user.token_expires_at < datetime.now(UTC) + TOKEN_REFRESH_BUFFER:
            await self._refresh_token()

        if self.user.access_token is None:
            raise AuthenticationExpired("No access token available")

        return self.user.access_token

    async def _refresh_token(self) -> None:
        """Refresh the access token using the refresh token.

        Raises:
            AuthenticationExpired: If refresh fails (user needs to re-auth)
        """
        if self.user.refresh_token is None or self.user.access_token is None:
            raise AuthenticationExpired("No tokens available for refresh")

        logger.info("Refreshing Tone 3000 token for user %s", self.user.username)

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.post(
                    f"{BASE_URL}/auth/session/refresh",
                    json={
                        "refresh_token": self.user.refresh_token,
                        "access_token": self.user.access_token,
                    },
                )

                if response.status_code == 401:
                    logger.warning(
                        "Refresh token expired for user %s", self.user.username
                    )
                    raise AuthenticationExpired(
                        "Refresh token expired, please log in again"
                    )

                response.raise_for_status()
                tokens = TokenResponse(**response.json())

                # Update user tokens
                self.user.access_token = tokens.access_token
                self.user.refresh_token = tokens.refresh_token
                self.user.token_expires_at = datetime.now(UTC) + timedelta(
                    seconds=tokens.expires_in
                )
                await self.db.commit()

                logger.info(
                    "Token refreshed successfully for user %s", self.user.username
                )

            except httpx.HTTPStatusError as e:
                logger.error("Token refresh failed: %s", e.response.text)
                raise AuthenticationExpired("Token refresh failed") from e
            except httpx.RequestError as e:
                logger.error("Token refresh request failed: %s", e)
                raise Tone3000Error("Unable to connect to Tone 3000") from e

    async def _request(
        self,
        method: str,
        path: str,
        retry_on_401: bool = True,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Make an authenticated request to the Tone 3000 API.

        Args:
            method: HTTP method (GET, POST, etc.)
            path: API path (e.g., "/tones/created")
            retry_on_401: Whether to retry once on 401 after token refresh
            **kwargs: Additional arguments for httpx request

        Returns:
            JSON response as dictionary

        Raises:
            Tone3000Error: On API errors
            AuthenticationExpired: If authentication fails
            RateLimitExceeded: If rate limit is hit
        """
        if self._client is None:
            raise Tone3000Error("Client not initialized, use async context manager")

        token = await self._ensure_valid_token()
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {token}"

        try:
            response = await self._client.request(
                method,
                path,
                headers=headers,
                **kwargs,
            )

            # Handle 401 with token refresh and retry
            if response.status_code == 401 and retry_on_401:
                logger.info("Got 401, attempting token refresh")
                await self._refresh_token()
                # Retry with new token
                return await self._request(method, path, retry_on_401=False, **kwargs)

            # Handle rate limiting (429)
            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After", "60")
                logger.warning(
                    "Rate limit exceeded, retry after %s seconds", retry_after
                )
                raise RateLimitExceeded(
                    f"Rate limit exceeded. Retry after {retry_after} seconds"
                )

            response.raise_for_status()
            return response.json()  # type: ignore[no-any-return]

        except httpx.HTTPStatusError as e:
            logger.error(
                "Tone 3000 API error: %s - %s",
                e.response.status_code,
                e.response.text,
            )
            raise Tone3000Error(f"API error: {e.response.status_code}") from e
        except httpx.RequestError as e:
            logger.error("Tone 3000 connection error: %s", e)
            raise Tone3000Error("Unable to connect to Tone 3000") from e

    # -------------------------------------------------------------------------
    # User Tones API
    # -------------------------------------------------------------------------

    async def get_user_tones(
        self, page: int = 1, per_page: int = 20
    ) -> PaginatedResponse:
        """Fetch the authenticated user's created tones.

        Args:
            page: Page number (1-indexed)
            per_page: Number of results per page

        Returns:
            Paginated response with tones
        """
        data = await self._request(
            "GET",
            "/tones/created",
            params={"page": page, "per_page": per_page},
        )
        return PaginatedResponse(
            data=[Tone(**t) for t in data.get("data", [])],
            total=data.get("total", 0),
            page=data.get("page", page),
            per_page=data.get("per_page", per_page),
            has_next=data.get("has_next", False),
        )

    async def get_favorited_tones(
        self, page: int = 1, per_page: int = 20
    ) -> PaginatedResponse:
        """Fetch the authenticated user's favorited tones.

        Args:
            page: Page number (1-indexed)
            per_page: Number of results per page

        Returns:
            Paginated response with tones
        """
        data = await self._request(
            "GET",
            "/tones/favorited",
            params={"page": page, "per_page": per_page},
        )
        return PaginatedResponse(
            data=[Tone(**t) for t in data.get("data", [])],
            total=data.get("total", 0),
            page=data.get("page", page),
            per_page=data.get("per_page", per_page),
            has_next=data.get("has_next", False),
        )

    async def search_tones(
        self,
        query: str | None = None,
        gear: str | None = None,
        platform: str | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> PaginatedResponse:
        """Search public tones.

        Args:
            query: Search query string
            gear: Filter by gear type (amp, pedal, ir, etc.)
            platform: Filter by platform (nam, ir, aida-x)
            page: Page number (1-indexed)
            per_page: Number of results per page

        Returns:
            Paginated response with matching tones
        """
        params: dict[str, Any] = {"page": page, "per_page": per_page}
        if query:
            params["query"] = query
        if gear:
            params["gear"] = gear
        if platform:
            params["platform"] = platform

        data = await self._request("GET", "/tones/search", params=params)
        return PaginatedResponse(
            data=[Tone(**t) for t in data.get("data", [])],
            total=data.get("total", 0),
            page=data.get("page", page),
            per_page=data.get("per_page", per_page),
            has_next=data.get("has_next", False),
        )

    async def get_tone(self, tone_id: int) -> Tone:
        """Get a specific tone by ID.

        Args:
            tone_id: The tone's ID

        Returns:
            The tone details
        """
        data = await self._request("GET", f"/tones/{tone_id}")
        return Tone(**data)

    # -------------------------------------------------------------------------
    # Models API
    # -------------------------------------------------------------------------

    async def get_models(self, tone_id: int) -> list[Model]:
        """Get downloadable models for a tone.

        Args:
            tone_id: The tone's ID

        Returns:
            List of downloadable model files
        """
        data = await self._request("GET", "/models", params={"tone_id": tone_id})
        return [Model(**m) for m in data.get("data", [])]

    async def download_model(self, model: Model) -> bytes:
        """Download a model file.

        Args:
            model: The model to download

        Returns:
            The model file contents as bytes
        """
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.get(model.model_url)
            response.raise_for_status()
            return response.content
