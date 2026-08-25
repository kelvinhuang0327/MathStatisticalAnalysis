"""Executable old/new parity for the legacy frontend Monte Carlo donor."""

from __future__ import annotations

import sqlite3

import pytest

from lottolab.application.use_cases.generate_bet import (
    GenerateOneBetInput,
    GenerateOneBetStatus,
    GeneratePortfolioReason,
    GeneratePortfolioStatus,
    build_production_generate_one_bet,
    build_production_generate_portfolio,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.strategies import LifecycleStatus, ResponseShape
from lottolab.strategies.adapters import (
    BigLottoFrontendMonteCarloAdapter,
    CausalDrawRow,
)
from lottolab.strategies.adapters.base import (
    InsufficientHistory,
    InvalidOutput,
    UnsupportedLotteryType,
)
from lottolab.strategies.catalog import production_catalog
from lottolab.strategies.executable_registry import ExecutableRegistry

STRATEGY_ID = "legacy_biglotto__frontend_monte_carlo_strategy__9d8fe030546e"


def _stride_row(index: int) -> CausalDrawRow:
    numbers = tuple(sorted(((index + step * 8) % 49) + 1 for step in range(6)))
    return CausalDrawRow(
        draw=f"frontend-monte-carlo-{index}",
        date=f"2020-{(index % 12) + 1:02d}-{(index % 28) + 1:02d}",
        numbers=numbers,
    )


def _history(length: int) -> tuple[CausalDrawRow, ...]:
    """LottoLab's canonical oldest-first causal history."""

    return tuple(_stride_row(index) for index in range(length))


def _constant_history(
    numbers: tuple[int, ...], length: int = 50
) -> tuple[CausalDrawRow, ...]:
    return tuple(
        CausalDrawRow(
            draw=f"frontend-monte-carlo-edge-{index}",
            date=f"2021-{(index % 12) + 1:02d}-{(index % 28) + 1:02d}",
            numbers=numbers,
        )
        for index in range(length)
    )


class _FormulaRandom:
    """The exact deterministic stream used to execute the JavaScript donor."""

    def __init__(self) -> None:
        self.calls = 0

    def random(self) -> float:
        value = ((self.calls * 37) % 997) / 997
        self.calls += 1
        return value


class _TieRandom:
    """Emit four balanced six-of-eight simulated draws in a fixed cycle."""

    _OMITTED_PAIRS = ((1, 2), (3, 4), (5, 6), (7, 8))
    _REPEATS_PER_NUMBER = 22
    _POOL_SIZE = 49 * _REPEATS_PER_NUMBER

    def __init__(self) -> None:
        self.calls = 0

    def random(self) -> float:
        simulation, position = divmod(self.calls, 6)
        omitted = self._OMITTED_PAIRS[simulation % len(self._OMITTED_PAIRS)]
        selected = tuple(number for number in range(1, 9) if number not in omitted)
        number = selected[position]
        self.calls += 1
        first_pool_index = (number - 1) * self._REPEATS_PER_NUMBER
        return (first_pool_index + 0.25) / self._POOL_SIZE


# Captured by importing and executing the donor JavaScript class with a
# synchronous StatisticsService-compatible seam and the same formula stream.
DONOR_GOLDENS: dict[int, tuple[tuple[int, ...], int]] = {
    1: ((1, 9, 17, 25, 33, 41), 89_821),
    2: ((10, 17, 18, 33, 41, 42), 71_216),
    6: ((1, 4, 10, 13, 19, 22), 60_000),
    10: ((1, 10, 17, 18, 25, 34), 60_000),
    49: ((1, 6, 12, 21, 26, 32), 60_000),
    50: ((1, 9, 17, 25, 33, 41), 60_000),
    200: ((1, 6, 12, 21, 26, 32), 60_000),
    500: ((1, 6, 12, 21, 26, 32), 60_000),
}


@pytest.mark.parametrize("length", sorted(DONOR_GOLDENS))
def test_matches_executed_donor_golden(length: int) -> None:
    expected, expected_calls = DONOR_GOLDENS[length]
    rng = _FormulaRandom()
    result = BigLottoFrontendMonteCarloAdapter(rng=rng).get_one_bet(
        _history(length), LotteryType.BIG_LOTTO
    )
    assert result == (expected, None)
    assert rng.calls == expected_calls


def test_frequency_only_history_is_order_independent() -> None:
    history = _history(50)
    forward_rng = _FormulaRandom()
    reverse_rng = _FormulaRandom()
    forward = BigLottoFrontendMonteCarloAdapter(rng=forward_rng).get_one_bet(
        history, LotteryType.BIG_LOTTO
    )
    reverse = BigLottoFrontendMonteCarloAdapter(rng=reverse_rng).get_one_bet(
        tuple(reversed(history)), LotteryType.BIG_LOTTO
    )
    assert forward == reverse == (DONOR_GOLDENS[50][0], None)
    assert forward_rng.calls == reverse_rng.calls == DONOR_GOLDENS[50][1]


@pytest.mark.parametrize(
    ("numbers", "expected", "expected_calls"),
    (
        ((1, 2, 3, 4, 5, 6), (1, 2, 3, 4, 5, 6), 89_826),
        ((44, 45, 46, 47, 48, 49), (44, 45, 46, 47, 48, 49), 89_816),
    ),
)
def test_edge_numbers_match_executed_donor(
    numbers: tuple[int, ...], expected: tuple[int, ...], expected_calls: int
) -> None:
    rng = _FormulaRandom()
    assert BigLottoFrontendMonteCarloAdapter(rng=rng).get_one_bet(
        _constant_history(numbers), LotteryType.BIG_LOTTO
    ) == (expected, None)
    assert rng.calls == expected_calls


def test_eight_way_probability_tie_uses_ascending_integer_key_order() -> None:
    # Across 49 stride rows every number appears six times, so every pool block
    # has 22 entries.  Four balanced omission pairs give numbers 1..8 exactly
    # 7,500 inclusions each; the donor's stable integer-key tie chooses 1..6.
    rng = _TieRandom()
    assert BigLottoFrontendMonteCarloAdapter(rng=rng).get_one_bet(
        _history(49), LotteryType.BIG_LOTTO
    ) == ((1, 2, 3, 4, 5, 6), None)
    assert rng.calls == 60_000


def test_minimum_history_and_output_contract_are_explicit() -> None:
    rng = _FormulaRandom()
    adapter = BigLottoFrontendMonteCarloAdapter(rng=rng)
    with pytest.raises(InsufficientHistory):
        adapter.get_one_bet((), LotteryType.BIG_LOTTO)
    assert rng.calls == 0

    execution = adapter.get_one_bet_with_emission(_history(1), LotteryType.BIG_LOTTO)
    assert execution.emitted_main_numbers == DONOR_GOLDENS[1][0]
    assert execution.legal_main_numbers == DONOR_GOLDENS[1][0]
    assert execution.special_number is None
    assert len(execution.legal_main_numbers) == 6
    assert execution.legal_main_numbers == tuple(sorted(set(execution.legal_main_numbers)))


def test_invalid_history_and_wrong_lottery_fail_closed() -> None:
    adapter = BigLottoFrontendMonteCarloAdapter(rng=_FormulaRandom())
    invalid = (CausalDrawRow("bad", "bad", (1, 1, 2, 3, 4, 5)),)
    with pytest.raises(InvalidOutput):
        adapter.get_one_bet(invalid, LotteryType.BIG_LOTTO)
    with pytest.raises(UnsupportedLotteryType):
        adapter.get_one_bet(_history(1), LotteryType.DAILY_539)


def test_catalog_and_registry_add_exactly_one_online_identity() -> None:
    catalog = production_catalog()
    descriptor = catalog.get(STRATEGY_ID)
    assert len(catalog) == 126
    assert [item.strategy_id for item in catalog].count(STRATEGY_ID) == 1
    assert descriptor.strategy_id == BigLottoFrontendMonteCarloAdapter.strategy_id
    assert descriptor.strategy_name == BigLottoFrontendMonteCarloAdapter.strategy_name
    assert descriptor.version == BigLottoFrontendMonteCarloAdapter.strategy_version
    assert descriptor.lottery_types == (LotteryType.BIG_LOTTO,)
    assert descriptor.lifecycle_status is LifecycleStatus.ONLINE
    assert descriptor.executable is True
    assert descriptor.response_shape is ResponseShape.SINGLE_TICKET
    assert descriptor.native_ticket_count == 1
    assert descriptor.min_history == 1
    assert descriptor.adapter_path == (
        "lottolab.strategies.adapters.biglotto_frontend_monte_carlo:"
        "BigLottoFrontendMonteCarloAdapter"
    )
    assert (
        "legacy_source_sha256:"
        "9d8fe030546e8b5bedb7423441a547ef53db30436dc681a80ec37087b355515b"
        in descriptor.provenance
    )
    assert "legacy_symbol:MonteCarloStrategy.predict" in descriptor.provenance
    assert "legacy_runtime:PredictionEngine.strategies.montecarlo" in descriptor.provenance
    assert "simulations:10000" in descriptor.provenance
    assert "fallback:NONE" in descriptor.provenance
    assert (
        "donor_execution:REVIVED_WITH_SYNCHRONOUS_STATISTICS_SERVICE_STUB_ISOLATED"
        in descriptor.provenance
    )
    assert ExecutableRegistry(catalog).load_adapter(STRATEGY_ID) is (
        BigLottoFrontendMonteCarloAdapter
    )


def _request(history: tuple[CausalDrawRow, ...]) -> GenerateOneBetInput:
    return GenerateOneBetInput(
        strategy_id=STRATEGY_ID,
        lottery_type=LotteryType.BIG_LOTTO,
        history=history,
    )


def test_production_single_ticket_generation_path_is_reachable() -> None:
    result = build_production_generate_one_bet().execute(_request(_history(20)))
    assert result.status is GenerateOneBetStatus.OK
    assert result.numbers is not None
    assert len(result.numbers) == 6
    assert result.numbers == tuple(sorted(set(result.numbers)))
    assert result.special_number is None
    assert result.reason_code is None


def test_portfolio_path_rejects_single_ticket_identity() -> None:
    result = build_production_generate_portfolio().execute(_request(_history(20)))
    assert result.status is GeneratePortfolioStatus.WRONG_RESPONSE_PATH
    assert result.numbers is None
    assert result.reason_code is GeneratePortfolioReason.STRATEGY_IS_NOT_PORTFOLIO


def test_production_generation_never_opens_a_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _forbidden_connect(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("Frontend Monte Carlo Strategy must not open a database")

    monkeypatch.setattr(sqlite3, "connect", _forbidden_connect)
    result = build_production_generate_one_bet().execute(_request(_history(20)))
    assert result.status is GenerateOneBetStatus.OK
