"""Focused contracts for the selected BigLotto wave-2 intake adapters."""

# pyright: reportPrivateUsage=false

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import pytest

from lottolab.domain.draws import LotteryType
from lottolab.domain.lottery_rules import BIG_LOTTO_RULE_CONTRACT
from lottolab.strategies.adapters.base import (
    BetAdapter,
    CausalDrawRow,
    InsufficientHistory,
    UnsupportedLotteryType,
)
from lottolab.strategies.adapters.biglotto_wave2 import (
    _ad_cooccurrence_anti_pairs,
    _ad_negative_consensus_remove,
    _ad_structural_sum_regression,
)
from lottolab.strategies.adapters.biglotto_wave2_intake import (
    BigLottoWave2NeighborAdCooccurrenceAntiPairsAdapter,
    BigLottoWave2SocialAdNegativeConsensusRemoveAdapter,
    BigLottoWave2SumRangeAdStructuralSumRegressionAdapter,
)
from lottolab.strategies.catalog import UnknownStrategyError, production_catalog

_SelectedCallable = Callable[[tuple[CausalDrawRow, ...]], tuple[int, ...]]


@dataclass(frozen=True, slots=True)
class _SelectedCase:
    adapter_class: type[BetAdapter]
    source_callable: _SelectedCallable
    strategy_id: str


_SELECTED_CASES = (
    _SelectedCase(
        BigLottoWave2NeighborAdCooccurrenceAntiPairsAdapter,
        _ad_cooccurrence_anti_pairs,
        "biglotto_wave2_neighbor_ad_cooccurrence_anti_pairs",
    ),
    _SelectedCase(
        BigLottoWave2SumRangeAdStructuralSumRegressionAdapter,
        _ad_structural_sum_regression,
        "biglotto_wave2_sum_range_ad_structural_sum_regression",
    ),
    _SelectedCase(
        BigLottoWave2SocialAdNegativeConsensusRemoveAdapter,
        _ad_negative_consensus_remove,
        "biglotto_wave2_social_ad_negative_consensus_remove",
    ),
)

_EXPECTED_CANDIDATE_IDS = (
    "biglotto_wave2_neighbor_ad_cooccurrence_anti_pairs::BIG_LOTTO",
    "biglotto_wave2_sum_range_ad_structural_sum_regression::BIG_LOTTO",
    "biglotto_wave2_social_ad_negative_consensus_remove::BIG_LOTTO",
)


def _history(rows: int) -> tuple[CausalDrawRow, ...]:
    return tuple(
        CausalDrawRow(
            draw=f"intake-{index}",
            date=f"2026-{(index % 12) + 1:02d}-{(index % 28) + 1:02d}",
            numbers=tuple(sorted(((index + step * 8) % 49) + 1 for step in range(6))),
        )
        for index in range(rows)
    )


@pytest.mark.parametrize("case", _SELECTED_CASES)
def test_selected_adapter_identity_and_native_support(case: _SelectedCase) -> None:
    adapter = case.adapter_class()

    assert adapter.strategy_id == case.strategy_id
    assert adapter.strategy_version == "v0.1"
    assert adapter.min_history == 1
    assert adapter.supported_lottery_types == (LotteryType.BIG_LOTTO,)


@pytest.mark.parametrize("case", _SELECTED_CASES)
def test_selected_adapter_rejects_wrong_lottery_type(case: _SelectedCase) -> None:
    with pytest.raises(UnsupportedLotteryType):
        case.adapter_class().get_one_bet(_history(1), LotteryType.POWER_LOTTO)


@pytest.mark.parametrize("case", _SELECTED_CASES)
def test_selected_adapter_enforces_proven_minimum_history(case: _SelectedCase) -> None:
    with pytest.raises(InsufficientHistory):
        case.adapter_class().get_one_bet((), LotteryType.BIG_LOTTO)


@pytest.mark.parametrize("case", _SELECTED_CASES)
def test_selected_adapter_is_exact_thin_delegation(case: _SelectedCase) -> None:
    history = _history(100)

    execution = case.adapter_class().get_one_bet_with_emission(
        history, LotteryType.BIG_LOTTO
    )

    assert execution.emitted_main_numbers == case.source_callable(history)
    assert execution.legal_main_numbers == case.source_callable(history)
    assert execution.special_number is None


@pytest.mark.parametrize("case", _SELECTED_CASES)
def test_selected_adapter_returns_one_deterministic_native_ticket(
    case: _SelectedCase,
) -> None:
    adapter = case.adapter_class()
    history = _history(100)

    first = adapter.get_one_bet(history, LotteryType.BIG_LOTTO)
    second = adapter.get_one_bet(history, LotteryType.BIG_LOTTO)
    ticket, special_number = first

    assert first == second
    assert special_number is None
    assert len(ticket) == BIG_LOTTO_RULE_CONTRACT.main_number_count
    assert len(set(ticket)) == BIG_LOTTO_RULE_CONTRACT.main_number_count
    assert all(
        BIG_LOTTO_RULE_CONTRACT.main_number_min
        <= number
        <= BIG_LOTTO_RULE_CONTRACT.main_number_max
        for number in ticket
    )


def test_selected_candidate_identities_remain_exact_ordered_and_distinct() -> None:
    candidate_ids = tuple(f"{case.strategy_id}::BIG_LOTTO" for case in _SELECTED_CASES)

    assert candidate_ids == _EXPECTED_CANDIDATE_IDS
    assert len(set(candidate_ids)) == 3


@pytest.mark.parametrize("case", _SELECTED_CASES)
def test_selected_adapter_is_not_catalog_registered(case: _SelectedCase) -> None:
    with pytest.raises(UnknownStrategyError):
        production_catalog().get(case.strategy_id)
