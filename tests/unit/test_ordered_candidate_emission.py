"""Closed domain-contract tests for producer-ordered candidate emissions."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace

import pytest

from lottolab.domain.draws import LotteryType
from lottolab.domain.ordered_candidate_emission import (
    ORDERED_CANDIDATE_EMISSION_SCHEMA_VERSION,
    AuxiliaryOperandAvailability,
    AuxiliaryOperandKind,
    OrderedCandidateEmission,
)


def _emission(
    *,
    lottery_type: LotteryType = LotteryType.BIG_LOTTO,
    emitted_main_numbers: tuple[int, ...] = (9, 4, 9, 2),
    auxiliary_operand_kind: AuxiliaryOperandKind = (
        AuxiliaryOperandKind.BIG_LOTTO_SPECIAL
    ),
    auxiliary_operand_availability: AuxiliaryOperandAvailability = (
        AuxiliaryOperandAvailability.EXPLICITLY_MISSING
    ),
    auxiliary_operand_value: int | None = None,
) -> OrderedCandidateEmission:
    return OrderedCandidateEmission(
        schema_version=ORDERED_CANDIDATE_EMISSION_SCHEMA_VERSION,
        lottery_type=lottery_type,
        strategy_id="fixture_strategy",
        strategy_version="v1",
        replicate=2,
        target_draw="101",
        history_cutoff="100",
        emitted_main_numbers=emitted_main_numbers,
        auxiliary_operand_kind=auxiliary_operand_kind,
        auxiliary_operand_availability=auxiliary_operand_availability,
        auxiliary_operand_value=auxiliary_operand_value,
    )


def test_model_is_frozen_and_preserves_order_and_duplicates_exactly() -> None:
    emission = _emission()

    assert emission.emitted_main_numbers == (9, 4, 9, 2)
    with pytest.raises(FrozenInstanceError):
        emission.replicate = 3  # pyright: ignore[reportAttributeAccessIssue]


@pytest.mark.parametrize(
    ("lottery_type", "kind", "availability", "value"),
    (
        (
            LotteryType.BIG_LOTTO,
            AuxiliaryOperandKind.BIG_LOTTO_SPECIAL,
            AuxiliaryOperandAvailability.PRESENT,
            49,
        ),
        (
            LotteryType.BIG_LOTTO,
            AuxiliaryOperandKind.BIG_LOTTO_SPECIAL,
            AuxiliaryOperandAvailability.EXPLICITLY_MISSING,
            None,
        ),
        (
            LotteryType.POWER_LOTTO,
            AuxiliaryOperandKind.POWER_LOTTO_ZONE2,
            AuxiliaryOperandAvailability.PRESENT,
            8,
        ),
        (
            LotteryType.POWER_LOTTO,
            AuxiliaryOperandKind.POWER_LOTTO_ZONE2,
            AuxiliaryOperandAvailability.EXPLICITLY_MISSING,
            None,
        ),
        (
            LotteryType.DAILY_539,
            AuxiliaryOperandKind.DAILY_539,
            AuxiliaryOperandAvailability.NOT_APPLICABLE,
            None,
        ),
    ),
)
def test_all_closed_auxiliary_combinations_are_accepted(
    lottery_type: LotteryType,
    kind: AuxiliaryOperandKind,
    availability: AuxiliaryOperandAvailability,
    value: int | None,
) -> None:
    maximum = {
        LotteryType.BIG_LOTTO: 49,
        LotteryType.POWER_LOTTO: 38,
        LotteryType.DAILY_539: 39,
    }[lottery_type]

    emission = _emission(
        lottery_type=lottery_type,
        emitted_main_numbers=(1, maximum),
        auxiliary_operand_kind=kind,
        auxiliary_operand_availability=availability,
        auxiliary_operand_value=value,
    )

    assert emission.auxiliary_operand_value == value


@pytest.mark.parametrize(
    ("lottery_type", "kind", "availability", "value"),
    (
        (
            LotteryType.BIG_LOTTO,
            AuxiliaryOperandKind.POWER_LOTTO_ZONE2,
            AuxiliaryOperandAvailability.EXPLICITLY_MISSING,
            None,
        ),
        (
            LotteryType.BIG_LOTTO,
            AuxiliaryOperandKind.BIG_LOTTO_SPECIAL,
            AuxiliaryOperandAvailability.NOT_APPLICABLE,
            None,
        ),
        (
            LotteryType.BIG_LOTTO,
            AuxiliaryOperandKind.BIG_LOTTO_SPECIAL,
            AuxiliaryOperandAvailability.PRESENT,
            50,
        ),
        (
            LotteryType.POWER_LOTTO,
            AuxiliaryOperandKind.POWER_LOTTO_ZONE2,
            AuxiliaryOperandAvailability.PRESENT,
            9,
        ),
        (
            LotteryType.DAILY_539,
            AuxiliaryOperandKind.DAILY_539,
            AuxiliaryOperandAvailability.EXPLICITLY_MISSING,
            None,
        ),
    ),
)
def test_every_other_auxiliary_combination_is_rejected(
    lottery_type: LotteryType,
    kind: AuxiliaryOperandKind,
    availability: AuxiliaryOperandAvailability,
    value: int | None,
) -> None:
    with pytest.raises(ValueError):
        _emission(
            lottery_type=lottery_type,
            emitted_main_numbers=(1,),
            auxiliary_operand_kind=kind,
            auxiliary_operand_availability=availability,
            auxiliary_operand_value=value,
        )


@pytest.mark.parametrize(
    ("lottery_type", "numbers"),
    (
        (LotteryType.BIG_LOTTO, (0,)),
        (LotteryType.BIG_LOTTO, (50,)),
        (LotteryType.POWER_LOTTO, (39,)),
        (LotteryType.DAILY_539, (40,)),
        (LotteryType.BIG_LOTTO, (True,)),
    ),
)
def test_game_specific_main_pool_validation_is_closed(
    lottery_type: LotteryType,
    numbers: tuple[int, ...],
) -> None:
    kind = {
        LotteryType.BIG_LOTTO: AuxiliaryOperandKind.BIG_LOTTO_SPECIAL,
        LotteryType.POWER_LOTTO: AuxiliaryOperandKind.POWER_LOTTO_ZONE2,
        LotteryType.DAILY_539: AuxiliaryOperandKind.DAILY_539,
    }[lottery_type]
    availability = (
        AuxiliaryOperandAvailability.NOT_APPLICABLE
        if lottery_type is LotteryType.DAILY_539
        else AuxiliaryOperandAvailability.EXPLICITLY_MISSING
    )
    with pytest.raises(ValueError):
        _emission(
            lottery_type=lottery_type,
            emitted_main_numbers=numbers,
            auxiliary_operand_kind=kind,
            auxiliary_operand_availability=availability,
        )


@pytest.mark.parametrize(
    "changes",
    (
        {"schema_version": "2.0.0"},
        {"strategy_id": ""},
        {"strategy_version": " v1"},
        {"replicate": 0},
        {"replicate": True},
        {"target_draw": "draw-101"},
        {"history_cutoff": "cutoff-100"},
        {"target_draw": "100"},
        {"emitted_main_numbers": ()},
        {"emitted_main_numbers": [1, 2, 3]},
    ),
)
def test_required_field_invariants_fail_closed(changes: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        replace(_emission(), **changes)  # pyright: ignore[reportArgumentType]
