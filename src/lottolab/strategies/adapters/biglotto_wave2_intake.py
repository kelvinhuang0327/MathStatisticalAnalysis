"""Standalone technical-intake adapters for ten resolved BigLotto wave-2 methods."""

# pyright: reportPrivateUsage=false

from __future__ import annotations

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import BetAdapter, CausalDrawRow
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


class BigLottoWave2NeighborAdCooccurrenceAntiPairsAdapter(BetAdapter):
    """Expose the selected A3 anti-pairs method as one native BigLotto ticket."""

    strategy_id = "biglotto_wave2_neighbor_ad_cooccurrence_anti_pairs"
    strategy_name = "BigLotto Wave 2 Neighbor AD Co-occurrence Anti-pairs"
    strategy_version = "v0.1"
    min_history = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)

    def _predict(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[int, ...]:
        return _ad_cooccurrence_anti_pairs(history)


class BigLottoWave2NeighborAdCooccurrenceConditionalAdapter(BetAdapter):
    """Expose the resolved A5 conditional method as one native BigLotto ticket."""

    strategy_id = "biglotto_wave2_neighbor_ad_cooccurrence_conditional"
    strategy_name = "BigLotto Wave 2 Neighbor AD Co-occurrence Conditional"
    strategy_version = "v0.1"
    min_history = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)

    def _predict(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[int, ...]:
        return _ad_cooccurrence_conditional(history)


class BigLottoWave2NeighborAdCooccurrenceTopPairsAdapter(BetAdapter):
    """Expose the resolved A1 top-pairs method as one native BigLotto ticket."""

    strategy_id = "biglotto_wave2_neighbor_ad_cooccurrence_top_pairs"
    strategy_name = "BigLotto Wave 2 Neighbor AD Co-occurrence Top Pairs"
    strategy_version = "v0.1"
    min_history = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)

    def _predict(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[int, ...]:
        return _ad_cooccurrence_top_pairs(history)


class BigLottoWave2NeighborAdCooccurrenceTransitionPairsAdapter(BetAdapter):
    """Expose the resolved A2 transition-pairs method as one native BigLotto ticket."""

    strategy_id = "biglotto_wave2_neighbor_ad_cooccurrence_transition_pairs"
    strategy_name = "BigLotto Wave 2 Neighbor AD Co-occurrence Transition Pairs"
    strategy_version = "v0.1"
    min_history = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)

    def _predict(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[int, ...]:
        return _ad_cooccurrence_transition_pairs(history)


class BigLottoWave2NeighborAdCooccurrenceTripletAdapter(BetAdapter):
    """Expose the resolved A4 triplet method as one native BigLotto ticket."""

    strategy_id = "biglotto_wave2_neighbor_ad_cooccurrence_triplet"
    strategy_name = "BigLotto Wave 2 Neighbor AD Co-occurrence Triplet"
    strategy_version = "v0.1"
    min_history = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)

    def _predict(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[int, ...]:
        return _ad_cooccurrence_triplet(history)


class BigLottoWave2NeighborAdGraphBridgeBetAdapter(BetAdapter):
    """Expose the resolved F2 graph-bridge method as one native BigLotto ticket."""

    strategy_id = "biglotto_wave2_neighbor_ad_graph_bridge_bet"
    strategy_name = "BigLotto Wave 2 Neighbor AD Graph Bridge Bet"
    strategy_version = "v0.1"
    min_history = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)

    def _predict(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[int, ...]:
        return _ad_graph_bridge_bet(history)


class BigLottoWave2NeighborAdGraphCentralityBetAdapter(BetAdapter):
    """Expose the resolved F1 graph-centrality method as one native BigLotto ticket."""

    strategy_id = "biglotto_wave2_neighbor_ad_graph_centrality_bet"
    strategy_name = "BigLotto Wave 2 Neighbor AD Graph Centrality Bet"
    strategy_version = "v0.1"
    min_history = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)

    def _predict(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[int, ...]:
        return _ad_graph_centrality_bet(history)


class BigLottoWave2NeighborAdGraphPagerankBetAdapter(BetAdapter):
    """Expose the resolved F3 graph-PageRank method as one native BigLotto ticket."""

    strategy_id = "biglotto_wave2_neighbor_ad_graph_pagerank_bet"
    strategy_name = "BigLotto Wave 2 Neighbor AD Graph PageRank Bet"
    strategy_version = "v0.1"
    min_history = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)

    def _predict(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[int, ...]:
        return _ad_graph_pagerank_bet(history)


class BigLottoWave2SumRangeAdStructuralSumRegressionAdapter(BetAdapter):
    """Expose the selected B2 sum-regression method as one native BigLotto ticket."""

    strategy_id = "biglotto_wave2_sum_range_ad_structural_sum_regression"
    strategy_name = "BigLotto Wave 2 Sum-range AD Structural Sum Regression"
    strategy_version = "v0.1"
    min_history = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)

    def _predict(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[int, ...]:
        return _ad_structural_sum_regression(history)


class BigLottoWave2SocialAdNegativeConsensusRemoveAdapter(BetAdapter):
    """Expose the selected D3 consensus-removal method as one native BigLotto ticket."""

    strategy_id = "biglotto_wave2_social_ad_negative_consensus_remove"
    strategy_name = "BigLotto Wave 2 Social AD Negative Consensus Remove"
    strategy_version = "v0.1"
    min_history = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)

    def _predict(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[int, ...]:
        return _ad_negative_consensus_remove(history)


__all__ = [
    "BigLottoWave2NeighborAdCooccurrenceAntiPairsAdapter",
    "BigLottoWave2NeighborAdCooccurrenceConditionalAdapter",
    "BigLottoWave2NeighborAdCooccurrenceTopPairsAdapter",
    "BigLottoWave2NeighborAdCooccurrenceTransitionPairsAdapter",
    "BigLottoWave2NeighborAdCooccurrenceTripletAdapter",
    "BigLottoWave2NeighborAdGraphBridgeBetAdapter",
    "BigLottoWave2NeighborAdGraphCentralityBetAdapter",
    "BigLottoWave2NeighborAdGraphPagerankBetAdapter",
    "BigLottoWave2SocialAdNegativeConsensusRemoveAdapter",
    "BigLottoWave2SumRangeAdStructuralSumRegressionAdapter",
]
