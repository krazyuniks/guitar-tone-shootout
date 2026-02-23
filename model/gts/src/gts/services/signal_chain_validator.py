"""Signal chain validation service.

Validates signal chain compositions against grammar rules.
"""

from dataclasses import dataclass, field
from enum import Enum

from core.domain.entities.signal_chain import SignalChain, SignalChainBlock
from core.domain.value_objects.block_position import BlockPosition
from core.domain.value_objects.signal_chain_enums import GearType


class ValidationRule(str, Enum):
    """Validation rule codes."""

    NO_AMP = "NO_AMP"
    MULTIPLE_AMPS = "MULTIPLE_AMPS"
    IR_REQUIRED = "IR_REQUIRED"
    IR_FORBIDDEN = "IR_FORBIDDEN"
    LOOP_FORBIDDEN = "LOOP_FORBIDDEN"
    MULTIPLE_IRS = "MULTIPLE_IRS"
    INVALID_ORDER = "INVALID_ORDER"


@dataclass(frozen=True, slots=True)
class ValidationError:
    """Represents a validation error in a signal chain.

    Attributes:
        code: Machine-readable error code for programmatic handling
        message: Human-readable error description
        position: Block position where error occurred (if applicable)
    """

    code: ValidationRule
    message: str
    position: int | None = None


@dataclass(frozen=True, slots=True)
class ValidationResult:
    """Result of signal chain validation.

    Attributes:
        is_valid: Whether the signal chain is valid
        errors: List of validation errors (empty if valid)
    """

    is_valid: bool
    errors: list[ValidationError] = field(default_factory=list)

    @classmethod
    def valid(cls) -> "ValidationResult":
        """Create a valid result with no errors."""
        return cls(is_valid=True, errors=[])

    @classmethod
    def invalid(cls, errors: list[ValidationError]) -> "ValidationResult":
        """Create an invalid result with the given errors."""
        return cls(is_valid=False, errors=errors)


@dataclass(frozen=True, slots=True)
class _CategorisedBlocks:
    """Blocks grouped by gear type with their chain positions."""

    amp_blocks: list[tuple[int, SignalChainBlock]]
    full_rig_blocks: list[tuple[int, SignalChainBlock]]
    ir_blocks: list[tuple[int, SignalChainBlock]]
    pedal_blocks: list[tuple[int, SignalChainBlock]]
    post_effect_blocks: list[tuple[int, SignalChainBlock]]

    @property
    def total_amps(self) -> int:
        return len(self.amp_blocks) + len(self.full_rig_blocks)

    @property
    def is_full_rig(self) -> bool:
        return len(self.full_rig_blocks) >= 1

    @property
    def amp_position(self) -> int:
        """Position of the first amp-type block."""
        if self.full_rig_blocks:
            return self.full_rig_blocks[0][0]
        return self.amp_blocks[0][0]


class SignalChainValidator:
    """Service for validating signal chain compositions.

    Signal Chain Grammar:
        [PrePedals*] -> AmpBlock -> [IRBlock?] -> [PostEffects*]

        - PrePedals: 0 or more pre-amp pedal captures (optional, stackable)
        - AmpBlock: Exactly ONE of:
            - HeadCapture (AMP) -> REQUIRES IRBlock after
            - FullRigCapture (FULL_RIG) -> IR baked in, NO IRBlock allowed
        - IRBlock: Exactly ONE IR file (required after HeadCapture only)
        - PostEffects: 0 or more post-amp effect captures (delay, reverb, etc.)

    Validation rules:
        - NO_AMP: Chain must have exactly one amp block (AMP or FULL_RIG)
        - MULTIPLE_AMPS: Only one amp allowed
        - IR_REQUIRED: Head amp (AMP) requires IR block
        - IR_FORBIDDEN: Full-rig amp cannot have IR
        - INVALID_ORDER: Pedals must precede amp, IR must follow amp,
                         post-effects must follow IR (or amp for full-rig)
        - MULTIPLE_IRS: Only one IR allowed
    """

    def validate(self, chain: SignalChain) -> ValidationResult:
        """Validate a signal chain against grammar rules."""
        cats = self._categorise_blocks(chain)
        errors: list[ValidationError] = []

        errors.extend(self._validate_amp_count(cats))
        errors.extend(self._validate_ir_count(cats))

        if cats.total_amps >= 1:
            if cats.total_amps == 1:
                errors.extend(self._validate_single_amp_rules(chain, cats))
            errors.extend(self._validate_ordering(cats))

        if errors:
            return ValidationResult.invalid(errors)
        return ValidationResult.valid()

    @staticmethod
    def _categorise_blocks(chain: SignalChain) -> _CategorisedBlocks:
        amp: list[tuple[int, SignalChainBlock]] = []
        full_rig: list[tuple[int, SignalChainBlock]] = []
        ir: list[tuple[int, SignalChainBlock]] = []
        pedal: list[tuple[int, SignalChainBlock]] = []
        post_effect: list[tuple[int, SignalChainBlock]] = []

        dispatch = {
            GearType.AMP: amp,
            GearType.FULL_RIG: full_rig,
            GearType.IR: ir,
            GearType.PEDAL: pedal,
            GearType.POST_EFFECT: post_effect,
        }
        for i, block in enumerate(chain.blocks):
            target = dispatch.get(block.gear_type)
            if target is not None:
                target.append((i, block))

        return _CategorisedBlocks(
            amp_blocks=amp,
            full_rig_blocks=full_rig,
            ir_blocks=ir,
            pedal_blocks=pedal,
            post_effect_blocks=post_effect,
        )

    @staticmethod
    def _validate_amp_count(cats: _CategorisedBlocks) -> list[ValidationError]:
        errors: list[ValidationError] = []
        if cats.total_amps == 0:
            errors.append(
                ValidationError(
                    code=ValidationRule.NO_AMP,
                    message="Signal chain must have exactly one amp block",
                )
            )
        elif cats.total_amps > 1:
            all_positions = sorted(
                [pos for pos, _ in cats.amp_blocks] + [pos for pos, _ in cats.full_rig_blocks]
            )
            errors.extend(
                ValidationError(
                    code=ValidationRule.MULTIPLE_AMPS,
                    message="Only one amp block allowed in signal chain",
                    position=pos,
                )
                for pos in all_positions[1:]
            )
        return errors

    @staticmethod
    def _validate_ir_count(cats: _CategorisedBlocks) -> list[ValidationError]:
        if len(cats.ir_blocks) <= 1:
            return []
        return [
            ValidationError(
                code=ValidationRule.MULTIPLE_IRS,
                message="Only one IR block allowed in signal chain",
                position=pos,
            )
            for pos, _ in cats.ir_blocks[1:]
        ]

    @staticmethod
    def _validate_single_amp_rules(
        chain: SignalChain, cats: _CategorisedBlocks
    ) -> list[ValidationError]:
        """Rules that apply only when there is exactly one amp."""
        errors: list[ValidationError] = []

        if not cats.is_full_rig and len(cats.ir_blocks) == 0:
            errors.append(
                ValidationError(
                    code=ValidationRule.IR_REQUIRED,
                    message="Head amp capture requires an IR block after it",
                    position=cats.amp_position,
                )
            )

        if cats.is_full_rig and len(cats.ir_blocks) > 0:
            errors.extend(
                ValidationError(
                    code=ValidationRule.IR_FORBIDDEN,
                    message="Full-rig amp has baked-in IR; no IR allowed",
                    position=pos,
                )
                for pos, _ in cats.ir_blocks
            )

        if cats.is_full_rig:
            errors.extend(
                ValidationError(
                    code=ValidationRule.LOOP_FORBIDDEN,
                    message="Loop position effects are incompatible with full-rig amps",
                    position=i,
                )
                for i, block in enumerate(chain.blocks)
                if block.block_position == BlockPosition.LOOP
            )

        return errors

    @staticmethod
    def _validate_ordering(cats: _CategorisedBlocks) -> list[ValidationError]:
        """Order rules: pedals before amp, IR after amp, post-effects after IR."""
        errors: list[ValidationError] = []
        amp_pos = cats.amp_position

        for pos, _ in cats.pedal_blocks:
            if pos > amp_pos:
                errors.append(
                    ValidationError(
                        code=ValidationRule.INVALID_ORDER,
                        message="Pedal blocks must come before the amp block",
                        position=pos,
                    )
                )

        for pos, _ in cats.ir_blocks:
            if pos < amp_pos:
                errors.append(
                    ValidationError(
                        code=ValidationRule.INVALID_ORDER,
                        message="IR block must come after the amp block",
                        position=pos,
                    )
                )

        min_post_pos = amp_pos
        if not cats.is_full_rig and len(cats.ir_blocks) > 0:
            min_post_pos = cats.ir_blocks[0][0]

        for pos, _ in cats.post_effect_blocks:
            if pos <= min_post_pos:
                errors.append(
                    ValidationError(
                        code=ValidationRule.INVALID_ORDER,
                        message="Post-effect blocks must come after the cabinet/IR",
                        position=pos,
                    )
                )

        return errors

    def get_next_valid_gear_types(self, chain: SignalChain) -> list[GearType]:
        """Get the gear types that can be validly added to this chain.

        Based on current chain state, returns what gear types are valid next:
        - Empty chain: PEDAL, AMP, FULL_RIG
        - Has pedals only: PEDAL (more), AMP, FULL_RIG
        - Has AMP: IR only (required)
        - Has FULL_RIG: POST_EFFECT (optional)
        - Has AMP + IR: POST_EFFECT (optional)

        Args:
            chain: The signal chain to analyse

        Returns:
            List of GearType values that can be added
        """
        has_amp = any(b.gear_type == GearType.AMP for b in chain.blocks)
        has_full_rig = any(b.gear_type == GearType.FULL_RIG for b in chain.blocks)
        has_ir = any(b.gear_type == GearType.IR for b in chain.blocks)

        # Full-rig chains can add post-effects
        if has_full_rig:
            return [GearType.POST_EFFECT]

        # Amp + IR can add post-effects
        if has_amp and has_ir:
            return [GearType.POST_EFFECT]

        # Amp without IR - must add IR
        if has_amp and not has_ir:
            return [GearType.IR]

        # No amp yet - can add pedals, amp, or full-rig
        return [GearType.PEDAL, GearType.AMP, GearType.FULL_RIG]

    def get_guidance_message(self, chain: SignalChain) -> str:
        """Get a user-friendly message about what to do next.

        Provides contextual guidance based on current chain state.

        Args:
            chain: The signal chain to analyse

        Returns:
            Human-readable guidance message
        """
        has_amp = any(b.gear_type == GearType.AMP for b in chain.blocks)
        has_full_rig = any(b.gear_type == GearType.FULL_RIG for b in chain.blocks)
        has_ir = any(b.gear_type == GearType.IR for b in chain.blocks)
        has_pedals = any(b.gear_type == GearType.PEDAL for b in chain.blocks)
        has_post_effects = any(b.gear_type == GearType.POST_EFFECT for b in chain.blocks)

        # Complete chains
        if has_full_rig:
            if has_post_effects:
                return "Signal chain complete! Add more post-effects (delay, reverb) or save."
            return (
                "Signal chain complete! Optionally add post-amp effects "
                "(delay, reverb, etc.) or save."
            )
        if has_amp and has_ir:
            if has_post_effects:
                return "Signal chain complete! Add more post-effects (delay, reverb) or save."
            return (
                "Signal chain complete! Optionally add post-amp effects "
                "(delay, reverb, etc.) or save."
            )

        # Needs IR
        if has_amp and not has_ir:
            return "Head amp selected - choose a cabinet/IR to complete the chain."

        # No amp yet
        if has_pedals:
            return "Add more pedals, or choose your amp to continue."
        return "Choose the first piece of gear in your signal chain."
