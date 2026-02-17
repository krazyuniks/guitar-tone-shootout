"""Integration smoke tests for worker service."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
@pytest.mark.integration
class TestWorkerSmoke:
    """Smoke tests verifying worker service wiring."""

    async def test_admin_app_can_be_created(self) -> None:
        """Test worker admin FastAPI app imports successfully."""
        from worker.admin import app

        assert app is not None
        assert app.title == "GTS Worker Admin API"

    async def test_admin_routes_registered(self) -> None:
        """Test admin API has expected routes."""
        from worker.admin import app

        routes = [r.path for r in app.routes]
        # Verify key admin API routes are registered
        assert "/health" in routes
        assert "/api/admin/jobs" in routes
        assert "/api/admin/jobs/{job_id}" in routes
        assert "/api/admin/jobs/{job_id}/cancel" in routes
        assert "/api/admin/jobs/{job_id}/retry" in routes

    async def test_taskiq_broker_can_be_imported(self) -> None:
        """Test TaskIQ broker can be imported and is valid broker instance."""
        from taskiq import InMemoryBroker
        from taskiq_redis import ListQueueBroker

        from worker.main import broker

        assert broker is not None
        assert isinstance(broker, ListQueueBroker | InMemoryBroker)
        if isinstance(broker, ListQueueBroker):
            # Verify broker has Redis URL stored when Redis is available.
            assert hasattr(broker, "_redis_url")

    async def test_job_handler_functions_can_be_imported(self) -> None:
        """Test job handler functions can be imported."""
        from worker.jobs import (
            handle_shootout_audio_job,
            handle_shootout_job,
            handle_shootout_master_job,
        )

        # Verify handlers exist
        assert handle_shootout_audio_job is not None
        assert handle_shootout_job is not None
        assert handle_shootout_master_job is not None

        # Verify they are callable (TaskIQ decorates them, so check callable instead)
        assert callable(handle_shootout_audio_job)
        assert callable(handle_shootout_job)
        assert callable(handle_shootout_master_job)

    async def test_audio_job_handler_can_be_imported(self) -> None:
        """Test audio job handler can be imported from audio module."""
        from worker.jobs.audio import handle_shootout_audio_job

        assert handle_shootout_audio_job is not None

    async def test_shootout_job_handler_can_be_imported(self) -> None:
        """Test shootout job handler can be imported from shootout module."""
        from worker.jobs.shootout import handle_shootout_job

        assert handle_shootout_job is not None

    async def test_master_audio_function_can_be_imported(self) -> None:
        """Test master audio creation function can be imported."""
        from worker.jobs.master_audio import create_master_audio

        assert create_master_audio is not None

        # Verify it is an async function
        import inspect

        assert inspect.iscoroutinefunction(create_master_audio)

    async def test_progress_publisher_can_be_imported(self) -> None:
        """Test progress publisher function can be imported."""
        from worker.progress import publish_progress

        assert publish_progress is not None

        # Verify it is an async function
        import inspect

        assert inspect.iscoroutinefunction(publish_progress)

    async def test_scheduler_job_functions_can_be_imported(self) -> None:
        """Test scheduler job functions can be imported."""
        from scheduler.schedules.jobs import (
            monitor_stale_jobs,
            process_pending_retries,
            scheduler_heartbeat,
        )

        # Verify all functions exist
        assert monitor_stale_jobs is not None
        assert process_pending_retries is not None
        assert scheduler_heartbeat is not None

        # Verify they are async functions
        import inspect

        assert inspect.iscoroutinefunction(monitor_stale_jobs)
        assert inspect.iscoroutinefunction(process_pending_retries)
        assert inspect.iscoroutinefunction(scheduler_heartbeat)

    async def test_scheduler_functions_have_schedule_labels(self) -> None:
        """Test scheduler functions have TaskIQ schedule labels."""
        from scheduler.schedules.jobs import (
            monitor_stale_jobs,
            process_pending_retries,
            scheduler_heartbeat,
        )

        # Verify schedule labels exist
        assert hasattr(monitor_stale_jobs, "labels")
        assert hasattr(process_pending_retries, "labels")
        assert hasattr(scheduler_heartbeat, "labels")

        # Verify labels contain schedule configuration
        assert "schedule" in monitor_stale_jobs.labels
        assert "schedule" in process_pending_retries.labels
        assert "schedule" in scheduler_heartbeat.labels

    async def test_domain_value_objects_can_be_imported(self) -> None:
        """Test worker domain imports resolve correctly."""
        from core.domain.value_objects.job_status import JobStatus, JobType

        # Verify enums exist
        assert JobStatus is not None
        assert JobType is not None

        # Verify expected enum values
        assert JobStatus.PENDING.value == "pending"
        assert JobStatus.RUNNING.value == "running"
        assert JobStatus.COMPLETED.value == "completed"
        assert JobStatus.FAILED.value == "failed"
        assert JobStatus.CANCELLED.value == "cancelled"
        assert JobStatus.DEAD_LETTERED.value == "dead_lettered"

        assert JobType.SHOOTOUT.value == "shootout"
        assert JobType.SHOOTOUT_AUDIO.value == "shootout_audio"
        assert JobType.SHOOTOUT_MASTER.value == "shootout_master"

    async def test_processing_service_has_enqueue_function(self) -> None:
        """Test processing service module has enqueue_to_worker function."""
        from webapp.services.processing_service import enqueue_to_worker

        assert enqueue_to_worker is not None

        # Verify it is an async function
        import inspect

        assert inspect.iscoroutinefunction(enqueue_to_worker)

    async def test_worker_admin_has_health_check_function(self) -> None:
        """Test worker admin module has health check function."""
        from worker.admin import health_check

        assert health_check is not None

        # Verify it is an async function
        import inspect

        assert inspect.iscoroutinefunction(health_check)

    async def test_worker_admin_has_check_redis_connectivity(self) -> None:
        """Test worker admin module has Redis connectivity check."""
        from worker.admin import check_redis_connectivity

        assert check_redis_connectivity is not None

        # Verify it is an async function
        import inspect

        assert inspect.iscoroutinefunction(check_redis_connectivity)

    async def test_worker_admin_has_check_database_connectivity(self) -> None:
        """Test worker admin module has database connectivity check."""
        from worker.admin import check_database_connectivity

        assert check_database_connectivity is not None

        # Verify it is an async function
        import inspect

        assert inspect.iscoroutinefunction(check_database_connectivity)

    async def test_worker_admin_has_get_worker_uptime(self) -> None:
        """Test worker admin module has uptime function."""
        from worker.admin import get_worker_uptime

        assert get_worker_uptime is not None

        # Verify it returns a float
        uptime = get_worker_uptime()
        assert isinstance(uptime, float)
        assert uptime >= 0.0

    async def test_worker_db_has_get_session_function(self) -> None:
        """Test worker db module has get_session function."""
        from worker.db import get_session

        assert get_session is not None

        # Verify it is an async context manager
        import inspect

        assert inspect.isasyncgenfunction(get_session) or inspect.isfunction(get_session)

    async def test_worker_config_has_settings_class(self) -> None:
        """Test worker config module has WorkerSettings class."""
        from worker.config import WorkerSettings

        assert WorkerSettings is not None

        # Verify it is a class
        import inspect

        assert inspect.isclass(WorkerSettings)

    async def test_worker_schemas_have_job_models(self) -> None:
        """Test worker schemas module has job summary and detail models."""
        from worker.schemas import JobDetail, JobSummary

        assert JobSummary is not None
        assert JobDetail is not None

        # Verify they are Pydantic models
        from pydantic import BaseModel

        assert issubclass(JobSummary, BaseModel)
        assert issubclass(JobDetail, BaseModel)
