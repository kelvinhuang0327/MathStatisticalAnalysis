"""Executable old/new parity for the legacy frontend Deviation donor."""

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
from lottolab.strategies.adapters import BigLottoFrontendDeviationAdapter
from lottolab.strategies.adapters.base import (
    CausalDrawRow,
    InsufficientHistory,
    InvalidOutput,
    UnsupportedLotteryType,
)
from lottolab.strategies.catalog import production_catalog
from lottolab.strategies.executable_registry import ExecutableRegistry

STRATEGY_ID = "legacy_biglotto__frontend_deviation_strategy__3c895052122e"


def _stride_row(index: int) -> CausalDrawRow:
    numbers = tuple(sorted(((index + step * 8) % 49) + 1 for step in range(6)))
    return CausalDrawRow(
        draw=f"frontend-deviation-{index}",
        date=f"2020-{(index % 12) + 1:02d}-{(index % 28) + 1:02d}",
        numbers=numbers,
    )


def _history(length: int) -> tuple[CausalDrawRow, ...]:
    """LottoLab's canonical oldest-first causal history."""
    return tuple(_stride_row(index) for index in range(length))


DONOR_GOLDENS: dict[int, tuple[int, ...]] = {
    1: (2, 3, 4, 5, 6, 7),
    2: (1, 2, 3, 4, 5, 6),
    3: (1, 2, 3, 9, 10, 11),
    6: (7, 8, 15, 16, 23, 24),
    10: (1, 2, 3, 4, 5, 6),
    20: (1, 2, 3, 9, 10, 11),
    50: (2, 3, 4, 5, 6, 7),
    100: (1, 2, 3, 4, 5, 6),
    500: (1, 2, 3, 4, 5, 6),
}


@pytest.mark.parametrize("length", sorted(DONOR_GOLDENS))
def test_matches_executed_donor_golden(length: int) -> None:
    assert BigLottoFrontendDeviationAdapter().get_one_bet(
        _history(length), LotteryType.BIG_LOTTO
    ) == (DONOR_GOLDENS[length], None)


def test_frequency_aggregation_is_invariant_to_causal_row_order() -> None:
    adapter = BigLottoFrontendDeviationAdapter()
    history = _history(20)
    assert adapter.get_one_bet(history, LotteryType.BIG_LOTTO) == adapter.get_one_bet(
        tuple(reversed(history)), LotteryType.BIG_LOTTO
    )


def test_minimum_history_is_explicit_and_donor_tie_order_is_ascending() -> None:
    adapter = BigLottoFrontendDeviationAdapter()
    with pytest.raises(InsufficientHistory):
        adapter.get_one_bet((), LotteryType.BIG_LOTTO)

    tied = (
        CausalDrawRow("tie-0", "tie-0", (10, 20, 30, 40, 45, 49)),
        CausalDrawRow("tie-1", "tie-1", (10, 20, 30, 40, 45, 49)),
    )
    assert adapter.get_one_bet(tied, LotteryType.BIG_LOTTO) == (
        (1, 2, 3, 4, 5, 6),
        None,
    )


def test_output_is_one_sorted_legal_ticket_and_deterministic() -> None:
    adapter = BigLottoFrontendDeviationAdapter()
    first = adapter.get_one_bet_with_emission(_history(500), LotteryType.BIG_LOTTO)
    second = adapter.get_one_bet_with_emission(_history(500), LotteryType.BIG_LOTTO)
    assert first == second
    assert first.emitted_main_numbers == DONOR_GOLDENS[500]
    assert first.legal_main_numbers == DONOR_GOLDENS[500]
    assert first.special_number is None


def test_invalid_history_and_wrong_lottery_fail_closed() -> None:
    adapter = BigLottoFrontendDeviationAdapter()
    invalid = (CausalDrawRow("bad", "bad", (1, 1, 2, 3, 4, 5)),)
    with pytest.raises(InvalidOutput):
        adapter.get_one_bet(invalid, LotteryType.BIG_LOTTO)
    with pytest.raises(UnsupportedLotteryType):
        adapter.get_one_bet(_history(1), LotteryType.DAILY_539)


def test_catalog_and_registry_add_exactly_one_online_identity() -> None:
    catalog = production_catalog()
    descriptor = catalog.get(STRATEGY_ID)
    assert len(catalog) == 119
    assert [item.strategy_id for item in catalog].count(STRATEGY_ID) == 1
    assert descriptor.strategy_id == BigLottoFrontendDeviationAdapter.strategy_id
    assert descriptor.strategy_name == BigLottoFrontendDeviationAdapter.strategy_name
    assert descriptor.version == BigLottoFrontendDeviationAdapter.strategy_version
    assert descriptor.lottery_types == (LotteryType.BIG_LOTTO,)
    assert descriptor.lifecycle_status is LifecycleStatus.ONLINE
    assert descriptor.executable is True
    assert descriptor.response_shape is ResponseShape.SINGLE_TICKET
    assert descriptor.native_ticket_count == 1
    assert descriptor.min_history == 1
    assert descriptor.adapter_path == (
        "lottolab.strategies.adapters.biglotto_frontend_deviation:"
        "BigLottoFrontendDeviationAdapter"
    )
    assert (
        "legacy_source_sha256:"
        "3c895052122ec899a4a5559b2a7411190621f077f5ccc53436aefac3fdc705fc"
        in descriptor.provenance
    )
    assert "legacy_symbol:DeviationStrategy.predict" in descriptor.provenance
    assert "legacy_runtime:PredictionEngine.strategies.deviation" in descriptor.provenance
    assert (
        "donor_execution:REVIVED_WITH_STATISTICS_SERVICE_STUB_ISOLATED"
        in descriptor.provenance
    )
    assert ExecutableRegistry(catalog).load_adapter(STRATEGY_ID) is (
        BigLottoFrontendDeviationAdapter
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
        raise AssertionError("Frontend Deviation Strategy must not open a database")

    monkeypatch.setattr(sqlite3, "connect", _forbidden_connect)
    result = build_production_generate_one_bet().execute(_request(_history(20)))
    assert result.status is GenerateOneBetStatus.OK
    assert result.numbers == DONOR_GOLDENS[20]
