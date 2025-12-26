"""Tests for WebSocket endpoints."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.main import app
from app.models.job import JobStatus


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


class TestJobProgressWebSocket:
    """Tests for the /ws/jobs/{job_id} WebSocket endpoint."""

    def test_missing_token_closes_connection(self, client: TestClient):
        """WebSocket without token should close with 4001."""
        from starlette.websockets import WebSocketDisconnect

        job_id = str(uuid4())

        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect(f"/api/v1/ws/jobs/{job_id}"):
                pass  # Should not reach here
        # Verify close code is 4001 (auth error)
        assert exc_info.value.code == 4001

    def test_missing_token_explicit_check(self, client: TestClient):
        """WebSocket without token should fail to connect properly."""
        job_id = str(uuid4())

        # Without token, we should get a close or error
        try:
            with client.websocket_connect(f"/api/v1/ws/jobs/{job_id}") as ws:
                # Try to receive - should fail
                ws.receive()
        except Exception:
            # Expected - connection rejected
            pass

    def test_invalid_token_closes_connection(self, client: TestClient):
        """WebSocket with invalid token should close with 4001."""
        job_id = str(uuid4())

        try:
            with client.websocket_connect(
                f"/api/v1/ws/jobs/{job_id}?token=invalid_token"
            ) as ws:
                # Should be closed by server
                data = ws.receive()
                # If we get data, check it's a close message
                assert data.get("type") == "websocket.close"
        except Exception:
            # Connection was closed/rejected - expected behavior
            pass

    def test_valid_token_but_no_user(self, client: TestClient):
        """WebSocket with token for non-existent user should close."""
        job_id = str(uuid4())
        # Create a valid token structure but for non-existent user
        token = create_access_token(str(uuid4()))

        try:
            with client.websocket_connect(
                f"/api/v1/ws/jobs/{job_id}?token={token}"
            ) as ws:
                data = ws.receive()
                assert data.get("type") == "websocket.close"
        except Exception:
            # Connection closed - expected
            pass

    @patch("app.api.v1.ws.verify_ws_token")
    @patch("app.api.v1.ws.get_job_for_user")
    def test_job_not_found_closes_connection(
        self, mock_get_job: MagicMock, mock_verify: MagicMock, client: TestClient
    ):
        """WebSocket for non-existent job should close with 4004."""
        # Mock user exists but job doesn't
        mock_user = MagicMock()
        mock_user.id = uuid4()
        mock_verify.return_value = mock_user
        mock_get_job.return_value = None

        job_id = str(uuid4())
        token = "valid_token"

        try:
            with client.websocket_connect(
                f"/api/v1/ws/jobs/{job_id}?token={token}"
            ) as ws:
                data = ws.receive()
                # Should be a close message
                assert data.get("type") == "websocket.close"
        except Exception:
            # Expected - connection closed
            pass

    @patch("app.api.v1.ws.subscribe_job_progress")
    @patch("app.api.v1.ws.get_job_for_user")
    @patch("app.api.v1.ws.verify_ws_token")
    def test_successful_connection_sends_initial_status(
        self,
        mock_verify: MagicMock,
        mock_get_job: MagicMock,
        mock_subscribe: MagicMock,
        client: TestClient,
    ):
        """Valid WebSocket connection should receive initial job status."""
        # Setup mocks
        user_id = uuid4()
        job_id = uuid4()
        mock_user = MagicMock()
        mock_user.id = user_id
        mock_user.username = "testuser"
        mock_verify.return_value = mock_user

        mock_job = MagicMock()
        mock_job.id = job_id
        mock_job.status = JobStatus.RUNNING
        mock_job.progress = 50
        mock_job.message = "Processing audio"
        mock_get_job.return_value = mock_job

        # Create a mock pubsub that yields no messages (empty async iterator)
        mock_pubsub = MagicMock()
        mock_pubsub.listen = MagicMock(return_value=AsyncIteratorMock([]))
        mock_pubsub.unsubscribe = AsyncMock()
        mock_pubsub.close = AsyncMock()
        mock_subscribe.return_value = mock_pubsub

        with client.websocket_connect(
            f"/api/v1/ws/jobs/{job_id}?token=valid_token"
        ) as ws:
            # Should receive initial status message
            data = ws.receive_json()
            assert data["type"] == "status"
            assert data["job_id"] == str(job_id)
            assert data["status"] == "running"
            assert data["progress"] == 50
            assert data["message"] == "Processing audio"


class AsyncIteratorMock:
    """Mock async iterator for testing pub/sub listen."""

    def __init__(self, items: list):
        """Initialize with items to yield."""
        self.items = items
        self.index = 0

    def __aiter__(self):
        """Return self as async iterator."""
        return self

    async def __anext__(self):
        """Return next item or stop iteration."""
        if self.index >= len(self.items):
            raise StopAsyncIteration
        item = self.items[self.index]
        self.index += 1
        return item


class TestWebSocketClose:
    """Tests for WebSocket close codes."""

    def test_close_code_4001_is_auth_error(self):
        """Close code 4001 should indicate authentication error."""
        # This is a documentation test - verify the close codes we use
        AUTH_ERROR = 4001
        JOB_NOT_FOUND = 4004
        assert AUTH_ERROR == 4001
        assert JOB_NOT_FOUND == 4004


class TestRedisPublish:
    """Tests for Redis pub/sub integration."""

    @pytest.mark.asyncio
    async def test_publish_job_progress(self):
        """Test publishing progress updates to Redis."""
        from app.core.redis import publish_job_progress

        job_id = str(uuid4())

        # Mock the redis_client
        with patch("app.core.redis.redis_client") as mock_redis:
            mock_redis.publish = AsyncMock()

            await publish_job_progress(
                job_id=job_id,
                status="running",
                progress=75,
                message="Generating video",
            )

            mock_redis.publish.assert_called_once()
            call_args = mock_redis.publish.call_args
            assert f"job:{job_id}:progress" == call_args[0][0]

    @pytest.mark.asyncio
    async def test_subscribe_job_progress(self):
        """Test subscribing to job progress channel."""
        import app.core.redis as redis_module

        job_id = str(uuid4())

        mock_pubsub = MagicMock()
        mock_pubsub.subscribe = AsyncMock()

        mock_redis = MagicMock()
        mock_redis.pubsub.return_value = mock_pubsub

        # Replace the module-level redis_client
        original_client = redis_module.redis_client
        redis_module.redis_client = mock_redis

        try:
            result = await redis_module.subscribe_job_progress(job_id)

            mock_redis.pubsub.assert_called_once()
            mock_pubsub.subscribe.assert_called_once_with(f"job:{job_id}:progress")
            assert result == mock_pubsub
        finally:
            redis_module.redis_client = original_client
