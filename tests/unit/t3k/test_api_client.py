"""Unit tests for T3K API client.

Tests use httpx MockTransport (not unittest.mock) to simulate API responses.
This verifies request construction, response parsing, and error handling.
"""

import json
import tempfile

import pytest
from cryptography.fernet import Fernet
from httpx import AsyncClient, MockTransport, Request, Response

from source_t3k.adapters.inbound.api_client import T3KAPIClient
from source_t3k.adapters.inbound.exceptions import (
    T3KAPIError,
    T3KAuthenticationError,
    T3KRateLimitError,
)
from source_t3k.adapters.inbound.token_manager import T3KTokenManager
from source_t3k.domain.entities import T3KModel, T3KTone, T3KUser

_FERNET_KEY = Fernet.generate_key()
_FERNET = Fernet(_FERNET_KEY)


def _make_token_manager() -> T3KTokenManager:
    """Create a token manager with a pre-set token and a backing auth file.

    The auth file contains encrypted tokens so that re-loading after a
    401 token clear works correctly.
    """
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as auth_file:
        json.dump(
            {
                "access_token": _FERNET.encrypt(b"fake-jwt").decode(),
                "refresh_token": _FERNET.encrypt(b"fake-refresh").decode(),
                "expires_at": "2099-01-01T00:00:00+00:00",
            },
            auth_file,
        )

    tm = T3KTokenManager(
        auth_file_path=auth_file.name,
        base_url="https://t3k.test",
        encryption_key=_FERNET_KEY.decode(),
    )
    # Pre-fill token so it doesn't read the file on the first call
    tm._access_token = "fake-jwt"
    tm._refresh_token = "fake-refresh"
    tm._expires_at = 9999999999.0
    return tm


def _make_client(handler) -> T3KAPIClient:
    """Create a T3KAPIClient wired to a MockTransport handler."""
    tm = _make_token_manager()
    client = T3KAPIClient(
        token_manager=tm,
        base_url="https://t3k.test",
        retry_base_wait=0.01,
    )
    client._client = AsyncClient(transport=MockTransport(handler))
    return client


def _tone_payload(tone_id: int = 1, **overrides) -> dict:
    base = {
        "id": tone_id,
        "title": f"Tone {tone_id}",
        "description": "desc",
        "tags": [{"name": "tag1"}],
        "makes": [{"name": "Fender"}],
        "gear": "amp",
        "platform": "nam",
        "models_count": 2,
        "favorites_count": 5,
        "downloads_count": 50,
        "images": ["https://t3k.test/img.jpg"],
        "user_id": "user-1",
        "url": f"https://t3k.test/tones/{tone_id}",
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-02T00:00:00Z",
    }
    base.update(overrides)
    return base


def _model_payload(model_id: int = 1, tone_id: int = 1) -> dict:
    return {
        "id": model_id,
        "tone_id": tone_id,
        "user_id": "user-1",
        "name": f"Model {model_id}",
        "model_url": f"https://t3k.test/models/{model_id}/file.nam",
        "size": "standard",
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-02T00:00:00Z",
    }


def _user_payload(user_id: str = "user-1") -> dict:
    return {
        "id": user_id,
        "username": f"user_{user_id}",
        "avatar_url": "https://t3k.test/avatar.jpg",
        "bio": "A guitarist",
        "url": f"https://t3k.test/users/{user_id}",
    }


class TestGetTones:
    @pytest.mark.asyncio
    async def test_returns_list_of_tones(self) -> None:
        def handler(request: Request) -> Response:
            return Response(200, json={"data": [_tone_payload(1), _tone_payload(2)]})

        client = _make_client(handler)
        tones = await client.get_tones(page=1, page_size=50)

        assert len(tones) == 2
        assert all(isinstance(t, T3KTone) for t in tones)
        assert tones[0].id == 1
        assert tones[0].title == "Tone 1"

    @pytest.mark.asyncio
    async def test_sends_correct_params(self) -> None:
        captured_request = None

        def handler(request: Request) -> Response:
            nonlocal captured_request
            captured_request = request
            return Response(200, json={"data": []})

        client = _make_client(handler)
        await client.get_tones(page=3, page_size=25, sort="popular")

        assert captured_request is not None
        assert "/api/v1/tones/search" in str(captured_request.url)
        assert "page=3" in str(captured_request.url)
        assert "page_size=25" in str(captured_request.url)

    @pytest.mark.asyncio
    async def test_includes_auth_header(self) -> None:
        captured_request = None

        def handler(request: Request) -> Response:
            nonlocal captured_request
            captured_request = request
            return Response(200, json={"data": []})

        client = _make_client(handler)
        await client.get_tones()

        assert captured_request is not None
        assert captured_request.headers["Authorization"] == "Bearer fake-jwt"


class TestGetModels:
    @pytest.mark.asyncio
    async def test_returns_list_of_models(self) -> None:
        def handler(request: Request) -> Response:
            return Response(200, json={"data": [_model_payload(1), _model_payload(2)]})

        client = _make_client(handler)
        models = await client.get_models(tone_id=42)

        assert len(models) == 2
        assert all(isinstance(m, T3KModel) for m in models)
        assert models[0].id == 1

    @pytest.mark.asyncio
    async def test_sends_tone_id_param(self) -> None:
        captured_request = None

        def handler(request: Request) -> Response:
            nonlocal captured_request
            captured_request = request
            return Response(200, json={"data": []})

        client = _make_client(handler)
        await client.get_models(tone_id=42)

        assert captured_request is not None
        assert "tone_id=42" in str(captured_request.url)


class TestGetUsers:
    @pytest.mark.asyncio
    async def test_returns_list_of_users(self) -> None:
        def handler(request: Request) -> Response:
            return Response(200, json={"data": [_user_payload("u1"), _user_payload("u2")]})

        client = _make_client(handler)
        users = await client.get_users(page=1, page_size=50)

        assert len(users) == 2
        assert all(isinstance(u, T3KUser) for u in users)
        assert users[0].id == "u1"


class TestErrorHandling:
    @pytest.mark.asyncio
    async def test_raises_auth_error_on_401(self) -> None:
        call_count = 0

        def handler(request: Request) -> Response:
            nonlocal call_count
            call_count += 1
            return Response(401, json={"error": "Unauthorized"})

        client = _make_client(handler)

        with pytest.raises(T3KAuthenticationError):
            await client.get_tones()

        # Should have retried once after clearing token
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_raises_rate_limit_error_on_429(self) -> None:
        def handler(request: Request) -> Response:
            return Response(429, json={"error": "Rate limit exceeded"})

        client = _make_client(handler)

        with pytest.raises(T3KRateLimitError):
            await client.get_tones()

    @pytest.mark.asyncio
    async def test_raises_api_error_on_500(self) -> None:
        def handler(request: Request) -> Response:
            return Response(500, json={"error": "Internal server error"})

        client = _make_client(handler)

        with pytest.raises(T3KAPIError, match="Internal server error"):
            await client.get_tones()
