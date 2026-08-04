"""Single-execution tests for legal bets paired with ordered emissions."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from lottolab.application.use_cases.generate_bet import (
    GenerateOneBet,
    GenerateOneBetReason,
    GenerateOneBetStatus,
    GeneratePortfolio,
    GeneratePortfolioReason,
    GeneratePortfolioStatus,
)
from lottolab.application.use_cases.generate_ordered_candidate_emission import (
    GenerateOrderedCandidateEmission,
    GenerateOrderedCandidateEmissionInput,
    GenerateOrderedPortfolioEmission,
    GenerateOrderedPortfolioEmissionInput,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.ordered_candidate_emission import (
    AuxiliaryOperandAvailability,
    AuxiliaryOperandKind,
)
from lottolab.domain.strategies import LifecycleStatus, ResponseShape, StrategyDescriptor
from lottolab.strategies.adapters.base import (
    BetAdapter,
    CausalDrawRow,
    InvalidOutput,
    PortfolioBetAdapter,
    RejectPrediction,
)
from lottolab.strategies.catalog import StrategyCatalog

_STRATEGY_ID = "fixture_ordered_emission"
_STRATEGY_VERSION = "v1"
_PORTFOLIO_STRATEGY_ID = "fixture_ordered_portfolio_emission"
_PORTFOLIO_NATIVE_COUNT = 3


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


def _portfolio_descriptor() -> StrategyDescriptor:
    return StrategyDescriptor(
        strategy_id=_PORTFOLIO_STRATEGY_ID,
        strategy_name="Fixture Ordered Portfolio Emission",
        version=_STRATEGY_VERSION,
        lottery_types=(LotteryType.BIG_LOTTO,),
        lifecycle_status=LifecycleStatus.OBSERVATION,
        executable=False,
        min_history=1,
        provenance=("fixture:ordered-portfolio-emission",),
        response_shape=ResponseShape.PORTFOLIO,
        native_ticket_count=_PORTFOLIO_NATIVE_COUNT,
    )


def _portfolio_request() -> GenerateOrderedPortfolioEmissionInput:
    return GenerateOrderedPortfolioEmissionInput(
        strategy_id=_PORTFOLIO_STRATEGY_ID,
        lottery_type=LotteryType.BIG_LOTTO,
        history=_history(),
        replicate=3,
        target_draw="101",
        history_cutoff="100",
    )


class _CountingPortfolioAdapter(PortfolioBetAdapter):
    strategy_id = _PORTFOLIO_STRATEGY_ID
    strategy_name = "Fixture Ordered Portfolio Emission"
    strategy_version = _STRATEGY_VERSION
    min_history = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)
    native_ticket_count = _PORTFOLIO_NATIVE_COUNT

    def __init__(self, outcome: str = "ok") -> None:
        self.outcome = outcome
        self.calls = 0

    def _predict_all(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[tuple[int, ...], ...]:
        self.calls += 1
        if self.outcome == "invalid":
            raise InvalidOutput
        if self.outcome == "duplicate":
            return (
                (6, 1, 5, 2, 4, 3),
                (6, 1, 5, 2, 4, 3),
                (12, 11, 10, 9, 8, 7),
            )
        return (
            (6, 1, 5, 2, 4, 3),
            (1, 2, 3, 4, 5, 6),
            (12, 11, 10, 9, 8, 7),
        )


def _portfolio_use_case(
    adapter: _CountingPortfolioAdapter,
) -> GenerateOrderedPortfolioEmission:
    generate_portfolio = GeneratePortfolio(
        StrategyCatalog((_portfolio_descriptor(),)),
        {_PORTFOLIO_STRATEGY_ID: adapter},
    )
    return GenerateOrderedPortfolioEmission(generate_portfolio)


def test_portfolio_execution_produces_one_ordered_emission_per_native_ticket() -> None:
    adapter = _CountingPortfolioAdapter()

    result = _portfolio_use_case(adapter).execute(_portfolio_request())

    assert adapter.calls == 1
    assert result.legal_bets.status is GeneratePortfolioStatus.OK
    assert result.legal_bets.numbers == (
        (1, 2, 3, 4, 5, 6),
        (1, 2, 3, 4, 5, 6),
        (7, 8, 9, 10, 11, 12),
    )
    assert result.emissions is not None
    assert len(result.emissions) == 3
    assert [emission.emitted_main_numbers for emission in result.emissions] == [
        (6, 1, 5, 2, 4, 3),
        (1, 2, 3, 4, 5, 6),
        (12, 11, 10, 9, 8, 7),
    ]
    for emission in result.emissions:
        assert emission.strategy_version == _STRATEGY_VERSION
        assert emission.replicate == 3
        assert emission.target_draw == "101"
        assert emission.history_cutoff == "100"


def test_portfolio_execution_preserves_native_order_and_positional_duplicates() -> None:
    adapter = _CountingPortfolioAdapter("duplicate")

    result = _portfolio_use_case(adapter).execute(_portfolio_request())

    assert result.legal_bets.status is GeneratePortfolioStatus.OK
    assert result.legal_bets.numbers == (
        (1, 2, 3, 4, 5, 6),
        (1, 2, 3, 4, 5, 6),
        (7, 8, 9, 10, 11, 12),
    )
    assert result.emissions is not None
    assert [emission.emitted_main_numbers for emission in result.emissions] == [
        (6, 1, 5, 2, 4, 3),
        (6, 1, 5, 2, 4, 3),
        (12, 11, 10, 9, 8, 7),
    ]


def test_portfolio_non_ok_legal_outcome_remains_closed_and_emits_nothing() -> None:
    adapter = _CountingPortfolioAdapter("invalid")

    result = _portfolio_use_case(adapter).execute(_portfolio_request())

    assert adapter.calls == 1
    assert result.legal_bets.status is GeneratePortfolioStatus.INVALID_OUTPUT
    assert result.legal_bets.reason_code is GeneratePortfolioReason.INVALID_OUTPUT
    assert result.legal_bets.numbers is None
    assert result.emissions is None


def test_portfolio_unknown_strategy_preserves_existing_closed_result_and_emits_nothing() -> (
    None
):
    result = GenerateOrderedPortfolioEmission(
        GeneratePortfolio(StrategyCatalog((_portfolio_descriptor(),)), {})
    ).execute(
        GenerateOrderedPortfolioEmissionInput(
            strategy_id="unknown",
            lottery_type=LotteryType.BIG_LOTTO,
            history=_history(),
            replicate=1,
            target_draw="101",
            history_cutoff="100",
        )
    )

    assert result.legal_bets.status is GeneratePortfolioStatus.STRATEGY_UNAVAILABLE
    assert result.legal_bets.reason_code is GeneratePortfolioReason.UNKNOWN_STRATEGY
    assert result.emissions is None


def test_portfolio_new_input_and_result_are_immutable() -> None:
    request = _portfolio_request()
    result = _portfolio_use_case(_CountingPortfolioAdapter()).execute(request)

    with pytest.raises(FrozenInstanceError):
        request.replicate = 4  # pyright: ignore[reportAttributeAccessIssue]
    with pytest.raises(FrozenInstanceError):
        result.emissions = None  # pyright: ignore[reportAttributeAccessIssue]
