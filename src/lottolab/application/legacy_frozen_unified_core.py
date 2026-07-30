"""Pure-Python ports of frozen UnifiedPredictionEngine BIG_LOTTO methods.

Only source-native number selection is reproduced here. Confidence fields,
special-number prediction, logging, caching, and POWER_LOTTO-only global
constraints cannot change the six BIG_LOTTO main numbers and are omitted.
"""

from __future__ import annotations

import math
import random
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Final

from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
    legacy_numpy_argsort,
)
from lottolab.application.strategy_preserving_20_ticket import Ticket

FROZEN_UNIFIED_SOURCE_SHA256: Final = (
    "32d0112c95ce33306002b2f4e13e2c768ff7612c0eb8750cd453cba73575e004"
)
FROZEN_PREDICTION_CONFIG_SHA256: Final = (
    "a269c35fd571720534201592bccc7f1e407fb1e7ad5f6e7451b885b92c035002"
)
FROZEN_CONFIG_LOADER_SHA256: Final = (
    "2becda7a755720ea7ba6ef6f7e9637a99d449d68b81536d12cf2320ec05e28a2"
)

_MIN_NUMBER = 1
_MAX_NUMBER = 49
_PICK_COUNT = 6
_TREND_LAMBDA = 0.01
_DEVIATION_WEIGHTS = {
    "frequency": 0.30,
    "zone": 0.25,
    "odd_even": 0.20,
    "high_low": 0.15,
    "gap": 0.10,
}
_STATISTICAL_PARAMS: Final = {
    "sum_range_mult": 0.4,
    "ac_min_mult": 0.15,
    "ac_max_mult": 0.35,
    "odd_tolerance": 2,
    "spread_mult": 0.4,
    "unique_last_digits_min": 4,
    "weight_power": 0.5,
}


@dataclass(frozen=True, slots=True)
class FrozenUnifiedTickets:
    """The five source methods in their frozen 5ME positional order."""

    statistical: Ticket
    deviation: Ticket
    markov: Ticket
    hot_cold: Ticket
    trend: Ticket
    markov_order: int
    statistical_candidate_count: int

    @property
    def five_me(self) -> tuple[Ticket, ...]:
        return (
            self.statistical,
            self.deviation,
            self.markov,
            self.hot_cold,
            self.trend,
        )

    @property
    def tme(self) -> tuple[Ticket, ...]:
        return (self.statistical, self.deviation, self.markov)


def _ticket(numbers: list[int]) -> Ticket:
    values = tuple(sorted(numbers))
    if (
        len(values) != _PICK_COUNT
        or len(set(values)) != _PICK_COUNT
        or any(
            type(number) is not int
            or not _MIN_NUMBER <= number <= _MAX_NUMBER
            for number in values
        )
    ):
        raise ValueError("FROZEN_UNIFIED_INVALID_TICKET")
    return values


def _numbers(history: tuple[LegacyHistoryDraw, ...]) -> tuple[Ticket, ...]:
    return tuple(draw.numbers for draw in history)


def frozen_trend_ticket(
    history: tuple[LegacyHistoryDraw, ...],
) -> Ticket:
    """Port trend_predict with BIG_LOTTO config and oldest-first history."""

    weighted_frequency: defaultdict[int, float] = defaultdict(float)
    for age, draw in enumerate(reversed(history[-100:])):
        weight = math.exp(-_TREND_LAMBDA * age)
        for number in draw.numbers:
            weighted_frequency[number] += weight
    total_weight = sum(weighted_frequency.values())
    probabilities = [
        (
            weighted_frequency.get(number, 0.0) / total_weight
            if total_weight > 0
            else 0.0
        )
        for number in range(_MIN_NUMBER, _MAX_NUMBER + 1)
    ]
    ranked = sorted(
        range(_MIN_NUMBER, _MAX_NUMBER + 1),
        key=lambda number: probabilities[number - 1],
        reverse=True,
    )
    return _ticket(ranked[:_PICK_COUNT])


def frozen_deviation_ticket(
    history: tuple[LegacyHistoryDraw, ...],
) -> Ticket:
    """Port deviation_predict with its frozen oldest-first gap semantics."""

    total_numbers = _MAX_NUMBER - _MIN_NUMBER + 1
    expected_frequency = len(history) * _PICK_COUNT / total_numbers
    all_numbers = [number for draw in history for number in draw.numbers]
    frequency = Counter(all_numbers)
    sum_squared_difference = sum(
        (frequency.get(number, 0) - expected_frequency) ** 2
        for number in range(_MIN_NUMBER, _MAX_NUMBER + 1)
    )
    standard_deviation = math.sqrt(
        sum_squared_difference / total_numbers
    )
    raw_scores = [0.0] * (_MAX_NUMBER + 1)
    for number in range(_MIN_NUMBER, _MAX_NUMBER + 1):
        z_score = (
            (frequency.get(number, 0) - expected_frequency)
            / standard_deviation
            if standard_deviation > 0
            else 0.0
        )
        if z_score < -1.5:
            raw_scores[number] += 0.8 + abs(z_score) * 0.1
        elif z_score > 2.0:
            raw_scores[number] += 0.2
        elif 0.5 < z_score < 1.5:
            raw_scores[number] += 0.6 + z_score * 0.1
        else:
            raw_scores[number] += 0.4
    maximum = max(raw_scores)
    scores = [
        value
        / (maximum + 1e-10)
        * _DEVIATION_WEIGHTS["frequency"]
        for value in raw_scores
    ]

    zone_size = total_numbers // 5
    zones: dict[int, list[int]] = {}
    for zone_id in range(1, 6):
        start = _MIN_NUMBER + (zone_id - 1) * zone_size
        end = (
            _MAX_NUMBER
            if zone_id == 5
            else _MIN_NUMBER + zone_id * zone_size - 1
        )
        zones[zone_id] = list(range(start, end + 1))
    zone_counts = {zone_id: 0 for zone_id in zones}
    for number in all_numbers:
        for zone_id, zone_numbers in zones.items():
            if number in zone_numbers:
                zone_counts[zone_id] += 1
    for zone_id, zone_numbers in zones.items():
        expected = (
            len(history)
            * _PICK_COUNT
            * len(zone_numbers)
            / total_numbers
        )
        zone_score = max(0.0, expected - zone_counts[zone_id])
        for number in zone_numbers:
            scores[number] += (
                zone_score
                * _DEVIATION_WEIGHTS["zone"]
                / len(zone_numbers)
            )

    odd_count = sum(number % 2 == 1 for number in all_numbers)
    expected_odd = len(all_numbers) / 2
    odd_deviation = expected_odd - odd_count
    for number in range(_MIN_NUMBER, _MAX_NUMBER + 1):
        if number % 2 == 1 and odd_deviation > 0:
            scores[number] += (
                _DEVIATION_WEIGHTS["odd_even"]
                * odd_deviation
                / expected_odd
            )
        elif number % 2 == 0 and odd_deviation < 0:
            scores[number] += (
                _DEVIATION_WEIGHTS["odd_even"]
                * abs(odd_deviation)
                / expected_odd
            )

    midpoint = (_MIN_NUMBER + _MAX_NUMBER) // 2
    small_count = sum(number <= midpoint for number in all_numbers)
    expected_small = len(all_numbers) / 2
    small_deviation = expected_small - small_count
    for number in range(_MIN_NUMBER, _MAX_NUMBER + 1):
        if number <= midpoint and small_deviation > 0:
            scores[number] += (
                _DEVIATION_WEIGHTS["high_low"]
                * small_deviation
                / expected_small
            )
        elif number > midpoint and small_deviation < 0:
            scores[number] += (
                _DEVIATION_WEIGHTS["high_low"]
                * abs(small_deviation)
                / expected_small
            )

    gaps: dict[int, int] = {}
    for number in range(_MIN_NUMBER, _MAX_NUMBER + 1):
        for index, draw in enumerate(history):
            if number in draw.numbers:
                gaps[number] = index
                break
        if number not in gaps:
            gaps[number] = len(history)
    maximum_gap = max(gaps.values()) if gaps else 1
    for number in range(_MIN_NUMBER, _MAX_NUMBER + 1):
        gap_score = (
            gaps.get(number, 0) / maximum_gap
            if maximum_gap > 0
            else 0.0
        )
        scores[number] += gap_score * _DEVIATION_WEIGHTS["gap"]

    ranked = sorted(
        range(_MIN_NUMBER, _MAX_NUMBER + 1),
        key=lambda number: scores[number],
        reverse=True,
    )
    return _ticket(ranked[:_PICK_COUNT])


def _markov_order1(
    draws: tuple[Ticket, ...],
) -> list[float]:
    matrix = [
        [0.1] * (_MAX_NUMBER + 1)
        for _ in range(_MAX_NUMBER + 1)
    ]
    analysis = draws[-100:]
    for index in range(len(analysis) - 1):
        weight = 1.0 + index / len(analysis)
        for current in analysis[index]:
            for following in analysis[index + 1]:
                matrix[current][following] += weight
    for row_index, row in enumerate(matrix):
        row_sum = sum(row)
        matrix[row_index] = [value / row_sum for value in row]
    probabilities = [0.0] * (_MAX_NUMBER + 1)
    for number in draws[-1]:
        row = matrix[number]
        for index, value in enumerate(row):
            probabilities[index] += value
    return probabilities


def _markov_order2(
    draws: tuple[Ticket, ...],
) -> list[float]:
    transitions: dict[
        tuple[int, int], defaultdict[int, float]
    ] = {}
    analysis = draws[-80:]
    for index in range(len(analysis) - 2):
        weight = 1.0 + index / len(analysis)
        for number2 in analysis[index]:
            for number1 in analysis[index + 1]:
                state = (number2, number1)
                counter = transitions.setdefault(
                    state, defaultdict(float)
                )
                for following in analysis[index + 2]:
                    counter[following] += weight
    if len(draws) < 2:
        return _markov_order1(draws)
    probabilities = [0.0] * (_MAX_NUMBER + 1)
    total_weight = 0.0
    for number2 in draws[-2]:
        for number1 in draws[-1]:
            counter = transitions.get((number2, number1))
            if counter is None:
                continue
            for following, count in counter.items():
                probabilities[following] += count
                total_weight += count
    if total_weight <= 0:
        return _markov_order1(draws)
    return [value / total_weight for value in probabilities]


def _markov_order3(
    draws: tuple[Ticket, ...],
) -> list[float]:
    transitions: dict[
        tuple[int, int, int], defaultdict[int, float]
    ] = {}
    analysis = draws[-60:]
    for index in range(len(analysis) - 3):
        weight = 1.0 + index / len(analysis)
        for number3 in analysis[index]:
            for number2 in analysis[index + 1]:
                for number1 in analysis[index + 2]:
                    state = (number3, number2, number1)
                    counter = transitions.setdefault(
                        state, defaultdict(float)
                    )
                    for following in analysis[index + 3]:
                        counter[following] += weight
    if len(draws) < 3:
        return _markov_order2(draws)
    probabilities = [0.0] * (_MAX_NUMBER + 1)
    total_weight = 0.0
    for number3 in draws[-3]:
        for number2 in draws[-2]:
            for number1 in draws[-1]:
                counter = transitions.get((number3, number2, number1))
                if counter is None:
                    continue
                for following, count in counter.items():
                    probabilities[following] += count
                    total_weight += count
    if total_weight <= 0:
        return _markov_order2(draws)
    return [value / total_weight for value in probabilities]


def frozen_markov_ticket(
    history: tuple[LegacyHistoryDraw, ...],
) -> tuple[Ticket, int]:
    """Port adaptive 1/2/3-order markov_predict for oldest-first input."""

    markov_history = history
    if (
        len(history) > 1
        and history[0].draw_number > history[-1].draw_number
    ):
        markov_history = tuple(reversed(history))
    draws = _numbers(markov_history)
    if len(draws) < 50:
        order = 1
        probabilities = _markov_order1(draws)
    elif len(draws) < 150:
        order = 2
        probabilities = _markov_order2(draws)
    else:
        order = 3
        probabilities = _markov_order3(draws)
    for number in draws[-1]:
        probabilities[number] *= 0.3
    probabilities[0] = -1.0
    ranked = list(reversed(legacy_numpy_argsort(probabilities)))
    selected = [
        index
        for index in ranked
        if _MIN_NUMBER <= index <= _MAX_NUMBER
    ][:_PICK_COUNT]
    return _ticket(selected), order


def frozen_hot_cold_ticket(
    history: tuple[LegacyHistoryDraw, ...],
) -> Ticket:
    """Port hot_cold_mix_predict number selection."""

    if len(history) < 15:
        frequency = Counter(
            number for draw in history for number in draw.numbers
        )
        maximum = max(frequency.values()) if frequency else 1
        window_scores = {
            number: frequency.get(number, 0) / maximum
            for number in range(_MIN_NUMBER, _MAX_NUMBER + 1)
        }
    else:
        windows = (15, 25, 45)
        weights = (0.5, 0.3, 0.2)
        by_window: list[dict[int, float]] = []
        for window in windows:
            frequency = Counter(
                number
                for draw in history[-min(window, len(history)) :]
                for number in draw.numbers
            )
            maximum = max(frequency.values()) if frequency else 1
            by_window.append(
                {
                    number: frequency.get(number, 0) / maximum
                    for number in range(_MIN_NUMBER, _MAX_NUMBER + 1)
                }
            )
        window_scores = {
            number: sum(
                scores[number] * weight
                for scores, weight in zip(
                    by_window, weights, strict=True
                )
            )
            for number in range(_MIN_NUMBER, _MAX_NUMBER + 1)
        }

    if len(history) < 30:
        transition_scores = {
            number: 0.0
            for number in range(_MIN_NUMBER, _MAX_NUMBER + 1)
        }
    else:
        frequency1 = Counter(
            number for draw in history[-30:-20] for number in draw.numbers
        )
        frequency2 = Counter(
            number for draw in history[-20:-10] for number in draw.numbers
        )
        frequency3 = Counter(
            number for draw in history[-10:] for number in draw.numbers
        )
        raw = {
            number: max(
                -1.0,
                min(
                    1.0,
                    (
                        frequency3.get(number, 0)
                        - 2 * frequency2.get(number, 0)
                        + frequency1.get(number, 0)
                    )
                    / 10,
                ),
            )
            for number in range(_MIN_NUMBER, _MAX_NUMBER + 1)
        }
        minimum = min(raw.values())
        maximum = max(raw.values())
        value_range = maximum - minimum if maximum > minimum else 1.0
        transition_scores = {
            number: (value - minimum) / value_range
            for number, value in raw.items()
        }

    final_scores = {
        number: window_scores[number] * 0.7
        + transition_scores[number] * 0.3
        for number in range(_MIN_NUMBER, _MAX_NUMBER + 1)
    }
    ranked = sorted(
        final_scores,
        key=lambda number: final_scores[number],
        reverse=True,
    )
    return _ticket(ranked[:_PICK_COUNT])


def frozen_frequency_ticket(
    history: tuple[LegacyHistoryDraw, ...],
) -> Ticket:
    """Port frequency_predict's BIG_LOTTO main-number selection."""

    if not history:
        raise ValueError("FROZEN_FREQUENCY_REQUIRES_HISTORY")
    basic_frequency = Counter(
        number for draw in history for number in draw.numbers
    )
    theoretical_average = (
        len(history) * _PICK_COUNT / (_MAX_NUMBER - _MIN_NUMBER + 1)
    )
    gaps: dict[int, int] = {}
    for number in range(_MIN_NUMBER, _MAX_NUMBER + 1):
        for index, draw in enumerate(history):
            if number in draw.numbers:
                gaps[number] = index
                break
        if number not in gaps:
            gaps[number] = len(history)

    weighted_counts: defaultdict[int, float] = defaultdict(float)
    total_weight = 0.0
    for age, draw in enumerate(reversed(history[-200:])):
        for number in draw.numbers:
            frequency_ratio = (
                basic_frequency.get(number, 0) / theoretical_average
                if theoretical_average
                else 0.0
            )
            if frequency_ratio > 1.3:
                decay_rate = 0.018
            elif frequency_ratio > 1.1:
                decay_rate = 0.013
            elif frequency_ratio < 0.7:
                decay_rate = 0.007
            elif frequency_ratio < 0.9:
                decay_rate = 0.009
            else:
                decay_rate = 0.01
            weight = math.exp(-decay_rate * age)
            weighted_counts[number] += weight
            total_weight += weight

    maximum_gap = max(gaps.values()) if gaps else 1
    average_weight = total_weight / (_MAX_NUMBER - _MIN_NUMBER + 1)
    scores = {
        number: (
            0.4
            * (
                weighted_counts.get(number, 0.0) / average_weight
                if total_weight > 0
                else 0.0
            )
            + 0.6
            * (
                gaps.get(number, 0) / maximum_gap
                if maximum_gap > 0
                else 0.0
            )
        )
        for number in range(_MIN_NUMBER, _MAX_NUMBER + 1)
    }
    ranked = sorted(
        scores,
        key=lambda number: scores[number],
        reverse=True,
    )
    return _ticket(ranked[:_PICK_COUNT])


def _population_stability(
    history: tuple[LegacyHistoryDraw, ...],
) -> float:
    if len(history) < 5:
        return 0.5
    frequencies = list(
        Counter(
            number for draw in history for number in draw.numbers
        ).values()
    )
    if len(frequencies) < 2:
        return 0.5
    mean = sum(frequencies) / len(frequencies)
    if mean == 0:
        return 0.5
    variance = sum(
        (frequency - mean) ** 2 for frequency in frequencies
    ) / len(frequencies)
    return 1 / (1 + math.sqrt(variance) / mean)


def frozen_bayesian_ticket(
    history: tuple[LegacyHistoryDraw, ...],
) -> Ticket:
    """Port bayesian_predict's BIG_LOTTO main-number selection."""

    if not history:
        raise ValueError("FROZEN_BAYESIAN_REQUIRES_HISTORY")
    long_term_frequency = Counter(
        number for draw in history for number in draw.numbers
    )
    recent_history = history[-20:]
    recent_frequency = Counter(
        number for draw in recent_history for number in draw.numbers
    )
    stability = _population_stability(recent_history)
    if len(history) < 50:
        likelihood_weight, prior_weight = 0.75, 0.25
    elif len(history) < 100:
        likelihood_weight, prior_weight = (
            (0.65, 0.35)
            if stability > 0.7
            else (0.55, 0.45)
        )
    else:
        likelihood_weight, prior_weight = (
            (0.6, 0.4)
            if stability > 0.7
            else (0.5, 0.5)
        )
    denominator = len(history) * _PICK_COUNT
    scores: dict[int, float] = {}
    for number in range(_MIN_NUMBER, _MAX_NUMBER + 1):
        prior = long_term_frequency.get(number, 0) / denominator
        if prior == 0:
            prior = 1 / (denominator * 10)
        likelihood = (
            recent_frequency.get(number, 0) / len(recent_history)
        )
        scores[number] = (
            likelihood * likelihood_weight + prior * prior_weight
        )
    ranked = sorted(
        scores,
        key=lambda number: scores[number],
        reverse=True,
    )
    return _ticket(ranked[:_PICK_COUNT])


def frozen_zone_balance_ticket(
    history: tuple[LegacyHistoryDraw, ...],
) -> Ticket:
    """Port zone_balance_predict's BIG_LOTTO main-number selection."""

    frequency = Counter(
        number for draw in history for number in draw.numbers
    )
    ranked_frequency = sorted(
        range(_MIN_NUMBER, _MAX_NUMBER + 1),
        key=lambda number: frequency.get(number, 0),
        reverse=True,
    )
    zone_sizes = (13, 12, 12, 12)
    zones: list[tuple[int, ...]] = []
    offset = 0
    for size in zone_sizes:
        zones.append(tuple(sorted(ranked_frequency[offset : offset + size])))
        offset += size

    zone_counts = [0] * len(zones)
    for draw in history[-min(len(history), 80) :]:
        for number in draw.numbers:
            for index, zone in enumerate(zones):
                if min(zone) <= number <= max(zone):
                    zone_counts[index] += 1
                    break
    recent_zone_counts = [0] * len(zones)
    for draw in history[-20:]:
        for number in draw.numbers:
            for index, zone in enumerate(zones):
                if min(zone) <= number <= max(zone):
                    recent_zone_counts[index] += 1
                    break
    total = sum(zone_counts) or 1
    recent_total = sum(recent_zone_counts) or 1
    targets = [
        round(
            (
                zone_counts[index] / total * 0.7
                + recent_zone_counts[index] / recent_total * 0.3
            )
            * _PICK_COUNT
        )
        for index in range(len(zones))
    ]
    while sum(targets) < _PICK_COUNT:
        targets[targets.index(min(targets))] += 1
    while sum(targets) > _PICK_COUNT:
        targets[targets.index(max(targets))] -= 1

    predicted: list[int] = []
    recent_frequency = Counter(
        number for draw in history[-30:] for number in draw.numbers
    )
    for index, zone in enumerate(zones):
        scored = [
            (
                number,
                frequency.get(number, 0) * 0.6
                + recent_frequency.get(number, 0) * 0.4,
            )
            for number in zone
        ]
        scored.sort(key=lambda item: item[1], reverse=True)
        predicted.extend(
            number for number, _score in scored[: targets[index]]
        )
    return _ticket(predicted)


def _statistical_conditions(numbers: list[int]) -> bool:
    total_numbers = _MAX_NUMBER - _MIN_NUMBER + 1
    total = sum(numbers)
    theoretical_min = (
        _MIN_NUMBER * _PICK_COUNT
        + _PICK_COUNT * (_PICK_COUNT - 1) / 2
    )
    theoretical_max = (
        _MAX_NUMBER * _PICK_COUNT
        - _PICK_COUNT * (_PICK_COUNT - 1) / 2
    )
    ideal_sum = (theoretical_min + theoretical_max) / 2
    sum_range = (
        theoretical_max - theoretical_min
    ) * _STATISTICAL_PARAMS["sum_range_mult"]
    if not (
        ideal_sum - sum_range / 2
        <= total
        <= ideal_sum + sum_range / 2
    ):
        return False
    ordered = sorted(numbers)
    differences = {
        ordered[right] - ordered[left]
        for left in range(len(ordered))
        for right in range(left + 1, len(ordered))
    }
    ac_value = len(differences) - (len(numbers) - 1)
    minimum_ac = max(
        _PICK_COUNT - 1,
        int(total_numbers * _STATISTICAL_PARAMS["ac_min_mult"]),
    )
    maximum_ac = min(
        _PICK_COUNT * (_PICK_COUNT - 1) / 2,
        int(total_numbers * _STATISTICAL_PARAMS["ac_max_mult"]),
    )
    if not minimum_ac <= ac_value <= maximum_ac:
        return False
    odd_count = sum(number % 2 == 1 for number in numbers)
    if abs(odd_count - round(_PICK_COUNT / 2)) > _STATISTICAL_PARAMS[
        "odd_tolerance"
    ]:
        return False
    if max(numbers) - min(numbers) < int(
        total_numbers * _STATISTICAL_PARAMS["spread_mult"]
    ):
        return False
    return (
        len({number % 10 for number in numbers})
        >= _STATISTICAL_PARAMS["unique_last_digits_min"]
    )


def frozen_statistical_ticket(
    history: tuple[LegacyHistoryDraw, ...],
) -> tuple[Ticket, int]:
    """Port statistical_predict including its len(history)-seeded RNG."""

    frequency = Counter(
        number for draw in history for number in draw.numbers
    )
    pool: list[int] = []
    for number in range(_MIN_NUMBER, _MAX_NUMBER + 1):
        weight = int(
            math.pow(
                max(1, frequency.get(number, 0)),
                _STATISTICAL_PARAMS["weight_power"],
            )
            * 10
        )
        pool.extend([number] * weight)
    rng = random.Random(len(history))
    valid: list[list[int]] = []
    for _ in range(2000):
        if len(valid) >= 20:
            break
        combination: set[int] = set()
        while len(combination) < _PICK_COUNT:
            combination.add(rng.choice(pool))
        candidate = list(combination)
        if _statistical_conditions(candidate):
            valid.append(candidate)
    if not valid:
        raise ValueError("FROZEN_STATISTICAL_FREQUENCY_FALLBACK_REQUIRED")
    best = max(
        valid,
        key=lambda candidate: sum(
            frequency.get(number, 0) for number in candidate
        ),
    )
    return _ticket(best), len(valid)


def generate_frozen_unified_tickets(
    history: tuple[LegacyHistoryDraw, ...],
) -> FrozenUnifiedTickets:
    """Generate the five frozen engine tickets once for a causal cutoff."""

    if not history:
        raise ValueError("FROZEN_UNIFIED_REQUIRES_HISTORY")
    statistical, candidate_count = frozen_statistical_ticket(history)
    markov, order = frozen_markov_ticket(history)
    return FrozenUnifiedTickets(
        statistical=statistical,
        deviation=frozen_deviation_ticket(history),
        markov=markov,
        hot_cold=frozen_hot_cold_ticket(history),
        trend=frozen_trend_ticket(history),
        markov_order=order,
        statistical_candidate_count=candidate_count,
    )


__all__ = [
    "FROZEN_CONFIG_LOADER_SHA256",
    "FROZEN_PREDICTION_CONFIG_SHA256",
    "FROZEN_UNIFIED_SOURCE_SHA256",
    "FrozenUnifiedTickets",
    "frozen_bayesian_ticket",
    "frozen_deviation_ticket",
    "frozen_frequency_ticket",
    "frozen_hot_cold_ticket",
    "frozen_markov_ticket",
    "frozen_statistical_ticket",
    "frozen_trend_ticket",
    "frozen_zone_balance_ticket",
    "generate_frozen_unified_tickets",
]
