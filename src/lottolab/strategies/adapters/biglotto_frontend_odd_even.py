"""Target-native port of the legacy frontend Odd/Even Balance strategy.

The donor is ``LotteryNewMeraged/src/engine/strategies/OddEvenBalanceStrategy.js``.
It counts the full 1..49 frequency map, chooses odd numbers when the total odd
frequency is tied with or greater than the total even frequency, and otherwise
chooses even numbers. Within that parity, the donor ranks by descending
frequency with the ascending integer insertion order preserved for ties. The
donor emits one ascending six-number ticket; its method and report fields have
no counterpart in the native single-ticket response and are intentionally not
invented here.

The legacy ``StatisticsService.calculateFrequency`` method is asynchronous in
the production service, while this donor calls it synchronously. The donor was
therefore genuinely revived with a bounded synchronous statistics-compatible
stub. The adapter reproduces the source-visible frequency map from
caller-supplied causal history and does not open a database.
"""

from __future__ import annotations

from collections import Counter
from typing import Final

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import BetAdapter, CausalDrawRow

_STRATEGY_ID: Final = "legacy_biglotto__frontend_odd_even_balance_strategy__5b7f125437d0"
_MIN_NUMBER: Final = 1
_MAX_NUMBER: Final = 49
_PICK_COUNT: Final = 6


class BigLottoFrontendOddEvenBalanceAdapter(BetAdapter):
    """Reproduce ``OddEvenBalanceStrategy.predict`` for one Big Lotto ticket."""

    strategy_id = _STRATEGY_ID
    strategy_name = "大樂透 Frontend Odd/Even Balance Strategy"
    strategy_version = "v0.1"
    min_history = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)

    def _predict(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[int, ...]:
        """Apply the donor's parity selection and stable frequency ranking."""

        frequency = Counter(number for row in history for number in row.numbers)
        odd_sum = sum(
            frequency.get(number, 0)
            for number in range(_MIN_NUMBER, _MAX_NUMBER + 1)
            if number % 2 != 0
        )
        even_sum = sum(
            frequency.get(number, 0)
            for number in range(_MIN_NUMBER, _MAX_NUMBER + 1)
            if number % 2 == 0
        )

        target_parity_is_odd = odd_sum >= even_sum
        candidates = [
            (number, frequency.get(number, 0))
            for number in range(_MIN_NUMBER, _MAX_NUMBER + 1)
            if (number % 2 != 0) is target_parity_is_odd
        ]

        # The donor constructs candidates in ascending integer order and uses
        # stable Array.sort((a, b) => b.freq - a.freq). The explicit number
        # key makes that JavaScript tie order visible and auditable in Python.
        candidates.sort(key=lambda item: (-item[1], item[0]))
        selected = [number for number, _frequency in candidates[:_PICK_COUNT]]
        return tuple(sorted(selected))


__all__ = ["BigLottoFrontendOddEvenBalanceAdapter"]
