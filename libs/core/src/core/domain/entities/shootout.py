"""Shootout aggregate for domain layer."""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from core.domain.entities.base import Entity, new_id, utcnow
from core.domain.value_objects.processing_metadata import ProcessingMetadata


class ShootoutError(Exception):
    """Base exception for Shootout domain errors."""

    pass


class DuplicateChainError(ShootoutError):
    """Raised when trying to add a duplicate chain."""

    pass


class ChainNotFoundError(ShootoutError):
    """Raised when a chain is not found in the shootout."""

    pass


class MaxChainsExceededError(ShootoutError):
    """Raised when max chain limit is exceeded."""

    pass


@dataclass(frozen=True, slots=True)
class ShootoutChain:
    """Value object representing a chain in a shootout.

    Links a signal chain to a shootout with ordering and labelling.

    Attributes:
        id: Unique identifier for this shootout-chain link
        shootout_id: Parent shootout ID
        signal_chain_id: Reference to the SignalChain
        position: Order in the shootout (0-indexed)
        label: Display label for this chain in the shootout
    """

    id: UUID
    shootout_id: UUID
    signal_chain_id: UUID
    position: int
    label: str

    def with_position(self, position: int) -> "ShootoutChain":
        """Return a new chain reference with updated position.

        Args:
            position: The new position

        Returns:
            A new ShootoutChain with the updated position
        """
        return ShootoutChain(
            id=self.id,
            shootout_id=self.shootout_id,
            signal_chain_id=self.signal_chain_id,
            position=position,
            label=self.label,
        )

    def with_label(self, label: str) -> "ShootoutChain":
        """Return a new chain reference with updated label.

        Args:
            label: The new label

        Returns:
            A new ShootoutChain with the updated label
        """
        return ShootoutChain(
            id=self.id,
            shootout_id=self.shootout_id,
            signal_chain_id=self.signal_chain_id,
            position=self.position,
            label=label,
        )


@dataclass(eq=False, slots=True)
class Shootout(Entity):
    """Aggregate root for tone comparison shootouts.

    A Shootout represents a comparison of multiple signal chains
    using a common DI track. It manages the collection of chains
    and enforces business rules.

    Attributes:
        id: Unique identifier
        user_id: Owner's user ID
        name: Display name for the shootout
        di_track_id: Reference to the DI track
        description: Optional description
        output_format: Output video format (mp4, etc.)
        sample_rate: Audio sample rate
        is_processed: Whether processing is complete
        output_path: Path to output video (after processing)
        processing_metadata: Processing metadata value object
        chains: List of chain references in this shootout
        created_at: When the shootout was created
        updated_at: When the shootout was last updated
    """

    MAX_CHAINS = 20  # Maximum number of chains allowed

    user_id: UUID = field(default_factory=new_id)
    name: str = ""
    di_track_id: UUID = field(default_factory=new_id)
    description: str | None = None
    output_format: str = "mp4"
    sample_rate: int = 44100
    is_processed: bool = False
    output_path: str | None = None
    processing_metadata: ProcessingMetadata | None = None
    chains: list[ShootoutChain] = field(default_factory=list)
    id: UUID = field(default_factory=new_id)
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)

    @property
    def chain_count(self) -> int:
        """Return the number of chains in this shootout."""
        return len(self.chains)

    def add_chain(self, chain: ShootoutChain) -> None:
        """Add a signal chain to the shootout.

        The chain will be added at the end.

        Args:
            chain: The chain reference to add

        Raises:
            MaxChainsExceededError: If max chain limit would be exceeded
            DuplicateChainError: If chain already exists in shootout
        """
        if self.chain_count >= self.MAX_CHAINS:
            raise MaxChainsExceededError(
                f"Cannot add more than {self.MAX_CHAINS} chains to a shootout"
            )

        # Check for duplicate
        for existing in self.chains:
            if existing.signal_chain_id == chain.signal_chain_id:
                raise DuplicateChainError(
                    f"Signal chain {chain.signal_chain_id} already in shootout"
                )

        # Set position to end of list
        next_position = (
            max(c.position for c in self.chains) + 1
            if self.chains
            else 0
        )
        new_chain = chain.with_position(next_position)

        self.chains.append(new_chain)
        self.updated_at = utcnow()

    def remove_chain(self, signal_chain_id: UUID) -> None:
        """Remove a signal chain from the shootout.

        Args:
            signal_chain_id: The signal chain ID

        Raises:
            ChainNotFoundError: If the chain is not found
        """
        for i, chain in enumerate(self.chains):
            if chain.signal_chain_id == signal_chain_id:
                self.chains.pop(i)
                self._reorder_positions()
                self.updated_at = utcnow()
                return

        raise ChainNotFoundError(
            f"Signal chain {signal_chain_id} not found in shootout"
        )

    def reorder_chain(self, signal_chain_id: UUID, new_position: int) -> None:
        """Move a chain to a new position.

        Args:
            signal_chain_id: The signal chain ID
            new_position: The new position (0-indexed)

        Raises:
            ChainNotFoundError: If the chain is not found
            ValueError: If new_position is out of bounds
        """
        if new_position < 0 or new_position >= self.chain_count:
            raise ValueError(f"Invalid position {new_position}")

        # Find the chain
        chain_index = None
        for i, chain in enumerate(self.chains):
            if chain.signal_chain_id == signal_chain_id:
                chain_index = i
                break

        if chain_index is None:
            raise ChainNotFoundError(
                f"Signal chain {signal_chain_id} not found in shootout"
            )

        # Move the chain
        chain = self.chains.pop(chain_index)
        self.chains.insert(new_position, chain)
        self._reorder_positions()
        self.updated_at = utcnow()

    def _reorder_positions(self) -> None:
        """Reorder positions to be sequential starting from 0."""
        self.chains = [
            chain.with_position(i) for i, chain in enumerate(self.chains)
        ]

    def get_chain(self, signal_chain_id: UUID) -> ShootoutChain:
        """Get a specific chain reference.

        Args:
            signal_chain_id: The signal chain ID

        Returns:
            The matching ShootoutChain

        Raises:
            ChainNotFoundError: If the chain is not found
        """
        for chain in self.chains:
            if chain.signal_chain_id == signal_chain_id:
                return chain

        raise ChainNotFoundError(
            f"Signal chain {signal_chain_id} not found in shootout"
        )

    def update_chain_label(self, signal_chain_id: UUID, label: str) -> None:
        """Update the label for a chain.

        Args:
            signal_chain_id: The signal chain ID
            label: The new label

        Raises:
            ChainNotFoundError: If the chain is not found
        """
        for i, chain in enumerate(self.chains):
            if chain.signal_chain_id == signal_chain_id:
                self.chains[i] = chain.with_label(label)
                self.updated_at = utcnow()
                return

        raise ChainNotFoundError(
            f"Signal chain {signal_chain_id} not found in shootout"
        )

    def mark_processed(
        self,
        output_path: str,
        metadata: ProcessingMetadata | None = None,
    ) -> None:
        """Mark the shootout as processed.

        Args:
            output_path: Path to the output video
            metadata: Optional processing metadata
        """
        self.is_processed = True
        self.output_path = output_path
        self.processing_metadata = metadata
        self.updated_at = utcnow()

    def reset_processing(self) -> None:
        """Reset processing state for re-processing."""
        self.is_processed = False
        self.output_path = None
        self.processing_metadata = None
        self.updated_at = utcnow()
