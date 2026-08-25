"""Target-native port of the legacy frontend Zone Balance strategy.

The donor is ``LotteryNewMeraged/src/engine/strategies/ZoneBalanceStrategy.js``.
It totals the complete Big Lotto frequency map within five dynamically sized
zones, selects the highest-frequency zone, and returns the six most frequent
numbers from that zone. The source response's method and report fields have no
counterpart in the native single-ticket response and are intentionally not
invented here.

The production StatisticsService exposes ``calculateFrequency`` as an async
method even though this donor calls it synchronously. The donor was genuinely
revived with a bounded synchronous statistics-compatible stub before this
port; the adapter reproduces that source-visible frequency map from
caller-supplied causal history and does not open a database.
"""

from __future__ import annotations

from collections import Counter
from typing import Final

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import BetAdapter, CausalDrawRow

_STRATEGY_ID: Final = "legacy_biglotto__frontend_zone_balance_strategy__6a016aa83b3e"
_MIN_NUMBER: Final = 1
_MAX_NUMBER: Final = 49
_PICK_COUNT: Final = 6
_ZONE_COUNT: Final = 5


class BigLottoFrontendZoneBalanceAdapter(BetAdapter):
    """Reproduce ``ZoneBalanceStrategy.predict`` for one Big Lotto ticket."""

    strategy_id = _STRATEGY_ID
    strategy_name = "大樂透 Frontend Zone Balance Strategy"
    strategy_version = "v0.1"
    min_history = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)

    def _predict(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[int, ...]:
        """Select the donor's highest-frequency zone and stable top numbers."""

        frequency = Counter(number for row in history for number in row.numbers)
        total_numbers = _MAX_NUMBER - _MIN_NUMBER + 1
        zone_size = (total_numbers + _ZONE_COUNT - 1) // _ZONE_COUNT
        zone_ranges = tuple(
            (
                _MIN_NUMBER + index * zone_size,
                min(_MIN_NUMBER + (index + 1) * zone_size - 1, _MAX_NUMBER),
            )
            for index in range(_ZONE_COUNT)
        )

        # The donor declares zones in ascending order and uses stable sort for
        # equal totals, so the first zone wins a tie.
        target_start, target_end = max(
            zone_ranges,
            key=lambda bounds: sum(
                frequency.get(number, 0)
                for number in range(bounds[0], bounds[1] + 1)
            ),
        )
        candidates = list(range(target_start, target_end + 1))
        candidates.sort(key=lambda number: (-frequency.get(number, 0), number))
        return tuple(sorted(candidates[:_PICK_COUNT]))


__all__ = ["BigLottoFrontendZoneBalanceAdapter"]
