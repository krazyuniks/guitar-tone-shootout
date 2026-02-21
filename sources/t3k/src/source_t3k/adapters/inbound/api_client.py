"""T3K API client.

HTTP client for the Tone3000 REST API using httpx. Implements per-endpoint
rate limiting and circuit breaker pattern for resilience.
"""

import asyncio
import logging
from collections.abc import Callable
from datetime import datetime
from typing import Any, TypeVar

from httpx import AsyncClient

from source_t3k.adapters.inbound.circuit_breaker import CircuitBreaker
from source_t3k.adapters.inbound.exceptions import (
    T3KAPIError,
    T3KAuthenticationError,
    T3KRateLimitError,
)
from source_t3k.adapters.inbound.rate_limiter import RateLimiter
from source_t3k.adapters.inbound.token_manager import T3KTokenManager
from source_t3k.adapters.inbound.vercel_solver import (
    is_vercel_challenge,
    load_cookies,
    solve_challenge,
)
from source_t3k.domain.entities import T3KModel, T3KTone, T3KUser
from source_t3k.domain.value_objects import T3KGearKind, T3KPlatform

T = TypeVar("T")
logger = logging.getLogger(__name__)


def _safe_enum[E](enum_cls: type[E], value: str, default: E) -> E:
    """Parse an enum value, returning default if unknown."""
    try:
        return enum_cls(value)  # type: ignore[call-arg]
    except ValueError:
        logger.warning("Unknown %s value: %r, using %s", enum_cls.__name__, value, default)
        return default


class T3KAPIClient:
    """Async HTTP client for the Tone3000 REST API.

    Provides methods to fetch tones, models, and users from the T3K API.
    Includes rate limiting and circuit breaker for resilience.
    """

    def __init__(
        self,
        token_manager: T3KTokenManager,
        base_url: str = "https://www.tone3000.com",
        requests_per_second: float = 0.75,
        circuit_breaker_threshold: int = 5,
        circuit_breaker_timeout: float = 30.0,
        retry_base_wait: float = 30.0,
    ) -> None:
        self._token_manager = token_manager
        self._base_url = base_url.rstrip("/")
        self._retry_base_wait = retry_base_wait

        # Load Vercel cookies (solved on host, same external IP)
        vercel_cookies = load_cookies()

        self._client = AsyncClient(
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
                ),
                "Accept": "application/json, text/html, */*",
                "Accept-Language": "en-US,en;q=0.9",
            },
            cookies=vercel_cookies or None,
        )

        self._rate_limiter = RateLimiter(requests_per_second=requests_per_second)

        self._circuit_breaker = CircuitBreaker(
            failure_threshold=circuit_breaker_threshold,
            timeout_seconds=circuit_breaker_timeout,
        )

    async def _get_auth_headers(self) -> dict[str, str]:
        """Get authentication headers with a valid JWT."""
        token = await self._token_manager.get_access_token()
        return {"Authorization": f"Bearer {token}"}

    async def get_tones(
        self, page: int = 1, page_size: int = 25, sort: str = "newest"
    ) -> list[T3KTone]:
        """Fetch a page of tones from the T3K API.

        Uses GET /api/v1/tones/search with pagination.
        """
        await self._rate_limiter.acquire()

        async def make_request() -> list[T3KTone]:
            headers = await self._get_auth_headers()
            response = await self._client.get(
                f"{self._base_url}/api/v1/tones/search",
                params={"page": page, "page_size": page_size, "sort": sort},
                headers=headers,
            )
            return self._handle_response(response, self._parse_tones)

        return await self._call_with_retry(make_request)

    async def get_models(self, tone_id: int) -> list[T3KModel]:
        """Fetch all models for a tone from the T3K API.

        Uses GET /api/v1/models?tone_id=N with pagination (max 100 per page).
        """
        all_models: list[T3KModel] = []
        page = 1

        while True:
            await self._rate_limiter.acquire()

            current_page = page

            async def make_request(pg: int = current_page) -> dict:
                headers = await self._get_auth_headers()
                response = await self._client.get(
                    f"{self._base_url}/api/v1/models",
                    params={"tone_id": tone_id, "page": pg, "page_size": 100},
                    headers=headers,
                )
                return self._handle_response(response, lambda d: d)

            data = await self._call_with_retry(make_request)
            page_models = self._parse_models(data)
            all_models.extend(page_models)

            total = data.get("total", 0)
            if not page_models or len(all_models) >= total or data.get("has_next") is False:
                break

            page += 1

        return all_models

    async def get_users(self, page: int = 1, page_size: int = 10) -> list[T3KUser]:
        """Fetch a page of users from the T3K API.

        Uses GET /api/v1/users.
        """
        await self._rate_limiter.acquire()

        async def make_request() -> list[T3KUser]:
            headers = await self._get_auth_headers()
            response = await self._client.get(
                f"{self._base_url}/api/v1/users",
                params={"page": page, "page_size": page_size},
                headers=headers,
            )
            return self._handle_response(response, self._parse_users)

        return await self._call_with_retry(make_request)

    async def _call_with_retry(self, make_request: Callable[..., Any]) -> Any:
        """Call via circuit breaker, with retry on 401, backoff on 429, and Vercel challenge solving."""
        max_retries = 3
        for attempt in range(max_retries + 1):
            try:
                return await self._circuit_breaker.call(make_request)
            except T3KAuthenticationError:
                logger.warning("T3K 401 — refreshing token and retrying")
                await self._token_manager._refresh()
                return await self._circuit_breaker.call(make_request)
            except T3KRateLimitError:
                if attempt >= max_retries:
                    raise
                wait = self._retry_base_wait * (2**attempt)
                logger.warning(
                    "T3K 429 — backing off %ds (attempt %d/%d)", wait, attempt + 1, max_retries
                )
                await asyncio.sleep(wait)
            except T3KAPIError as e:
                if "Vercel challenge solved" in str(e) and attempt < max_retries:
                    logger.info(
                        "Retrying after Vercel challenge solve (attempt %d/%d)",
                        attempt + 1,
                        max_retries,
                    )
                    await asyncio.sleep(2)
                    continue
                if "Circuit breaker" in str(e):
                    raise
                raise
            except Exception as e:
                if "Circuit breaker" in str(e):
                    raise T3KAPIError(str(e)) from e
                raise
        raise T3KAPIError("Request failed after retries")

    def _handle_response(self, response: Any, parser: Callable[[dict[str, Any]], T]) -> T:
        """Handle API response, raising typed exceptions on errors."""
        if response.status_code == 401:
            raise T3KAuthenticationError("T3K API returned 401")

        if response.status_code == 429:
            raise T3KRateLimitError("Rate limit exceeded")

        if response.status_code >= 400:
            body = response.text
            if is_vercel_challenge(response.status_code, body):
                logger.warning("Vercel challenge detected — attempting headless solve")
                if solve_challenge(self._base_url):
                    raise T3KAPIError("Vercel challenge solved — retry request")
                raise T3KAPIError("Vercel challenge could not be solved")

            error_msg = f"API error: {response.status_code}"
            try:
                error_data = response.json()
                if "error" in error_data:
                    error_msg = error_data["error"]
                else:
                    error_msg = f"API error: {response.status_code} — {error_data}"
            except Exception:
                error_msg = f"API error: {response.status_code} — {body[:200]}"
            logger.error(
                "T3K API %d: %s %s",
                response.status_code,
                response.request.method,
                response.request.url,
            )
            raise T3KAPIError(error_msg)

        data = response.json()
        return parser(data)

    # ── Parsers ──────────────────────────────────────────────────────────

    def _parse_tones(self, data: dict[str, Any]) -> list[T3KTone]:
        """Parse tones list — expects {"data": [...]}."""
        return [self._parse_tone_data(item) for item in data["data"]]

    def _parse_tone_data(self, d: dict[str, Any]) -> T3KTone:
        user_data = d.get("user")
        user = self._parse_user_data(user_data) if user_data else None

        return T3KTone(
            id=int(d["id"]),
            title=d.get("title", ""),
            description=d.get("description") or "",
            tags=_extract_names(d.get("tags", [])),
            makes=_extract_names(d.get("makes", [])),
            gear=_safe_enum(T3KGearKind, d.get("gear", "amp"), T3KGearKind.AMP),
            platform=_safe_enum(T3KPlatform, d.get("platform", "nam"), T3KPlatform.NAM),
            models_count=d.get("models_count", 0),
            favorites_count=d.get("favorites_count", 0),
            downloads_count=d.get("downloads_count", 0),
            images=d.get("images") or [],
            user_id=str(d.get("user_id", "")),
            user=user,
            url=d.get("url", ""),
            created_at=_parse_datetime(d.get("created_at", "")),
            updated_at=_parse_datetime(d.get("updated_at", "")),
        )

    def _parse_models(self, data: dict[str, Any]) -> list[T3KModel]:
        """Parse models list — expects {"data": [...]}."""
        return [self._parse_model_data(item) for item in data["data"]]

    def _parse_model_data(self, d: dict[str, Any]) -> T3KModel:
        return T3KModel(
            id=int(d["id"]),
            tone_id=int(d.get("tone_id", 0)),
            user_id=str(d.get("user_id", "")),
            name=d.get("name", ""),
            model_url=d.get("model_url", ""),
            size=d.get("size") or "standard",
            created_at=_parse_datetime(d.get("created_at", "")),
            updated_at=_parse_datetime(d.get("updated_at", "")),
        )

    def _parse_users(self, data: dict[str, Any]) -> list[T3KUser]:
        """Parse users list — expects {"data": [...]}."""
        return [self._parse_user_data(item) for item in data["data"]]

    def _parse_user_data(self, d: dict[str, Any]) -> T3KUser:
        return T3KUser(
            id=str(d["id"]),
            username=d.get("username", ""),
            avatar_url=d.get("avatar_url", ""),
            bio=d.get("bio", ""),
            url=d.get("url", ""),
        )


def _extract_names(items: list[Any]) -> list[str]:
    """Extract name strings from API tag/make objects.

    The T3K API returns tags and makes as [{"name": "foo"}, ...].
    """
    return [item["name"] if isinstance(item, dict) else str(item) for item in items]


def _parse_datetime(value: str) -> datetime:
    """Parse ISO 8601 datetime string, handling Z suffix."""
    if not value:
        return datetime.min
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
