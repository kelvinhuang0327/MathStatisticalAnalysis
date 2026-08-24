"""Target-native port of the legacy frontend Deviation strategy.

The donor is ``LotteryNewMeraged/src/engine/strategies/DeviationStrategy.js``.
The frontend receives newest-first rows, but the donor's frequency aggregate
is order-independent, so the native oldest-first causal history can be
consumed directly without changing the result.  The donor returns probability
and presentation metadata in addition to its six numbers; only the native
single-ticket number output is load-bearing here.

The legacy ``StatisticsService.calculateFrequency`` dependency is synchronous
at the donor call site even though the production service is asynchronous.
The donor algorithm was executed with a bounded synchronous statistics stub
before this port; the adapter reproduces that source-visible frequency map
from the caller-supplied causal history and does not open a database.
"""

from __future__ import annotations

import math
from collections import Counter
from typing import Final

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import BetAdapter, CausalDrawRow

_STRATEGY_ID: Final = "legacy_biglotto__frontend_deviation_strategy__3c895052122e"
_MIN_NUMBER: Final = 1
_MAX_NUMBER: Final = 49
_PICK_COUNT: Final = 6


class BigLottoFrontendDeviationAdapter(BetAdapter):
    """Reproduce ``DeviationStrategy.predict`` for Big Lotto tickets."""

    strategy_id = _STRATEGY_ID
    strategy_name = "大樂透 Frontend Deviation Strategy"
    strategy_version = "v0.1"
    min_history = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)

    def _predict(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[int, ...]:
        """Apply the donor's population deviation scoring and ranking rules."""

        frequency = Counter(number for row in history for number in row.numbers)
        total_numbers = _MAX_NUMBER - _MIN_NUMBER + 1
        expected_frequency = len(history) * _PICK_COUNT / total_numbers

        sum_squared_difference = sum(
            (frequency.get(number, 0) - expected_frequency) ** 2
            for number in range(_MIN_NUMBER, _MAX_NUMBER + 1)
        )
        standard_deviation = math.sqrt(sum_squared_difference / total_numbers)

        probabilities: dict[int, float] = {}
        for number in range(_MIN_NUMBER, _MAX_NUMBER + 1):
            current_frequency = frequency.get(number, 0)
            z_score = (
                (current_frequency - expected_frequency) / standard_deviation
                if standard_deviation > 0
                else 0.0
            )

            if z_score < -1.5:
                score = 0.8 + abs(z_score) * 0.1
            elif z_score > 2.0:
                score = 0.2
            elif z_score > 0.5 and z_score < 1.5:
                score = 0.6 + z_score * 0.1
            else:
                score = 0.4
            probabilities[number] = score

        total_probability = sum(probabilities.values())
        if total_probability > 0:
            probabilities = {
                number: probability / total_probability
                for number, probability in probabilities.items()
            }
        else:
            probabilities = {
                number: 1 / total_numbers
                for number in range(_MIN_NUMBER, _MAX_NUMBER + 1)
            }

        # JS Object.entries() enumerates integer-like keys in ascending order;
        # stable equal-score sorting therefore uses the ascending number order.
        ranked = sorted(
            probabilities.items(),
            key=lambda item: (-item[1], item[0]),
        )[:_PICK_COUNT]
        return tuple(sorted(number for number, _probability in ranked))


__all__ = ["BigLottoFrontendDeviationAdapter"]
