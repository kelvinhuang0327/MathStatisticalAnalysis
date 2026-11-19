"""Replay the frozen HPSB V2 single-ticket strategy on strictly prior draws."""

from collections import Counter, defaultdict
from functools import lru_cache
from typing import cast

from lottolab.application.legacy_frozen_unified_core import (
    frozen_bayesian_ticket,
    frozen_deviation_ticket,
    frozen_frequency_ticket,
    frozen_markov_ticket,
    frozen_statistical_ticket,
    frozen_trend_ticket,
)
from lottolab.application.legacy_history_native_portfolios import LegacyHistoryDraw
from lottolab.application.strategy_preserving_20_ticket import Ticket
from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import CausalDrawRow, PortfolioBetAdapter
from lottolab.strategies.adapters.biglotto_wave4 import _unified_hot_cold_mix_ticket
from lottolab.strategies.adapters.biglotto_wave14 import _apply_zdp, _unified_repeat_booster_ticket

_AUDIT_WINDOW = 15
_PICK = 6


def _frozen_history(history: tuple[CausalDrawRow, ...]) -> tuple[LegacyHistoryDraw, ...]:
    return tuple(LegacyHistoryDraw(row.draw, cast(Ticket, row.numbers)) for row in history)


def _statistical(history: tuple[LegacyHistoryDraw, ...]) -> Ticket:
    try:
        return frozen_statistical_ticket(history)[0]
    except ValueError as exc:
        if str(exc) != "FROZEN_STATISTICAL_FREQUENCY_FALLBACK_REQUIRED":
            raise
        return frozen_frequency_ticket(history)


@lru_cache(maxsize=_AUDIT_WINDOW + 1)
def _audit_tickets(history: tuple[CausalDrawRow, ...]) -> dict[str, tuple[int, ...]]:
    # Adjacent targets share 15 prefix results. Key by the complete history
    # so a different draw sequence of the same length is evaluated separately.
    frozen = _frozen_history(history)
    return {
        # The donor adds the three window weights left to right. Python 3.13
        # sum() would round tied hot/cold candidates differently.
        "hot_cold_mix": _unified_hot_cold_mix_ticket(history),
        "markov": frozen_markov_ticket(frozen)[0],
        "deviation": frozen_deviation_ticket(frozen),
        "trend": frozen_trend_ticket(frozen),
        "statistical": _statistical(frozen),
    }


def _dms_ticket(history: tuple[CausalDrawRow, ...]) -> tuple[int, ...]:
    wins: Counter[str] = Counter()
    for index in range(len(history) - _AUDIT_WINDOW, len(history)):
        actual = set(history[index].numbers)
        for method, ticket in _audit_tickets(history[:index]).items():
            if len(actual.intersection(ticket)) >= 3:
                wins[method] += 1

    current = _audit_tickets(history)
    # The donor scans each method's entire window before moving to the next
    # method. Ties follow declaration order even when the first hit came later.
    return current[max(current, key=wins.__getitem__)]


def _static_candidates(history: tuple[CausalDrawRow, ...]) -> list[int]:
    frozen = _frozen_history(history)
    weighted_tickets = (
        (_statistical(frozen), 1.5),
        (frozen_markov_ticket(frozen)[0], 2.0),
        (_unified_repeat_booster_ticket(history), 1.2),
        (frozen_bayesian_ticket(frozen), 1.5),
        (_unified_hot_cold_mix_ticket(history), 1.2),
        (frozen_deviation_ticket(frozen), 0.8),
    )
    votes: defaultdict[int, float] = defaultdict(float)
    for ticket, weight in weighted_tickets:
        for rank, number in enumerate(ticket):
            votes[number] += weight * (0.8 + 0.2 * ((_PICK - rank) / _PICK))
    return sorted(votes, key=votes.__getitem__, reverse=True)


class FrozenHpsbOptimizer(PortfolioBetAdapter):
    strategy_id = "legacy_biglotto__hpsb_optimizer__cf5cd7d971e8"
    strategy_version = "legacy-source-49a25effa62f-cf5cd7d971e8"
    strategy_name = "大樂透 HPSB V2"
    min_history = 1
    native_ticket_count = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)

    def _predict_all(
        self, history: tuple[CausalDrawRow, ...], lottery_type: LotteryType
    ) -> tuple[tuple[int, ...], ...]:
        if len(history) < _AUDIT_WINDOW + 5:
            candidates = _static_candidates(history)
        else:
            candidates = list(_dms_ticket(history))
        return (tuple(_apply_zdp(candidates, _PICK)),)
