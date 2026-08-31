"""Synthetic QuickML successor characterization, not historical performance evidence."""

# pyright: reportPrivateUsage=false

from __future__ import annotations

import json

import pytest
from tests.unit.test_biglotto_wave12_adapters import QUICK_ML_GOLDENS, _wave12_history

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.biglotto_quickml_corrected_successor import (
    BigLottoQuickMlCorrectedSuccessorAdapter,
)
from lottolab.strategies.adapters.biglotto_wave12 import (
    BigLottoQuickMlPredictAdapter,
    Wave12FrozenSourceError,
)
from lottolab.strategies.catalog import UnknownStrategyError, production_catalog
from lottolab.strategies.executable_registry import ExecutableRegistry

SUCCESSOR_GOLDENS: dict[int, tuple[tuple[int, ...], ...]] = {
    5: ((1, 9, 17, 25, 33, 41), (5, 6, 7, 13, 19, 21)),
    6: ((1, 9, 17, 25, 33, 41), (6, 7, 8, 14, 20, 22)),
    7: ((3, 11, 19, 27, 35, 43), (7, 8, 15, 16, 21, 23)),
    50: ((6, 14, 22, 30, 39, 47), (1, 2, 9, 17, 23, 42)),
}

PINNED_GOLDENS = {**QUICK_ML_GOLDENS, **SUCCESSOR_GOLDENS}


def test_frozen_quick_ml_boundary_remains_unchanged() -> None:
    adapter = BigLottoQuickMlPredictAdapter()
    assert adapter.get_bets(_wave12_history(4), LotteryType.BIG_LOTTO) == QUICK_ML_GOLDENS[4]
    with pytest.raises(Wave12FrozenSourceError) as excinfo:
        adapter.get_bets(_wave12_history(5), LotteryType.BIG_LOTTO)
    assert excinfo.value.reason_code == "FROZEN_SOURCE_PATTERN_SLICE_INDEX_ERROR"
    assert str(excinfo.value) == "FROZEN_SOURCE_PATTERN_SLICE_INDEX_ERROR"


@pytest.mark.parametrize("n", sorted(QUICK_ML_GOLDENS))
def test_successor_matches_frozen_quick_ml_for_histories_one_through_four(n: int) -> None:
    history = _wave12_history(n)
    frozen = BigLottoQuickMlPredictAdapter().get_bets(history, LotteryType.BIG_LOTTO)
    successor = BigLottoQuickMlCorrectedSuccessorAdapter().get_bets(history, LotteryType.BIG_LOTTO)
    assert successor == frozen == QUICK_ML_GOLDENS[n]


@pytest.mark.parametrize("n", sorted(SUCCESSOR_GOLDENS))
def test_successor_matches_golden_with_exactly_two_legal_tickets(n: int) -> None:
    history = _wave12_history(n)
    bets = BigLottoQuickMlCorrectedSuccessorAdapter().get_bets(history, LotteryType.BIG_LOTTO)
    assert bets == SUCCESSOR_GOLDENS[n]
    assert len(bets) == 2
    for ticket in bets:
        assert len(ticket) == len(set(ticket)) == 6
        assert all(type(number) is int and 1 <= number <= 49 for number in ticket)
        assert ticket == tuple(sorted(ticket))


@pytest.mark.parametrize("n", sorted(PINNED_GOLDENS))
def test_successor_repeated_execution_is_byte_identical_for_every_pinned_case(n: int) -> None:
    history = _wave12_history(n)
    adapter = BigLottoQuickMlCorrectedSuccessorAdapter()
    outputs = (
        adapter.get_bets(history, LotteryType.BIG_LOTTO),
        adapter.get_bets(history, LotteryType.BIG_LOTTO),
        BigLottoQuickMlCorrectedSuccessorAdapter().get_bets(history, LotteryType.BIG_LOTTO),
    )
    actual = [json.dumps(bets, separators=(",", ":")).encode("ascii") for bets in outputs]
    expected = json.dumps(PINNED_GOLDENS[n], separators=(",", ":")).encode("ascii")
    assert actual == [expected, expected, expected]


def test_successor_has_a_distinct_identity_and_explicit_derivative_provenance() -> None:
    adapter = BigLottoQuickMlCorrectedSuccessorAdapter()
    assert adapter.strategy_id == "research_biglotto__quick_ml_corrected_successor_v1"
    assert adapter.strategy_id != BigLottoQuickMlPredictAdapter.strategy_id
    assert adapter.strategy_version == "v1"
    assert adapter.status == "UNREGISTERED_RESEARCH_DERIVATIVE"
    assert adapter.provenance == (
        "frozen_parent_strategy_id:legacy_biglotto__quick_ml_predict__8b7ba0b52e2d",
        "frozen_donor_source:tools/quick_ml_predict.py",
        "frozen_donor_source_sha256:"
        "8b7ba0b52e2dfcb7bd39997be9dbfab90a81f6e44c3fcf269ac5c9ddaa266d80",
        "frozen_implementation_module:src/lottolab/strategies/adapters/biglotto_wave12.py",
        "correction:historical-pattern range(3, len(recent_first) - 1)"
        " -> range(3, len(recent_first) - 3)",
        "lineage_status:DISTINCT_DERIVATIVE",
    )


def test_successor_is_absent_from_production_catalog_and_executable_registry() -> None:
    strategy_id = BigLottoQuickMlCorrectedSuccessorAdapter.strategy_id
    catalog = production_catalog()
    assert strategy_id not in {descriptor.strategy_id for descriptor in catalog}
    with pytest.raises(UnknownStrategyError):
        catalog.get(strategy_id)
    registry = ExecutableRegistry(catalog)
    assert strategy_id not in registry.executable_ids()
    with pytest.raises(UnknownStrategyError):
        registry.load_adapter(strategy_id)
