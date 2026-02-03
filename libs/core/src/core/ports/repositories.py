"""Repository port definitions for domain layer.

These protocols define the interface that the domain layer expects
from persistence implementations. Infrastructure adapters implement
these protocols to provide actual storage.

Note: T3K-specific repositories are NOT in core. They belong in
sources/t3k. Core only has unified Gear repository.
"""

from typing import Protocol
from uuid import UUID

from core.domain.entities.di_track import DITrack
from core.domain.entities.gear import Gear
from core.domain.entities.job import Job
from core.domain.entities.shootout import Shootout
from core.domain.entities.signal_chain import SignalChain
from core.domain.entities.signal_chain_group import SignalChainGroup
from core.domain.entities.user import User
from core.domain.value_objects.job_status import JobStatus, JobType
from core.domain.value_objects.signal_chain_enums import GearType


class UserRepository(Protocol):
    """Protocol for user persistence operations."""

    async def get_by_id(self, user_id: UUID) -> User | None:
        """Get a user by their ID.

        Args:
            user_id: The user's UUID

        Returns:
            The User if found, None otherwise
        """
        ...

    async def get_by_identity(
        self,
        provider: str,
        external_id: str,
    ) -> User | None:
        """Get a user by an external identity.

        Args:
            provider: The identity provider name
            external_id: The ID from the external provider

        Returns:
            The User if found, None otherwise
        """
        ...

    async def get_by_email(self, email: str) -> User | None:
        """Get a user by email address.

        Args:
            email: The email address

        Returns:
            The User if found, None otherwise
        """
        ...

    async def save(self, user: User) -> None:
        """Save a user (create or update).

        Args:
            user: The user to save
        """
        ...

    async def delete(self, user_id: UUID) -> None:
        """Delete a user by ID.

        Args:
            user_id: The user's UUID
        """
        ...


class GearRepository(Protocol):
    """Protocol for unified gear persistence operations.

    This is the core domain's view of gear, abstracting away
    source-specific details (T3K, user uploads, etc.)
    """

    async def get_by_id(self, gear_id: UUID) -> Gear | None:
        """Get gear by its internal ID.

        Args:
            gear_id: The gear's UUID

        Returns:
            The Gear if found, None otherwise
        """
        ...

    async def get_by_source(
        self,
        source_name: str,
        source_record_id: str,
    ) -> Gear | None:
        """Get gear by its source identifier.

        Args:
            source_name: Name of the source (e.g., 't3k')
            source_record_id: ID in the source system

        Returns:
            The Gear if found, None otherwise
        """
        ...

    async def search(
        self,
        *,
        query: str | None = None,
        gear_type: GearType | None = None,
        manufacturer: str | None = None,
        tags: list[str] | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Gear]:
        """Search for gear with filters.

        Args:
            query: Optional text search on name/description
            gear_type: Optional filter by gear type
            manufacturer: Optional filter by manufacturer
            tags: Optional filter by tags (AND logic)
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            List of matching Gear ordered by name
        """
        ...

    async def count(
        self,
        *,
        query: str | None = None,
        gear_type: GearType | None = None,
        manufacturer: str | None = None,
        tags: list[str] | None = None,
    ) -> int:
        """Count gear matching filters.

        Args:
            query: Optional text search
            gear_type: Optional filter by gear type
            manufacturer: Optional filter by manufacturer
            tags: Optional filter by tags

        Returns:
            Count of matching gear
        """
        ...

    async def save(self, gear: Gear) -> None:
        """Save gear (create or update).

        Args:
            gear: The gear to save
        """
        ...

    async def delete(self, gear_id: UUID) -> None:
        """Delete gear by ID.

        Args:
            gear_id: The gear's UUID
        """
        ...


class DITrackRepository(Protocol):
    """Protocol for DI track persistence operations."""

    async def get_by_id(self, track_id: UUID) -> DITrack | None:
        """Get a DI track by its ID.

        Args:
            track_id: The track's UUID

        Returns:
            The DITrack if found, None otherwise
        """
        ...

    async def get_by_user_id(
        self,
        user_id: UUID,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[DITrack]:
        """Get DI tracks for a user.

        Args:
            user_id: The owner's UUID
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            List of DITracks ordered by created_at desc
        """
        ...

    async def count_by_user_id(self, user_id: UUID) -> int:
        """Count DI tracks for a user.

        Args:
            user_id: The owner's UUID

        Returns:
            Count of tracks
        """
        ...

    async def save(self, track: DITrack) -> None:
        """Save a DI track (create or update).

        Args:
            track: The track to save
        """
        ...

    async def delete(self, track_id: UUID) -> None:
        """Delete a DI track by ID.

        Args:
            track_id: The track's UUID
        """
        ...


class SignalChainRepository(Protocol):
    """Protocol for signal chain persistence operations."""

    async def get_by_id(self, chain_id: UUID) -> SignalChain | None:
        """Get a signal chain by its ID.

        Args:
            chain_id: The chain's UUID

        Returns:
            The SignalChain with all blocks loaded, or None
        """
        ...

    async def get_by_user_id(
        self,
        user_id: UUID,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[SignalChain]:
        """Get signal chains for a user.

        Args:
            user_id: The user's UUID
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            List of SignalChains ordered by created_at desc
        """
        ...

    async def count_by_user_id(self, user_id: UUID) -> int:
        """Count signal chains for a user.

        Args:
            user_id: The user's UUID

        Returns:
            Count of chains
        """
        ...

    async def save(self, chain: SignalChain) -> None:
        """Save a signal chain (create or update).

        This should save both the chain and its blocks.

        Args:
            chain: The chain to save
        """
        ...

    async def delete(self, chain_id: UUID) -> None:
        """Delete a signal chain by ID.

        This should cascade delete blocks.

        Args:
            chain_id: The chain's UUID
        """
        ...


class SignalChainGroupRepository(Protocol):
    """Protocol for signal chain group persistence operations."""

    async def get_by_id(self, group_id: UUID) -> SignalChainGroup | None:
        """Get a group by its ID.

        Args:
            group_id: The group's UUID

        Returns:
            The SignalChainGroup if found, None otherwise
        """
        ...

    async def get_by_user_id(
        self,
        user_id: UUID,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[SignalChainGroup]:
        """Get groups for a user.

        Args:
            user_id: The user's UUID
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            List of SignalChainGroups ordered by created_at desc
        """
        ...

    async def save(self, group: SignalChainGroup) -> None:
        """Save a group (create or update).

        Args:
            group: The group to save
        """
        ...

    async def delete(self, group_id: UUID) -> None:
        """Delete a group by ID.

        Args:
            group_id: The group's UUID
        """
        ...


class ShootoutRepository(Protocol):
    """Protocol for shootout persistence operations."""

    async def get_by_id(self, shootout_id: UUID) -> Shootout | None:
        """Get a shootout by its ID.

        Args:
            shootout_id: The shootout's UUID

        Returns:
            The Shootout with all chains loaded, or None
        """
        ...

    async def get_by_user_id(
        self,
        user_id: UUID,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Shootout]:
        """Get shootouts for a user.

        Args:
            user_id: The owner's UUID
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            List of Shootouts ordered by created_at desc
        """
        ...

    async def save(self, shootout: Shootout) -> None:
        """Save a shootout (create or update).

        This should save both the shootout and its chains.

        Args:
            shootout: The shootout to save
        """
        ...

    async def delete(self, shootout_id: UUID) -> None:
        """Delete a shootout by ID.

        This should cascade delete chains.

        Args:
            shootout_id: The shootout's UUID
        """
        ...

    async def count_by_user_id(self, user_id: UUID) -> int:
        """Count shootouts for a user.

        Args:
            user_id: The owner's UUID

        Returns:
            The count of shootouts
        """
        ...

    async def get_public(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Shootout]:
        """Get public (processed) shootouts.

        Args:
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            List of processed Shootouts ordered by created_at desc
        """
        ...

    async def count_public(self) -> int:
        """Count public (processed) shootouts.

        Returns:
            The count of processed shootouts
        """
        ...


class JobRepository(Protocol):
    """Protocol for job persistence operations."""

    async def get_by_id(self, job_id: UUID) -> Job | None:
        """Get a job by its ID.

        Args:
            job_id: The job's UUID

        Returns:
            The Job if found, None otherwise
        """
        ...

    async def get_by_task_id(self, task_id: str) -> Job | None:
        """Get a job by its TaskIQ task ID.

        Args:
            task_id: The TaskIQ task ID

        Returns:
            The Job if found, None otherwise
        """
        ...

    async def get_by_user_id(
        self,
        user_id: UUID,
        *,
        status: JobStatus | None = None,
        job_type: JobType | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Job]:
        """Get jobs for a user, optionally filtered.

        Args:
            user_id: The owner's UUID
            status: Optional status filter
            job_type: Optional type filter
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            List of Jobs ordered by created_at desc
        """
        ...

    async def get_by_entity_id(self, entity_id: UUID) -> list[Job]:
        """Get jobs for an entity.

        Args:
            entity_id: The entity's UUID

        Returns:
            List of Jobs for this entity
        """
        ...

    async def get_active_by_user_id(self, user_id: UUID) -> list[Job]:
        """Get active (non-terminal) jobs for a user.

        Args:
            user_id: The owner's UUID

        Returns:
            List of active Jobs
        """
        ...

    async def get_children(self, parent_job_id: UUID) -> list[Job]:
        """Get child jobs for a parent job.

        Args:
            parent_job_id: The parent job's UUID

        Returns:
            List of child Jobs
        """
        ...

    async def count_by_user_id(
        self,
        user_id: UUID,
        *,
        status: JobStatus | None = None,
    ) -> int:
        """Count jobs for a user, optionally filtered by status.

        Args:
            user_id: The owner's UUID
            status: Optional status filter

        Returns:
            The count of matching jobs
        """
        ...

    async def save(self, job: Job) -> None:
        """Save a job (create or update).

        Args:
            job: The job to save
        """
        ...

    async def delete(self, job_id: UUID) -> None:
        """Delete a job by ID.

        Args:
            job_id: The job's UUID
        """
        ...

    async def get_pending_for_retry(self, limit: int = 10) -> list[Job]:
        """Get pending jobs that are ready for retry.

        Args:
            limit: Maximum number of results

        Returns:
            List of Jobs ready for retry
        """
        ...


class AuditRepository(Protocol):
    """Protocol for audit log persistence operations."""

    async def log_event(
        self,
        *,
        event_type: str,
        entity_type: str,
        entity_id: UUID,
        user_id: UUID | None,
        details: dict[str, object] | None = None,
    ) -> None:
        """Log an audit event.

        Args:
            event_type: Type of event (e.g., 'created', 'updated', 'deleted')
            entity_type: Type of entity (e.g., 'shootout', 'signal_chain')
            entity_id: The entity's UUID
            user_id: The acting user's UUID (None for system actions)
            details: Optional additional details
        """
        ...
