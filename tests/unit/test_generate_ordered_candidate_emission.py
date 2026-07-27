"""Single-execution tests for legal bets paired with ordered emissions."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from lottolab.application.use_cases.generate_bet import (
    GenerateOneBet,
    GenerateOneBetReason,
    GenerateOneBetStatus,
)
from lottolab.application.use_cases.generate_ordered_candidate_emission import (
    GenerateOrderedCandidateEmission,
    GenerateOrderedCandidateEmissionInput,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.ordered_candidate_emission import (
    AuxiliaryOperandAvailability,
    AuxiliaryOperandKind,
)
from lottolab.domain.strategies import LifecycleStatus, StrategyDescriptor
from lottolab.strategies.adapters.base import (
    BetAdapter,
    CausalDrawRow,
    InvalidOutput,
    RejectPrediction,
)
from lottolab.strategies.catalog import StrategyCatalog

_STRATEGY_ID = "fixture_ordered_emission"
_STRATEGY_VERSION = "v1"


def _descriptor() -> StrategyDescriptor:
    return StrategyDescriptor(
        strategy_id=_STRATEGY_ID,
        strategy_name="Fixture Ordered Emission",
        version=_STRATEGY_VERSION,
        lottery_types=(LotteryType.BIG_LOTTO,),
        lifecycle_status=LifecycleStatus.OBSERVATION,
        executable=False,
        min_history=1,
        provenance=("fixture:ordered-emission",),
    )


def _history() -> tuple[CausalDrawRow, ...]:
    return (CausalDrawRow("100", "2026-01-01", (1, 2, 3, 4, 5, 6)),)


def _request() -> GenerateOrderedCandidateEmissionInput:
    return GenerateOrderedCandidateEmissionInput(
        strategy_id=_STRATEGY_ID,
        lottery_type=LotteryType.BIG_LOTTO,
        history=_history(),
        replicate=3,
        target_draw="101",
        history_cutoff="100",
    )


class _CountingAdapter(BetAdapter):
    strategy_id = _STRATEGY_ID
    strategy_name = "Fixture Ordered Emission"
    strategy_version = _STRATEGY_VERSION
    min_history = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)

    def __init__(self, outcome: str = "ok") -> None:
        self.outcome = outcome
        self.calls = 0

    def _predict(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[int, ...]:
        self.calls += 1
        if self.outcome == "reject":
            raise RejectPrediction
        if self.outcome == "invalid":
            raise InvalidOutput
        if self.outcome == "duplicate":
            return (6, 5, 4, 3, 2, 2)
        return (6, 1, 5, 2, 4, 3)


def _use_case(adapter: _CountingAdapter) -> GenerateOrderedCandidateEmission:
    generate_one_bet = GenerateOneBet(
        StrategyCatalog((_descriptor(),)),
        {_STRATEGY_ID: adapter},
    )
    return GenerateOrderedCandidateEmission(generate_one_bet)


def test_one_adapter_execution_produces_raw_emission_and_canonical_legal_bet() -> None:
    adapter = _CountingAdapter()

    result = _use_case(adapter).execute(_request())

    assert adapter.calls == 1
    assert result.legal_bet.status is GenerateOneBetStatus.OK
    assert result.legal_bet.numbers == (1, 2, 3, 4, 5, 6)
    assert result.emission is not None
    assert result.emission.emitted_main_numbers == (6, 1, 5, 2, 4, 3)
    assert result.emission.strategy_version == _STRATEGY_VERSION
    assert result.emission.replicate == 3
    assert result.emission.target_draw == "101"
    assert result.emission.history_cutoff == "100"
    assert (
        result.emission.auxiliary_operand_kind
        is AuxiliaryOperandKind.BIG_LOTTO_SPECIAL
    )
    assert (
        result.emission.auxiliary_operand_availability
        is AuxiliaryOperandAvailability.EXPLICITLY_MISSING
    )
    assert result.emission.auxiliary_operand_value is None


@pytest.mark.parametrize(
    ("outcome", "status", "reason"),
    (
        (
            "reject",
            GenerateOneBetStatus.REJECTED,
            GenerateOneBetReason.REJECTED_BY_STRATEGY,
        ),
        (
            "invalid",
            GenerateOneBetStatus.INVALID_OUTPUT,
            GenerateOneBetReason.INVALID_OUTPUT,
        ),
        (
            "duplicate",
            GenerateOneBetStatus.INVALID_OUTPUT,
            GenerateOneBetReason.INVALID_OUTPUT,
        ),
    ),
)
def test_non_ok_legal_outcomes_remain_closed_and_emit_nothing(
    outcome: str,
    status: GenerateOneBetStatus,
    reason: GenerateOneBetReason,
) -> None:
    adapter = _CountingAdapter(outcome)

    result = _use_case(adapter).execute(_request())

    assert adapter.calls == 1
    assert result.legal_bet.status is status
    assert result.legal_bet.reason_code is reason
    assert result.legal_bet.numbers is None
    assert result.emission is None


def test_unknown_strategy_preserves_existing_closed_result_and_emits_nothing() -> None:
    result = GenerateOrderedCandidateEmission(
        GenerateOneBet(StrategyCatalog((_descriptor(),)), {})
    ).execute(
        GenerateOrderedCandidateEmissionInput(
            strategy_id="unknown",
            lottery_type=LotteryType.BIG_LOTTO,
            history=_history(),
            replicate=1,
            target_draw="101",
            history_cutoff="100",
        )
    )

    assert result.legal_bet.status is GenerateOneBetStatus.STRATEGY_UNAVAILABLE
    assert result.legal_bet.reason_code is GenerateOneBetReason.UNKNOWN_STRATEGY
    assert result.emission is None


def test_new_input_and_result_are_immutable() -> None:
    request = _request()
    result = _use_case(_CountingAdapter()).execute(request)

    with pytest.raises(FrozenInstanceError):
        request.replicate = 4  # pyright: ignore[reportAttributeAccessIssue]
    with pytest.raises(FrozenInstanceError):
        result.emission = None  # pyright: ignore[reportAttributeAccessIssue]
