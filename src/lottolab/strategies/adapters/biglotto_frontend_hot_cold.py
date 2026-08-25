"""Target-native port of the legacy frontend Hot/Cold Mix strategy.

The donor is ``LotteryNewMeraged/src/engine/strategies/HotColdMixStrategy.js``.
Its statistics service ranks the initialized Big Lotto number domain by
frequency, taking the first ten for each of the hot and cold pools. The
strategy emits the first three numbers from each pool as one sorted ticket.
The source response's method and report fields have no counterpart in the
native single-ticket response and are intentionally not invented here.

The production statistics service exposes asynchronous methods at the donor
call site, so a bounded synchronous service stub was used to revive and
execute the donor. This adapter reproduces the source-visible frequency map
from caller-supplied causal history and does not open a database.
"""

from __future__ import annotations

from collections import Counter
from typing import Final

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import BetAdapter, CausalDrawRow

_STRATEGY_ID: Final = "legacy_biglotto__frontend_hot_cold_mix_strategy__92e0540fac02"
_MIN_NUMBER: Final = 1
_MAX_NUMBER: Final = 49
_PICK_COUNT: Final = 6
_POOL_COUNT: Final = 10


class BigLottoFrontendHotColdAdapter(BetAdapter):
    """Reproduce ``HotColdMixStrategy.predict`` for one Big Lotto ticket."""

    strategy_id = _STRATEGY_ID
    strategy_name = "大樂透 Frontend Hot/Cold Mix Strategy"
    strategy_version = "v0.1"
    min_history = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)

    def _predict(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[int, ...]:
        """Select three hot then three cold numbers using source tie order."""

        frequency = Counter(number for row in history for number in row.numbers)

        # StatisticsService initializes every integer-like key from 1 through
        # 49. Object.entries() therefore gives ascending-number order for
        # equal frequencies, which the donor's stable sort preserves.
        hot_pool = sorted(
            range(_MIN_NUMBER, _MAX_NUMBER + 1),
            key=lambda number: (-frequency.get(number, 0), number),
        )[:_POOL_COUNT]
        cold_pool = sorted(
            range(_MIN_NUMBER, _MAX_NUMBER + 1),
            key=lambda number: (frequency.get(number, 0), number),
        )[:_POOL_COUNT]

        hot_count = (_PICK_COUNT + 1) // 2
        selected = [*hot_pool[:hot_count], *cold_pool[: _PICK_COUNT - hot_count]]
        return tuple(sorted(selected))


__all__ = ["BigLottoFrontendHotColdAdapter"]
