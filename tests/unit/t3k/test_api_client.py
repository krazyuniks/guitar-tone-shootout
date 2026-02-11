"""Unit tests for T3K API client.

The T3K API client is an EXTERNAL API adapter, so mocking httpx responses
is acceptable per testing policy. Tests verify request construction, response
parsing, error handling, and integration with rate limiter and circuit breaker.
"""

from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient, Request, Response

from source_t3k.adapters.inbound.api_client import T3KAPIClient
from source_t3k.adapters.inbound.exceptions import T3KAPIError, T3KRateLimitError
from source_t3k.domain.entities import T3KCreator, T3KModel, T3KPack
from source_t3k.domain.value_objects import T3KPackType, T3KPlatform


@pytest.fixture
def mock_httpx_client() -> AsyncMock:
    """Create a mock httpx AsyncClient."""
    return AsyncMock(spec=AsyncClient)


@pytest.fixture
def api_client(mock_httpx_client: AsyncMock) -> T3KAPIClient:
    """Create a T3KAPIClient with mocked dependencies."""
    client = T3KAPIClient(
        base_url="https://api.tone3000.com",
        api_key="test-api-key",
    )
    # Replace the internal client with our mock
    client._client = mock_httpx_client
    return client


class TestT3KAPIClientGetPacks:
    """Test T3KAPIClient.get_packs() method."""

    @pytest.mark.asyncio
    async def test_get_packs_returns_list_of_packs(
        self, api_client: T3KAPIClient, mock_httpx_client: AsyncMock
    ) -> None:
        """get_packs should return a list of T3KPack entities."""
        # Mock response data
        mock_response_data = {
            "items": [
                {
                    "id": "pack-1",
                    "name": "Pack One",
                    "slug": "pack-one",
                    "creator_id": "creator-1",
                    "description": "First pack",
                    "thumbnail_url": "https://t3k.com/pack1.jpg",
                    "platform": "nam",
                    "pack_type": "amp",
                    "created_at": "2024-01-01T00:00:00Z",
                    "updated_at": "2024-01-02T00:00:00Z",
                },
                {
                    "id": "pack-2",
                    "name": "Pack Two",
                    "slug": "pack-two",
                    "creator_id": "creator-2",
                    "description": "Second pack",
                    "thumbnail_url": "https://t3k.com/pack2.jpg",
                    "platform": "aida_x",
                    "pack_type": "pedal",
                    "created_at": "2024-01-03T00:00:00Z",
                    "updated_at": "2024-01-04T00:00:00Z",
                },
            ]
        }

        mock_httpx_client.get.return_value = Response(
            status_code=200,
            json=mock_response_data,
            request=Request("GET", "https://api.tone3000.com/packs"),
        )

        # Call the method
        packs = await api_client.get_packs(page=1, per_page=10)

        # Verify the result
        assert len(packs) == 2
        assert all(isinstance(pack, T3KPack) for pack in packs)
        assert packs[0].id == "pack-1"
        assert packs[0].name == "Pack One"
        assert packs[0].platform == T3KPlatform.NAM
        assert packs[1].id == "pack-2"
        assert packs[1].pack_type == T3KPackType.PEDAL

    @pytest.mark.asyncio
    async def test_get_packs_sends_correct_request(
        self, api_client: T3KAPIClient, mock_httpx_client: AsyncMock
    ) -> None:
        """get_packs should send request with correct pagination parameters."""
        mock_httpx_client.get.return_value = Response(
            status_code=200,
            json={"items": []},
            request=Request("GET", "https://api.tone3000.com/packs"),
        )

        await api_client.get_packs(page=2, per_page=50)

        # Verify request parameters
        mock_httpx_client.get.assert_called_once()
        call_args = mock_httpx_client.get.call_args
        assert "/packs" in str(call_args[0][0])
        assert call_args[1]["params"]["page"] == 2
        assert call_args[1]["params"]["per_page"] == 50

    @pytest.mark.asyncio
    async def test_get_packs_includes_auth_header(
        self, api_client: T3KAPIClient, mock_httpx_client: AsyncMock
    ) -> None:
        """get_packs should include API key in Authorization header."""
        mock_httpx_client.get.return_value = Response(
            status_code=200,
            json={"items": []},
            request=Request("GET", "https://api.tone3000.com/packs"),
        )

        await api_client.get_packs(page=1, per_page=10)

        call_args = mock_httpx_client.get.call_args
        assert call_args[1]["headers"]["Authorization"] == "Bearer test-api-key"


class TestT3KAPIClientGetPack:
    """Test T3KAPIClient.get_pack() method."""

    @pytest.mark.asyncio
    async def test_get_pack_returns_single_pack(
        self, api_client: T3KAPIClient, mock_httpx_client: AsyncMock
    ) -> None:
        """get_pack should return a single T3KPack entity."""
        mock_response_data = {
            "id": "pack-123",
            "name": "Test Pack",
            "slug": "test-pack",
            "creator_id": "creator-1",
            "description": "A test pack",
            "thumbnail_url": "https://t3k.com/pack.jpg",
            "platform": "nam",
            "pack_type": "amp",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-02T00:00:00Z",
        }

        mock_httpx_client.get.return_value = Response(
            status_code=200,
            json=mock_response_data,
            request=Request("GET", "https://api.tone3000.com/packs/pack-123"),
        )

        pack = await api_client.get_pack(pack_id="pack-123")

        assert isinstance(pack, T3KPack)
        assert pack.id == "pack-123"
        assert pack.name == "Test Pack"
        assert pack.platform == T3KPlatform.NAM

    @pytest.mark.asyncio
    async def test_get_pack_sends_correct_request(
        self, api_client: T3KAPIClient, mock_httpx_client: AsyncMock
    ) -> None:
        """get_pack should request the correct pack by ID."""
        mock_httpx_client.get.return_value = Response(
            status_code=200,
            json={
                "id": "pack-456",
                "name": "Pack",
                "slug": "pack",
                "creator_id": "c1",
                "description": "desc",
                "thumbnail_url": "url",
                "platform": "ir",
                "pack_type": "ir",
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z",
            },
            request=Request("GET", "https://api.tone3000.com/packs/pack-456"),
        )

        await api_client.get_pack(pack_id="pack-456")

        call_args = mock_httpx_client.get.call_args
        assert "/packs/pack-456" in str(call_args[0][0])


class TestT3KAPIClientGetModels:
    """Test T3KAPIClient.get_models() method."""

    @pytest.mark.asyncio
    async def test_get_models_returns_list_of_models(
        self, api_client: T3KAPIClient, mock_httpx_client: AsyncMock
    ) -> None:
        """get_models should return a list of T3KModel entities for a pack."""
        mock_response_data = {
            "items": [
                {
                    "id": "model-1",
                    "pack_id": "pack-123",
                    "name": "Model One",
                    "filename": "model1.nam",
                    "file_size": 1024000,
                    "download_url": "https://t3k.com/download/model1.nam",
                    "checksum": "abc123",
                    "created_at": "2024-01-01T00:00:00Z",
                    "updated_at": "2024-01-02T00:00:00Z",
                },
                {
                    "id": "model-2",
                    "pack_id": "pack-123",
                    "name": "Model Two",
                    "filename": "model2.nam",
                    "file_size": 2048000,
                    "download_url": "https://t3k.com/download/model2.nam",
                    "checksum": "def456",
                    "created_at": "2024-01-03T00:00:00Z",
                    "updated_at": "2024-01-04T00:00:00Z",
                },
            ]
        }

        mock_httpx_client.get.return_value = Response(
            status_code=200,
            json=mock_response_data,
            request=Request("GET", "https://api.tone3000.com/packs/pack-123/models"),
        )

        models = await api_client.get_models(pack_id="pack-123")

        assert len(models) == 2
        assert all(isinstance(model, T3KModel) for model in models)
        assert models[0].id == "model-1"
        assert models[0].pack_id == "pack-123"
        assert models[0].filename == "model1.nam"
        assert models[1].id == "model-2"

    @pytest.mark.asyncio
    async def test_get_models_sends_correct_request(
        self, api_client: T3KAPIClient, mock_httpx_client: AsyncMock
    ) -> None:
        """get_models should request models for the correct pack ID."""
        mock_httpx_client.get.return_value = Response(
            status_code=200,
            json={"items": []},
            request=Request("GET", "https://api.tone3000.com/packs/pack-789/models"),
        )

        await api_client.get_models(pack_id="pack-789")

        call_args = mock_httpx_client.get.call_args
        assert "/packs/pack-789/models" in str(call_args[0][0])


class TestT3KAPIClientGetCreators:
    """Test T3KAPIClient.get_creators() method."""

    @pytest.mark.asyncio
    async def test_get_creators_returns_list_of_creators(
        self, api_client: T3KAPIClient, mock_httpx_client: AsyncMock
    ) -> None:
        """get_creators should return a list of T3KCreator entities."""
        mock_response_data = {
            "items": [
                {
                    "id": "creator-1",
                    "username": "user1",
                    "display_name": "User One",
                    "avatar_url": "https://t3k.com/avatar1.jpg",
                    "profile_url": "https://t3k.com/profile/user1",
                },
                {
                    "id": "creator-2",
                    "username": "user2",
                    "display_name": "User Two",
                    "avatar_url": "https://t3k.com/avatar2.jpg",
                    "profile_url": "https://t3k.com/profile/user2",
                },
            ]
        }

        mock_httpx_client.get.return_value = Response(
            status_code=200,
            json=mock_response_data,
            request=Request("GET", "https://api.tone3000.com/creators"),
        )

        creators = await api_client.get_creators(page=1, per_page=10)

        assert len(creators) == 2
        assert all(isinstance(creator, T3KCreator) for creator in creators)
        assert creators[0].id == "creator-1"
        assert creators[0].username == "user1"
        assert creators[1].display_name == "User Two"

    @pytest.mark.asyncio
    async def test_get_creators_sends_correct_request(
        self, api_client: T3KAPIClient, mock_httpx_client: AsyncMock
    ) -> None:
        """get_creators should send request with correct pagination."""
        mock_httpx_client.get.return_value = Response(
            status_code=200,
            json={"items": []},
            request=Request("GET", "https://api.tone3000.com/creators"),
        )

        await api_client.get_creators(page=3, per_page=25)

        call_args = mock_httpx_client.get.call_args
        assert "/creators" in str(call_args[0][0])
        assert call_args[1]["params"]["page"] == 3
        assert call_args[1]["params"]["per_page"] == 25


class TestT3KAPIClientErrorHandling:
    """Test T3K API client error handling."""

    @pytest.mark.asyncio
    async def test_raises_rate_limit_error_on_429(
        self, api_client: T3KAPIClient, mock_httpx_client: AsyncMock
    ) -> None:
        """API client should raise T3KRateLimitError on 429 status."""
        mock_response = Response(
            status_code=429,
            json={"error": "Rate limit exceeded"},
            request=Request("GET", "https://api.tone3000.com/packs"),
        )
        mock_httpx_client.get.return_value = mock_response

        with pytest.raises(T3KRateLimitError, match="Rate limit exceeded"):
            await api_client.get_packs(page=1, per_page=10)

    @pytest.mark.asyncio
    async def test_raises_api_error_on_404(
        self, api_client: T3KAPIClient, mock_httpx_client: AsyncMock
    ) -> None:
        """API client should raise T3KAPIError on 404 status."""
        mock_response = Response(
            status_code=404,
            json={"error": "Pack not found"},
            request=Request("GET", "https://api.tone3000.com/packs/missing"),
        )
        mock_httpx_client.get.return_value = mock_response

        with pytest.raises(T3KAPIError, match="Pack not found"):
            await api_client.get_pack(pack_id="missing")

    @pytest.mark.asyncio
    async def test_raises_api_error_on_500(
        self, api_client: T3KAPIClient, mock_httpx_client: AsyncMock
    ) -> None:
        """API client should raise T3KAPIError on 500 status."""
        mock_response = Response(
            status_code=500,
            json={"error": "Internal server error"},
            request=Request("GET", "https://api.tone3000.com/packs"),
        )
        mock_httpx_client.get.return_value = mock_response

        with pytest.raises(T3KAPIError, match="Internal server error"):
            await api_client.get_packs(page=1, per_page=10)

    @pytest.mark.asyncio
    async def test_raises_api_error_on_invalid_json(
        self, api_client: T3KAPIClient, mock_httpx_client: AsyncMock
    ) -> None:
        """API client should raise T3KAPIError on invalid JSON response."""
        # Create a response with invalid JSON structure
        mock_response = Response(
            status_code=200,
            content=b"invalid json",
            request=Request("GET", "https://api.tone3000.com/packs"),
        )
        mock_httpx_client.get.return_value = mock_response

        with pytest.raises(T3KAPIError, match="Invalid JSON"):
            await api_client.get_packs(page=1, per_page=10)


class TestT3KAPIClientRateLimiting:
    """Test T3K API client rate limiting integration."""

    @pytest.mark.asyncio
    async def test_uses_rate_limiter_for_list_endpoints(self, mock_httpx_client: AsyncMock) -> None:
        """API client should apply rate limiter to list endpoints."""
        client = T3KAPIClient(
            base_url="https://api.tone3000.com",
            api_key="test-key",
            list_requests_per_second=10,
        )
        client._client = mock_httpx_client

        mock_httpx_client.get.return_value = Response(
            status_code=200,
            json={"items": []},
            request=Request("GET", "https://api.tone3000.com/packs"),
        )

        # Rate limiter should be configured with the provided value
        assert client._list_rate_limiter is not None

    @pytest.mark.asyncio
    async def test_uses_rate_limiter_for_detail_endpoints(
        self, mock_httpx_client: AsyncMock
    ) -> None:
        """API client should apply rate limiter to detail endpoints."""
        client = T3KAPIClient(
            base_url="https://api.tone3000.com",
            api_key="test-key",
            detail_requests_per_second=30,
        )
        client._client = mock_httpx_client

        mock_httpx_client.get.return_value = Response(
            status_code=200,
            json={
                "id": "pack-1",
                "name": "Pack",
                "slug": "pack",
                "creator_id": "c1",
                "description": "desc",
                "thumbnail_url": "url",
                "platform": "nam",
                "pack_type": "amp",
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z",
            },
            request=Request("GET", "https://api.tone3000.com/packs/pack-1"),
        )

        # Rate limiter should be configured with the provided value
        assert client._detail_rate_limiter is not None


class TestT3KAPIClientCircuitBreaker:
    """Test T3K API client circuit breaker integration."""

    @pytest.mark.asyncio
    async def test_uses_circuit_breaker(self, mock_httpx_client: AsyncMock) -> None:
        """API client should wrap requests with circuit breaker."""
        client = T3KAPIClient(
            base_url="https://api.tone3000.com",
            api_key="test-key",
            circuit_breaker_threshold=3,
            circuit_breaker_timeout=5,
        )
        client._client = mock_httpx_client

        # Circuit breaker should be configured
        assert client._circuit_breaker is not None

    @pytest.mark.asyncio
    async def test_circuit_breaker_opens_after_failures(self, mock_httpx_client: AsyncMock) -> None:
        """Circuit breaker should open after consecutive failures."""
        client = T3KAPIClient(
            base_url="https://api.tone3000.com",
            api_key="test-key",
            circuit_breaker_threshold=2,
            circuit_breaker_timeout=5,
        )
        client._client = mock_httpx_client

        # Mock consecutive failures
        mock_httpx_client.get.return_value = Response(
            status_code=500,
            json={"error": "Server error"},
            request=Request("GET", "https://api.tone3000.com/packs"),
        )

        # First failure
        with pytest.raises(T3KAPIError):
            await client.get_packs(page=1, per_page=10)

        # Second failure should open the breaker
        with pytest.raises(T3KAPIError):
            await client.get_packs(page=1, per_page=10)

        # Third request should be rejected by open circuit breaker
        with pytest.raises(T3KAPIError, match="Circuit breaker"):
            await client.get_packs(page=1, per_page=10)
