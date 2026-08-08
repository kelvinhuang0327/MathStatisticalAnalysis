"""Target-native GameSpec core for exhaustive BIG_LOTTO -> P638 ports.

The frozen BIG_LOTTO donors share a pool/pick-parameterized prediction core.
This module re-expresses that core against the authoritative POWER_LOTTO
first-zone rule contract (1..38, pick 6).  It imports no BIG_LOTTO adapter and
does not compute the POWER_LOTTO second zone; complete-ticket composition stays
owned by :class:`P638StrategySpec` and ``second_zone_predict``.

All random branches preserve a donor-declared seed.  Cache decorators only
memoize pure causal-history functions and cannot change ticket order or values.
"""

from __future__ import annotations

# pyright: reportPrivateUsage=false
import math
import random
import threading
from collections import Counter, defaultdict
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from functools import lru_cache
from typing import Final, cast

from lottolab.domain.lottery_rules import POWER_LOTTO_RULE_CONTRACT
from lottolab.strategies.adapters.biglotto_batch15_cross_lottery_core import (
    DAILY539_GAME,
    TargetGameSpec,
)
from lottolab.strategies.adapters.powerlotto_wave1 import P638HistoryRow


@dataclass(frozen=True, slots=True)
class FirstZoneGameSpec:
    """Validated first-zone bounds used by the portable donor formulas."""

    minimum: int
    maximum: int
    pick_count: int

    def __post_init__(self) -> None:
        if self.minimum < 1 or self.maximum < self.minimum:
            raise ValueError("invalid first-zone bounds")
        if not 1 <= self.pick_count <= self.maximum - self.minimum + 1:
            raise ValueError("invalid first-zone pick count")


POWER_LOTTO_FIRST_ZONE_GAME: Final = FirstZoneGameSpec(
    minimum=POWER_LOTTO_RULE_CONTRACT.main_number_min,
    maximum=POWER_LOTTO_RULE_CONTRACT.main_number_max,
    pick_count=POWER_LOTTO_RULE_CONTRACT.main_number_count,
)

MINIMUM: Final = POWER_LOTTO_FIRST_ZONE_GAME.minimum
MAXIMUM: Final = POWER_LOTTO_FIRST_ZONE_GAME.maximum
PICK_COUNT: Final = POWER_LOTTO_FIRST_ZONE_GAME.pick_count
HIGH_HALF_START: Final = (MINIMUM + MAXIMUM) // 2 + 1

DAILY539_FIRST_ZONE_GAME: Final = FirstZoneGameSpec(
    minimum=DAILY539_GAME.minimum,
    maximum=DAILY539_GAME.maximum,
    pick_count=DAILY539_GAME.pick_count,
)

_GAME_PATCH_LOCK = threading.RLock()


def _clear_cached_core_functions() -> None:
    """Drop cached outputs before changing the active target GameSpec.

    The legacy portable core predates the cross-target runner and its cached
    functions key only on causal history.  Clearing those caches at the
    target boundary prevents a DAILY_539 result from being reused by a
    POWER_LOTTO call (or the reverse) while retaining the existing P638
    default behavior and its performance within one replay.
    """

    for function_name in (
        "bayesian_ticket",
        "deviation_ticket",
        "frequency_ticket",
        "hot_cold_mix_ticket",
        "markov_ticket",
        "statistical_ticket",
        "trend_ticket",
    ):
        function = globals().get(function_name)
        if function is not None and hasattr(function, "cache_clear"):
            function.cache_clear()


@contextmanager
def use_first_zone_game(game: FirstZoneGameSpec | TargetGameSpec) -> Generator[None]:
    """Run the shared portable formulas against one target-native GameSpec.

    The existing P638 adapters import these constants as module-local values,
    so the boundary patches only the already shared core and its thin wave
    wrappers for the duration of one serialized prediction.  The default
    outside this context remains the authoritative P638 6-of-38 contract.
    """

    minimum = game.minimum
    maximum = game.maximum
    pick_count = game.pick_count
    with _GAME_PATCH_LOCK:
        import lottolab.strategies.adapters.powerlotto_wave3 as wave3
        import lottolab.strategies.adapters.powerlotto_wave4 as wave4
        import lottolab.strategies.adapters.powerlotto_wave5 as wave5

        core_values = (MINIMUM, MAXIMUM, PICK_COUNT, HIGH_HALF_START)
        wave3_values = (wave3._MIN_NUM, wave3._POOL, wave3._PICK)
        wave4_values = (wave4.MINIMUM, wave4.MAXIMUM, wave4.PICK_COUNT)
        wave5_values = (wave5.MINIMUM, wave5.MAXIMUM, wave5.PICK_COUNT)
        _clear_cached_core_functions()
        globals().update(
            MINIMUM=minimum,
            MAXIMUM=maximum,
            PICK_COUNT=pick_count,
            HIGH_HALF_START=(minimum + maximum) // 2 + 1,
        )
        wave3._MIN_NUM, wave3._POOL, wave3._PICK = minimum, maximum, pick_count
        wave4.MINIMUM, wave4.MAXIMUM, wave4.PICK_COUNT = minimum, maximum, pick_count
        wave5.MINIMUM, wave5.MAXIMUM, wave5.PICK_COUNT = minimum, maximum, pick_count
        try:
            yield
        finally:
            globals().update(
                MINIMUM=core_values[0],
                MAXIMUM=core_values[1],
                PICK_COUNT=core_values[2],
                HIGH_HALF_START=core_values[3],
            )
            wave3._MIN_NUM, wave3._POOL, wave3._PICK = wave3_values
            wave4.MINIMUM, wave4.MAXIMUM, wave4.PICK_COUNT = wave4_values
            wave5.MINIMUM, wave5.MAXIMUM, wave5.PICK_COUNT = wave5_values
            _clear_cached_core_functions()


_DEVIATION_WEIGHTS: Final = {
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


def ticket(numbers: list[int] | tuple[int, ...]) -> tuple[int, ...]:
    """Validate, sort, and freeze one P638 first-zone ticket."""

    values = tuple(sorted(numbers))
    if (
        len(values) != PICK_COUNT
        or len(set(values)) != PICK_COUNT
        or any(type(number) is not int or not MINIMUM <= number <= MAXIMUM for number in values)
    ):
        raise ValueError("P638_PORTABLE_CORE_INVALID_TICKET")
    return values


def numpy_argsort(values: list[float]) -> list[int]:
    """Frozen NumPy legacy float64 indirect-introsort tie semantics."""

    indices = list(range(len(values)))
    if len(indices) < 2:
        return indices
    stack: list[tuple[int, int, int]] = []
    lower, upper = 0, len(indices) - 1
    depth = (len(indices).bit_length() - 1) * 2
    while True:
        if depth < 0:
            raise AssertionError("unexpected introsort heap fallback")
        while upper - lower > 15:
            middle = lower + ((upper - lower) >> 1)
            if values[indices[middle]] < values[indices[lower]]:
                indices[middle], indices[lower] = indices[lower], indices[middle]
            if values[indices[upper]] < values[indices[middle]]:
                indices[upper], indices[middle] = indices[middle], indices[upper]
            if values[indices[middle]] < values[indices[lower]]:
                indices[middle], indices[lower] = indices[lower], indices[middle]
            pivot = values[indices[middle]]
            left, right = lower, upper - 1
            indices[middle], indices[right] = indices[right], indices[middle]
            while True:
                left += 1
                while values[indices[left]] < pivot:
                    left += 1
                right -= 1
                while pivot < values[indices[right]]:
                    right -= 1
                if left >= right:
                    break
                indices[left], indices[right] = indices[right], indices[left]
            indices[left], indices[upper - 1] = indices[upper - 1], indices[left]
            depth -= 1
            if left - lower < upper - left:
                stack.append((left + 1, upper, depth))
                upper = left - 1
            else:
                stack.append((lower, left - 1, depth))
                lower = left + 1
        for position in range(lower + 1, upper + 1):
            value_index = indices[position]
            cursor = position
            previous = position - 1
            while cursor > lower and values[value_index] < values[indices[previous]]:
                indices[cursor] = indices[previous]
                cursor -= 1
                previous -= 1
            indices[cursor] = value_index
        if not stack:
            return indices
        lower, upper, depth = stack.pop()


@lru_cache(maxsize=4096)
def deviation_ticket(history: tuple[P638HistoryRow, ...]) -> tuple[int, ...]:
    """UnifiedPredictionEngine.deviation_predict with the P638 GameSpec."""

    total_numbers = MAXIMUM - MINIMUM + 1
    expected_frequency = len(history) * PICK_COUNT / total_numbers
    all_numbers = [number for draw in history for number in draw.numbers]
    frequency = Counter(all_numbers)
    squared = sum(
        (frequency.get(number, 0) - expected_frequency) ** 2
        for number in range(MINIMUM, MAXIMUM + 1)
    )
    standard_deviation = math.sqrt(squared / total_numbers)
    raw_scores = [0.0] * (MAXIMUM + 1)
    for number in range(MINIMUM, MAXIMUM + 1):
        z_score = (
            (frequency.get(number, 0) - expected_frequency) / standard_deviation
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
    maximum_score = max(raw_scores)
    scores = [
        value / (maximum_score + 1e-10) * _DEVIATION_WEIGHTS["frequency"] for value in raw_scores
    ]

    zone_size = total_numbers // 5
    zones: dict[int, list[int]] = {}
    for zone_id in range(1, 6):
        start = MINIMUM + (zone_id - 1) * zone_size
        end = MAXIMUM if zone_id == 5 else MINIMUM + zone_id * zone_size - 1
        zones[zone_id] = list(range(start, end + 1))
    zone_counts = {zone_id: 0 for zone_id in zones}
    for number in all_numbers:
        for zone_id, zone_numbers in zones.items():
            if number in zone_numbers:
                zone_counts[zone_id] += 1
    for zone_id, zone_numbers in zones.items():
        expected = len(history) * PICK_COUNT * len(zone_numbers) / total_numbers
        zone_score = max(0.0, expected - zone_counts[zone_id])
        for number in zone_numbers:
            scores[number] += zone_score * _DEVIATION_WEIGHTS["zone"] / len(zone_numbers)

    odd_count = sum(number % 2 == 1 for number in all_numbers)
    expected_odd = len(all_numbers) / 2
    odd_deviation = expected_odd - odd_count
    midpoint = (MINIMUM + MAXIMUM) // 2
    small_count = sum(number <= midpoint for number in all_numbers)
    expected_small = len(all_numbers) / 2
    small_deviation = expected_small - small_count
    for number in range(MINIMUM, MAXIMUM + 1):
        if expected_odd and number % 2 == 1 and odd_deviation > 0:
            scores[number] += _DEVIATION_WEIGHTS["odd_even"] * odd_deviation / expected_odd
        elif expected_odd and number % 2 == 0 and odd_deviation < 0:
            scores[number] += _DEVIATION_WEIGHTS["odd_even"] * abs(odd_deviation) / expected_odd
        if expected_small and number <= midpoint and small_deviation > 0:
            scores[number] += _DEVIATION_WEIGHTS["high_low"] * small_deviation / expected_small
        elif expected_small and number > midpoint and small_deviation < 0:
            scores[number] += _DEVIATION_WEIGHTS["high_low"] * abs(small_deviation) / expected_small

    gaps: dict[int, int] = {}
    for number in range(MINIMUM, MAXIMUM + 1):
        for index, draw in enumerate(history):
            if number in draw.numbers:
                gaps[number] = index
                break
        else:
            gaps[number] = len(history)
    maximum_gap = max(gaps.values()) if gaps else 1
    for number in range(MINIMUM, MAXIMUM + 1):
        scores[number] += (
            gaps[number] / maximum_gap * _DEVIATION_WEIGHTS["gap"] if maximum_gap > 0 else 0.0
        )
    ranked = sorted(range(MINIMUM, MAXIMUM + 1), key=lambda number: scores[number], reverse=True)
    return ticket(ranked[:PICK_COUNT])


def _markov_order1(draws: tuple[tuple[int, ...], ...]) -> list[float]:
    matrix = [[0.1] * (MAXIMUM + 1) for _ in range(MAXIMUM + 1)]
    analysis = draws[-100:]
    for index in range(len(analysis) - 1):
        weight = 1.0 + index / len(analysis)
        for current in analysis[index]:
            for following in analysis[index + 1]:
                matrix[current][following] += weight
    for row_index, row in enumerate(matrix):
        row_sum = sum(row)
        matrix[row_index] = [value / row_sum for value in row]
    probabilities = [0.0] * (MAXIMUM + 1)
    for number in draws[-1]:
        for index, value in enumerate(matrix[number]):
            probabilities[index] += value
    return probabilities


def _markov_order2(draws: tuple[tuple[int, ...], ...]) -> list[float]:
    transitions: dict[tuple[int, int], defaultdict[int, float]] = {}
    analysis = draws[-80:]
    for index in range(len(analysis) - 2):
        weight = 1.0 + index / len(analysis)
        for number2 in analysis[index]:
            for number1 in analysis[index + 1]:
                counter = transitions.setdefault((number2, number1), defaultdict(float))
                for following in analysis[index + 2]:
                    counter[following] += weight
    if len(draws) < 2:
        return _markov_order1(draws)
    probabilities = [0.0] * (MAXIMUM + 1)
    total_weight = 0.0
    for number2 in draws[-2]:
        for number1 in draws[-1]:
            counter = transitions.get((number2, number1))
            if counter is not None:
                for following, count in counter.items():
                    probabilities[following] += count
                    total_weight += count
    return (
        [value / total_weight for value in probabilities]
        if total_weight > 0
        else _markov_order1(draws)
    )


def _markov_order3(draws: tuple[tuple[int, ...], ...]) -> list[float]:
    transitions: dict[tuple[int, int, int], defaultdict[int, float]] = {}
    analysis = draws[-60:]
    for index in range(len(analysis) - 3):
        weight = 1.0 + index / len(analysis)
        for number3 in analysis[index]:
            for number2 in analysis[index + 1]:
                for number1 in analysis[index + 2]:
                    counter = transitions.setdefault(
                        (number3, number2, number1), defaultdict(float)
                    )
                    for following in analysis[index + 3]:
                        counter[following] += weight
    if len(draws) < 3:
        return _markov_order2(draws)
    probabilities = [0.0] * (MAXIMUM + 1)
    total_weight = 0.0
    for number3 in draws[-3]:
        for number2 in draws[-2]:
            for number1 in draws[-1]:
                counter = transitions.get((number3, number2, number1))
                if counter is not None:
                    for following, count in counter.items():
                        probabilities[following] += count
                        total_weight += count
    return (
        [value / total_weight for value in probabilities]
        if total_weight > 0
        else _markov_order2(draws)
    )


@lru_cache(maxsize=4096)
def markov_ticket(history: tuple[P638HistoryRow, ...]) -> tuple[int, ...]:
    """Adaptive Unified order-1/2/3 Markov ticket with donor argsort."""

    draws = tuple(draw.numbers for draw in history)
    if not draws:
        raise ValueError("FROZEN_MARKOV_REQUIRES_HISTORY")
    if len(draws) < 50:
        probabilities = _markov_order1(draws)
    elif len(draws) < 150:
        probabilities = _markov_order2(draws)
    else:
        probabilities = _markov_order3(draws)
    for number in draws[-1]:
        probabilities[number] *= 0.3
    probabilities[0] = -1.0
    ranked = list(reversed(numpy_argsort(probabilities)))
    return ticket([number for number in ranked if MINIMUM <= number <= MAXIMUM][:PICK_COUNT])


def _statistical_conditions(numbers: list[int]) -> bool:
    total_numbers = MAXIMUM - MINIMUM + 1
    total = sum(numbers)
    theoretical_min = MINIMUM * PICK_COUNT + PICK_COUNT * (PICK_COUNT - 1) / 2
    theoretical_max = MAXIMUM * PICK_COUNT - PICK_COUNT * (PICK_COUNT - 1) / 2
    ideal_sum = (theoretical_min + theoretical_max) / 2
    sum_range = (theoretical_max - theoretical_min) * _STATISTICAL_PARAMS["sum_range_mult"]
    if not ideal_sum - sum_range / 2 <= total <= ideal_sum + sum_range / 2:
        return False
    ordered = sorted(numbers)
    differences = {
        ordered[right] - ordered[left]
        for left in range(len(ordered))
        for right in range(left + 1, len(ordered))
    }
    ac_value = len(differences) - (len(numbers) - 1)
    minimum_ac = max(PICK_COUNT - 1, int(total_numbers * _STATISTICAL_PARAMS["ac_min_mult"]))
    maximum_ac = min(
        PICK_COUNT * (PICK_COUNT - 1) / 2,
        int(total_numbers * _STATISTICAL_PARAMS["ac_max_mult"]),
    )
    odd_count = sum(number % 2 == 1 for number in numbers)
    return (
        minimum_ac <= ac_value <= maximum_ac
        and abs(odd_count - round(PICK_COUNT / 2)) <= _STATISTICAL_PARAMS["odd_tolerance"]
        and max(numbers) - min(numbers) >= int(total_numbers * _STATISTICAL_PARAMS["spread_mult"])
        and len({number % 10 for number in numbers})
        >= _STATISTICAL_PARAMS["unique_last_digits_min"]
    )


@lru_cache(maxsize=4096)
def statistical_ticket(history: tuple[P638HistoryRow, ...]) -> tuple[int, ...]:
    """Seeded Unified statistical candidate search under P638 bounds."""

    frequency = Counter(number for draw in history for number in draw.numbers)
    pool: list[int] = []
    for number in range(MINIMUM, MAXIMUM + 1):
        weight = int(
            math.pow(max(1, frequency.get(number, 0)), _STATISTICAL_PARAMS["weight_power"]) * 10
        )
        pool.extend([number] * weight)
    rng = random.Random(len(history))
    valid: list[list[int]] = []
    for _ in range(2000):
        if len(valid) >= 20:
            break
        combination: set[int] = set()
        while len(combination) < PICK_COUNT:
            combination.add(rng.choice(pool))
        candidate = list(combination)
        if _statistical_conditions(candidate):
            valid.append(candidate)
    if not valid:
        raise ValueError("FROZEN_STATISTICAL_FREQUENCY_FALLBACK_REQUIRED")
    best = max(valid, key=lambda row: sum(frequency.get(number, 0) for number in row))
    return ticket(best)


def _population_stability(history: tuple[P638HistoryRow, ...]) -> float:
    if len(history) < 5:
        return 0.5
    frequencies = list(Counter(number for draw in history for number in draw.numbers).values())
    if len(frequencies) < 2:
        return 0.5
    mean = sum(frequencies) / len(frequencies)
    if mean == 0:
        return 0.5
    variance = sum((value - mean) ** 2 for value in frequencies) / len(frequencies)
    return 1 / (1 + math.sqrt(variance) / mean)


@lru_cache(maxsize=4096)
def bayesian_ticket(history: tuple[P638HistoryRow, ...]) -> tuple[int, ...]:
    if not history:
        raise ValueError("FROZEN_BAYESIAN_REQUIRES_HISTORY")
    long_term = Counter(number for draw in history for number in draw.numbers)
    recent = history[-20:]
    recent_frequency = Counter(number for draw in recent for number in draw.numbers)
    stability = _population_stability(recent)
    if len(history) < 50:
        likelihood_weight, prior_weight = 0.75, 0.25
    elif len(history) < 100:
        likelihood_weight, prior_weight = (0.65, 0.35) if stability > 0.7 else (0.55, 0.45)
    else:
        likelihood_weight, prior_weight = (0.6, 0.4) if stability > 0.7 else (0.5, 0.5)
    denominator = len(history) * PICK_COUNT
    scores: dict[int, float] = {}
    for number in range(MINIMUM, MAXIMUM + 1):
        prior = long_term.get(number, 0) / denominator
        if prior == 0:
            prior = 1 / (denominator * 10)
        likelihood = recent_frequency.get(number, 0) / len(recent)
        scores[number] = likelihood * likelihood_weight + prior * prior_weight
    return ticket(sorted(scores, key=lambda number: scores[number], reverse=True)[:PICK_COUNT])


@lru_cache(maxsize=4096)
def frequency_ticket(history: tuple[P638HistoryRow, ...]) -> tuple[int, ...]:
    if not history:
        raise ValueError("FROZEN_FREQUENCY_REQUIRES_HISTORY")
    basic = Counter(number for draw in history for number in draw.numbers)
    theoretical = len(history) * PICK_COUNT / (MAXIMUM - MINIMUM + 1)
    gaps: dict[int, int] = {}
    for number in range(MINIMUM, MAXIMUM + 1):
        for index, draw in enumerate(history):
            if number in draw.numbers:
                gaps[number] = index
                break
        else:
            gaps[number] = len(history)
    weighted: defaultdict[int, float] = defaultdict(float)
    total_weight = 0.0
    for age, draw in enumerate(reversed(history[-200:])):
        for number in draw.numbers:
            ratio = basic.get(number, 0) / theoretical if theoretical else 0.0
            if ratio > 1.3:
                decay = 0.018
            elif ratio > 1.1:
                decay = 0.013
            elif ratio < 0.7:
                decay = 0.007
            elif ratio < 0.9:
                decay = 0.009
            else:
                decay = 0.01
            weight = math.exp(-decay * age)
            weighted[number] += weight
            total_weight += weight
    maximum_gap = max(gaps.values()) if gaps else 1
    average_weight = total_weight / (MAXIMUM - MINIMUM + 1)
    scores = {
        number: 0.4 * (weighted.get(number, 0.0) / average_weight if total_weight > 0 else 0.0)
        + 0.6 * (gaps[number] / maximum_gap if maximum_gap > 0 else 0.0)
        for number in range(MINIMUM, MAXIMUM + 1)
    }
    return ticket(sorted(scores, key=lambda number: scores[number], reverse=True)[:PICK_COUNT])


@lru_cache(maxsize=4096)
def hot_cold_mix_ticket(history: tuple[P638HistoryRow, ...]) -> tuple[int, ...]:
    if len(history) < 15:
        frequency = Counter(number for draw in history for number in draw.numbers)
        maximum = max(frequency.values()) if frequency else 1
        window_scores = {
            number: frequency.get(number, 0) / maximum for number in range(MINIMUM, MAXIMUM + 1)
        }
    else:
        window_scores_by_name: dict[str, dict[int, float]] = {}
        for name, size in (("short", 15), ("mid", 25), ("long", 45)):
            recent = history[-min(size, len(history)) :]
            frequency = Counter(number for draw in recent for number in draw.numbers)
            maximum = max(frequency.values()) if frequency else 1
            window_scores_by_name[name] = {
                number: frequency.get(number, 0) / maximum for number in range(MINIMUM, MAXIMUM + 1)
            }
        window_scores = {
            number: window_scores_by_name["short"][number] * 0.5
            + window_scores_by_name["mid"][number] * 0.3
            + window_scores_by_name["long"][number] * 0.2
            for number in range(MINIMUM, MAXIMUM + 1)
        }
    if len(history) < 30:
        transitions = dict.fromkeys(range(MINIMUM, MAXIMUM + 1), 0.0)
    else:
        periods = (history[-30:-20], history[-20:-10], history[-10:])
        frequencies = [
            Counter(number for draw in period for number in draw.numbers) for period in periods
        ]
        raw = {
            number: max(
                -1.0,
                min(
                    1.0,
                    (
                        (frequencies[2].get(number, 0) - frequencies[1].get(number, 0))
                        - (frequencies[1].get(number, 0) - frequencies[0].get(number, 0))
                    )
                    / 10,
                ),
            )
            for number in range(MINIMUM, MAXIMUM + 1)
        }
        low, high = min(raw.values()), max(raw.values())
        span = high - low if high > low else 1
        transitions = {number: (score - low) / span for number, score in raw.items()}
    final = {
        number: window_scores[number] * 0.7 + transitions[number] * 0.3
        for number in range(MINIMUM, MAXIMUM + 1)
    }
    return ticket(sorted(final, key=lambda number: final[number], reverse=True)[:PICK_COUNT])


@dataclass(frozen=True, slots=True)
class _Zone:
    start: int
    end: int
    numbers: tuple[int, ...]


@lru_cache(maxsize=4096)
def zone_balance_ticket(history: tuple[P638HistoryRow, ...]) -> tuple[int, ...]:
    frequency = Counter(number for draw in history for number in draw.numbers)
    pairs = [(number, frequency.get(number, 0)) for number in range(MINIMUM, MAXIMUM + 1)]
    sorted_pairs = sorted(pairs, key=lambda pair: pair[1], reverse=True)
    zone_count = 4
    zone_size, remainder = divmod(len(sorted_pairs), zone_count)
    zones: list[_Zone] = []
    offset = 0
    for index in range(zone_count):
        size = zone_size + (1 if index < remainder else 0)
        numbers = tuple(sorted(pair[0] for pair in sorted_pairs[offset : offset + size]))
        if numbers:
            zones.append(_Zone(min(numbers), max(numbers), numbers))
        offset += size
    zone_counts = [0] * len(zones)
    for draw in history[-min(len(history), 80) :]:
        for number in draw.numbers:
            for index, zone in enumerate(zones):
                if zone.start <= number <= zone.end:
                    zone_counts[index] += 1
                    break
    recent_counts = [0] * len(zones)
    for draw in history[-20:]:
        for number in draw.numbers:
            for index, zone in enumerate(zones):
                if zone.start <= number <= zone.end:
                    recent_counts[index] += 1
                    break
    total, recent_total = sum(zone_counts) or 1, sum(recent_counts) or 1
    targets = [
        round(
            (zone_counts[index] / total * 0.7 + recent_counts[index] / recent_total * 0.3)
            * PICK_COUNT
        )
        for index in range(len(zones))
    ]
    while sum(targets) < PICK_COUNT:
        targets[targets.index(min(targets))] += 1
    while sum(targets) > PICK_COUNT:
        targets[targets.index(max(targets))] -= 1
    recent_frequency = Counter(number for draw in history[-30:] for number in draw.numbers)
    predicted: list[int] = []
    for index, zone in enumerate(zones):
        scored = [
            (number, frequency.get(number, 0) * 0.6 + recent_frequency.get(number, 0) * 0.4)
            for number in zone.numbers
        ]
        scored.sort(key=lambda item: item[1], reverse=True)
        predicted.extend(number for number, _score in scored[: targets[index]])
    return ticket(predicted)


@lru_cache(maxsize=4096)
def trend_ticket(history: tuple[P638HistoryRow, ...]) -> tuple[int, ...]:
    weighted: defaultdict[int, float] = defaultdict(float)
    for age, draw in enumerate(reversed(history[-100:])):
        weight = math.exp(-0.01 * age)
        for number in draw.numbers:
            weighted[number] += weight
    total = sum(weighted.values())
    probabilities = {
        number: weighted.get(number, 0.0) / total if total > 0 else 0.0
        for number in range(MINIMUM, MAXIMUM + 1)
    }
    ranked = sorted(
        probabilities,
        key=lambda number: probabilities[number],
        reverse=True,
    )
    return ticket(ranked[:PICK_COUNT])


def high_prize_trend_ticket(
    history: tuple[P638HistoryRow, ...], lambda_value: float
) -> tuple[int, ...]:
    weighted: dict[int, float] = {}
    for age, draw in enumerate(reversed(history)):
        weight = math.exp(-lambda_value * age)
        for number in draw.numbers:
            weighted[number] = weighted.get(number, 0.0) + weight
    total = sum(weighted.values())
    ranked = sorted(
        range(MINIMUM, MAXIMUM + 1),
        key=lambda number: weighted.get(number, 0.0) / total,
        reverse=True,
    )
    return ticket(ranked[:PICK_COUNT])


@lru_cache(maxsize=4096)
def kill_numbers(history: tuple[P638HistoryRow, ...], count: int = 10) -> tuple[int, ...]:
    if len(history) < 30:
        return ()
    zone_size = MAXIMUM / 5
    zone_counts = [0] * 5
    for draw in history[-30:]:
        for number in draw.numbers:
            zone_counts[min(int((number - 1) / zone_size), 4)] += 1
    total = sum(zone_counts)
    entropy = -sum((value / total) * math.log2(value / total) for value in zone_counts if value)
    if entropy < 2.0:
        dynamic_count = min(15, count + 2)
    elif entropy > 2.2:
        dynamic_count = max(5, count - 5)
    else:
        dynamic_count = count
    frequency = Counter(number for draw in history[-100:] for number in draw.numbers)
    gaps = dict.fromkeys(range(MINIMUM, MAXIMUM + 1), 999)
    for index, draw in enumerate(reversed(history)):
        for number in draw.numbers:
            if gaps[number] == 999:
                gaps[number] = index
    scores = [
        (number, float(frequency.get(number, 0) + (100 if gaps[number] > 22 else 0)))
        for number in range(MINIMUM, MAXIMUM + 1)
    ]
    scores.sort(key=lambda item: item[1])
    return tuple(sorted(number for number, _score in scores[:dynamic_count]))


def weighted_candidates(
    specifications: tuple[tuple[tuple[int, ...], float], ...],
    *,
    limit: int,
    excluded: tuple[int, ...] = (),
) -> list[int]:
    """Frozen weighted-Counter aggregation shared by portfolio wrappers."""

    scores: Counter[int] = Counter()
    for row, weight in specifications:
        for number in row:
            scores[number] += cast(int, weight)
    for number in excluded:
        scores[number] = -9999
    return [number for number, _score in scores.most_common(limit)]


@lru_cache(maxsize=4096)
def optimized_ensemble_ticket(history: tuple[P638HistoryRow, ...]) -> tuple[int, ...]:
    if len(history) < 20:
        return ticket(list(range(MINIMUM, MINIMUM + PICK_COUNT)))
    recent = history[-5:]
    momentum = dict.fromkeys(range(MINIMUM, MAXIMUM + 1), 0.0)
    for index, draw in enumerate(recent):
        weight = math.exp(index / 5)
        for number in draw.numbers:
            momentum[number] += weight
    for number in history[-1].numbers:
        momentum[number] *= 1.2
    window = history[-150:]
    frequency = Counter(number for draw in window for number in draw.numbers)
    target_frequency = len(window) * PICK_COUNT / MAXIMUM
    entropy = {
        number: 1.0 / (abs(frequency.get(number, 0) - target_frequency) + 0.1)
        for number in range(MINIMUM, MAXIMUM + 1)
    }
    last_seen = dict.fromkeys(range(MINIMUM, MAXIMUM + 1), -1)
    for index, draw in enumerate(history):
        for number in draw.numbers:
            last_seen[number] = index
    lag = {}
    for number in range(MINIMUM, MAXIMUM + 1):
        distance = len(history) - last_seen[number]
        lag[number] = 1.5 if 6 <= distance <= 12 else (1.25 if distance > 25 else 1.0)
    scores = [0.0] * (MAXIMUM + 1)
    for number in range(MINIMUM, MAXIMUM + 1):
        scores[number] = momentum[number] * 0.4 + entropy[number] * 40.0 * 0.3 + lag[number] * 0.2
    ranked = [index + 1 for index in reversed(numpy_argsort(scores[1:]))]
    return ticket(ranked[:PICK_COUNT])


@lru_cache(maxsize=4096)
def repeat_booster_ticket(history: tuple[P638HistoryRow, ...]) -> tuple[int, ...]:
    if not history:
        raise ValueError("FROZEN_REPEAT_BOOSTER_REQUIRES_HISTORY")
    last_1 = set(history[0].numbers)
    last_2: set[int] = set(history[1].numbers) if len(history) > 1 else set()
    scores: defaultdict[int, float] = defaultdict(float)
    for number in last_1:
        scores[number] += 1.5
    for number in last_2:
        if number not in last_1:
            scores[number] += 1.0
    frequency = Counter(number for draw in history[:50] for number in draw.numbers)
    for number in scores:
        scores[number] *= 1 + frequency.get(number, 0) / 10.0
    predicted = [
        number for number, _score in sorted(scores.items(), key=lambda item: -item[1])[:PICK_COUNT]
    ]
    if len(predicted) < PICK_COUNT:
        predicted.extend(
            number for number, _count in frequency.most_common(20) if number not in predicted
        )
    return ticket(predicted[:PICK_COUNT])


def echo_scores(history: tuple[P638HistoryRow, ...], max_lag: int = 5) -> dict[int, float]:
    if len(history) < max_lag + 1:
        return {}
    latest = set(history[-1].numbers)
    scores: dict[int, float] = {}
    for lag in range(1, max_lag + 1):
        past = set(history[-(lag + 1)].numbers)
        overlap = latest & past
        if len(overlap) >= 2:
            weight = len(overlap) / PICK_COUNT / lag
            for number in overlap:
                scores[number] = scores.get(number, 0.0) + weight * 0.5
            for number in past - latest:
                scores[number] = scores.get(number, 0.0) + weight
    if scores:
        maximum = max(scores.values())
        if maximum > 0:
            scores = {number: value / maximum for number, value in scores.items()}
    return scores


def continuous_temperature(
    history: tuple[P638HistoryRow, ...], window: int = 50
) -> dict[int, float]:
    recent = history[-window:] if len(history) > window else history
    short_window = min(20, len(recent))
    short_recent = history[-short_window:] if len(history) > short_window else history
    long_frequency = Counter(number for draw in recent for number in draw.numbers)
    short_frequency = Counter(number for draw in short_recent for number in draw.numbers)
    gaps: dict[int, int] = {}
    for number in range(MINIMUM, MAXIMUM + 1):
        gap = 0
        for draw in reversed(history):
            if number in draw.numbers:
                break
            gap += 1
        gaps[number] = gap
    sorted_frequencies = sorted(
        long_frequency.get(number, 0) for number in range(MINIMUM, MAXIMUM + 1)
    )
    temperatures: dict[int, float] = {}
    for number in range(MINIMUM, MAXIMUM + 1):
        value = long_frequency.get(number, 0)
        frequency_component = (
            sum(1 for candidate in sorted_frequencies if candidate <= value) / MAXIMUM
        )
        gap_component = math.exp(-gaps[number] / (MAXIMUM / PICK_COUNT))
        expected_short = short_window * PICK_COUNT / MAXIMUM
        expected_long = len(recent) * PICK_COUNT / MAXIMUM
        short_ratio = short_frequency.get(number, 0) / max(expected_short, 0.1)
        long_ratio = value / max(expected_long, 0.1)
        trend_component = min(1.0, max(0.0, 0.5 + (short_ratio - long_ratio) * 0.5))
        temperatures[number] = (
            frequency_component * 0.40 + gap_component * 0.30 + trend_component * 0.30
        )
    return temperatures


__all__ = [
    "DAILY539_FIRST_ZONE_GAME",
    "HIGH_HALF_START",
    "MAXIMUM",
    "MINIMUM",
    "PICK_COUNT",
    "POWER_LOTTO_FIRST_ZONE_GAME",
    "FirstZoneGameSpec",
    "bayesian_ticket",
    "continuous_temperature",
    "deviation_ticket",
    "echo_scores",
    "frequency_ticket",
    "high_prize_trend_ticket",
    "hot_cold_mix_ticket",
    "kill_numbers",
    "markov_ticket",
    "numpy_argsort",
    "optimized_ensemble_ticket",
    "repeat_booster_ticket",
    "statistical_ticket",
    "ticket",
    "trend_ticket",
    "use_first_zone_game",
    "weighted_candidates",
    "zone_balance_ticket",
]
