"""Target-native port of the legacy frontend Frequency strategy.

The donor is ``LotteryNewMeraged/src/engine/strategies/FrequencyStrategy.js``.
Its frontend data is newest-first, while LottoLab causal histories are
oldest-first, so the adapter reverses the validated history before applying
the donor's frequency ranking. The donor's probability, confidence, and
report fields have no counterpart in the native single-ticket response and
are intentionally not invented here.
"""

from __future__ import annotations

from collections import Counter
from typing import Final

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import BetAdapter, CausalDrawRow

_STRATEGY_ID: Final = "legacy_biglotto__frontend_frequency_strategy__2e3e8febb5f1"
_MIN_NUMBER: Final = 1
_MAX_NUMBER: Final = 49
_PICK_COUNT: Final = 6


class BigLottoFrontendFrequencyAdapter(BetAdapter):
    """Reproduce ``FrequencyStrategy.predict`` for Big Lotto single tickets."""

    strategy_id = _STRATEGY_ID
    strategy_name = "大樂透 Frontend Frequency Strategy"
    strategy_version = "v0.1"
    min_history = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)

    def _predict(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[int, ...]:
        """Apply the donor's newest-first frequency and stable ranking semantics."""

        newest_first = tuple(reversed(history))
        frequency = Counter(number for row in newest_first for number in row.numbers)
        total_draws = len(newest_first)
        probabilities = {
            number: frequency[number] / total_draws
            for number in range(_MIN_NUMBER, _MAX_NUMBER + 1)
        }

        # Object.entries() starts with integer-like keys in ascending order and
        # the donor's stable sort preserves that order for equal probabilities.
        ranked = sorted(
            probabilities.items(),
            key=lambda item: (-item[1], item[0]),
        )[:_PICK_COUNT]
        return tuple(sorted(number for number, _probability in ranked))
