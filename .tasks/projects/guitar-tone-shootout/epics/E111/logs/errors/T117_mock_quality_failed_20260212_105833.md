# Error Report: T117 — mock_quality_failed

**Time:** 2026-02-12T10:58:33.744455+00:00
**Phase:** mock_quality_failed
**Task:** T117

## Output

```
x tests/unit/t3k/test_sync_model_download_integration.py:21 [mock_import]
  BANNED: unittest.mock import — use real services
x tests/unit/t3k/test_sync_model_download_integration.py:55 [mock_usage]
  BANNED: AsyncMock() — use real services
x tests/unit/t3k/test_sync_model_download_integration.py:92 [mock_usage]
  BANNED: AsyncMock() — use real services
! tests/unit/t3k/test_sync_model_download_integration.py:136 [weak_assertion]
  Weak assertion: 'is not None' doesn't verify correctness
x tests/unit/t3k/test_sync_model_download_integration.py:148 [mock_config]
  BANNED: mock .return_value — use real services
x tests/unit/t3k/test_sync_model_download_integration.py:185 [mock_config]
  BANNED: mock .return_value — use real services
x tests/unit/t3k/test_sync_model_download_integration.py:215 [mock_config]
  BANNED: mock .return_value — use real services
x tests/unit/t3k/test_sync_model_download_integration.py:275 [mock_config]
  BANNED: mock .return_value — use real services
x tests/unit/t3k/test_sync_model_download_integration.py:278 [mock_usage]
  BANNED: AsyncMock() — use real services
x tests/unit/t3k/test_sync_model_download_integration.py:279 [mock_config]
  BANNED: mock .side_effect — use real services
x tests/unit/t3k/test_sync_model_download_integration.py:312 [mock_config]
  BANNED: mock .return_value — use real services
x tests/unit/t3k/test_sync_model_download_integration.py:314 [mock_usage]
  BANNED: AsyncMock() — use real services
x tests/unit/t3k/test_sync_model_download_integration.py:315 [mock_config]
  BANNED: mock .side_effect — use real services
x tests/unit/t3k/test_sync_model_download_integration.py:343 [mock_config]
  BANNED: mock .return_value — use real services
! tests/unit/worker/test_admin_api_extensions.py:399 [weak_assertion]
  Weak assertion: 'is not None' doesn't verify correctness

Errors: 13, Warnings: 2
Test quality check failed

```
