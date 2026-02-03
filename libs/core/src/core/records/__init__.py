"""Sync record schemas - contracts for source adapter communication."""

from core.records.gear_sync import GearSyncRecord, SyncOperation

__all__ = [
    "GearSyncRecord",
    "SyncOperation",
]
