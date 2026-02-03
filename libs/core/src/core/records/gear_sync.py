"""Gear sync record schema for source adapter communication.

Core owns this contract. Source adapters must produce GearSyncRecords
that conform to this schema. Worker consumes these records to update
the unified Gear in gts_core database.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any


class SyncOperation(str, Enum):
    """Type of sync operation."""

    CREATE = "create"  # New gear from source
    UPDATE = "update"  # Updated gear from source
    DELETE = "delete"  # Gear removed from source


@dataclass(frozen=True, slots=True)
class GearSyncRecord:
    """Value object representing a gear sync message.

    This is the contract between source adapters and the worker.
    Source adapters publish these to pgmq queues, and the worker
    consumes them to update the unified Gear in gts_core.

    Attributes:
        source_name: Name of the source (e.g., 't3k', 'user_upload')
        source_record_id: ID in the source system
        source_updated_at: When the record was updated in source
        operation: Type of sync operation
        payload: Source-specific data (varies by source)
    """

    source_name: str
    source_record_id: str
    source_updated_at: datetime
    operation: SyncOperation
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization.

        Returns:
            Dict representation suitable for JSON/pgmq
        """
        return {
            "source_name": self.source_name,
            "source_record_id": self.source_record_id,
            "source_updated_at": self.source_updated_at.isoformat(),
            "operation": self.operation.value,
            "payload": self.payload,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GearSyncRecord":
        """Create from dictionary.

        Args:
            data: Dict with sync record data

        Returns:
            GearSyncRecord instance
        """
        source_updated_at = data["source_updated_at"]
        if isinstance(source_updated_at, str):
            source_updated_at = datetime.fromisoformat(
                source_updated_at.replace("Z", "+00:00")
            )

        return cls(
            source_name=data["source_name"],
            source_record_id=data["source_record_id"],
            source_updated_at=source_updated_at,
            operation=SyncOperation(data["operation"]),
            payload=data["payload"],
        )

    def is_create(self) -> bool:
        """Check if this is a create operation."""
        return self.operation == SyncOperation.CREATE

    def is_update(self) -> bool:
        """Check if this is an update operation."""
        return self.operation == SyncOperation.UPDATE

    def is_delete(self) -> bool:
        """Check if this is a delete operation."""
        return self.operation == SyncOperation.DELETE

    def get_payload_value(self, key: str, default: Any = None) -> Any:
        """Get a value from the payload.

        Args:
            key: The key to look up
            default: Default value if key not found

        Returns:
            The value or default
        """
        return self.payload.get(key, default)
