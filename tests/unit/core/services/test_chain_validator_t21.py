"""Unit tests for SignalChainValidator domain service (T21).

Tests validation rules for signal chain composition:
- NO_AMP: Chain must have exactly one amp
- MULTIPLE_AMPS: Only one amp allowed
- IR_REQUIRED: HEAD amp requires IR
- IR_FORBIDDEN: FULL_RIG amp forbids IR
- LOOP_FORBIDDEN: FULL_RIG forbids loop position effects
- INVALID_ORDER: Blocks must be in correct position order
"""

from uuid import uuid4

import pytest

from core.domain.entities.signal_chain import SignalChain, SignalChainBlock
from core.domain.value_objects.block_position import BlockPosition
from core.domain.value_objects.signal_chain_enums import GearType
from core.services.signal_chain_validator import (
    SignalChainValidator,
    ValidationError,
    ValidationResult,
    ValidationRule,
)


@pytest.fixture
def validator() -> SignalChainValidator:
    """Create a validator instance."""
    return SignalChainValidator()


@pytest.fixture
def empty_chain() -> SignalChain:
    """Create an empty signal chain."""
    return SignalChain(id=uuid4(), user_id=uuid4(), name="Test Chain")


@pytest.fixture
def make_block():
    """Factory for creating signal chain blocks."""

    def _make(
        gear_type: GearType,
        position: int = 0,
        block_position: BlockPosition = BlockPosition.PRE,
    ) -> SignalChainBlock:
        return SignalChainBlock(
            id=uuid4(),
            signal_chain_id=uuid4(),
            position=position,
            user_gear_id=uuid4(),
            gear_type=gear_type,
            block_position=block_position,
        )

    return _make


class TestNoAmpValidation:
    """Tests for NO_AMP validation rule."""

    def test_empty_chain_fails_no_amp(
        self, validator: SignalChainValidator, empty_chain: SignalChain
    ) -> None:
        """Test that empty chain fails NO_AMP validation."""
        result = validator.validate(empty_chain)

        assert result.is_valid is False
        assert len(result.errors) == 1
        assert result.errors[0].code == ValidationRule.NO_AMP
        assert "must have exactly one amp" in result.errors[0].message.lower()

    def test_pedals_only_fails_no_amp(
        self,
        validator: SignalChainValidator,
        empty_chain: SignalChain,
        make_block,
    ) -> None:
        """Test that chain with only pedals fails NO_AMP validation."""
        empty_chain.add_block(make_block(GearType.PEDAL, block_position=BlockPosition.PRE))
        empty_chain.add_block(make_block(GearType.PEDAL, block_position=BlockPosition.PRE))

        result = validator.validate(empty_chain)

        assert result.is_valid is False
        assert any(err.code == ValidationRule.NO_AMP for err in result.errors)


class TestMultipleAmpsValidation:
    """Tests for MULTIPLE_AMPS validation rule."""

    def test_two_amps_fails(
        self,
        validator: SignalChainValidator,
        empty_chain: SignalChain,
        make_block,
    ) -> None:
        """Test that chain with two AMP blocks fails."""
        empty_chain.add_block(make_block(GearType.AMP, block_position=BlockPosition.PRE))
        empty_chain.add_block(make_block(GearType.AMP, block_position=BlockPosition.PRE))

        result = validator.validate(empty_chain)

        assert result.is_valid is False
        assert any(err.code == ValidationRule.MULTIPLE_AMPS for err in result.errors)
        # Should report position of second amp
        multiple_amp_errors = [e for e in result.errors if e.code == ValidationRule.MULTIPLE_AMPS]
        assert len(multiple_amp_errors) >= 1
        assert multiple_amp_errors[0].position is not None

    def test_amp_and_full_rig_fails(
        self,
        validator: SignalChainValidator,
        empty_chain: SignalChain,
        make_block,
    ) -> None:
        """Test that AMP + FULL_RIG combination fails."""
        empty_chain.add_block(make_block(GearType.AMP, block_position=BlockPosition.PRE))
        empty_chain.add_block(make_block(GearType.FULL_RIG, block_position=BlockPosition.PRE))

        result = validator.validate(empty_chain)

        assert result.is_valid is False
        assert any(err.code == ValidationRule.MULTIPLE_AMPS for err in result.errors)

    def test_three_amps_reports_all_extra(
        self,
        validator: SignalChainValidator,
        empty_chain: SignalChain,
        make_block,
    ) -> None:
        """Test that three amps reports position for all extras."""
        empty_chain.add_block(make_block(GearType.AMP, block_position=BlockPosition.PRE))
        empty_chain.add_block(make_block(GearType.FULL_RIG, block_position=BlockPosition.PRE))
        empty_chain.add_block(make_block(GearType.AMP, block_position=BlockPosition.PRE))

        result = validator.validate(empty_chain)

        assert result.is_valid is False
        multiple_amp_errors = [e for e in result.errors if e.code == ValidationRule.MULTIPLE_AMPS]
        # Should report 2 errors for positions 1 and 2
        assert len(multiple_amp_errors) >= 2


class TestIrRequiredValidation:
    """Tests for IR_REQUIRED validation rule."""

    def test_head_amp_without_ir_fails(
        self,
        validator: SignalChainValidator,
        empty_chain: SignalChain,
        make_block,
    ) -> None:
        """Test that HEAD amp (AMP) without IR fails."""
        empty_chain.add_block(make_block(GearType.AMP, block_position=BlockPosition.PRE))

        result = validator.validate(empty_chain)

        assert result.is_valid is False
        assert any(err.code == ValidationRule.IR_REQUIRED for err in result.errors)
        ir_required_error = next(e for e in result.errors if e.code == ValidationRule.IR_REQUIRED)
        assert "requires an ir" in ir_required_error.message.lower()
        assert ir_required_error.position == 0  # Position of amp

    def test_head_amp_with_ir_passes(
        self,
        validator: SignalChainValidator,
        empty_chain: SignalChain,
        make_block,
    ) -> None:
        """Test that HEAD amp with IR passes IR_REQUIRED."""
        empty_chain.add_block(make_block(GearType.AMP, block_position=BlockPosition.PRE))
        empty_chain.add_block(make_block(GearType.IR, block_position=BlockPosition.POST))

        result = validator.validate(empty_chain)

        # May fail for other reasons (order) but not IR_REQUIRED
        ir_required_errors = [e for e in result.errors if e.code == ValidationRule.IR_REQUIRED]
        assert len(ir_required_errors) == 0


class TestIrForbiddenValidation:
    """Tests for IR_FORBIDDEN validation rule."""

    def test_full_rig_with_ir_fails(
        self,
        validator: SignalChainValidator,
        empty_chain: SignalChain,
        make_block,
    ) -> None:
        """Test that FULL_RIG amp with IR fails."""
        empty_chain.add_block(make_block(GearType.FULL_RIG, block_position=BlockPosition.PRE))
        empty_chain.add_block(make_block(GearType.IR, block_position=BlockPosition.POST))

        result = validator.validate(empty_chain)

        assert result.is_valid is False
        assert any(err.code == ValidationRule.IR_FORBIDDEN for err in result.errors)
        ir_forbidden_error = next(e for e in result.errors if e.code == ValidationRule.IR_FORBIDDEN)
        assert "full-rig" in ir_forbidden_error.message.lower()
        assert ir_forbidden_error.position == 1  # Position of IR

    def test_full_rig_without_ir_passes_ir_forbidden(
        self,
        validator: SignalChainValidator,
        empty_chain: SignalChain,
        make_block,
    ) -> None:
        """Test that FULL_RIG without IR passes IR_FORBIDDEN rule."""
        empty_chain.add_block(make_block(GearType.FULL_RIG, block_position=BlockPosition.PRE))

        result = validator.validate(empty_chain)

        # Should not have IR_FORBIDDEN error
        ir_forbidden_errors = [e for e in result.errors if e.code == ValidationRule.IR_FORBIDDEN]
        assert len(ir_forbidden_errors) == 0


class TestLoopForbiddenValidation:
    """Tests for LOOP_FORBIDDEN validation rule.

    FULL_RIG amps have baked-in preamp and power amp sections.
    Loop position effects (which go between preamp and power amp)
    are incompatible with FULL_RIG amps.
    """

    def test_validation_rule_loop_forbidden_exists(self) -> None:
        """Test that LOOP_FORBIDDEN validation rule exists."""
        assert hasattr(ValidationRule, "LOOP_FORBIDDEN")
        assert ValidationRule.LOOP_FORBIDDEN.value == "LOOP_FORBIDDEN"

    def test_full_rig_with_loop_effect_fails(
        self,
        validator: SignalChainValidator,
        empty_chain: SignalChain,
        make_block,
    ) -> None:
        """Test that FULL_RIG with loop position effect fails."""
        empty_chain.add_block(make_block(GearType.FULL_RIG, block_position=BlockPosition.PRE))
        empty_chain.add_block(make_block(GearType.POST_EFFECT, block_position=BlockPosition.LOOP))

        result = validator.validate(empty_chain)

        assert result.is_valid is False
        assert any(err.code == ValidationRule.LOOP_FORBIDDEN for err in result.errors)
        loop_forbidden_error = next(
            e for e in result.errors if e.code == ValidationRule.LOOP_FORBIDDEN
        )
        assert "loop" in loop_forbidden_error.message.lower()
        assert "full-rig" in loop_forbidden_error.message.lower()
        assert loop_forbidden_error.position == 1  # Position of loop effect

    def test_full_rig_with_multiple_loop_effects_reports_all(
        self,
        validator: SignalChainValidator,
        empty_chain: SignalChain,
        make_block,
    ) -> None:
        """Test that multiple loop effects all get reported."""
        empty_chain.add_block(make_block(GearType.FULL_RIG, block_position=BlockPosition.PRE))
        empty_chain.add_block(make_block(GearType.POST_EFFECT, block_position=BlockPosition.LOOP))
        empty_chain.add_block(make_block(GearType.POST_EFFECT, block_position=BlockPosition.LOOP))

        result = validator.validate(empty_chain)

        assert result.is_valid is False
        loop_errors = [e for e in result.errors if e.code == ValidationRule.LOOP_FORBIDDEN]
        assert len(loop_errors) == 2
        assert loop_errors[0].position == 1
        assert loop_errors[1].position == 2

    def test_full_rig_with_post_effect_passes(
        self,
        validator: SignalChainValidator,
        empty_chain: SignalChain,
        make_block,
    ) -> None:
        """Test that FULL_RIG with POST position effect is allowed."""
        empty_chain.add_block(make_block(GearType.FULL_RIG, block_position=BlockPosition.PRE))
        empty_chain.add_block(make_block(GearType.POST_EFFECT, block_position=BlockPosition.POST))

        result = validator.validate(empty_chain)

        # Should not have LOOP_FORBIDDEN error
        loop_errors = [e for e in result.errors if e.code == ValidationRule.LOOP_FORBIDDEN]
        assert len(loop_errors) == 0

    def test_head_amp_with_loop_effect_allowed(
        self,
        validator: SignalChainValidator,
        empty_chain: SignalChain,
        make_block,
    ) -> None:
        """Test that HEAD amp (AMP) CAN use loop position effects."""
        empty_chain.add_block(make_block(GearType.AMP, block_position=BlockPosition.PRE))
        empty_chain.add_block(make_block(GearType.POST_EFFECT, block_position=BlockPosition.LOOP))
        empty_chain.add_block(make_block(GearType.IR, block_position=BlockPosition.POST))

        result = validator.validate(empty_chain)

        # Should not have LOOP_FORBIDDEN error (only FULL_RIG forbids loop)
        loop_errors = [e for e in result.errors if e.code == ValidationRule.LOOP_FORBIDDEN]
        assert len(loop_errors) == 0


class TestInvalidOrderValidation:
    """Tests for INVALID_ORDER validation rule."""

    def test_pedal_after_amp_fails(
        self,
        validator: SignalChainValidator,
        empty_chain: SignalChain,
        make_block,
    ) -> None:
        """Test that pedal after amp fails order validation."""
        empty_chain.add_block(make_block(GearType.AMP, block_position=BlockPosition.PRE))
        empty_chain.add_block(make_block(GearType.IR, block_position=BlockPosition.POST))
        empty_chain.add_block(make_block(GearType.PEDAL, block_position=BlockPosition.PRE))

        result = validator.validate(empty_chain)

        assert result.is_valid is False
        assert any(err.code == ValidationRule.INVALID_ORDER for err in result.errors)
        order_error = next(
            e
            for e in result.errors
            if e.code == ValidationRule.INVALID_ORDER and "pedal" in e.message.lower()
        )
        assert order_error.position == 2  # Position of misplaced pedal

    def test_ir_before_amp_fails(
        self,
        validator: SignalChainValidator,
        empty_chain: SignalChain,
        make_block,
    ) -> None:
        """Test that IR before amp fails order validation."""
        empty_chain.add_block(make_block(GearType.IR, block_position=BlockPosition.POST))
        empty_chain.add_block(make_block(GearType.AMP, block_position=BlockPosition.PRE))

        result = validator.validate(empty_chain)

        assert result.is_valid is False
        assert any(err.code == ValidationRule.INVALID_ORDER for err in result.errors)
        order_error = next(
            e
            for e in result.errors
            if e.code == ValidationRule.INVALID_ORDER and "ir" in e.message.lower()
        )
        assert order_error.position == 0  # Position of misplaced IR

    def test_post_effect_before_ir_fails(
        self,
        validator: SignalChainValidator,
        empty_chain: SignalChain,
        make_block,
    ) -> None:
        """Test that post-effect before IR fails."""
        empty_chain.add_block(make_block(GearType.AMP, block_position=BlockPosition.PRE))
        empty_chain.add_block(make_block(GearType.POST_EFFECT, block_position=BlockPosition.POST))
        empty_chain.add_block(make_block(GearType.IR, block_position=BlockPosition.POST))

        result = validator.validate(empty_chain)

        assert result.is_valid is False
        assert any(err.code == ValidationRule.INVALID_ORDER for err in result.errors)
        order_error = next(
            e
            for e in result.errors
            if e.code == ValidationRule.INVALID_ORDER and "post-effect" in e.message.lower()
        )
        assert order_error.position == 1  # Position of misplaced post-effect

    def test_valid_order_passes(
        self,
        validator: SignalChainValidator,
        empty_chain: SignalChain,
        make_block,
    ) -> None:
        """Test that correct order passes validation."""
        empty_chain.add_block(make_block(GearType.PEDAL, block_position=BlockPosition.PRE))
        empty_chain.add_block(make_block(GearType.PEDAL, block_position=BlockPosition.PRE))
        empty_chain.add_block(make_block(GearType.AMP, block_position=BlockPosition.PRE))
        empty_chain.add_block(make_block(GearType.IR, block_position=BlockPosition.POST))
        empty_chain.add_block(make_block(GearType.POST_EFFECT, block_position=BlockPosition.POST))
        empty_chain.add_block(make_block(GearType.POST_EFFECT, block_position=BlockPosition.POST))

        result = validator.validate(empty_chain)

        assert result.is_valid is True
        assert len(result.errors) == 0


class TestDetailedValidationErrors:
    """Tests for detailed validation error reporting."""

    def test_validation_error_has_code(
        self,
        validator: SignalChainValidator,
        empty_chain: SignalChain,
    ) -> None:
        """Test that validation errors include machine-readable code."""
        result = validator.validate(empty_chain)

        assert result.is_valid is False
        assert len(result.errors) > 0
        for error in result.errors:
            assert isinstance(error.code, ValidationRule)

    def test_validation_error_has_message(
        self,
        validator: SignalChainValidator,
        empty_chain: SignalChain,
    ) -> None:
        """Test that validation errors include human-readable message."""
        result = validator.validate(empty_chain)

        assert result.is_valid is False
        for error in result.errors:
            assert isinstance(error.message, str)
            assert len(error.message) > 0

    def test_validation_error_includes_position_when_applicable(
        self,
        validator: SignalChainValidator,
        empty_chain: SignalChain,
        make_block,
    ) -> None:
        """Test that position-specific errors include position."""
        # Create chain with multiple amps to get position-specific error
        empty_chain.add_block(make_block(GearType.AMP, block_position=BlockPosition.PRE))
        empty_chain.add_block(make_block(GearType.AMP, block_position=BlockPosition.PRE))

        result = validator.validate(empty_chain)

        assert result.is_valid is False
        multiple_amp_errors = [e for e in result.errors if e.code == ValidationRule.MULTIPLE_AMPS]
        assert len(multiple_amp_errors) > 0
        for error in multiple_amp_errors:
            assert error.position is not None
            assert isinstance(error.position, int)

    def test_multiple_validation_errors_reported(
        self,
        validator: SignalChainValidator,
        empty_chain: SignalChain,
        make_block,
    ) -> None:
        """Test that multiple validation errors are all reported."""
        # Create chain with multiple violations:
        # - Multiple amps
        # - Wrong order (IR before amp)
        empty_chain.add_block(make_block(GearType.IR, block_position=BlockPosition.POST))
        empty_chain.add_block(make_block(GearType.AMP, block_position=BlockPosition.PRE))
        empty_chain.add_block(make_block(GearType.FULL_RIG, block_position=BlockPosition.PRE))

        result = validator.validate(empty_chain)

        assert result.is_valid is False
        # Should have at least MULTIPLE_AMPS and INVALID_ORDER errors
        error_codes = {e.code for e in result.errors}
        assert ValidationRule.MULTIPLE_AMPS in error_codes
        assert ValidationRule.INVALID_ORDER in error_codes


class TestValidationResultHelper:
    """Tests for ValidationResult helper methods."""

    def test_valid_result_is_valid(self) -> None:
        """Test ValidationResult.valid() creates valid result."""
        result = ValidationResult.valid()

        assert result.is_valid is True
        assert len(result.errors) == 0

    def test_invalid_result_is_invalid(self) -> None:
        """Test ValidationResult.invalid() creates invalid result."""
        errors = [
            ValidationError(
                code=ValidationRule.NO_AMP,
                message="Test error",
            )
        ]
        result = ValidationResult.invalid(errors)

        assert result.is_valid is False
        assert len(result.errors) == 1
        assert result.errors[0].code == ValidationRule.NO_AMP
