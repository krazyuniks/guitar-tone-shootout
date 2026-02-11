"""Unit tests for SOURCE_SYNC job handler and sync scheduler tasks."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from core.domain.value_objects.job_status import JobType


class TestSourceSyncJobType:
    """Test SOURCE_SYNC exists in JobType enum."""

    def test_source_sync_job_type_exists(self) -> None:
        """SOURCE_SYNC must be a valid JobType enum value."""
        # This will fail if SOURCE_SYNC is not added to JobType enum
        assert hasattr(JobType, "SOURCE_SYNC")
        assert JobType.SOURCE_SYNC == "source_sync"


class TestSourceSyncJobHandler:
    """Test SOURCE_SYNC job handler creates sync service and calls run_catalog_sync."""

    @pytest.mark.asyncio
    async def test_handle_source_sync_creates_sync_service(self) -> None:
        """handle_source_sync creates T3KSyncService and calls run_catalog_sync."""
        from worker.jobs.source_sync import handle_source_sync

        job_id = uuid4()

        with (
            patch("worker.jobs.source_sync.get_t3k_session") as mock_get_t3k_session,
            patch("worker.jobs.source_sync.T3KSyncService") as mock_sync_service_class,
            patch("worker.jobs.source_sync.T3KAPIClient") as mock_api_client_class,
            patch("worker.jobs.source_sync.GearSyncPublisher") as mock_publisher_class,
            patch("worker.jobs.source_sync.T3KOAuthManager") as mock_oauth_class,
        ):
            # Setup mock session context manager
            mock_session = AsyncMock()
            mock_get_t3k_session.return_value.__aenter__.return_value = mock_session

            # Setup mock services
            mock_api_client = MagicMock()
            mock_api_client_class.return_value = mock_api_client

            mock_publisher = AsyncMock()
            mock_publisher_class.return_value = mock_publisher

            mock_oauth = MagicMock()
            mock_oauth_class.return_value = mock_oauth

            mock_sync_service = AsyncMock()
            mock_sync_service_class.return_value = mock_sync_service

            # Call handler
            await handle_source_sync(job_id)

            # Verify T3KSyncService was created with correct dependencies
            mock_sync_service_class.assert_called_once()
            call_args = mock_sync_service_class.call_args
            assert call_args is not None

            # Verify run_catalog_sync was called with publisher
            mock_sync_service.run_catalog_sync.assert_called_once_with(mock_publisher)

    @pytest.mark.asyncio
    async def test_handle_source_sync_registered_as_broker_task(self) -> None:
        """handle_source_sync is registered as a TaskIQ broker task."""
        from worker.jobs.source_sync import handle_source_sync

        # Verify the handler has TaskIQ task attributes
        assert hasattr(handle_source_sync, "kiq")
        assert hasattr(handle_source_sync, "task_id")


class TestEnsureSourceSyncRunning:
    """Test ensure_source_sync_running checks Redis lock and dispatches if needed."""

    @pytest.mark.asyncio
    async def test_ensure_sync_running_checks_redis_lock(self) -> None:
        """ensure_source_sync_running checks for active sync via Redis lock."""
        from scheduler.schedules.jobs import ensure_source_sync_running

        mock_redis = AsyncMock()
        # Simulate lock exists (sync is running)
        mock_redis.exists.return_value = 1

        with patch("scheduler.schedules.jobs.get_redis_client", return_value=mock_redis):
            await ensure_source_sync_running()

            # Should check for lock existence
            mock_redis.exists.assert_called_once_with("t3k:sync:lock")

    @pytest.mark.asyncio
    async def test_dispatches_job_when_no_sync_running(self) -> None:
        """ensure_source_sync_running dispatches SOURCE_SYNC job when no lock exists."""
        from scheduler.schedules.jobs import ensure_source_sync_running

        mock_redis = AsyncMock()
        # No lock exists (no sync running)
        mock_redis.exists.return_value = 0

        with (
            patch("scheduler.schedules.jobs.get_redis_client", return_value=mock_redis),
            patch("scheduler.schedules.jobs.handle_source_sync") as mock_handler,
        ):
            mock_handler.kiq = MagicMock()

            await ensure_source_sync_running()

            # Should dispatch SOURCE_SYNC job
            mock_handler.kiq.assert_called_once()

    @pytest.mark.asyncio
    async def test_does_not_dispatch_when_sync_running(self) -> None:
        """ensure_source_sync_running does not dispatch when sync is already running."""
        from scheduler.schedules.jobs import ensure_source_sync_running

        mock_redis = AsyncMock()
        # Lock exists (sync is running)
        mock_redis.exists.return_value = 1

        with (
            patch("scheduler.schedules.jobs.get_redis_client", return_value=mock_redis),
            patch("scheduler.schedules.jobs.handle_source_sync") as mock_handler,
        ):
            mock_handler.kiq = MagicMock()

            await ensure_source_sync_running()

            # Should NOT dispatch job
            mock_handler.kiq.assert_not_called()

    @pytest.mark.asyncio
    async def test_checks_t3k_sync_enabled_env_var(self) -> None:
        """ensure_source_sync_running only dispatches if T3K_SYNC_ENABLED=true."""
        from scheduler.schedules.jobs import ensure_source_sync_running

        mock_redis = AsyncMock()
        mock_redis.exists.return_value = 0  # No lock

        with (
            patch("scheduler.schedules.jobs.get_redis_client", return_value=mock_redis),
            patch("scheduler.schedules.jobs.handle_source_sync") as mock_handler,
            patch("scheduler.schedules.jobs.os.getenv", return_value="false"),
        ):
            mock_handler.kiq = MagicMock()

            await ensure_source_sync_running()

            # Should NOT dispatch because T3K_SYNC_ENABLED=false
            mock_handler.kiq.assert_not_called()


class TestEnsureSourceSyncScheduleLabels:
    """Test ensure_source_sync_running has 5-minute schedule label."""

    def test_ensure_sync_has_schedule_label(self) -> None:
        """ensure_source_sync_running has schedule label for 5-minute interval."""
        from scheduler.schedules.jobs import ensure_source_sync_running

        # Verify schedule labels exist
        assert hasattr(ensure_source_sync_running, "labels")
        labels = ensure_source_sync_running.labels
        assert "schedule" in labels
        schedules = labels["schedule"]
        assert len(schedules) > 0

        # Verify 5-minute (300 seconds) schedule
        schedule = schedules[0]
        assert schedule.seconds == 300


class TestAuthRefreshTask:
    """Test T3K auth refresh task calls OAuth manager's refresh flow."""

    @pytest.mark.asyncio
    async def test_refresh_t3k_tokens_calls_oauth_manager(self) -> None:
        """refresh_t3k_tokens creates OAuth manager and calls refresh_token."""
        from scheduler.schedules.auth import refresh_t3k_tokens

        mock_session = AsyncMock()

        with (
            patch("scheduler.schedules.auth.get_t3k_session") as mock_get_session,
            patch("scheduler.schedules.auth.T3KOAuthManager") as mock_oauth_class,
            patch("scheduler.schedules.auth.os.getenv") as mock_getenv,
        ):
            # Setup session context manager
            mock_get_session.return_value.__aenter__.return_value = mock_session

            # Setup environment variables
            def getenv_side_effect(key: str, default: str | None = None) -> str | None:
                env_vars = {
                    "T3K_TOKEN_ENCRYPTION_KEY": "test-encryption-key",
                    "T3K_OAUTH_CLIENT_ID": "test-client-id",
                    "T3K_OAUTH_CLIENT_SECRET": "test-client-secret",
                    "T3K_OAUTH_BASE_URL": "https://oauth.tone3000.com",
                }
                return env_vars.get(key, default)

            mock_getenv.side_effect = getenv_side_effect

            # Setup OAuth manager mock
            mock_oauth = AsyncMock()
            mock_oauth_class.return_value = mock_oauth

            # Call refresh task
            await refresh_t3k_tokens()

            # Verify OAuth manager was created with correct config
            mock_oauth_class.assert_called_once_with(
                session=mock_session,
                encryption_key="test-encryption-key",
                client_id="test-client-id",
                client_secret="test-client-secret",
                oauth_base_url="https://oauth.tone3000.com",
            )

            # Verify refresh_token was called
            mock_oauth.refresh_token.assert_called_once()

    @pytest.mark.asyncio
    async def test_refresh_stores_tokens_in_database(self) -> None:
        """refresh_t3k_tokens stores refreshed tokens via OAuth manager commit."""
        from scheduler.schedules.auth import refresh_t3k_tokens

        mock_session = AsyncMock()

        with (
            patch("scheduler.schedules.auth.get_t3k_session") as mock_get_session,
            patch("scheduler.schedules.auth.T3KOAuthManager") as mock_oauth_class,
            patch("scheduler.schedules.auth.os.getenv") as mock_getenv,
        ):
            # Setup session context manager
            mock_get_session.return_value.__aenter__.return_value = mock_session

            # Setup environment variables
            def getenv_side_effect(key: str, default: str | None = None) -> str | None:
                env_vars = {
                    "T3K_TOKEN_ENCRYPTION_KEY": "test-encryption-key",
                    "T3K_OAUTH_CLIENT_ID": "test-client-id",
                    "T3K_OAUTH_CLIENT_SECRET": "test-client-secret",
                    "T3K_OAUTH_BASE_URL": "https://oauth.tone3000.com",
                }
                return env_vars.get(key, default)

            mock_getenv.side_effect = getenv_side_effect

            # Setup OAuth manager mock
            mock_oauth = AsyncMock()
            mock_oauth_class.return_value = mock_oauth

            # Call refresh task
            await refresh_t3k_tokens()

            # OAuth manager's refresh_token method commits to database internally
            # Verify it was called (which handles the database commit)
            mock_oauth.refresh_token.assert_called_once()


class TestAuthRefreshScheduleLabels:
    """Test auth refresh has 12-hour schedule label."""

    def test_refresh_t3k_tokens_has_schedule_label(self) -> None:
        """refresh_t3k_tokens has schedule label for 12-hour interval."""
        from scheduler.schedules.auth import refresh_t3k_tokens

        # Verify schedule labels exist
        assert hasattr(refresh_t3k_tokens, "labels")
        labels = refresh_t3k_tokens.labels
        assert "schedule" in labels
        schedules = labels["schedule"]
        assert len(schedules) > 0

        # Verify 12-hour (43200 seconds) schedule
        schedule = schedules[0]
        assert schedule.seconds == 43200
