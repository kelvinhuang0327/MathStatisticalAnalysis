"""Target-native port of the legacy minimal dual-bet producer.

The donor reads newest-first history and uses the newest 100 rows.  The
target adapter contract supplies causal history oldest-first, so this module
reverses the validated rows before applying the donor's index-based window.
The donor's two native main-number tickets, stable frequency ties, 20-number
candidate pools, and three-zone fill order are preserved exactly.  The
producer is deterministic and has no external prediction-time dependency.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import CausalDrawRow, PortfolioBetAdapter

_STRATEGY_ID = "legacy_biglotto__minimal_dual_bet_strategy__3c9657df7ff4"
_HISTORY_WINDOW = 100
_CANDIDATE_POOL_SIZE = 20
_NUMBER_MIN = 1
_NUMBER_MAX = 38
_PICK_COUNT = 6
_ZONES = ((1, 13), (14, 25), (26, 38))


def _select_with_zone_balance(
    candidates: Sequence[int], target: int = _PICK_COUNT
) -> tuple[int, ...]:
    """Apply the donor's two-per-zone selection and ascending fill fallback."""

    selected: list[int] = []
    for start, end in _ZONES:
        zone_candidates = [
            number
            for number in candidates
            if start <= number <= end and number not in selected
        ]
        selected.extend(zone_candidates[:2])

    while len(selected) < target and candidates:
        remaining = [number for number in candidates if number not in selected]
        if not remaining:
            break
        selected.append(remaining[0])

    return tuple(selected[:target])


def _minimal_dual_bets(
    history: tuple[CausalDrawRow, ...],
) -> tuple[tuple[int, ...], tuple[int, ...]]:
    """Return the donor-exact ordered pair of main-number tickets."""

    source_history = tuple(reversed(history))
    recent = source_history[: min(_HISTORY_WINDOW, len(source_history))]
    frequency: Counter[int] = Counter(
        number for row in recent for number in row.numbers
    )

    sorted_numbers = sorted(
        range(_NUMBER_MIN, _NUMBER_MAX + 1),
        key=lambda number: frequency.get(number, 0),
        reverse=True,
    )
    bet1 = _select_with_zone_balance(
        sorted_numbers[:_CANDIDATE_POOL_SIZE]
    )

    remaining = [number for number in sorted_numbers if number not in bet1]
    bet2 = _select_with_zone_balance(
        remaining[:_CANDIDATE_POOL_SIZE]
    )

    return tuple(sorted(bet1)), tuple(sorted(bet2))


class BigLottoMinimalDualBetStrategyAdapter(PortfolioBetAdapter):
    """Deterministic two-ticket port of ``MinimalDualBetStrategy``."""

    strategy_id = _STRATEGY_ID
    strategy_name = "大樂透 Minimal Dual Bet Strategy 2注"
    strategy_version = "v0.1"
    min_history = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)
    native_ticket_count = 2

    def _predict_all(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[tuple[int, ...], ...]:
        return _minimal_dual_bets(history)


__all__ = ["BigLottoMinimalDualBetStrategyAdapter"]
