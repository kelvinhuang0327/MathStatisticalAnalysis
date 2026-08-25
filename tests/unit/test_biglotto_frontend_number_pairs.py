"""Executable old/new parity for the legacy frontend Number Pairs donor."""

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
    BigLottoFrontendNumberPairsAdapter,
    CausalDrawRow,
)
from lottolab.strategies.adapters.base import (
    InsufficientHistory,
    InvalidOutput,
    UnsupportedLotteryType,
)
from lottolab.strategies.catalog import production_catalog
from lottolab.strategies.executable_registry import ExecutableRegistry

STRATEGY_ID = "legacy_biglotto__frontend_number_pairs_strategy__72ebb17b5a96"
_RANDOM_VALUES = tuple(((index * 37) % 997) / 997 for index in range(183))


def _stride_row(index: int) -> CausalDrawRow:
    numbers = tuple(sorted(((index + step * 8) % 49) + 1 for step in range(6)))
    return CausalDrawRow(
        draw=f"frontend-number-pairs-{index}",
        date=f"2020-{(index % 12) + 1:02d}-{(index % 28) + 1:02d}",
        numbers=numbers,
    )


def _history(length: int) -> tuple[CausalDrawRow, ...]:
    """LottoLab's canonical oldest-first causal history."""
    return tuple(_stride_row(index) for index in range(length))


class _SequenceRandom:
    def __init__(self, values: tuple[float, ...]) -> None:
        self._values = values
        self.calls = 0

    def random(self) -> float:
        value = self._values[self.calls]
        self.calls += 1
        return value


class _ZeroRandom:
    def random(self) -> float:
        return 0.0


# Captured by directly importing and executing the donor JavaScript module
# with the same 183-value Math.random sequence, then checking the target port.
DONOR_GOLDENS: dict[int, tuple[int, ...]] = {
    1: (1, 9, 17, 25, 33, 41),
    2: (2, 10, 18, 26, 34, 42),
    6: (6, 14, 22, 30, 38, 46),
    10: (2, 10, 18, 26, 34, 42),
    50: (1, 9, 17, 25, 33, 41),
    200: (4, 12, 20, 28, 36, 44),
}


@pytest.mark.parametrize("length", sorted(DONOR_GOLDENS))
def test_matches_executed_donor_golden(length: int) -> None:
    rng = _SequenceRandom(_RANDOM_VALUES)
    result = BigLottoFrontendNumberPairsAdapter(rng=rng).get_one_bet(
        _history(length), LotteryType.BIG_LOTTO
    )
    assert result == (DONOR_GOLDENS[length], None)
    assert rng.calls == 183


def test_newest_first_reversal_preserves_stable_pair_insertion_order() -> None:
    history = _history(2)
    adapter = BigLottoFrontendNumberPairsAdapter(rng=_ZeroRandom())
    assert adapter.get_one_bet(history, LotteryType.BIG_LOTTO) == (
        (2, 10, 18, 26, 34, 42),
        None,
    )
    assert adapter.get_one_bet(tuple(reversed(history)), LotteryType.BIG_LOTTO) == (
        (1, 9, 17, 25, 33, 41),
        None,
    )


def test_strict_numeric_candidate_ties_match_donor() -> None:
    history = (
        CausalDrawRow("tie", "2026-01-01", (10, 11, 12, 13, 14, 15)),
    )
    assert BigLottoFrontendNumberPairsAdapter(rng=_ZeroRandom()).get_one_bet(
        history, LotteryType.BIG_LOTTO
    ) == ((10, 11, 12, 13, 14, 15), None)


def test_minimum_history_and_output_contract_are_explicit() -> None:
    adapter = BigLottoFrontendNumberPairsAdapter(rng=_SequenceRandom(_RANDOM_VALUES))
    with pytest.raises(InsufficientHistory):
        adapter.get_one_bet((), LotteryType.BIG_LOTTO)

    execution = adapter.get_one_bet_with_emission(_history(1), LotteryType.BIG_LOTTO)
    assert execution.emitted_main_numbers == DONOR_GOLDENS[1]
    assert execution.legal_main_numbers == DONOR_GOLDENS[1]
    assert execution.special_number is None
    assert len(execution.legal_main_numbers) == 6
    assert execution.legal_main_numbers == tuple(sorted(set(execution.legal_main_numbers)))


def test_invalid_history_and_wrong_lottery_fail_closed() -> None:
    adapter = BigLottoFrontendNumberPairsAdapter(rng=_ZeroRandom())
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
    assert descriptor.strategy_id == BigLottoFrontendNumberPairsAdapter.strategy_id
    assert descriptor.strategy_name == BigLottoFrontendNumberPairsAdapter.strategy_name
    assert descriptor.version == BigLottoFrontendNumberPairsAdapter.strategy_version
    assert descriptor.lottery_types == (LotteryType.BIG_LOTTO,)
    assert descriptor.lifecycle_status is LifecycleStatus.ONLINE
    assert descriptor.executable is True
    assert descriptor.response_shape is ResponseShape.SINGLE_TICKET
    assert descriptor.native_ticket_count == 1
    assert descriptor.min_history == 1
    assert descriptor.adapter_path == (
        "lottolab.strategies.adapters.biglotto_frontend_number_pairs:"
        "BigLottoFrontendNumberPairsAdapter"
    )
    assert (
        "legacy_source_sha256:"
        "72ebb17b5a96cd7d168e3e2011d0ec817ec386ac907620d942105a5e92ac11ff"
        in descriptor.provenance
    )
    assert "legacy_symbol:NumberPairsStrategy.predict" in descriptor.provenance
    assert "legacy_runtime:PredictionEngine.strategies.number_pairs" in descriptor.provenance
    assert "legacy_history_order:NEWEST_FIRST" in descriptor.provenance
    assert "target_history_order:OLDEST_FIRST" in descriptor.provenance
    assert (
        "donor_execution:EXECUTABLE_DIRECT_NODE_MODULE_IMPORT_WITH_FIXED_RANDOM_SEQUENCE"
        in descriptor.provenance
    )
    assert ExecutableRegistry(catalog).load_adapter(STRATEGY_ID) is (
        BigLottoFrontendNumberPairsAdapter
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
        raise AssertionError("Frontend Number Pairs Strategy must not open a database")

    monkeypatch.setattr(sqlite3, "connect", _forbidden_connect)
    result = build_production_generate_one_bet().execute(_request(_history(20)))
    assert result.status is GenerateOneBetStatus.OK
