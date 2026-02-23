"""SignalChain aggregate and related entities for domain layer.

A SignalChain represents a composition of gear that can be
processed together. It follows specific grammar rules for valid compositions.

Signal Chain Grammar:
    [PrePedals*] -> AmpBlock -> [IRBlock?] -> [PostEffects*]

    - PrePedals: 0 or more pre-amp pedal captures (overdrive, fuzz, etc.)
    - AmpBlock: Exactly ONE of:
        - HeadCapture (AMP) -> REQUIRES IRBlock after
        - FullRigCapture (FULL_RIG) -> IR baked in, NO IRBlock allowed
    - IRBlock: Exactly ONE IR file (required after HeadCapture only)
    - PostEffects: 0 or more post-amp effect captures (delay, reverb, etc.)
"""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from gts.domain.entities.base import Entity, new_id, utcnow
from gts.domain.value_objects.block_position import BlockPosition
from gts.domain.value_objects.signal_chain_enums import GearType, Platform


@dataclass(frozen=True, slots=True)
class SignalChainBlock:
    """A single block in a signal chain.

    Represents one component (pedal, amp, full-rig, IR, or post-effect) in
    the signal chain. Blocks are ordered by position and reference gear
    from the user's library via user_gear_id.

    Attributes:
        id: Unique identifier for this block
        signal_chain_id: Parent signal chain ID
        position: Order in the chain (0-indexed)
        user_gear_id: Reference to UserGear item from user's library
        gear_type: Type of gear (pedal, amp, full_rig, ir, post_effect)
        block_position: Position relative to amp (pre/loop/post)
    """

    id: UUID
    signal_chain_id: UUID
    position: int
    user_gear_id: UUID
    gear_type: GearType
    block_position: BlockPosition = BlockPosition.PRE

    def with_position(self, position: int) -> "SignalChainBlock":
        """Return a new block with updated position.

        Args:
            position: The new position

        Returns:
            A new SignalChainBlock with the updated position
        """
        return SignalChainBlock(
            id=self.id,
            signal_chain_id=self.signal_chain_id,
            position=position,
            user_gear_id=self.user_gear_id,
            gear_type=self.gear_type,
            block_position=self.block_position,
        )


@dataclass(eq=False, slots=True)
class SignalChain(Entity):
    """Aggregate root for signal chain composition.

    A SignalChain represents a user-created composition of gear
    that can be processed together. It enforces grammar rules for valid
    signal chain compositions.

    Valid chain grammar:
        [PrePedals*] -> AmpBlock -> [IRBlock?] -> [PostEffects*]

    Validation is delegated to SignalChainValidator service.

    Attributes:
        id: Unique identifier
        user_id: Owner's user ID
        name: Display name for the signal chain
        description: Optional description
        platform: Target platform (nam, aida_x, etc.)
        created_at: When the chain was created
        updated_at: When the chain was last updated
        blocks: Ordered list of blocks in this chain
    """

    user_id: UUID = field(default_factory=new_id)
    name: str = ""
    platform: Platform = Platform.NAM
    description: str | None = None
    blocks: list[SignalChainBlock] = field(default_factory=list)
    id: UUID = field(default_factory=new_id)
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)

    @property
    def block_count(self) -> int:
        """Return the number of blocks in this signal chain."""
        return len(self.blocks)

    def add_block(self, block: SignalChainBlock) -> None:
        """Add a block to the signal chain.

        The block will be added at the end of the chain.

        Args:
            block: The block to add
        """
        # Update position to be at the end
        new_block = block.with_position(len(self.blocks))
        self.blocks.append(new_block)
        self.updated_at = utcnow()

    def remove_block(self, block_id: UUID) -> bool:
        """Remove a block from the signal chain.

        Args:
            block_id: The ID of the block to remove

        Returns:
            True if removed, False if not found
        """
        for i, block in enumerate(self.blocks):
            if block.id == block_id:
                self.blocks.pop(i)
                self._reorder_positions()
                self.updated_at = utcnow()
                return True
        return False

    def reorder_block(self, block_id: UUID, new_position: int) -> bool:
        """Move a block to a new position.

        Args:
            block_id: The ID of the block to move
            new_position: The new position (0-indexed)

        Returns:
            True if moved, False if not found or invalid position
        """
        if new_position < 0 or new_position >= self.block_count:
            return False

        # Find the block
        block_index = None
        for i, block in enumerate(self.blocks):
            if block.id == block_id:
                block_index = i
                break

        if block_index is None:
            return False

        # Move the block
        block = self.blocks.pop(block_index)
        self.blocks.insert(new_position, block)
        self._reorder_positions()
        self.updated_at = utcnow()
        return True

    def _reorder_positions(self) -> None:
        """Reorder positions to be sequential starting from 0."""
        self.blocks = [block.with_position(i) for i, block in enumerate(self.blocks)]

    def get_block(self, block_id: UUID) -> SignalChainBlock | None:
        """Get a block by ID.

        Args:
            block_id: The block ID

        Returns:
            The block if found, None otherwise
        """
        for block in self.blocks:
            if block.id == block_id:
                return block
        return None

    def get_blocks_by_type(self, gear_type: GearType) -> list[SignalChainBlock]:
        """Get all blocks of a specific type.

        Args:
            gear_type: The gear type to filter by

        Returns:
            List of matching blocks
        """
        return [b for b in self.blocks if b.gear_type == gear_type]

    def has_amp(self) -> bool:
        """Check if chain has an amp (AMP or FULL_RIG)."""
        return any(b.gear_type in (GearType.AMP, GearType.FULL_RIG) for b in self.blocks)

    def has_ir(self) -> bool:
        """Check if chain has an IR."""
        return any(b.gear_type == GearType.IR for b in self.blocks)

    def is_complete(self) -> bool:
        """Check if the signal chain is complete and ready for use.

        A chain is complete when:
        - It has a FULL_RIG amp, OR
        - It has an AMP + IR combination

        Returns:
            True if the chain is complete, False otherwise
        """
        has_amp = any(b.gear_type == GearType.AMP for b in self.blocks)
        has_full_rig = any(b.gear_type == GearType.FULL_RIG for b in self.blocks)
        has_ir = self.has_ir()

        return has_full_rig or (has_amp and has_ir)
