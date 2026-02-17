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
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pytest


class FakeResponse:
    """Test double for httpx.Response."""

    def __init__(
        self,
        status_code: int = 200,
        json_data: dict | list | None = None,
        text: str = "",
    ) -> None:
        self.status_code = status_code
        self._json_data = json_data or {}
        self.text = text

    def json(self) -> dict | list:
        return self._json_data


class FakeAsyncClient:
    """Test double for httpx.AsyncClient that records HTTP calls."""

    def __init__(
        self,
        *,
        get_responses: list[FakeResponse] | None = None,
        post_response: FakeResponse | None = None,
        error: Exception | None = None,
    ) -> None:
        self._get_responses = get_responses or []
        self._get_index = 0
        self._post_response = post_response
        self._error = error
        self.get_calls: list[str] = []
        self.post_calls: list[str] = []

    async def get(self, url: str) -> FakeResponse:
        self.get_calls.append(url)
        if self._error:
            raise self._error
        resp = self._get_responses[self._get_index]
        self._get_index += 1
        return resp

    async def post(self, url: str) -> FakeResponse:
        self.post_calls.append(url)
        if self._error:
            raise self._error
        return self._post_response

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        pass


def _patch_httpx_client(monkeypatch: pytest.MonkeyPatch, client: FakeAsyncClient) -> None:
    """Replace httpx.AsyncClient with a factory returning the fake client."""

    class FakeClientFactory:
        def __init__(self, **_kwargs):
            pass

        async def __aenter__(self):
            return client

        async def __aexit__(self, *_args):
            pass

    monkeypatch.setattr("scripts.gts_admin.httpx.AsyncClient", FakeClientFactory)


class TestGtsAdminCLIExists:
    """Test that the gts-admin script exists and is importable."""

    def test_script_exists_and_is_importable(self) -> None:
        """gts-admin script exists at scripts/gts-admin and has main function."""
        from scripts.gts_admin import main

        assert callable(main)

    def test_script_has_cli_parser(self) -> None:
        """gts-admin script has CLI argument parser."""
        from scripts.gts_admin import create_parser

        parser = create_parser()
        assert parser is not None


class TestGtsAdminSourceStatus:
    """Tests for 'just admin source-status <source>' command."""

    async def test_source_status_calls_correct_endpoint(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """source-status command calls GET /api/admin/sources/{source}/sync/status."""
        from scripts.gts_admin import source_status

        client = FakeAsyncClient(
            get_responses=[
                FakeResponse(
                    json_data={
                        "status": "idle",
                        "enabled": True,
                        "checkpoint": "2024-01-01T00:00:00Z",
                    }
                )
            ]
        )
        _patch_httpx_client(monkeypatch, client)

        await source_status("t3k", base_url="http://localhost:8001")

        assert client.get_calls == ["http://localhost:8001/api/admin/sources/t3k/sync/status"]

    async def test_source_status_displays_table_format(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """source-status command displays sync status as table."""
        from scripts.gts_admin import source_status

        client = FakeAsyncClient(
            get_responses=[
                FakeResponse(
                    json_data={
                        "status": "idle",
                        "enabled": True,
                        "checkpoint": "2024-01-01T00:00:00Z",
                    }
                )
            ]
        )
        _patch_httpx_client(monkeypatch, client)

        await source_status("t3k", base_url="http://localhost:8001")

        captured = capsys.readouterr().out
        assert "status" in captured.lower()
        assert "idle" in captured
        assert "checkpoint" in captured.lower()


class TestGtsAdminSourceSync:
    """Tests for 'just admin source-sync <source>' command."""

    async def test_source_sync_calls_correct_endpoint(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """source-sync command calls POST /api/admin/sources/{source}/sync."""
        from scripts.gts_admin import source_sync

        client = FakeAsyncClient(
            post_response=FakeResponse(
                status_code=202,
                json_data={"message": "Sync triggered for t3k"},
            )
        )
        _patch_httpx_client(monkeypatch, client)

        await source_sync("t3k", base_url="http://localhost:8001")

        assert client.post_calls == ["http://localhost:8001/api/admin/sources/t3k/sync"]

    async def test_source_sync_shows_confirmation(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """source-sync command displays confirmation message."""
        from scripts.gts_admin import source_sync

        client = FakeAsyncClient(
            post_response=FakeResponse(
                status_code=202,
                json_data={"message": "Sync triggered for t3k"},
            )
        )
        _patch_httpx_client(monkeypatch, client)

        await source_sync("t3k", base_url="http://localhost:8001")

        captured = capsys.readouterr().out
        assert "triggered" in captured.lower()


class TestGtsAdminJobs:
    """Tests for 'just admin jobs [--status=STATUS]' command."""

    async def test_jobs_calls_correct_endpoint_without_filter(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """jobs command calls GET /api/admin/jobs without status filter."""
        from scripts.gts_admin import list_jobs

        client = FakeAsyncClient(get_responses=[FakeResponse(json_data=[])])
        _patch_httpx_client(monkeypatch, client)

        await list_jobs(status=None, base_url="http://localhost:8001")

        assert client.get_calls == ["http://localhost:8001/api/admin/jobs"]

    async def test_jobs_calls_correct_endpoint_with_status_filter(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """jobs command calls GET /api/admin/jobs?status=running when filtered."""
        from scripts.gts_admin import list_jobs

        client = FakeAsyncClient(get_responses=[FakeResponse(json_data=[])])
        _patch_httpx_client(monkeypatch, client)

        await list_jobs(status="running", base_url="http://localhost:8001")

        assert "status=running" in client.get_calls[0]

    async def test_jobs_displays_table_format(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """jobs command displays job list in table format."""
        from scripts.gts_admin import list_jobs

        client = FakeAsyncClient(
            get_responses=[
                FakeResponse(
                    json_data=[
                        {
                            "id": "123e4567-e89b-12d3-a456-426614174000",
                            "job_type": "audio_processing",
                            "status": "running",
                            "created_at": "2024-01-01T00:00:00Z",
                        }
                    ]
                )
            ]
        )
        _patch_httpx_client(monkeypatch, client)

        await list_jobs(status=None, base_url="http://localhost:8001")

        captured = capsys.readouterr().out
        assert "type" in captured.lower()
        assert "status" in captured.lower()


class TestGtsAdminJobHealth:
    """Tests for 'just admin job-health' command."""

    async def test_job_health_calls_health_endpoint(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """job-health command calls GET /health endpoint."""
        from scripts.gts_admin import job_health

        client = FakeAsyncClient(
            get_responses=[
                FakeResponse(
                    json_data={
                        "status": "healthy",
                        "redis": "connected",
                        "database": "connected",
                        "uptime": 1234.5,
                    }
                )
            ]
        )
        _patch_httpx_client(monkeypatch, client)

        await job_health(base_url="http://localhost:8001")

        assert client.get_calls == ["http://localhost:8001/health"]

    async def test_job_health_displays_redis_db_uptime(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """job-health command displays Redis, DB, uptime info."""
        from scripts.gts_admin import job_health

        client = FakeAsyncClient(
            get_responses=[
                FakeResponse(
                    json_data={
                        "status": "healthy",
                        "redis": "connected",
                        "database": "connected",
                        "uptime": 1234.5,
                    }
                ),
            ]
        )
        _patch_httpx_client(monkeypatch, client)

        await job_health(base_url="http://localhost:8001")

        captured = capsys.readouterr().out
        assert "redis" in captured.lower()
        assert "database" in captured.lower()
        assert "uptime" in captured.lower()


class TestGtsAdminUnlockSync:
    """Tests for 'just admin unlock-sync <source>' command."""

    async def test_unlock_sync_calls_correct_endpoint(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """unlock-sync command calls POST /api/admin/sources/{source}/sync/unlock."""
        from scripts.gts_admin import unlock_sync

        client = FakeAsyncClient(
            post_response=FakeResponse(json_data={"message": "Sync lock released for t3k"})
        )
        _patch_httpx_client(monkeypatch, client)

        await unlock_sync("t3k", base_url="http://localhost:8001")

        assert client.post_calls == ["http://localhost:8001/api/admin/sources/t3k/sync/unlock"]

    async def test_unlock_sync_displays_confirmation(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """unlock-sync command displays confirmation message."""
        from scripts.gts_admin import unlock_sync

        client = FakeAsyncClient(
            post_response=FakeResponse(json_data={"message": "Sync lock released for t3k"})
        )
        _patch_httpx_client(monkeypatch, client)

        await unlock_sync("t3k", base_url="http://localhost:8001")

        captured = capsys.readouterr().out
        assert "released" in captured.lower()


class TestGtsAdminUnlockScheduler:
    """Tests for 'just admin unlock-scheduler' command."""

    async def test_unlock_scheduler_calls_correct_endpoint(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """unlock-scheduler command calls POST /api/admin/scheduler/unlock."""
        from scripts.gts_admin import unlock_scheduler

        client = FakeAsyncClient(
            post_response=FakeResponse(json_data={"message": "Scheduler lock released"})
        )
        _patch_httpx_client(monkeypatch, client)

        await unlock_scheduler(base_url="http://localhost:8001")

        assert client.post_calls == ["http://localhost:8001/api/admin/scheduler/unlock"]

    async def test_unlock_scheduler_displays_confirmation(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """unlock-scheduler command displays confirmation message."""
        from scripts.gts_admin import unlock_scheduler

        client = FakeAsyncClient(
            post_response=FakeResponse(json_data={"message": "Scheduler lock released"})
        )
        _patch_httpx_client(monkeypatch, client)

        await unlock_scheduler(base_url="http://localhost:8001")

        captured = capsys.readouterr().out
        assert "released" in captured.lower()


class TestGtsAdminConnectionErrors:
    """Tests for connection error handling."""

    async def test_connection_error_produces_clear_message(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Connection errors produce user-friendly error message."""
        from scripts.gts_admin import source_status

        client = FakeAsyncClient(error=ConnectionError("Connection refused"))
        _patch_httpx_client(monkeypatch, client)

        with contextlib.suppress(SystemExit):
            await source_status("t3k", base_url="http://localhost:8001")

        captured = capsys.readouterr().out
        assert "worker" in captured.lower()
        assert "reachable" in captured.lower() or "not running" in captured.lower()

    async def test_http_error_displays_status_code(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """HTTP errors display status code and message."""
        from scripts.gts_admin import source_status

        client = FakeAsyncClient(
            get_responses=[FakeResponse(status_code=404, text="Source not found")]
        )
        _patch_httpx_client(monkeypatch, client)

        with contextlib.suppress(SystemExit):
            await source_status("unknown", base_url="http://localhost:8001")

        captured = capsys.readouterr().out
        assert "404" in captured or "not found" in captured.lower()


class TestGtsAdminDockerAndHostURLs:
    """Tests for Docker internal and host URL handling."""

    def test_uses_docker_internal_url_by_default(self) -> None:
        """CLI uses http://worker:8001 for Docker internal communication by default."""
        from scripts.gts_admin import get_base_url

        url = get_base_url()
        assert url == "http://worker:8001"

    def test_supports_localhost_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """CLI supports http://localhost:8001 override for host execution."""
        from scripts.gts_admin import get_base_url

        monkeypatch.setenv("GTS_WORKER_URL", "http://localhost:8001")
        url = get_base_url()
        assert url == "http://localhost:8001"


class TestJustfileRegistration:
    """Tests for justfile admin recipe registration."""

    def test_justfile_has_admin_recipe(self) -> None:
        """Justfile contains 'admin' recipe that calls scripts/gts-admin."""
        import re
        from pathlib import Path

        justfile_path = Path("/app/justfile")
        assert justfile_path.exists()

        justfile_content = justfile_path.read_text()

        admin_recipe_pattern = r"^admin\s+.*:.*\n.*gts-admin"
        assert re.search(
            admin_recipe_pattern, justfile_content, re.MULTILINE
        ), "justfile must have 'admin' recipe that calls scripts/gts-admin"

    def test_justfile_admin_recipe_accepts_arguments(self) -> None:
        """Justfile admin recipe accepts variable arguments."""
        import re
        from pathlib import Path

        justfile_path = Path("/app/justfile")
        justfile_content = justfile_path.read_text()

        admin_args_pattern = r"^admin\s+[+*]"
        assert re.search(
            admin_args_pattern, justfile_content, re.MULTILINE
        ), "justfile admin recipe must accept variable arguments (+ARGS or *ARGS)"


class TestGtsAdminMainEntryPoint:
    """Tests for main entry point and CLI routing."""

    def test_main_parses_subcommands(self) -> None:
        """main() function parses subcommands correctly."""
        from scripts.gts_admin import create_parser

        parser = create_parser()

        args = parser.parse_args(["source-status", "t3k"])
        assert args.command == "source-status"
        assert args.source == "t3k"

        args = parser.parse_args(["source-sync", "t3k"])
        assert args.command == "source-sync"
        assert args.source == "t3k"

        args = parser.parse_args(["jobs"])
        assert args.command == "jobs"

        args = parser.parse_args(["jobs", "--status", "running"])
        assert args.command == "jobs"
        assert args.status == "running"

        args = parser.parse_args(["job-health"])
        assert args.command == "job-health"

        args = parser.parse_args(["unlock-sync", "t3k"])
        assert args.command == "unlock-sync"
        assert args.source == "t3k"

        args = parser.parse_args(["unlock-scheduler"])
        assert args.command == "unlock-scheduler"

    async def test_main_routes_to_correct_functions(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """main() routes subcommands to correct handler functions."""
        from scripts.gts_admin import main

        routed_commands: list[str] = []

        async def fake_source_status(*_args, **_kwargs):
            routed_commands.append("source-status")

        async def fake_source_sync(*_args, **_kwargs):
            routed_commands.append("source-sync")

        async def fake_list_jobs(*_args, **_kwargs):
            routed_commands.append("jobs")

        async def fake_job_health(*_args, **_kwargs):
            routed_commands.append("job-health")

        async def fake_unlock_sync(*_args, **_kwargs):
            routed_commands.append("unlock-sync")

        async def fake_unlock_scheduler(*_args, **_kwargs):
            routed_commands.append("unlock-scheduler")

        monkeypatch.setattr("scripts.gts_admin.source_status", fake_source_status)
        monkeypatch.setattr("scripts.gts_admin.source_sync", fake_source_sync)
        monkeypatch.setattr("scripts.gts_admin.list_jobs", fake_list_jobs)
        monkeypatch.setattr("scripts.gts_admin.job_health", fake_job_health)
        monkeypatch.setattr("scripts.gts_admin.unlock_sync", fake_unlock_sync)
        monkeypatch.setattr("scripts.gts_admin.unlock_scheduler", fake_unlock_scheduler)

        test_cases = [
            (["gts-admin", "source-status", "t3k"], "source-status"),
            (["gts-admin", "source-sync", "t3k"], "source-sync"),
            (["gts-admin", "jobs"], "jobs"),
            (["gts-admin", "job-health"], "job-health"),
            (["gts-admin", "unlock-sync", "t3k"], "unlock-sync"),
            (["gts-admin", "unlock-scheduler"], "unlock-scheduler"),
        ]

        for argv, expected_command in test_cases:
            routed_commands.clear()
            monkeypatch.setattr("sys.argv", argv)
            await main()
            assert routed_commands == [
                expected_command
            ], f"Expected {expected_command}, got {routed_commands}"
