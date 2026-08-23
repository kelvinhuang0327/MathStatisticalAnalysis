"""Target-native port of the legacy frontend Trend strategy.

The donor is ``LotteryNewMeraged/src/engine/strategies/TrendStrategy.js``.
Its frontend data is newest-first, while LottoLab causal histories are
oldest-first, so the adapter reverses the validated history before applying
the donor's exponential decay weighting (lambda = 0.05). The donor emits one
ascending six-number ticket; its extra probability/report fields have no
counterpart in the native single-ticket response and are intentionally not
invented here.
"""

from __future__ import annotations

import math

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import BetAdapter, CausalDrawRow

_MIN_NUM = 1
_MAX_NUM = 49
_PICK = 6
_LAMBDA = 0.05


class BigLottoFrontendTrendAdapter(BetAdapter):
    """Reproduce ``TrendStrategy.predict`` for Big Lotto single tickets."""

    strategy_id = "legacy_biglotto__frontend_trend_strategy__a5f4554c80ef"
    strategy_name = "大樂透 Frontend Trend Strategy"
    strategy_version = "v0.1"
    min_history = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)

    def _predict(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[int, ...]:
        """Apply the donor's newest-first exponential decay and ranking semantics."""

        newest_first = tuple(reversed(history))
        weighted_frequency: dict[int, float] = {
            number: 0.0 for number in range(_MIN_NUM, _MAX_NUM + 1)
        }

        for age, draw in enumerate(newest_first):
            weight = math.exp(-_LAMBDA * age)
            for number in draw.numbers:
                if number in weighted_frequency:
                    weighted_frequency[number] += weight

        total_weight = sum(weighted_frequency.values())
        if total_weight > 0.0:
            probabilities = {
                number: freq / total_weight
                for number, freq in weighted_frequency.items()
            }
        else:
            uniform = 1.0 / (_MAX_NUM - _MIN_NUM + 1)
            probabilities = {
                number: uniform for number in range(_MIN_NUM, _MAX_NUM + 1)
            }

        # In JS: Object.entries() enumerates integer-like keys in ascending order
        # and JS sort is stable, keeping ascending order for equal probabilities.
        ranked = sorted(
            probabilities.items(),
            key=lambda item: (-item[1], item[0]),
        )[:_PICK]
        return tuple(sorted(number for number, _probability in ranked))
