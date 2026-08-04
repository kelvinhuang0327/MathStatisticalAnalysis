"""BigLotto native-strategy wave 6 frozen BACKTESTED portfolio ports.

The four adapters preserve the fixed native portfolios emitted by frozen
donor commit ``49a25effa62fc24f40789c16be6f11bdfb41a4a9``.  The donor
scripts' database-backed shells are intentionally absent: callers provide the
causal history, and only the load-bearing pure selection functions execute.

Shared ``UnifiedPredictionEngine`` methods reuse the verified strategy-layer
ports from waves 3 and 4.  This module adds the donor's scalar trend and EWMA
variants and restores the Unified Markov method's exact text draw-identifier
reversal guard before delegating to the shared numeric implementation.

``verify_gemini_3bet_claim.py`` remains excluded.  Its frozen source returns
``None`` when fewer than 14 distinct weighted candidates exist, and the 11
recorded closures occur at non-prefix history sizes, so neither a fixed
minimum history nor a complete three-ticket execution contract can close it.
"""

# pyright: reportPrivateUsage=false
# Intentional reuse of already-verified sibling strategy helpers; waves 3-4
# are not modified and the strategies package does not import application code.

from __future__ import annotations

import math
from collections import Counter, defaultdict
from collections.abc import Callable
from typing import cast

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import (
    CausalDrawRow,
    PortfolioBetAdapter,
)
from lottolab.strategies.adapters.biglotto_wave3 import (
    _ticket,
    _unified_bayesian_ticket,
    _unified_deviation_ticket,
    _unified_frequency_ticket,
    _unified_markov_ticket,
    _unified_statistical_ticket,
)
from lottolab.strategies.adapters.biglotto_wave4 import (
    _unified_hot_cold_mix_ticket,
    _unified_zone_balance_ticket,
)

_PICK = 6
_WINDOWS = (50, 100, 200, 300, 500)


def _frozen_markov_ticket(
    history: tuple[CausalDrawRow, ...],
) -> tuple[int, ...]:
    """Preserve ``markov_predict``'s frozen text draw-ID ordering guard."""

    markov_history = history
    if len(history) > 1 and history[0].draw > history[-1].draw:
        markov_history = tuple(reversed(history))
    return _unified_markov_ticket(markov_history)


def _unified_trend_ticket(
    history: tuple[CausalDrawRow, ...],
) -> tuple[int, ...]:
    """Port ``UnifiedPredictionEngine.trend_predict`` for BIG_LOTTO."""

    weighted_frequency: defaultdict[int, float] = defaultdict(float)
    for age, draw in enumerate(reversed(history[-100:])):
        weight = math.exp(-0.01 * age)
        for number in draw.numbers:
            weighted_frequency[number] += weight
    total_weight = sum(weighted_frequency.values())
    probabilities = [
        (
            weighted_frequency.get(number, 0.0) / total_weight
            if total_weight > 0
            else 0.0
        )
        for number in range(1, 50)
    ]
    ranked = sorted(
        range(1, 50),
        key=lambda number: probabilities[number - 1],
        reverse=True,
    )
    return _ticket(ranked[:_PICK])


def _ewma_ticket(
    history: tuple[CausalDrawRow, ...],
    lambda_value: float,
) -> tuple[int, ...]:
    """Port one frozen scalar exponential-decay 10-bet variant."""

    weighted_frequency: defaultdict[int, float] = defaultdict(float)
    for age, draw in enumerate(reversed(history)):
        for number in draw.numbers:
            weighted_frequency[number] += math.exp(-lambda_value * age)
    total = sum(weighted_frequency.values())
    probabilities = {
        number: weighted_frequency.get(number, 0.0) / total
        for number in range(1, 50)
    }
    ranked = sorted(
        probabilities,
        key=lambda number: probabilities[number],
        reverse=True,
    )
    return _ticket(ranked[:_PICK])


class BigLottoAutoOptimizerAlphaAdapter(PortfolioBetAdapter):
    """Five Unified methods by five trailing windows, method-major order."""

    strategy_id = "legacy_biglotto__auto_optimizer_alpha__7eaa9572e384"
    strategy_name = "大樂透 Auto Optimizer Alpha（5方法×5窗口）"  # noqa: RUF001
    strategy_version = "v0.1"
    min_history = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)
    native_ticket_count = 25

    def _predict_all(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[tuple[int, ...], ...]:
        methods: tuple[
            Callable[[tuple[CausalDrawRow, ...]], tuple[int, ...]], ...
        ] = (
            _unified_zone_balance_ticket,
            _unified_bayesian_ticket,
            _unified_trend_ticket,
            _unified_frequency_ticket,
            _unified_deviation_ticket,
        )
        return tuple(
            method(history[-window:])
            for method in methods
            for window in _WINDOWS
        )


class BigLottoTenBetBacktestAdapter(PortfolioBetAdapter):
    """Seven Unified tickets then EWMA lambda 0.03, 0.10, and 0.15."""

    strategy_id = "legacy_biglotto__backtest_10bet_biglotto__054e85b088be"
    strategy_name = "大樂透 10注 Unified＋EWMA 回測組合"  # noqa: RUF001
    strategy_version = "v0.1"
    min_history = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)
    native_ticket_count = 10

    def _predict_all(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[tuple[int, ...], ...]:
        return (
            _frozen_markov_ticket(history),
            _unified_deviation_ticket(history),
            _unified_statistical_ticket(history),
            _unified_trend_ticket(history),
            _unified_frequency_ticket(history),
            _unified_bayesian_ticket(history),
            _unified_hot_cold_mix_ticket(history),
            _ewma_ticket(history, 0.03),
            _ewma_ticket(history, 0.10),
            _ewma_ticket(history, 0.15),
        )


class BigLottoTmeThreeAdapter(PortfolioBetAdapter):
    """Statistical, deviation, and Markov tickets in frozen TME order."""

    strategy_id = "legacy_biglotto__test_tme__f3bb5106dfe3"
    strategy_name = "大樂透 TME 三方法獨立組合"
    strategy_version = "v0.1"
    min_history = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)
    native_ticket_count = 3

    def _predict_all(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[tuple[int, ...], ...]:
        return (
            _unified_statistical_ticket(history),
            _unified_deviation_ticket(history),
            _frozen_markov_ticket(history),
        )


class BigLottoGeminiTwoBetVerifierAdapter(PortfolioBetAdapter):
    """Frozen Gemini V1 weighted Top-12 slices at 0:6 and 3:9."""

    strategy_id = "legacy_biglotto__verify_gemini_2bet_claim__d5ca233aa776"
    strategy_name = "大樂透 Gemini V1 雙注驗證組合"
    strategy_version = "v0.1"
    min_history = 50
    supported_lottery_types = (LotteryType.BIG_LOTTO,)
    native_ticket_count = 2

    def _predict_all(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[tuple[int, ...], ...]:
        candidates: Counter[int] = Counter()
        for ticket, weight in (
            (_unified_deviation_ticket(history), 2.0),
            (_frozen_markov_ticket(history), 1.5),
            (_unified_statistical_ticket(history), 1.0),
        ):
            for number in ticket:
                candidates[number] += cast(int, weight)
        top_candidates = [
            number for number, _score in candidates.most_common(12)
        ]
        return (
            _ticket(top_candidates[0:6]),
            _ticket(top_candidates[3:9]),
        )


__all__ = [
    "BigLottoAutoOptimizerAlphaAdapter",
    "BigLottoGeminiTwoBetVerifierAdapter",
    "BigLottoTenBetBacktestAdapter",
    "BigLottoTmeThreeAdapter",
]
