"""Focused contracts for the resolved BigLotto wave-2 intake adapters."""

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
    _ad_cooccurrence_conditional,
    _ad_cooccurrence_top_pairs,
    _ad_cooccurrence_transition_pairs,
    _ad_cooccurrence_triplet,
    _ad_graph_bridge_bet,
    _ad_graph_centrality_bet,
    _ad_graph_pagerank_bet,
    _ad_negative_consensus_remove,
    _ad_structural_sum_regression,
)
from lottolab.strategies.adapters.biglotto_wave2_intake import (
    BigLottoWave2NeighborAdCooccurrenceAntiPairsAdapter,
    BigLottoWave2NeighborAdCooccurrenceConditionalAdapter,
    BigLottoWave2NeighborAdCooccurrenceTopPairsAdapter,
    BigLottoWave2NeighborAdCooccurrenceTransitionPairsAdapter,
    BigLottoWave2NeighborAdCooccurrenceTripletAdapter,
    BigLottoWave2NeighborAdGraphBridgeBetAdapter,
    BigLottoWave2NeighborAdGraphCentralityBetAdapter,
    BigLottoWave2NeighborAdGraphPagerankBetAdapter,
    BigLottoWave2SocialAdNegativeConsensusRemoveAdapter,
    BigLottoWave2SumRangeAdStructuralSumRegressionAdapter,
)

_ResolvedCallable = Callable[[tuple[CausalDrawRow, ...]], tuple[int, ...]]


@dataclass(frozen=True, slots=True)
class _ResolvedCase:
    adapter_class: type[BetAdapter]
    source_callable: _ResolvedCallable
    strategy_id: str


_RESOLVED_CASES = (
    _ResolvedCase(
        BigLottoWave2NeighborAdCooccurrenceAntiPairsAdapter,
        _ad_cooccurrence_anti_pairs,
        "biglotto_wave2_neighbor_ad_cooccurrence_anti_pairs",
    ),
    _ResolvedCase(
        BigLottoWave2SumRangeAdStructuralSumRegressionAdapter,
        _ad_structural_sum_regression,
        "biglotto_wave2_sum_range_ad_structural_sum_regression",
    ),
    _ResolvedCase(
        BigLottoWave2SocialAdNegativeConsensusRemoveAdapter,
        _ad_negative_consensus_remove,
        "biglotto_wave2_social_ad_negative_consensus_remove",
    ),
    _ResolvedCase(
        BigLottoWave2NeighborAdCooccurrenceConditionalAdapter,
        _ad_cooccurrence_conditional,
        "biglotto_wave2_neighbor_ad_cooccurrence_conditional",
    ),
    _ResolvedCase(
        BigLottoWave2NeighborAdCooccurrenceTopPairsAdapter,
        _ad_cooccurrence_top_pairs,
        "biglotto_wave2_neighbor_ad_cooccurrence_top_pairs",
    ),
    _ResolvedCase(
        BigLottoWave2NeighborAdCooccurrenceTransitionPairsAdapter,
        _ad_cooccurrence_transition_pairs,
        "biglotto_wave2_neighbor_ad_cooccurrence_transition_pairs",
    ),
    _ResolvedCase(
        BigLottoWave2NeighborAdCooccurrenceTripletAdapter,
        _ad_cooccurrence_triplet,
        "biglotto_wave2_neighbor_ad_cooccurrence_triplet",
    ),
    _ResolvedCase(
        BigLottoWave2NeighborAdGraphBridgeBetAdapter,
        _ad_graph_bridge_bet,
        "biglotto_wave2_neighbor_ad_graph_bridge_bet",
    ),
    _ResolvedCase(
        BigLottoWave2NeighborAdGraphCentralityBetAdapter,
        _ad_graph_centrality_bet,
        "biglotto_wave2_neighbor_ad_graph_centrality_bet",
    ),
    _ResolvedCase(
        BigLottoWave2NeighborAdGraphPagerankBetAdapter,
        _ad_graph_pagerank_bet,
        "biglotto_wave2_neighbor_ad_graph_pagerank_bet",
    ),
)

_EXPECTED_CANDIDATE_IDS = (
    "biglotto_wave2_neighbor_ad_cooccurrence_anti_pairs::BIG_LOTTO",
    "biglotto_wave2_sum_range_ad_structural_sum_regression::BIG_LOTTO",
    "biglotto_wave2_social_ad_negative_consensus_remove::BIG_LOTTO",
    "biglotto_wave2_neighbor_ad_cooccurrence_conditional::BIG_LOTTO",
    "biglotto_wave2_neighbor_ad_cooccurrence_top_pairs::BIG_LOTTO",
    "biglotto_wave2_neighbor_ad_cooccurrence_transition_pairs::BIG_LOTTO",
    "biglotto_wave2_neighbor_ad_cooccurrence_triplet::BIG_LOTTO",
    "biglotto_wave2_neighbor_ad_graph_bridge_bet::BIG_LOTTO",
    "biglotto_wave2_neighbor_ad_graph_centrality_bet::BIG_LOTTO",
    "biglotto_wave2_neighbor_ad_graph_pagerank_bet::BIG_LOTTO",
)

_EXPECTED_MIN_HISTORY = {
    "biglotto_wave2_neighbor_ad_cooccurrence_conditional": 50,
}


def _history(rows: int) -> tuple[CausalDrawRow, ...]:
    return tuple(
        CausalDrawRow(
            draw=f"intake-{index}",
            date=f"2026-{(index % 12) + 1:02d}-{(index % 28) + 1:02d}",
            numbers=tuple(sorted(((index + step * 8) % 49) + 1 for step in range(6))),
        )
        for index in range(rows)
    )


@pytest.mark.parametrize("case", _RESOLVED_CASES)
def test_resolved_adapter_identity_and_native_support(case: _ResolvedCase) -> None:
    adapter = case.adapter_class()

    assert adapter.strategy_id == case.strategy_id
    assert adapter.strategy_version == "v0.1"
    assert adapter.min_history == _EXPECTED_MIN_HISTORY.get(case.strategy_id, 1)
    assert adapter.supported_lottery_types == (LotteryType.BIG_LOTTO,)


@pytest.mark.parametrize("case", _RESOLVED_CASES)
def test_resolved_adapter_rejects_wrong_lottery_type(case: _ResolvedCase) -> None:
    with pytest.raises(UnsupportedLotteryType):
        case.adapter_class().get_one_bet(_history(1), LotteryType.POWER_LOTTO)


@pytest.mark.parametrize("case", _RESOLVED_CASES)
def test_resolved_adapter_enforces_proven_minimum_history(case: _ResolvedCase) -> None:
    with pytest.raises(InsufficientHistory):
        case.adapter_class().get_one_bet((), LotteryType.BIG_LOTTO)


def test_conditional_adapter_enforces_source_safe_minimum_history() -> None:
    adapter = BigLottoWave2NeighborAdCooccurrenceConditionalAdapter()

    assert adapter.min_history == 50
    with pytest.raises(InsufficientHistory):
        adapter.get_one_bet(_history(49), LotteryType.BIG_LOTTO)

    ticket, special_number = adapter.get_one_bet(_history(50), LotteryType.BIG_LOTTO)
    assert len(ticket) == BIG_LOTTO_RULE_CONTRACT.main_number_count
    assert special_number is None


@pytest.mark.parametrize("case", _RESOLVED_CASES)
def test_resolved_adapter_is_exact_thin_delegation(case: _ResolvedCase) -> None:
    history = _history(100)

    execution = case.adapter_class().get_one_bet_with_emission(
        history, LotteryType.BIG_LOTTO
    )

    assert execution.emitted_main_numbers == case.source_callable(history)
    assert execution.legal_main_numbers == case.source_callable(history)
    assert execution.special_number is None


@pytest.mark.parametrize("case", _RESOLVED_CASES)
def test_resolved_adapter_returns_one_deterministic_native_ticket(
    case: _ResolvedCase,
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


def test_resolved_candidate_identities_remain_exact_ordered_and_distinct() -> None:
    candidate_ids = tuple(f"{case.strategy_id}::BIG_LOTTO" for case in _RESOLVED_CASES)

    assert candidate_ids == _EXPECTED_CANDIDATE_IDS
    assert len(set(candidate_ids)) == 10
