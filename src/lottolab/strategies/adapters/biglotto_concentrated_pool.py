"""Target-native port of the frozen concentrated-pool predictor.

The donor is ``lottery_api/models/concentrated_pool_predictor.py`` at
``49a25effa62fc24f40789c16be6f11bdfb41a4a9`` (sha256
``a03b9070574950b634376ac944dbc58b503c188f47850a23a2de065a85e7fc8b``).
Its semantics were recovered in
``lottolab.application.legacy_history_native_portfolios_wave2._concentrated_pool``.
This adapter copies that producer into the strategy layer so production
generate does not import application code.

The donor reads newest-first history. The adapter contract supplies
oldest-first causal rows, so the producer reverses them at the edge and
keeps the donor's 50/30/10/100 windows, 28-number pool, zone-balanced first
ticket, and gap-weighted second ticket. The producer is deterministic and
has no prediction-time dependency.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import (
    CausalDrawRow,
    InvalidOutput,
    PortfolioBetAdapter,
)

_STRATEGY_ID = "legacy_biglotto__concentrated_pool_predictor__a03b90705749"
_MIN_NUMBER = 1
_MAX_NUMBER = 49
_PICK_COUNT = 6
_POOL_SIZE = 28
_ZONES = ((1, 10), (11, 20), (21, 30), (31, 40), (41, 49))


@dataclass(slots=True)
class _NumberScore:
    number: int
    frequency_score: float = 0.0
    gap_score: float = 0.0
    zone_score: float = 0.0
    trend_score: float = 0.0
    pair_score: float = 0.0
    total_score: float = 0.0


def _ticket(numbers: list[int]) -> tuple[int, ...]:
    values = tuple(sorted(numbers))
    if (
        len(values) != _PICK_COUNT
        or len(set(values)) != _PICK_COUNT
        or any(not _MIN_NUMBER <= number <= _MAX_NUMBER for number in values)
    ):
        raise InvalidOutput(f"{_STRATEGY_ID}: concentrated-pool ticket is not a legal 6-of-49 set")
    return values


def _concentrated_pool_bets(
    history: tuple[CausalDrawRow, ...],
) -> tuple[tuple[int, ...], tuple[int, ...]]:
    """Return the donor-exact ordered pair of main-number tickets."""

    recent_first = tuple(reversed(history))
    frequency_history = recent_first[:50]
    frequency = Counter(number for draw in frequency_history for number in draw.numbers)
    maximum_frequency = max(frequency.values()) if frequency else 1
    frequency_scores = {
        number: frequency.get(number, 0) / maximum_frequency for number in range(1, 50)
    }

    last_seen = {number: len(recent_first) for number in range(1, 50)}
    for index, draw in enumerate(recent_first):
        for number in draw.numbers:
            if last_seen[number] == len(recent_first):
                last_seen[number] = index
    ideal_gap = 49 / 6
    gap_scores: dict[int, float] = {}
    for number, gap in last_seen.items():
        optimal_low = ideal_gap * 1.2
        optimal_high = ideal_gap * 2.5
        if gap < optimal_low:
            gap_scores[number] = gap / optimal_low * 0.5
        elif gap <= optimal_high:
            gap_scores[number] = 1.0
        else:
            gap_scores[number] = max(
                0.3,
                0.9 ** ((gap - optimal_high) / ideal_gap),
            )

    zone_frequency: defaultdict[int, Counter[int]] = defaultdict(Counter)
    for draw in recent_first[:30]:
        for number in draw.numbers:
            for zone_index, (low, high) in enumerate(_ZONES):
                if low <= number <= high:
                    zone_frequency[zone_index][number] += 1
                    break
    zone_scores: dict[int, float] = {}
    for zone_index, (low, high) in enumerate(_ZONES):
        counter = zone_frequency[zone_index]
        maximum = max(counter.values()) if counter else 1
        for number in range(low, high + 1):
            zone_scores[number] = counter.get(number, 0) / maximum

    short_window = min(10, len(recent_first))
    long_window = min(50, len(recent_first))
    short_frequency = Counter(
        number for draw in recent_first[:short_window] for number in draw.numbers
    )
    long_frequency = Counter(
        number for draw in recent_first[:long_window] for number in draw.numbers
    )
    trend_scores: dict[int, float] = {}
    for number in range(1, 50):
        short_rate = short_frequency.get(number, 0) / short_window
        long_rate = long_frequency.get(number, 0) / long_window
        trend_ratio = (
            short_rate / long_rate if long_rate > 0 else 1.0 if short_rate > 0 else 0.5
        )
        if trend_ratio >= 1.5:
            trend_scores[number] = 1.0
        elif trend_ratio >= 1.0:
            trend_scores[number] = 0.6 + 0.4 * (trend_ratio - 1.0) / 0.5
        elif trend_ratio >= 0.5:
            trend_scores[number] = 0.3 + 0.3 * (trend_ratio - 0.5) / 0.5
        else:
            trend_scores[number] = 0.3 * trend_ratio / 0.5

    pair_count: defaultdict[tuple[int, int], int] = defaultdict(int)
    for draw in recent_first[:100]:
        numbers = draw.numbers
        for index, first in enumerate(numbers):
            for second in numbers[index + 1 :]:
                pair_count[(min(first, second), max(first, second))] += 1
    pair_heat: defaultdict[int, float] = defaultdict(float)
    for (first, second), count in pair_count.items():
        pair_heat[first] += count
        pair_heat[second] += count
    maximum_heat = max(pair_heat.values()) if pair_heat else 1
    pair_scores = {
        number: pair_heat.get(number, 0) / maximum_heat for number in range(1, 50)
    }

    pool: list[_NumberScore] = []
    for number in range(1, 50):
        score = _NumberScore(
            number=number,
            frequency_score=frequency_scores[number],
            gap_score=gap_scores[number],
            zone_score=zone_scores[number],
            trend_score=trend_scores[number],
            pair_score=pair_scores[number],
        )
        score.total_score = (
            0.25 * score.frequency_score
            + 0.20 * score.gap_score
            + 0.15 * score.zone_score
            + 0.25 * score.trend_score
            + 0.15 * score.pair_score
        )
        pool.append(score)
    pool.sort(key=lambda item: -item.total_score)
    pool = pool[:_POOL_SIZE]

    selected: list[int] = []
    zone_counts = [0] * len(_ZONES)
    target_per_zone = _PICK_COUNT / len(_ZONES)
    for score in sorted(pool, key=lambda item: -item.total_score):
        if len(selected) >= _PICK_COUNT:
            break
        zone_index = next(
            (
                index
                for index, (low, high) in enumerate(_ZONES)
                if low <= score.number <= high
            ),
            None,
        )
        if zone_index is not None and zone_counts[zone_index] < target_per_zone + 0.5:
            selected.append(score.number)
            zone_counts[zone_index] += 1
    if len(selected) < _PICK_COUNT:
        remaining = [score.number for score in pool if score.number not in selected]
        selected.extend(remaining[: _PICK_COUNT - len(selected)])
    first_ticket = _ticket(selected[:_PICK_COUNT])
    remaining_pool = [score for score in pool if score.number not in first_ticket]
    if len(remaining_pool) < _PICK_COUNT:
        raise InvalidOutput(f"{_STRATEGY_ID}: concentrated-pool remainder is too small")
    remaining_pool.sort(key=lambda item: -(item.gap_score * 0.6 + item.total_score * 0.4))
    second_ticket = _ticket([score.number for score in remaining_pool[:_PICK_COUNT]])
    return (first_ticket, second_ticket)


class BigLottoConcentratedPoolPredictorAdapter(PortfolioBetAdapter):
    """Deterministic two-ticket port of ``concentrated_pool_predictor``."""

    strategy_id = _STRATEGY_ID
    strategy_name = "大樂透 Concentrated Pool Predictor 2注"
    strategy_version = "v0.1"
    min_history = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)
    native_ticket_count = 2

    def _predict_all(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[tuple[int, ...], ...]:
        return _concentrated_pool_bets(history)


__all__ = ["BigLottoConcentratedPoolPredictorAdapter"]
