"""DB-free native port of the legacy BIG_LOTTO Orthogonal 2-Bet donor.

The donor is ``LotteryNewMeraged/lottery_api/models/orthogonal_2bet.py``
(source SHA-256 ``aa51b0e5e4a400c189aa87c4e478f7b5429223ea1ec81dea13ebebe2b1df42f1``).
Its runtime imports NumPy and the unused unified prediction engine, so the
donor was bounded-revived around the pure ``predict`` path before this port.

The donor consumes oldest-first history. It first builds a 30-number elite
pool from long/short frequency and recency-gap scores, then emits two
positional tickets: a weighted-frequency Trend-Master ticket and a disjoint
Gap-Hunter ticket. The legacy stable descending-score sort is intentionally
retained, including source insertion order for equal-score ties.
"""

from __future__ import annotations

from collections import Counter
from typing import ClassVar, Final

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import CausalDrawRow, PortfolioBetAdapter

_STRATEGY_ID: Final = "legacy_biglotto__orthogonal_2bet_optimizer__aa51b0e5e4a4"
_MIN_NUMBER: Final = 1
_MAX_NUMBER: Final = 49
_PICK_COUNT: Final = 6
_ELITE_POOL_SIZE: Final = 30
_TREND_WINDOW: Final = 500
_GAP_WINDOW: Final = 50


def _recency_gaps(history: tuple[CausalDrawRow, ...]) -> dict[int, int]:
    """Return each legal number's distance from the newest visible draw."""

    gaps: dict[int, int] = {}
    for number in range(_MIN_NUMBER, _MAX_NUMBER + 1):
        for index, row in enumerate(reversed(history)):
            if number in row.numbers:
                gaps[number] = index
                break
        if number not in gaps:
            gaps[number] = len(history)
    return gaps


def _elite_pool(history: tuple[CausalDrawRow, ...]) -> tuple[int, ...]:
    """Port ``SmartSelector.select_elite_numbers`` exactly for BIG_LOTTO."""

    long_history = history[-_TREND_WINDOW:] if len(history) > _TREND_WINDOW else history
    short_history = history[-_GAP_WINDOW:] if len(history) > _GAP_WINDOW else history
    long_frequency = Counter(number for row in long_history for number in row.numbers)
    short_frequency = Counter(number for row in short_history for number in row.numbers)
    gaps = _recency_gaps(history)

    max_long_frequency = max(long_frequency.values(), default=1)
    max_short_frequency = max(short_frequency.values(), default=1)
    scores: dict[int, float] = {}
    for number in range(_MIN_NUMBER, _MAX_NUMBER + 1):
        long_score = long_frequency.get(number, 0) / max_long_frequency
        short_score = short_frequency.get(number, 0) / max_short_frequency
        gap = gaps[number]
        if gap > 50:
            gap_score = 0.2
        elif gap > 30:
            gap_score = 0.5
        elif gap > 10:
            gap_score = 1.0
        else:
            gap_score = 0.6
        scores[number] = 0.4 * long_score + 0.3 * short_score + 0.3 * gap_score

    # ``scores`` is populated in ascending number order. Python's stable sort
    # therefore preserves the donor's ascending-number tie-break.
    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    return tuple(sorted(number for number, _score in ranked[:_ELITE_POOL_SIZE]))


def _trend_ticket(
    history: tuple[CausalDrawRow, ...],
    elite_pool: tuple[int, ...],
) -> tuple[int, ...]:
    """Port the donor's weighted long-window Trend-Master ticket."""

    data = history[-_TREND_WINDOW:] if len(history) > _TREND_WINDOW else history
    weighted_scores: dict[int, float] = {}
    for index, row in enumerate(data):
        weight = 1.0 + (index / len(data)) * 0.5
        for number in row.numbers:
            if number in elite_pool:
                weighted_scores[number] = weighted_scores.get(number, 0.0) + weight

    ranked = sorted(weighted_scores.items(), key=lambda item: item[1], reverse=True)
    return tuple(sorted(number for number, _score in ranked[:_PICK_COUNT]))


def _gap_score(gap: int) -> float:
    if 10 <= gap <= 25:
        return 100.0
    if 5 <= gap < 10:
        return 60.0
    if 25 < gap <= 40:
        return 50.0
    return 10.0


def _gap_ticket(
    history: tuple[CausalDrawRow, ...],
    elite_pool: tuple[int, ...],
    excluded: tuple[int, ...],
) -> tuple[int, ...]:
    """Port the donor's short-window Gap-Hunter ticket and exclusion rule."""

    data = history[-_GAP_WINDOW:] if len(history) > _GAP_WINDOW else history
    flat_numbers = tuple(number for row in data for number in row.numbers)
    expected_frequency = len(data) * _PICK_COUNT / _MAX_NUMBER
    gap_scores: dict[int, float] = {}
    excluded_numbers = set(excluded)

    for number in elite_pool:
        if number in excluded_numbers:
            gap_scores[number] = -9999.0
            continue

        gap = len(history)
        for index, row in enumerate(reversed(history)):
            if number in row.numbers:
                gap = index
                break

        score = _gap_score(gap)
        frequency = flat_numbers.count(number)
        if frequency < expected_frequency:
            score += (expected_frequency - frequency) * 20.0
        gap_scores[number] = score

    ranked = sorted(gap_scores.items(), key=lambda item: item[1], reverse=True)
    return tuple(sorted(number for number, _score in ranked[:_PICK_COUNT]))


class BigLottoOrthogonal2BetAdapter(PortfolioBetAdapter):
    """The legacy Trend-Master then disjoint Gap-Hunter two-ticket portfolio."""

    strategy_id: ClassVar[str] = _STRATEGY_ID
    strategy_name: ClassVar[str] = "大樂透 Orthogonal 2-Bet Trend/Gap"
    strategy_version: ClassVar[str] = "v0.1"
    min_history: ClassVar[int] = 1
    supported_lottery_types: ClassVar[tuple[LotteryType, ...]] = (LotteryType.BIG_LOTTO,)
    native_ticket_count: ClassVar[int] = 2

    def _predict_all(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[tuple[int, ...], ...]:
        del lottery_type
        elite_pool = _elite_pool(history)
        trend_ticket = _trend_ticket(history, elite_pool)
        gap_ticket = _gap_ticket(history, elite_pool, trend_ticket)
        return trend_ticket, gap_ticket


__all__ = ["BigLottoOrthogonal2BetAdapter"]
