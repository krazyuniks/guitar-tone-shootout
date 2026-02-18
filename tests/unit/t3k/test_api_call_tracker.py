"""Unit tests for APICallTracker."""

import time

from source_t3k.services.api_call_tracker import APICallTracker


class TestAPICallTracker:
    def test_records_success_and_failure(self) -> None:
        tracker = APICallTracker()
        tracker.record_success()
        tracker.record_success()
        tracker.record_failure()

        metrics = tracker.get_metrics()
        one_min = metrics[0]
        assert one_min.window_seconds == 60
        assert one_min.successful == 2
        assert one_min.failed == 1

    def test_metrics_windows_aggregate_correctly(self) -> None:
        tracker = APICallTracker()
        tracker.record_success()
        tracker.record_failure()

        metrics = tracker.get_metrics()
        assert len(metrics) == 4
        windows = [m.window_seconds for m in metrics]
        assert windows == [60, 300, 3600, 86400]

        # All windows should see the same counts (records are recent)
        for m in metrics:
            assert m.successful == 1
            assert m.failed == 1

    def test_prunes_old_entries(self) -> None:
        tracker = APICallTracker()

        # Record with a fake old timestamp by manipulating the deque directly
        fake_old_time = time.monotonic() - 90000  # older than 24h
        tracker._records.append((fake_old_time, True))
        tracker._records.append((fake_old_time, False))

        # Record a fresh one
        tracker.record_success()

        metrics = tracker.get_metrics()
        one_day = metrics[3]
        # Old entries should have been pruned
        assert one_day.successful == 1
        assert one_day.failed == 0

    def test_empty_tracker_returns_zeros(self) -> None:
        tracker = APICallTracker()
        metrics = tracker.get_metrics()

        assert len(metrics) == 4
        for m in metrics:
            assert m.successful == 0
            assert m.failed == 0
            assert m.avg_success_per_minute == 0.0
            assert m.avg_failure_per_minute == 0.0

    def test_avg_per_minute_calculation(self) -> None:
        tracker = APICallTracker()
        for _ in range(60):
            tracker.record_success()
        for _ in range(30):
            tracker.record_failure()

        metrics = tracker.get_metrics()
        one_min = metrics[0]
        assert one_min.avg_success_per_minute == 60.0
        assert one_min.avg_failure_per_minute == 30.0
