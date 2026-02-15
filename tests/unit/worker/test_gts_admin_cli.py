"""Unit tests for gts-admin CLI tool.

Tests the Python CLI wrapper that calls worker admin API HTTP endpoints.
The CLI is registered as `just admin` in the justfile.

Tests focus on:
- CLI argument parsing and command routing
- HTTP client calls to correct endpoints
- Output formatting (table format)
- Error handling (connection errors)
- Justfile registration
"""

from __future__ import annotations

import contextlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestGtsAdminCLIExists:
    """Test that the gts-admin script exists and is importable."""

    def test_script_exists_and_is_importable(self) -> None:
        """gts-admin script exists at scripts/gts-admin and has main function."""
        # Standard import should work (will fail if file doesn't exist)
        from scripts.gts_admin import main

        assert callable(main)

    def test_script_has_cli_parser(self) -> None:
        """gts-admin script has CLI argument parser."""
        from scripts.gts_admin import create_parser

        parser = create_parser()
        assert parser is not None


class TestGtsAdminSourceStatus:
    """Tests for 'just admin source-status <source>' command."""

    @pytest.mark.asyncio
    async def test_source_status_calls_correct_endpoint(self) -> None:
        """source-status command calls GET /api/admin/sources/{source}/sync/status."""
        from scripts.gts_admin import source_status

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "idle",
            "enabled": True,
            "checkpoint": "2024-01-01T00:00:00Z",
        }

        with patch("scripts.gts_admin.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value.__aenter__.return_value = mock_client

            await source_status("t3k", base_url="http://localhost:8001")

            # Verify correct endpoint was called
            mock_client.get.assert_called_once_with(
                "http://localhost:8001/api/admin/sources/t3k/sync/status"
            )

    @pytest.mark.asyncio
    async def test_source_status_displays_table_format(self) -> None:
        """source-status command displays sync status as table."""
        from scripts.gts_admin import source_status

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "idle",
            "enabled": True,
            "checkpoint": "2024-01-01T00:00:00Z",
        }

        with patch("scripts.gts_admin.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value.__aenter__.return_value = mock_client

            with patch("scripts.gts_admin.print") as mock_print:
                await source_status("t3k", base_url="http://localhost:8001")

                # Verify table output was printed
                printed_output = "\n".join([str(call[0][0]) for call in mock_print.call_args_list])
                assert "status" in printed_output.lower()
                assert "idle" in printed_output
                assert "checkpoint" in printed_output.lower()


class TestGtsAdminSourceSync:
    """Tests for 'just admin source-sync <source>' command."""

    @pytest.mark.asyncio
    async def test_source_sync_calls_correct_endpoint(self) -> None:
        """source-sync command calls POST /api/admin/sources/{source}/sync."""
        from scripts.gts_admin import source_sync

        mock_response = MagicMock()
        mock_response.status_code = 202
        mock_response.json.return_value = {"message": "Sync triggered for t3k"}

        with patch("scripts.gts_admin.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value.__aenter__.return_value = mock_client

            await source_sync("t3k", base_url="http://localhost:8001")

            # Verify correct endpoint was called
            mock_client.post.assert_called_once_with(
                "http://localhost:8001/api/admin/sources/t3k/sync"
            )

    @pytest.mark.asyncio
    async def test_source_sync_shows_confirmation(self) -> None:
        """source-sync command displays confirmation message."""
        from scripts.gts_admin import source_sync

        mock_response = MagicMock()
        mock_response.status_code = 202
        mock_response.json.return_value = {"message": "Sync triggered for t3k"}

        with patch("scripts.gts_admin.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value.__aenter__.return_value = mock_client

            with patch("scripts.gts_admin.print") as mock_print:
                await source_sync("t3k", base_url="http://localhost:8001")

                # Verify confirmation was printed
                printed_output = "\n".join([str(call[0][0]) for call in mock_print.call_args_list])
                assert "triggered" in printed_output.lower()


class TestGtsAdminJobs:
    """Tests for 'just admin jobs [--status=STATUS]' command."""

    @pytest.mark.asyncio
    async def test_jobs_calls_correct_endpoint_without_filter(self) -> None:
        """jobs command calls GET /api/admin/jobs without status filter."""
        from scripts.gts_admin import list_jobs

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = []

        with patch("scripts.gts_admin.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value.__aenter__.return_value = mock_client

            await list_jobs(status=None, base_url="http://localhost:8001")

            # Verify correct endpoint was called
            mock_client.get.assert_called_once()
            call_url = mock_client.get.call_args[0][0]
            assert call_url == "http://localhost:8001/api/admin/jobs"

    @pytest.mark.asyncio
    async def test_jobs_calls_correct_endpoint_with_status_filter(self) -> None:
        """jobs command calls GET /api/admin/jobs?status=running when filtered."""
        from scripts.gts_admin import list_jobs

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = []

        with patch("scripts.gts_admin.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value.__aenter__.return_value = mock_client

            await list_jobs(status="running", base_url="http://localhost:8001")

            # Verify correct endpoint was called with query param
            call_url = mock_client.get.call_args[0][0]
            assert "status=running" in call_url

    @pytest.mark.asyncio
    async def test_jobs_displays_table_format(self) -> None:
        """jobs command displays job list in table format."""
        from scripts.gts_admin import list_jobs

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "job_type": "audio_processing",
                "status": "running",
                "created_at": "2024-01-01T00:00:00Z",
            }
        ]

        with patch("scripts.gts_admin.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value.__aenter__.return_value = mock_client

            with patch("scripts.gts_admin.print") as mock_print:
                await list_jobs(status=None, base_url="http://localhost:8001")

                # Verify table output was printed
                printed_output = "\n".join([str(call[0][0]) for call in mock_print.call_args_list])
                assert "job_type" in printed_output.lower() or "type" in printed_output.lower()
                assert "status" in printed_output.lower()


class TestGtsAdminJobHealth:
    """Tests for 'just admin job-health' command."""

    @pytest.mark.asyncio
    async def test_job_health_calls_health_endpoint(self) -> None:
        """job-health command calls GET /health endpoint."""
        from scripts.gts_admin import job_health

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "healthy",
            "redis": "connected",
            "database": "connected",
            "uptime": 1234.5,
        }

        with patch("scripts.gts_admin.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value.__aenter__.return_value = mock_client

            await job_health(base_url="http://localhost:8001")

            # Verify correct endpoint was called
            mock_client.get.assert_called_once_with("http://localhost:8001/health")

    @pytest.mark.asyncio
    async def test_job_health_displays_redis_db_uptime(self) -> None:
        """job-health command displays Redis, DB, uptime, and active jobs count."""
        from scripts.gts_admin import job_health

        mock_health_response = MagicMock()
        mock_health_response.status_code = 200
        mock_health_response.json.return_value = {
            "status": "healthy",
            "redis": "connected",
            "database": "connected",
            "uptime": 1234.5,
        }

        mock_jobs_response = MagicMock()
        mock_jobs_response.status_code = 200
        mock_jobs_response.json.return_value = [{"id": "1"}, {"id": "2"}]

        with patch("scripts.gts_admin.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            # First call to /health, second call to /api/admin/jobs
            mock_client.get = AsyncMock(side_effect=[mock_health_response, mock_jobs_response])
            mock_client_class.return_value.__aenter__.return_value = mock_client

            with patch("scripts.gts_admin.print") as mock_print:
                await job_health(base_url="http://localhost:8001")

                # Verify health info was printed
                printed_output = "\n".join([str(call[0][0]) for call in mock_print.call_args_list])
                assert "redis" in printed_output.lower()
                assert "database" in printed_output.lower() or "db" in printed_output.lower()
                assert "uptime" in printed_output.lower()
                assert "active" in printed_output.lower() or "jobs" in printed_output.lower()


class TestGtsAdminUnlockSync:
    """Tests for 'just admin unlock-sync <source>' command."""

    @pytest.mark.asyncio
    async def test_unlock_sync_calls_correct_endpoint(self) -> None:
        """unlock-sync command calls POST /api/admin/sources/{source}/sync/unlock."""
        from scripts.gts_admin import unlock_sync

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"message": "Sync lock released for t3k"}

        with patch("scripts.gts_admin.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value.__aenter__.return_value = mock_client

            await unlock_sync("t3k", base_url="http://localhost:8001")

            # Verify correct endpoint was called
            mock_client.post.assert_called_once_with(
                "http://localhost:8001/api/admin/sources/t3k/sync/unlock"
            )

    @pytest.mark.asyncio
    async def test_unlock_sync_displays_confirmation(self) -> None:
        """unlock-sync command displays confirmation message."""
        from scripts.gts_admin import unlock_sync

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"message": "Sync lock released for t3k"}

        with patch("scripts.gts_admin.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value.__aenter__.return_value = mock_client

            with patch("scripts.gts_admin.print") as mock_print:
                await unlock_sync("t3k", base_url="http://localhost:8001")

                # Verify confirmation was printed
                printed_output = "\n".join([str(call[0][0]) for call in mock_print.call_args_list])
                assert "released" in printed_output.lower() or "unlocked" in printed_output.lower()


class TestGtsAdminUnlockScheduler:
    """Tests for 'just admin unlock-scheduler' command."""

    @pytest.mark.asyncio
    async def test_unlock_scheduler_calls_correct_endpoint(self) -> None:
        """unlock-scheduler command calls POST /api/admin/scheduler/unlock."""
        from scripts.gts_admin import unlock_scheduler

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"message": "Scheduler lock released"}

        with patch("scripts.gts_admin.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value.__aenter__.return_value = mock_client

            await unlock_scheduler(base_url="http://localhost:8001")

            # Verify correct endpoint was called
            mock_client.post.assert_called_once_with(
                "http://localhost:8001/api/admin/scheduler/unlock"
            )

    @pytest.mark.asyncio
    async def test_unlock_scheduler_displays_confirmation(self) -> None:
        """unlock-scheduler command displays confirmation message."""
        from scripts.gts_admin import unlock_scheduler

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"message": "Scheduler lock released"}

        with patch("scripts.gts_admin.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value.__aenter__.return_value = mock_client

            with patch("scripts.gts_admin.print") as mock_print:
                await unlock_scheduler(base_url="http://localhost:8001")

                # Verify confirmation was printed
                printed_output = "\n".join([str(call[0][0]) for call in mock_print.call_args_list])
                assert "released" in printed_output.lower() or "unlocked" in printed_output.lower()


class TestGtsAdminConnectionErrors:
    """Tests for connection error handling."""

    @pytest.mark.asyncio
    async def test_connection_error_produces_clear_message(self) -> None:
        """Connection errors produce user-friendly error message."""
        from scripts.gts_admin import source_status

        with patch("scripts.gts_admin.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=Exception("Connection refused"))
            mock_client_class.return_value.__aenter__.return_value = mock_client

            with patch("scripts.gts_admin.print") as mock_print:
                # Should not raise exception, should print error
                with contextlib.suppress(SystemExit):
                    await source_status("t3k", base_url="http://localhost:8001")

                # Verify error message was printed
                printed_output = "\n".join([str(call[0][0]) for call in mock_print.call_args_list])
                assert "worker" in printed_output.lower()
                assert (
                    "reachable" in printed_output.lower() or "not running" in printed_output.lower()
                )

    @pytest.mark.asyncio
    async def test_http_error_displays_status_code(self) -> None:
        """HTTP errors display status code and message."""
        from scripts.gts_admin import source_status

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Source not found"

        with patch("scripts.gts_admin.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value.__aenter__.return_value = mock_client

            with patch("scripts.gts_admin.print") as mock_print:
                with contextlib.suppress(SystemExit):
                    await source_status("unknown", base_url="http://localhost:8001")

                # Verify error was printed
                printed_output = "\n".join([str(call[0][0]) for call in mock_print.call_args_list])
                assert "404" in printed_output or "not found" in printed_output.lower()


class TestGtsAdminDockerAndHostURLs:
    """Tests for Docker internal and host URL handling."""

    @pytest.mark.asyncio
    async def test_uses_docker_internal_url_by_default(self) -> None:
        """CLI uses http://worker:8001 for Docker internal communication by default."""
        from scripts.gts_admin import get_base_url

        # When not overridden, should use Docker internal URL
        url = get_base_url()
        assert url == "http://worker:8001"

    @pytest.mark.asyncio
    async def test_supports_localhost_override(self) -> None:
        """CLI supports http://localhost:8001 override for host execution."""
        from scripts.gts_admin import get_base_url

        # When ENV var set, should use localhost
        with patch.dict("os.environ", {"GTS_WORKER_URL": "http://localhost:8001"}):
            url = get_base_url()
            assert url == "http://localhost:8001"


class TestJustfileRegistration:
    """Tests for justfile admin recipe registration."""

    def test_justfile_has_admin_recipe(self) -> None:
        """Justfile contains 'admin' recipe that calls scripts/gts-admin."""
        import re
        from pathlib import Path

        # Path in Docker container is /app
        justfile_path = Path("/app/justfile")
        assert justfile_path.exists()

        justfile_content = justfile_path.read_text()

        # Check for admin recipe
        # Pattern: admin command at start of line, followed by recipe body
        admin_recipe_pattern = r"^admin\s+.*:.*\n.*gts-admin"
        assert re.search(admin_recipe_pattern, justfile_content, re.MULTILINE), (
            "justfile must have 'admin' recipe that calls scripts/gts-admin"
        )

    def test_justfile_admin_recipe_accepts_arguments(self) -> None:
        """Justfile admin recipe accepts variable arguments."""
        import re
        from pathlib import Path

        # Path in Docker container is /app
        justfile_path = Path("/app/justfile")
        justfile_content = justfile_path.read_text()

        # Check for admin recipe with arguments
        # Pattern: admin +ARGS: or admin *ARGS:
        admin_args_pattern = r"^admin\s+[+*]"
        assert re.search(admin_args_pattern, justfile_content, re.MULTILINE), (
            "justfile admin recipe must accept variable arguments (+ARGS or *ARGS)"
        )


class TestGtsAdminMainEntryPoint:
    """Tests for main entry point and CLI routing."""

    def test_main_parses_subcommands(self) -> None:
        """main() function parses subcommands correctly."""
        from scripts.gts_admin import create_parser

        parser = create_parser()

        # Test source-status subcommand
        args = parser.parse_args(["source-status", "t3k"])
        assert args.command == "source-status"
        assert args.source == "t3k"

        # Test source-sync subcommand
        args = parser.parse_args(["source-sync", "t3k"])
        assert args.command == "source-sync"
        assert args.source == "t3k"

        # Test jobs subcommand
        args = parser.parse_args(["jobs"])
        assert args.command == "jobs"

        # Test jobs with status filter
        args = parser.parse_args(["jobs", "--status", "running"])
        assert args.command == "jobs"
        assert args.status == "running"

        # Test job-health subcommand
        args = parser.parse_args(["job-health"])
        assert args.command == "job-health"

        # Test unlock-sync subcommand
        args = parser.parse_args(["unlock-sync", "t3k"])
        assert args.command == "unlock-sync"
        assert args.source == "t3k"

        # Test unlock-scheduler subcommand
        args = parser.parse_args(["unlock-scheduler"])
        assert args.command == "unlock-scheduler"

    @pytest.mark.asyncio
    async def test_main_routes_to_correct_functions(self) -> None:
        """main() routes subcommands to correct handler functions."""
        from scripts.gts_admin import main

        # Mock all command functions
        with (
            patch("scripts.gts_admin.source_status") as mock_source_status,
            patch("scripts.gts_admin.source_sync") as mock_source_sync,
            patch("scripts.gts_admin.list_jobs") as mock_list_jobs,
            patch("scripts.gts_admin.job_health") as mock_job_health,
            patch("scripts.gts_admin.unlock_sync") as mock_unlock_sync,
            patch("scripts.gts_admin.unlock_scheduler") as mock_unlock_scheduler,
        ):
            # Make all mocks async
            for mock in [
                mock_source_status,
                mock_source_sync,
                mock_list_jobs,
                mock_job_health,
                mock_unlock_sync,
                mock_unlock_scheduler,
            ]:
                mock.return_value = AsyncMock()

            # Test each command routing
            with patch("sys.argv", ["gts-admin", "source-status", "t3k"]):
                await main()
                mock_source_status.assert_called_once()

            with patch("sys.argv", ["gts-admin", "source-sync", "t3k"]):
                await main()
                mock_source_sync.assert_called_once()

            with patch("sys.argv", ["gts-admin", "jobs"]):
                await main()
                mock_list_jobs.assert_called_once()

            with patch("sys.argv", ["gts-admin", "job-health"]):
                await main()
                mock_job_health.assert_called_once()

            with patch("sys.argv", ["gts-admin", "unlock-sync", "t3k"]):
                await main()
                mock_unlock_sync.assert_called_once()

            with patch("sys.argv", ["gts-admin", "unlock-scheduler"]):
                await main()
                mock_unlock_scheduler.assert_called_once()
