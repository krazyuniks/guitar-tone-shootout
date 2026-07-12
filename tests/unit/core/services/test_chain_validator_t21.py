"""Unit tests for signal chain capture ordering and composition rules."""

from uuid import uuid4

import pytest

from gts.domain.entities.signal_chain import SignalChain, SignalChainBlock
from gts.domain.value_objects.signal_chain_enums import GearType
from gts.services.signal_chain_validator import SignalChainValidator, ValidationRule


@pytest.fixture
def validator() -> SignalChainValidator:
    return SignalChainValidator()


@pytest.fixture
def chain() -> SignalChain:
    return SignalChain(id=uuid4(), user_id=uuid4(), name="Test Chain")


def add_blocks(chain: SignalChain, *gear_types: GearType) -> None:
    for gear_type in gear_types:
        chain.add_block(
            SignalChainBlock(
                id=uuid4(),
                signal_chain_id=chain.id,
                position=0,
                user_gear_id=uuid4(),
                gear_type=gear_type,
            )
        )


def error_codes(validator: SignalChainValidator, chain: SignalChain) -> set[ValidationRule]:
    return {error.code for error in validator.validate(chain).errors}


def test_chain_requires_one_amp(validator: SignalChainValidator, chain: SignalChain) -> None:
    add_blocks(chain, GearType.PEDAL)

    assert ValidationRule.NO_AMP in error_codes(validator, chain)


def test_chain_rejects_multiple_amps(validator: SignalChainValidator, chain: SignalChain) -> None:
    add_blocks(chain, GearType.AMP, GearType.FULL_RIG)

    assert ValidationRule.MULTIPLE_AMPS in error_codes(validator, chain)


def test_head_capture_requires_ir(validator: SignalChainValidator, chain: SignalChain) -> None:
    add_blocks(chain, GearType.AMP)

    assert ValidationRule.IR_REQUIRED in error_codes(validator, chain)


def test_full_rig_capture_rejects_ir(validator: SignalChainValidator, chain: SignalChain) -> None:
    add_blocks(chain, GearType.FULL_RIG, GearType.IR)

    assert ValidationRule.IR_FORBIDDEN in error_codes(validator, chain)


def test_chain_rejects_multiple_irs(validator: SignalChainValidator, chain: SignalChain) -> None:
    add_blocks(chain, GearType.AMP, GearType.IR, GearType.IR)

    assert ValidationRule.MULTIPLE_IRS in error_codes(validator, chain)


@pytest.mark.parametrize(
    "gear_types",
    [
        (GearType.AMP, GearType.IR, GearType.PEDAL),
        (GearType.IR, GearType.AMP),
        (GearType.AMP, GearType.POST_EFFECT, GearType.IR),
    ],
)
def test_chain_rejects_invalid_capture_order(
    validator: SignalChainValidator,
    chain: SignalChain,
    gear_types: tuple[GearType, ...],
) -> None:
    add_blocks(chain, *gear_types)

    assert ValidationRule.INVALID_ORDER in error_codes(validator, chain)


@pytest.mark.parametrize(
    "gear_types",
    [
        (GearType.FULL_RIG,),
        (GearType.PEDAL, GearType.AMP, GearType.IR, GearType.POST_EFFECT),
    ],
)
def test_valid_capture_chain_passes(
    validator: SignalChainValidator,
    chain: SignalChain,
    gear_types: tuple[GearType, ...],
) -> None:
    add_blocks(chain, *gear_types)

    result = validator.validate(chain)

    assert result.is_valid is True
    assert result.errors == []
