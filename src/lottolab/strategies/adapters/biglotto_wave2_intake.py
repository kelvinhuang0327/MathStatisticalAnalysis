"""Standalone technical-intake adapters for three selected BigLotto wave-2 methods."""

# pyright: reportPrivateUsage=false

from __future__ import annotations

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import BetAdapter, CausalDrawRow
from lottolab.strategies.adapters.biglotto_wave2 import (
    _ad_cooccurrence_anti_pairs,
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
    "BigLottoWave2SocialAdNegativeConsensusRemoveAdapter",
    "BigLottoWave2SumRangeAdStructuralSumRegressionAdapter",
]
