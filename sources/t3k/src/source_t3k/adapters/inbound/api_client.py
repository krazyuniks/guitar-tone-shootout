"""T3K API client.

HTTP client for the Tone3000 REST API using httpx. Implements per-endpoint
rate limiting and circuit breaker pattern for resilience.
"""

from collections.abc import Callable
from datetime import datetime
from typing import Any, TypeVar

from httpx import AsyncClient

from source_t3k.adapters.inbound.circuit_breaker import CircuitBreaker
from source_t3k.adapters.inbound.exceptions import T3KAPIError, T3KRateLimitError
from source_t3k.adapters.inbound.rate_limiter import RateLimiter
from source_t3k.domain.entities import T3KCreator, T3KModel, T3KPack
from source_t3k.domain.value_objects import T3KPackType, T3KPlatform

T = TypeVar("T")


class T3KAPIClient:
    """Async HTTP client for the Tone3000 REST API.

    Provides methods to fetch packs, models, and creators from the T3K API.
    Includes rate limiting and circuit breaker for resilience.

    Attributes:
        base_url: Base URL of the T3K API
        api_key: API key for authentication
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        list_requests_per_second: float = 10.0,
        detail_requests_per_second: float = 30.0,
        circuit_breaker_threshold: int = 5,
        circuit_breaker_timeout: float = 30.0,
    ) -> None:
        """Initialize T3K API client.

        Args:
            base_url: Base URL of the T3K API
            api_key: API key for authentication
            list_requests_per_second: Rate limit for list endpoints
            detail_requests_per_second: Rate limit for detail endpoints
            circuit_breaker_threshold: Failures before circuit opens
            circuit_breaker_timeout: Seconds before circuit enters half-open
        """
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._client = AsyncClient()

        # Rate limiters for different endpoint types
        self._list_rate_limiter = RateLimiter(requests_per_second=list_requests_per_second)
        self._detail_rate_limiter = RateLimiter(requests_per_second=detail_requests_per_second)

        # Circuit breaker for all requests
        self._circuit_breaker = CircuitBreaker(
            failure_threshold=circuit_breaker_threshold,
            timeout_seconds=circuit_breaker_timeout,
        )

    def _get_auth_headers(self) -> dict[str, str]:
        """Get authentication headers for API requests.

        Returns:
            Dictionary with Authorization header
        """
        return {"Authorization": f"Bearer {self._api_key}"}

    async def get_packs(self, page: int, per_page: int) -> list[T3KPack]:
        """Fetch a page of packs from the T3K API.

        Args:
            page: Page number (1-indexed)
            per_page: Number of items per page

        Returns:
            List of T3KPack entities

        Raises:
            T3KRateLimitError: If rate limit is exceeded (HTTP 429)
            T3KAPIError: If API returns an error response
        """
        await self._list_rate_limiter.acquire()

        async def make_request() -> list[T3KPack]:
            response = await self._client.get(
                f"{self._base_url}/packs",
                params={"page": page, "per_page": per_page},
                headers=self._get_auth_headers(),
            )
            return self._handle_response(response, self._parse_packs)

        try:
            return await self._circuit_breaker.call(make_request)
        except Exception as e:
            if "Circuit breaker" in str(e):
                raise T3KAPIError(str(e)) from e
            raise

    async def get_pack(self, pack_id: str) -> T3KPack:
        """Fetch a single pack by ID from the T3K API.

        Args:
            pack_id: T3K pack ID

        Returns:
            T3KPack entity

        Raises:
            T3KRateLimitError: If rate limit is exceeded (HTTP 429)
            T3KAPIError: If API returns an error response or pack not found
        """
        await self._detail_rate_limiter.acquire()

        async def make_request() -> T3KPack:
            response = await self._client.get(
                f"{self._base_url}/packs/{pack_id}",
                headers=self._get_auth_headers(),
            )
            return self._handle_response(response, self._parse_pack)

        try:
            return await self._circuit_breaker.call(make_request)
        except Exception as e:
            if "Circuit breaker" in str(e):
                raise T3KAPIError(str(e)) from e
            raise

    async def get_models(self, pack_id: str) -> list[T3KModel]:
        """Fetch all models for a pack from the T3K API.

        Args:
            pack_id: T3K pack ID

        Returns:
            List of T3KModel entities

        Raises:
            T3KRateLimitError: If rate limit is exceeded (HTTP 429)
            T3KAPIError: If API returns an error response
        """
        await self._detail_rate_limiter.acquire()

        async def make_request() -> list[T3KModel]:
            response = await self._client.get(
                f"{self._base_url}/packs/{pack_id}/models",
                headers=self._get_auth_headers(),
            )
            return self._handle_response(response, self._parse_models)

        try:
            return await self._circuit_breaker.call(make_request)
        except Exception as e:
            if "Circuit breaker" in str(e):
                raise T3KAPIError(str(e)) from e
            raise

    async def get_creators(self, page: int, per_page: int) -> list[T3KCreator]:
        """Fetch a page of creators from the T3K API.

        Args:
            page: Page number (1-indexed)
            per_page: Number of items per page

        Returns:
            List of T3KCreator entities

        Raises:
            T3KRateLimitError: If rate limit is exceeded (HTTP 429)
            T3KAPIError: If API returns an error response
        """
        await self._list_rate_limiter.acquire()

        async def make_request() -> list[T3KCreator]:
            response = await self._client.get(
                f"{self._base_url}/creators",
                params={"page": page, "per_page": per_page},
                headers=self._get_auth_headers(),
            )
            return self._handle_response(response, self._parse_creators)

        try:
            return await self._circuit_breaker.call(make_request)
        except Exception as e:
            if "Circuit breaker" in str(e):
                raise T3KAPIError(str(e)) from e
            raise

    def _handle_response(self, response: Any, parser: Callable[[dict[str, Any]], T]) -> T:
        """Handle API response and parse data.

        Args:
            response: httpx Response object
            parser: Parser function for response data

        Returns:
            Parsed data from parser function

        Raises:
            T3KRateLimitError: If rate limit is exceeded (HTTP 429)
            T3KAPIError: If API returns an error response or parsing fails
        """
        if response.status_code == 429:
            error_msg = "Rate limit exceeded"
            try:
                error_data = response.json()
                if "error" in error_data:
                    error_msg = error_data["error"]
            except Exception:
                pass
            raise T3KRateLimitError(error_msg)

        if response.status_code >= 400:
            error_msg = f"API error: {response.status_code}"
            try:
                error_data = response.json()
                if "error" in error_data:
                    error_msg = error_data["error"]
            except Exception:
                pass
            raise T3KAPIError(error_msg)

        try:
            data = response.json()
            return parser(data)
        except Exception as e:
            raise T3KAPIError(f"Invalid JSON response: {e}") from e

    def _parse_packs(self, data: dict[str, Any]) -> list[T3KPack]:
        """Parse packs list from API response.

        Args:
            data: API response data

        Returns:
            List of T3KPack entities

        Raises:
            T3KAPIError: If response structure is invalid
        """
        if "items" not in data:
            raise T3KAPIError("Invalid JSON: missing 'items' field")

        return [self._parse_pack_data(item) for item in data["items"]]

    def _parse_pack(self, data: dict[str, Any]) -> T3KPack:
        """Parse single pack from API response.

        Args:
            data: API response data

        Returns:
            T3KPack entity

        Raises:
            T3KAPIError: If response structure is invalid
        """
        return self._parse_pack_data(data)

    def _parse_pack_data(self, data: dict[str, Any]) -> T3KPack:
        """Parse pack data from raw dictionary.

        Args:
            data: Raw pack data

        Returns:
            T3KPack entity

        Raises:
            T3KAPIError: If data structure is invalid
        """
        try:
            return T3KPack(
                id=data["id"],
                name=data["name"],
                slug=data["slug"],
                creator_id=data["creator_id"],
                description=data["description"],
                thumbnail_url=data["thumbnail_url"],
                platform=T3KPlatform(data["platform"]),
                pack_type=T3KPackType(data["pack_type"]),
                created_at=datetime.fromisoformat(data["created_at"].replace("Z", "+00:00")),
                updated_at=datetime.fromisoformat(data["updated_at"].replace("Z", "+00:00")),
            )
        except (KeyError, ValueError) as e:
            raise T3KAPIError(f"Invalid JSON: {e}") from e

    def _parse_models(self, data: dict[str, Any]) -> list[T3KModel]:
        """Parse models list from API response.

        Args:
            data: API response data

        Returns:
            List of T3KModel entities

        Raises:
            T3KAPIError: If response structure is invalid
        """
        if "items" not in data:
            raise T3KAPIError("Invalid JSON: missing 'items' field")

        return [self._parse_model_data(item) for item in data["items"]]

    def _parse_model_data(self, data: dict[str, Any]) -> T3KModel:
        """Parse model data from raw dictionary.

        Args:
            data: Raw model data

        Returns:
            T3KModel entity

        Raises:
            T3KAPIError: If data structure is invalid
        """
        try:
            return T3KModel(
                id=data["id"],
                pack_id=data["pack_id"],
                name=data["name"],
                filename=data["filename"],
                file_size=data["file_size"],
                download_url=data["download_url"],
                checksum=data["checksum"],
                created_at=datetime.fromisoformat(data["created_at"].replace("Z", "+00:00")),
                updated_at=datetime.fromisoformat(data["updated_at"].replace("Z", "+00:00")),
            )
        except (KeyError, ValueError) as e:
            raise T3KAPIError(f"Invalid JSON: {e}") from e

    def _parse_creators(self, data: dict[str, Any]) -> list[T3KCreator]:
        """Parse creators list from API response.

        Args:
            data: API response data

        Returns:
            List of T3KCreator entities

        Raises:
            T3KAPIError: If response structure is invalid
        """
        if "items" not in data:
            raise T3KAPIError("Invalid JSON: missing 'items' field")

        return [self._parse_creator_data(item) for item in data["items"]]

    def _parse_creator_data(self, data: dict[str, Any]) -> T3KCreator:
        """Parse creator data from raw dictionary.

        Args:
            data: Raw creator data

        Returns:
            T3KCreator entity

        Raises:
            T3KAPIError: If data structure is invalid
        """
        try:
            return T3KCreator(
                id=data["id"],
                username=data["username"],
                display_name=data["display_name"],
                avatar_url=data["avatar_url"],
                profile_url=data["profile_url"],
            )
        except (KeyError, ValueError) as e:
            raise T3KAPIError(f"Invalid JSON: {e}") from e
