"""Unit tests for SyncHealthTracker."""

from __future__ import annotations

from gts.domain.value_objects.source_auth_status import SourceAuthStatus
from t3k_sync.health import ServiceState, SyncHealthTracker


class TestSyncHealthTracker:
    """Test SyncHealthTracker state transitions."""

    def test_initial_state_is_healthy(self) -> None:
        tracker = SyncHealthTracker()
        assert tracker.state == ServiceState.HEALTHY
        assert tracker.consecutive_failures == 0

    def test_record_sync_success_resets_failures(self) -> None:
        tracker = SyncHealthTracker()
        tracker.consecutive_failures = 5
        tracker.state = ServiceState.DEGRADED
        tracker.record_sync_success()
        assert tracker.state == ServiceState.HEALTHY
        assert tracker.consecutive_failures == 0
        assert tracker.last_successful_sync is not None

    def test_record_sync_failure_increments_count(self) -> None:
        tracker = SyncHealthTracker()
        tracker.record_sync_failure("test error")
        assert tracker.consecutive_failures == 1
        assert tracker.last_error == "test error"
        assert tracker.state == ServiceState.HEALTHY  # Not degraded yet

    def test_three_failures_transitions_to_degraded(self) -> None:
        tracker = SyncHealthTracker()
        tracker.record_sync_failure("error 1")
        tracker.record_sync_failure("error 2")
        tracker.record_sync_failure("error 3")
        assert tracker.state == ServiceState.DEGRADED

    def test_auth_failure_transitions_to_waiting(self) -> None:
        tracker = SyncHealthTracker()
        tracker.record_auth_failure(SourceAuthStatus.LOGIN_REQUIRED)
        assert tracker.state == ServiceState.WAITING_FOR_AUTH
        assert tracker.auth_status == SourceAuthStatus.LOGIN_REQUIRED

    def test_auth_recovery_resets_to_healthy(self) -> None:
        tracker = SyncHealthTracker()
        tracker.record_auth_failure(SourceAuthStatus.LOGIN_REQUIRED)
        tracker.record_auth_healthy(SourceAuthStatus.VALID)
        assert tracker.state == ServiceState.HEALTHY
        assert tracker.consecutive_failures == 0

    def test_scheduler_interval_normal_when_healthy(self) -> None:
        tracker = SyncHealthTracker()
        assert tracker.get_scheduler_interval(60.0) == 60.0

    def test_scheduler_interval_backs_off_when_waiting_for_auth(self) -> None:
        tracker = SyncHealthTracker()
        tracker.record_auth_failure(SourceAuthStatus.LOGIN_REQUIRED)
        assert tracker.get_scheduler_interval(60.0) == 300.0

    def test_scheduler_interval_max_backoff(self) -> None:
        tracker = SyncHealthTracker()
        for _ in range(5):
            tracker.record_auth_failure(SourceAuthStatus.LOGIN_REQUIRED)
        assert tracker.get_scheduler_interval(60.0) == 600.0

    def test_health_response_healthy(self) -> None:
        tracker = SyncHealthTracker()
        resp = tracker.health_response()
        assert resp == {"status": "healthy"}

    def test_health_response_degraded(self) -> None:
        tracker = SyncHealthTracker()
        for _ in range(3):
            tracker.record_sync_failure("db timeout")
        resp = tracker.health_response()
        assert resp["status"] == "degraded"
        assert resp["reason"] == "db timeout"
        assert "since" in resp

    def test_health_response_waiting_for_auth(self) -> None:
        tracker = SyncHealthTracker()
        tracker.record_auth_failure(SourceAuthStatus.LOGIN_REQUIRED)
        resp = tracker.health_response()
        assert resp["status"] == "waiting_for_auth"
        assert "login_required" in resp["reason"]
