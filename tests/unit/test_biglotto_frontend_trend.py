"""Executable old/new parity for the legacy frontend Trend donor.

The expected tickets were produced by executing the actual donor entry point
``TrendStrategy.predict`` with Node against the same oldest-first histories
reversed into the donor's newest-first input order. The donor was executed from
``LotteryNewMeraged/src/engine/strategies/TrendStrategy.js`` before this adapter
was implemented.
"""

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
from lottolab.strategies.adapters import BigLottoFrontendTrendAdapter
from lottolab.strategies.adapters.base import (
    CausalDrawRow,
    InsufficientHistory,
    InvalidOutput,
    UnsupportedLotteryType,
)
from lottolab.strategies.catalog import production_catalog
from lottolab.strategies.executable_registry import ExecutableRegistry

STRATEGY_ID = "legacy_biglotto__frontend_trend_strategy__a5f4554c80ef"


def _stride_row(index: int) -> CausalDrawRow:
    numbers = tuple(sorted(((index + step * 8) % 49) + 1 for step in range(6)))
    return CausalDrawRow(
        draw=f"frontend-trend-{index}",
        date=f"2020-{(index % 12) + 1:02d}-{(index % 28) + 1:02d}",
        numbers=numbers,
    )


def _history(length: int) -> tuple[CausalDrawRow, ...]:
    """LottoLab's canonical oldest-first causal history."""
    return tuple(_stride_row(index) for index in range(length))


DONOR_GOLDENS: dict[int, tuple[int, ...]] = {
    1: (1, 9, 17, 25, 33, 41),
    2: (2, 10, 18, 26, 34, 42),
    3: (3, 11, 19, 27, 35, 43),
    6: (6, 14, 22, 30, 38, 46),
    20: (3, 11, 20, 28, 36, 44),
    50: (1, 9, 17, 25, 33, 41),
    100: (2, 10, 18, 26, 34, 42),
    500: (1, 10, 18, 26, 34, 42),
}


@pytest.mark.parametrize("length", sorted(DONOR_GOLDENS))
def test_matches_executed_donor_golden(length: int) -> None:
    assert BigLottoFrontendTrendAdapter().get_one_bet(
        _history(length), LotteryType.BIG_LOTTO
    ) == (DONOR_GOLDENS[length], None)


def test_minimum_history_and_donor_fallback_are_explicit() -> None:
    adapter = BigLottoFrontendTrendAdapter()
    with pytest.raises(InsufficientHistory):
        adapter.get_one_bet((), LotteryType.BIG_LOTTO)
    assert adapter.get_one_bet(_history(1), LotteryType.BIG_LOTTO) == (
        DONOR_GOLDENS[1],
        None,
    )


def test_ranking_ties_preserve_ascending_integer_key_order() -> None:
    history = (
        CausalDrawRow("tie-0", "tie-0", (10, 20, 30, 40, 45, 49)),
        CausalDrawRow("tie-1", "tie-1", (10, 20, 30, 40, 45, 49)),
    )
    assert BigLottoFrontendTrendAdapter().get_one_bet(history, LotteryType.BIG_LOTTO) == (
        (10, 20, 30, 40, 45, 49),
        None,
    )


def test_edge_number_boundaries_and_history_order_match_donor() -> None:
    history = (
        CausalDrawRow("edge-0", "edge-0", (1, 2, 3, 4, 5, 6)),
        CausalDrawRow("edge-1", "edge-1", (44, 45, 46, 47, 48, 49)),
    )
    # edge-1 is newer in oldest-first history, so it gets higher weight (exp(0) vs exp(-0.05))
    assert BigLottoFrontendTrendAdapter().get_one_bet(history, LotteryType.BIG_LOTTO) == (
        (44, 45, 46, 47, 48, 49),
        None,
    )


def test_output_is_one_sorted_legal_ticket_and_deterministic() -> None:
    adapter = BigLottoFrontendTrendAdapter()
    first = adapter.get_one_bet_with_emission(_history(500), LotteryType.BIG_LOTTO)
    second = adapter.get_one_bet_with_emission(_history(500), LotteryType.BIG_LOTTO)
    assert first == second
    assert first.emitted_main_numbers == DONOR_GOLDENS[500]
    assert first.legal_main_numbers == DONOR_GOLDENS[500]
    assert first.special_number is None


def test_invalid_history_and_wrong_lottery_fail_closed() -> None:
    adapter = BigLottoFrontendTrendAdapter()
    invalid = (CausalDrawRow("bad", "bad", (1, 1, 2, 3, 4, 5)),)
    with pytest.raises(InvalidOutput):
        adapter.get_one_bet(invalid, LotteryType.BIG_LOTTO)
    with pytest.raises(UnsupportedLotteryType):
        adapter.get_one_bet(_history(1), LotteryType.DAILY_539)


def test_catalog_and_registry_add_exactly_one_online_identity() -> None:
    catalog = production_catalog()
    descriptor = catalog.get(STRATEGY_ID)
    assert len(catalog) == 117
    assert descriptor.strategy_id == BigLottoFrontendTrendAdapter.strategy_id
    assert descriptor.strategy_name == BigLottoFrontendTrendAdapter.strategy_name
    assert descriptor.version == BigLottoFrontendTrendAdapter.strategy_version
    assert descriptor.lottery_types == (LotteryType.BIG_LOTTO,)
    assert descriptor.lifecycle_status is LifecycleStatus.ONLINE
    assert descriptor.executable is True
    assert descriptor.response_shape is ResponseShape.SINGLE_TICKET
    assert descriptor.native_ticket_count == 1
    assert descriptor.min_history == 1
    assert descriptor.adapter_path == (
        "lottolab.strategies.adapters.biglotto_frontend_trend:"
        "BigLottoFrontendTrendAdapter"
    )
    assert (
        "legacy_source_sha256:"
        "a5f4554c80ef364f60afa5c9761889c28a18fd2cc79ac97b712eca573eb8e309"
        in descriptor.provenance
    )
    assert "legacy_symbol:TrendStrategy.predict" in descriptor.provenance
    assert "legacy_runtime:PredictionEngine.strategies.trend" in descriptor.provenance
    assert ExecutableRegistry(catalog).load_adapter(STRATEGY_ID) is BigLottoFrontendTrendAdapter


def _request(history: tuple[CausalDrawRow, ...]) -> GenerateOneBetInput:
    return GenerateOneBetInput(
        strategy_id=STRATEGY_ID,
        lottery_type=LotteryType.BIG_LOTTO,
        history=history,
    )


def test_production_single_ticket_generation_path_is_reachable() -> None:
    result = build_production_generate_one_bet().execute(_request(_history(20)))
    assert result.status is GenerateOneBetStatus.OK
    assert result.numbers == DONOR_GOLDENS[20]
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
        raise AssertionError("Frontend Trend Strategy must not open a database")

    monkeypatch.setattr(sqlite3, "connect", _forbidden_connect)
    result = build_production_generate_one_bet().execute(_request(_history(20)))
    assert result.status is GenerateOneBetStatus.OK
    assert result.numbers == DONOR_GOLDENS[20]
