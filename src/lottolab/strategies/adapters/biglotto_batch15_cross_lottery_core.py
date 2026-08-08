"""Pure target-game ports of the nine BigLotto Batch-15 producers.

The native Batch-15 module is intentionally bound to BIG_LOTTO's 6-of-49
contract.  This module keeps the same donor control flow while taking the
target pool and pick count from a small immutable game specification.  The
two target wrappers use only the resulting number tuples; they own their
respective history validation and, for POWER_LOTTO, second-zone composition.

No donor adapter is imported here.  Every function is a pure function of the
causal number history and the target game specification.  The seeded
statistical search uses only the history length as its donor-declared seed.
"""

from __future__ import annotations

import math
import random
from collections import Counter, defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from typing import Final, cast

from lottolab.domain.draws import LotteryType


@dataclass(frozen=True, slots=True)
class TargetGameSpec:
    """The target first-zone contract used by one portable producer set."""

    lottery_type: LotteryType
    maximum: int
    pick_count: int

    def __post_init__(self) -> None:
        if self.maximum < 1 or not 1 <= self.pick_count <= self.maximum:
            raise ValueError("invalid target game specification")

    @property
    def minimum(self) -> int:
        return 1

    @property
    def midpoint(self) -> int:
        return (self.minimum + self.maximum) // 2


DAILY539_GAME: Final = TargetGameSpec(
    lottery_type=LotteryType.DAILY_539,
    maximum=39,
    pick_count=5,
)
POWERLOTTO_GAME: Final = TargetGameSpec(
    lottery_type=LotteryType.POWER_LOTTO,
    maximum=38,
    pick_count=6,
)

type NumberHistory = tuple[tuple[int, ...], ...]
type Ticket = tuple[int, ...]
type TicketSet = tuple[Ticket, ...]
type TicketPredictor = Callable[[NumberHistory, TargetGameSpec], Ticket]


def validate_ticket(value: object, game: TargetGameSpec, context: str) -> Ticket:
    """Validate and sort one target-native ticket."""

    if type(value) is not tuple:
        raise ValueError(f"{context}: expected an exact tuple")
    raw = cast(tuple[object, ...], value)
    if len(raw) != game.pick_count or not all(type(number) is int for number in raw):
        raise ValueError(f"{context}: expected {game.pick_count} exact integers")
    validated = cast(tuple[int, ...], raw)
    numbers = tuple(sorted(validated))
    if len(set(numbers)) != game.pick_count or any(
        number < game.minimum or number > game.maximum for number in numbers
    ):
        raise ValueError(f"{context}: ticket is outside the target game contract")
    return numbers


def _ticket(numbers: list[int] | tuple[int, ...], game: TargetGameSpec) -> Ticket:
    """Sort and validate one untrusted producer result."""

    values = tuple(sorted(numbers))
    if (
        len(values) != game.pick_count
        or len(set(values)) != game.pick_count
        or any(
            type(number) is not int
            or number < game.minimum
            or number > game.maximum
            for number in values
        )
    ):
        raise ValueError("BATCH15_CROSS_LOTTERY_INVALID_TICKET")
    return values


def _gaps_desc(history_desc: NumberHistory, game: TargetGameSpec) -> dict[int, int]:
    gaps: dict[int, int] = {}
    for number in range(game.minimum, game.maximum + 1):
        for index, draw in enumerate(history_desc):
            if number in draw:
                gaps[number] = index
                break
        else:
            gaps[number] = len(history_desc)
    return gaps


def cold_hunter_predict(history: NumberHistory, game: TargetGameSpec) -> Ticket:
    """Port ``ColdHunterPredictor.cold_hunter_predict``."""

    history_desc = tuple(reversed(history))
    gaps = _gaps_desc(history_desc, game)
    hot = sorted((item for item in gaps.items() if item[1] <= 3), key=lambda item: item[1])
    warm = sorted(
        (item for item in gaps.items() if 4 <= item[1] <= 9),
        key=lambda item: item[1],
        reverse=True,
    )
    cold = sorted(
        (item for item in gaps.items() if item[1] >= 10),
        key=lambda item: item[1],
        reverse=True,
    )
    predicted = [number for number, _gap in hot[:3]]
    predicted.extend(number for number, _gap in warm[:1] if number not in predicted)
    predicted.extend(number for number, _gap in cold[:2] if number not in predicted)
    for number, _gap in sorted(gaps.items(), key=lambda item: item[1], reverse=True):
        if len(predicted) >= game.pick_count:
            break
        if number not in predicted:
            predicted.append(number)
    return _ticket(predicted[: game.pick_count], game)


def short_window_deviation_predict(history: NumberHistory, game: TargetGameSpec) -> Ticket:
    """Port ``ColdHunterPredictor.short_window_deviation_predict``."""

    history_desc = tuple(reversed(history))
    recent = history_desc[:50]
    if len(recent) < 10:
        recent = history_desc
    frequency = Counter(number for draw in recent for number in draw)
    expected = len(recent) * game.pick_count / game.maximum
    scores: dict[int, float] = {}
    for number in range(game.minimum, game.maximum + 1):
        scores[number] = max(0.0, expected - frequency.get(number, 0))
    gaps = _gaps_desc(recent, game)
    maximum_gap = max(gaps.values()) if gaps else 1
    for number in range(game.minimum, game.maximum + 1):
        gap_score = gaps.get(number, 0) / maximum_gap
        scores[number] = scores[number] * 0.75 + gap_score * 0.25
    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    return _ticket([number for number, _score in ranked[: game.pick_count]], game)


def rebound_aware_predict(history: NumberHistory, game: TargetGameSpec) -> Ticket:
    """Port ``ColdHunterPredictor.rebound_aware_predict``."""

    history_desc = tuple(reversed(history))
    consecutive_small = 0
    found_break = False
    for draw in history_desc[:10]:
        large_count = sum(number > game.midpoint for number in draw)
        if not found_break:
            if large_count <= 2:
                consecutive_small += 1
            else:
                found_break = True
    should_rebound = consecutive_small >= 3
    gaps = _gaps_desc(history_desc, game)
    large = {number: gap for number, gap in gaps.items() if number > game.midpoint}
    small = {number: gap for number, gap in gaps.items() if number <= game.midpoint}
    target_large, target_small = (4, 2) if should_rebound else (3, 3)
    predicted: list[int] = []

    large_hot = sorted(
        (item for item in large.items() if item[1] <= 3), key=lambda item: item[1]
    )
    large_cold = sorted(
        (item for item in large.items() if item[1] >= 10),
        key=lambda item: item[1],
        reverse=True,
    )
    large_warm = sorted(
        (item for item in large.items() if 4 <= item[1] <= 9),
        key=lambda item: item[1],
        reverse=True,
    )
    if large_hot:
        predicted.append(large_hot[0][0])
    if large_cold:
        for number, _gap in large_cold:
            if number not in predicted:
                predicted.append(number)
                break
    for number, _gap in large_warm + large_cold[1:] + large_hot[1:]:
        if sum(candidate > game.midpoint for candidate in predicted) >= target_large:
            break
        if number not in predicted:
            predicted.append(number)

    small_hot = sorted(
        (item for item in small.items() if item[1] <= 3), key=lambda item: item[1]
    )
    small_cold = sorted(
        (item for item in small.items() if item[1] >= 10),
        key=lambda item: item[1],
        reverse=True,
    )
    small_warm = sorted(
        (item for item in small.items() if 4 <= item[1] <= 9),
        key=lambda item: item[1],
        reverse=True,
    )
    if small_hot:
        for number, _gap in small_hot:
            if number not in predicted:
                predicted.append(number)
                break
    for number, _gap in small_warm + small_cold + small_hot[1:]:
        if sum(candidate <= game.midpoint for candidate in predicted) >= target_small:
            break
        if number not in predicted:
            predicted.append(number)
    return _ticket(predicted[: game.pick_count], game)


def zone_momentum_candidate(history: NumberHistory, game: TargetGameSpec) -> Ticket:
    """Return the donor's raw zone-momentum result, including short closure."""

    history_desc = tuple(reversed(history))
    zone_size = (game.maximum - game.minimum + 1) // 5
    zones: dict[int, list[int]] = {}
    for zone_id in range(1, 6):
        start = game.minimum + (zone_id - 1) * zone_size
        end = game.maximum if zone_id == 5 else game.minimum + zone_id * zone_size - 1
        zones[zone_id] = list(range(start, end + 1))
    number_zone = {number: zone_id for zone_id, values in zones.items() for number in values}
    long_counts = dict.fromkeys(zones, 0)
    for draw in history_desc:
        for number in draw:
            long_counts[number_zone[number]] += 1
    long_total = sum(long_counts.values())
    long_ratio = {
        zone: count / long_total if long_total > 0 else 0.2
        for zone, count in long_counts.items()
    }
    short_counts = dict.fromkeys(zones, 0)
    for draw in history_desc[:10]:
        for number in draw:
            short_counts[number_zone[number]] += 1
    short_total = sum(short_counts.values())
    short_ratio = {
        zone: count / short_total if short_total > 0 else 0.2
        for zone, count in short_counts.items()
    }
    momentum = {
        zone: short_ratio[zone] - long_ratio[zone]
        for zone in zones
    }
    gaps = _gaps_desc(history_desc, game)
    predicted: list[int] = []
    for zone_id, score in sorted(momentum.items(), key=lambda item: item[1]):
        if len(predicted) >= game.pick_count:
            break
        zone_gaps = sorted(
            ((number, gaps.get(number, 0)) for number in zones[zone_id]),
            key=lambda item: item[1],
            reverse=True,
        )
        quota = 2 if score < -0.05 else 1
        for number, _gap in zone_gaps:
            if number in predicted:
                continue
            predicted.append(number)
            quota -= 1
            if len(predicted) >= game.pick_count or quota <= 0:
                break
    return tuple(sorted(predicted))


def pure_cold_predict(history: NumberHistory, game: TargetGameSpec) -> Ticket:
    """Port ``ColdHunterPredictor.pure_cold_predict``."""

    history_desc = tuple(reversed(history))
    gaps = _gaps_desc(history_desc, game)
    ranked = sorted(gaps.items(), key=lambda item: item[1], reverse=True)
    return _ticket([number for number, _gap in ranked[: game.pick_count]], game)


def moderate_rank_predict(history: NumberHistory, game: TargetGameSpec) -> Ticket:
    """Port ``ColdHunterPredictor.moderate_rank_predict``."""

    history_desc = tuple(reversed(history))
    gaps = _gaps_desc(history_desc, game)
    last_draw: set[int] = set(history_desc[0]) if history_desc else set()
    filtered = {number: gap for number, gap in gaps.items() if number not in last_draw}
    hot = sorted(
        (item for item in filtered.items() if item[1] <= 3), key=lambda item: item[1]
    )
    warm = sorted(
        (item for item in filtered.items() if 4 <= item[1] <= 7),
        key=lambda item: item[1],
        reverse=True,
    )
    moderate_cold = sorted(
        (item for item in filtered.items() if 8 <= item[1] <= 14),
        key=lambda item: item[1],
        reverse=True,
    )
    predicted: list[int] = []
    selected_hot = hot[5:15]
    hot_small = [number for number, _gap in selected_hot if number <= game.midpoint]
    hot_large = [number for number, _gap in selected_hot if number > game.midpoint]
    if hot_small:
        predicted.append(hot_small[0])
    if hot_large:
        predicted.append(hot_large[0])
    for number, _gap in selected_hot:
        hot_count = sum(gaps.get(candidate, 0) <= 3 for candidate in predicted)
        if hot_count >= 3:
            break
        if number not in predicted:
            predicted.append(number)
    for number, _gap in warm[:3]:
        if number not in predicted:
            predicted.append(number)
            break
    for number, _gap in moderate_cold:
        if sum(gaps.get(candidate, 0) >= 8 for candidate in predicted) >= 2:
            break
        if number not in predicted:
            predicted.append(number)
    for number, _gap in sorted(filtered.items(), key=lambda item: item[1]):
        if len(predicted) >= game.pick_count:
            break
        if number not in predicted:
            predicted.append(number)
    return _ticket(predicted[: game.pick_count], game)


def _gap_pressure_sigmoid(value: float, steepness: float = 3.0) -> float:
    return 1.0 / (1.0 + math.exp(-steepness * value))


def gap_pressure_predict(history: NumberHistory, game: TargetGameSpec) -> Ticket:
    """Port ``GapPressureScorer.predict`` with target-game bounds."""

    draw_count = len(history)
    scores: dict[int, float] = {}
    for number in range(game.minimum, game.maximum + 1):
        appearances = [index for index, draw in enumerate(history) if number in draw]
        if not appearances:
            scores[number] = 2.0
            continue
        count = len(appearances)
        current_gap = (draw_count - 1) - appearances[-1]
        if count >= 2:
            intervals = [appearances[i + 1] - appearances[i] for i in range(count - 1)]
            average_interval = sum(intervals) / len(intervals)
        else:
            average_interval = draw_count / count
        average_interval = max(average_interval, 1.0)
        scores[number] = _gap_pressure_sigmoid(current_gap / average_interval - 1.0) * 2.0
    last_draw = set(history[-1])
    ranked = sorted(
        ((number, score) for number, score in scores.items() if number not in last_draw),
        key=lambda item: item[1],
        reverse=True,
    )
    return _ticket([number for number, _score in ranked[: game.pick_count]], game)


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


def _numpy_argsort(values: list[float]) -> list[int]:
    """Port the donor's NumPy legacy float64 indirect introsort."""

    indices = list(range(len(values)))
    if len(indices) < 2:
        return indices
    stack: list[tuple[int, int, int]] = []
    lower = 0
    upper = len(indices) - 1
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
            left = lower
            right = upper - 1
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
            pivot_slot = upper - 1
            indices[left], indices[pivot_slot] = indices[pivot_slot], indices[left]
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
            break
        lower, upper, depth = stack.pop()
    return indices


@lru_cache(maxsize=4096)
def unified_deviation_ticket(history: NumberHistory, game: TargetGameSpec) -> Ticket:
    total_numbers = game.maximum - game.minimum + 1
    expected = len(history) * game.pick_count / total_numbers
    frequency = Counter(number for draw in history for number in draw)
    squared = sum(
        (frequency.get(number, 0) - expected) ** 2
        for number in range(game.minimum, game.maximum + 1)
    )
    standard_deviation = math.sqrt(squared / total_numbers)
    raw_scores: dict[int, float] = {}
    for number in range(game.minimum, game.maximum + 1):
        z_score = (
            (frequency.get(number, 0) - expected) / standard_deviation
            if standard_deviation > 0
            else 0.0
        )
        if z_score < -1.5:
            raw_scores[number] = 0.8 + abs(z_score) * 0.1
        elif z_score > 2.0:
            raw_scores[number] = 0.2
        elif 0.5 < z_score < 1.5:
            raw_scores[number] = 0.6 + z_score * 0.1
        else:
            raw_scores[number] = 0.4
    maximum_score = max(raw_scores.values())
    scores = {
        number: raw_scores[number] / (maximum_score + 1e-10) * _DEVIATION_WEIGHTS["frequency"]
        for number in raw_scores
    }

    zone_size = total_numbers // 5
    zones: dict[int, list[int]] = {}
    for zone_id in range(1, 6):
        start = game.minimum + (zone_id - 1) * zone_size
        end = game.maximum if zone_id == 5 else game.minimum + zone_id * zone_size - 1
        zones[zone_id] = list(range(start, end + 1))
    zone_counts = dict.fromkeys(zones, 0)
    for number in (number for draw in history for number in draw):
        for zone_id, zone_numbers in zones.items():
            if number in zone_numbers:
                zone_counts[zone_id] += 1
                break
    for zone_id, zone_numbers in zones.items():
        zone_expected = len(history) * game.pick_count * len(zone_numbers) / total_numbers
        zone_score = max(0.0, zone_expected - zone_counts[zone_id])
        for number in zone_numbers:
            scores[number] += zone_score * _DEVIATION_WEIGHTS["zone"] / len(zone_numbers)

    total_hits = len(history) * game.pick_count
    expected_odd = total_hits / 2
    odd_deviation = expected_odd - sum(number % 2 for draw in history for number in draw)
    expected_small = total_hits / 2
    small_count = sum(number <= game.midpoint for draw in history for number in draw)
    small_deviation = expected_small - small_count
    for number in range(game.minimum, game.maximum + 1):
        if expected_odd and number % 2 == 1 and odd_deviation > 0:
            scores[number] += _DEVIATION_WEIGHTS["odd_even"] * odd_deviation / expected_odd
        elif expected_odd and number % 2 == 0 and odd_deviation < 0:
            scores[number] += _DEVIATION_WEIGHTS["odd_even"] * abs(odd_deviation) / expected_odd
        if expected_small and number <= game.midpoint and small_deviation > 0:
            scores[number] += _DEVIATION_WEIGHTS["high_low"] * small_deviation / expected_small
        elif expected_small and number > game.midpoint and small_deviation < 0:
            scores[number] += _DEVIATION_WEIGHTS["high_low"] * abs(small_deviation) / expected_small

    gaps = {
        number: next(
            (index for index, draw in enumerate(history) if number in draw),
            len(history),
        )
        for number in range(game.minimum, game.maximum + 1)
    }
    maximum_gap = max(gaps.values()) if gaps else 1
    for number in scores:
        if maximum_gap > 0:
            scores[number] += gaps[number] / maximum_gap * _DEVIATION_WEIGHTS["gap"]
    ranked = sorted(
        range(game.minimum, game.maximum + 1),
        key=lambda number: scores[number],
        reverse=True,
    )
    return _ticket(ranked[: game.pick_count], game)


def _markov_order1(draws: NumberHistory, game: TargetGameSpec) -> list[float]:
    matrix = [[0.1] * (game.maximum + 1) for _ in range(game.maximum + 1)]
    analysis = draws[-100:]
    for index in range(len(analysis) - 1):
        weight = 1.0 + index / len(analysis)
        for current in analysis[index]:
            for following in analysis[index + 1]:
                matrix[current][following] += weight
    for row_index, row in enumerate(matrix):
        row_sum = sum(row)
        matrix[row_index] = [value / row_sum for value in row]
    probabilities = [0.0] * (game.maximum + 1)
    for current in draws[-1]:
        for index, value in enumerate(matrix[current]):
            probabilities[index] += value
    return probabilities


def _markov_order2(draws: NumberHistory, game: TargetGameSpec) -> list[float]:
    transitions: dict[tuple[int, int], defaultdict[int, float]] = {}
    analysis = draws[-80:]
    for index in range(len(analysis) - 2):
        weight = 1.0 + index / len(analysis)
        for prior in analysis[index]:
            for current in analysis[index + 1]:
                counter = transitions.setdefault((prior, current), defaultdict(float))
                for following in analysis[index + 2]:
                    counter[following] += weight
    if len(draws) < 2:
        return _markov_order1(draws, game)
    probabilities = [0.0] * (game.maximum + 1)
    total_weight = 0.0
    for prior in draws[-2]:
        for current in draws[-1]:
            counter = transitions.get((prior, current))
            if counter is not None:
                for following, count in counter.items():
                    probabilities[following] += count
                    total_weight += count
    return (
        [value / total_weight for value in probabilities]
        if total_weight > 0
        else _markov_order1(draws, game)
    )


def _markov_order3(draws: NumberHistory, game: TargetGameSpec) -> list[float]:
    transitions: dict[tuple[int, int, int], defaultdict[int, float]] = {}
    analysis = draws[-60:]
    for index in range(len(analysis) - 3):
        weight = 1.0 + index / len(analysis)
        for prior2 in analysis[index]:
            for prior1 in analysis[index + 1]:
                for current in analysis[index + 2]:
                    counter = transitions.setdefault((prior2, prior1, current), defaultdict(float))
                    for following in analysis[index + 3]:
                        counter[following] += weight
    if len(draws) < 3:
        return _markov_order2(draws, game)
    probabilities = [0.0] * (game.maximum + 1)
    total_weight = 0.0
    for prior2 in draws[-3]:
        for prior1 in draws[-2]:
            for current in draws[-1]:
                counter = transitions.get((prior2, prior1, current))
                if counter is not None:
                    for following, count in counter.items():
                        probabilities[following] += count
                        total_weight += count
    return (
        [value / total_weight for value in probabilities]
        if total_weight > 0
        else _markov_order2(draws, game)
    )


@lru_cache(maxsize=4096)
def unified_markov_ticket(history: NumberHistory, game: TargetGameSpec) -> Ticket:
    if not history:
        raise ValueError("BATCH15_CROSS_LOTTERY_MARKOV_REQUIRES_HISTORY")
    if len(history) < 50:
        probabilities = _markov_order1(history, game)
    elif len(history) < 150:
        probabilities = _markov_order2(history, game)
    else:
        probabilities = _markov_order3(history, game)
    for number in history[-1]:
        probabilities[number] *= 0.3
    probabilities[0] = -1.0
    ranked = list(reversed(_numpy_argsort(probabilities)))
    return _ticket(
        [number for number in ranked if game.minimum <= number <= game.maximum][: game.pick_count],
        game,
    )


def _statistical_conditions(numbers: list[int], game: TargetGameSpec) -> bool:
    total_numbers = game.maximum - game.minimum + 1
    total = sum(numbers)
    theoretical_min = game.minimum * game.pick_count + game.pick_count * (game.pick_count - 1) / 2
    theoretical_max = game.maximum * game.pick_count - game.pick_count * (game.pick_count - 1) / 2
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
    minimum_ac = max(game.pick_count - 1, int(total_numbers * _STATISTICAL_PARAMS["ac_min_mult"]))
    maximum_ac = min(
        game.pick_count * (game.pick_count - 1) / 2,
        int(total_numbers * _STATISTICAL_PARAMS["ac_max_mult"]),
    )
    odd_count = sum(number % 2 == 1 for number in numbers)
    return (
        minimum_ac <= ac_value <= maximum_ac
        and abs(odd_count - round(game.pick_count / 2)) <= _STATISTICAL_PARAMS["odd_tolerance"]
        and max(numbers) - min(numbers) >= int(total_numbers * _STATISTICAL_PARAMS["spread_mult"])
        and len({number % 10 for number in numbers}) >= _STATISTICAL_PARAMS[
            "unique_last_digits_min"
        ]
    )


@lru_cache(maxsize=4096)
def unified_statistical_ticket(history: NumberHistory, game: TargetGameSpec) -> Ticket:
    frequency = Counter(number for draw in history for number in draw)
    pool: list[int] = []
    for number in range(game.minimum, game.maximum + 1):
        weight = int(
            math.pow(max(1, frequency.get(number, 0)), _STATISTICAL_PARAMS["weight_power"])
            * 10
        )
        pool.extend([number] * weight)
    rng = random.Random(len(history))
    valid: list[list[int]] = []
    for _ in range(2000):
        if len(valid) >= 20:
            break
        combination: set[int] = set()
        while len(combination) < game.pick_count:
            combination.add(rng.choice(pool))
        candidate = list(combination)
        if _statistical_conditions(candidate, game):
            valid.append(candidate)
    if not valid:
        raise ValueError("BATCH15_CROSS_LOTTERY_STATISTICAL_FALLBACK_REQUIRED")
    best = max(valid, key=lambda row: sum(frequency.get(number, 0) for number in row))
    return _ticket(best, game)


@lru_cache(maxsize=4096)
def unified_hot_cold_mix_ticket(history: NumberHistory, game: TargetGameSpec) -> Ticket:
    if len(history) < 15:
        frequency = Counter(number for draw in history for number in draw)
        maximum = max(frequency.values()) if frequency else 1
        window_scores = {
            number: frequency.get(number, 0) / maximum
            for number in range(game.minimum, game.maximum + 1)
        }
    else:
        windows: dict[str, dict[int, float]] = {}
        for name, size in (("short", 15), ("mid", 25), ("long", 45)):
            recent = history[-min(size, len(history)) :]
            frequency = Counter(number for draw in recent for number in draw)
            maximum = max(frequency.values()) if frequency else 1
            windows[name] = {
                number: frequency.get(number, 0) / maximum
                for number in range(game.minimum, game.maximum + 1)
            }
        window_scores = {
            number: windows["short"][number] * 0.5
            + windows["mid"][number] * 0.3
            + windows["long"][number] * 0.2
            for number in range(game.minimum, game.maximum + 1)
        }
    if len(history) < 30:
        transitions = dict.fromkeys(range(game.minimum, game.maximum + 1), 0.0)
    else:
        periods = (history[-30:-20], history[-20:-10], history[-10:])
        frequencies = [Counter(number for draw in period for number in draw) for period in periods]
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
            for number in range(game.minimum, game.maximum + 1)
        }
        low, high = min(raw.values()), max(raw.values())
        span = high - low if high > low else 1
        transitions = {
            number: (score - low) / span for number, score in raw.items()
        }
    final = {
        number: window_scores[number] * 0.7 + transitions[number] * 0.3
        for number in range(game.minimum, game.maximum + 1)
    }
    return _ticket(
        sorted(final, key=lambda number: final[number], reverse=True)[: game.pick_count],
        game,
    )


@lru_cache(maxsize=4096)
def unified_trend_ticket(history: NumberHistory, game: TargetGameSpec) -> Ticket:
    weighted: defaultdict[int, float] = defaultdict(float)
    for age, draw in enumerate(reversed(history[-100:])):
        weight = math.exp(-0.01 * age)
        for number in draw:
            weighted[number] += weight
    total = sum(weighted.values())
    probabilities = {
        number: weighted.get(number, 0.0) / total if total > 0 else 0.0
        for number in range(game.minimum, game.maximum + 1)
    }
    ranked = sorted(probabilities, key=lambda number: probabilities[number], reverse=True)
    return _ticket(ranked[: game.pick_count], game)


_DMS_METHODS: Final[tuple[tuple[str, TicketPredictor], ...]] = (
    ("hot_cold_mix", unified_hot_cold_mix_ticket),
    ("markov", unified_markov_ticket),
    ("deviation", unified_deviation_ticket),
    ("trend", unified_trend_ticket),
    ("statistical", unified_statistical_ticket),
)


def _audit_hit_counts(
    history: NumberHistory,
    game: TargetGameSpec,
    window: int,
) -> list[tuple[str, int]]:
    performance: list[tuple[str, int]] = []
    for name, predictor in _DMS_METHODS:
        hits = 0
        for offset in range(window):
            index = len(history) - window + offset
            if index <= 0:
                continue
            try:
                ticket = predictor(history[:index], game)
            except ValueError:
                continue
            if len(set(ticket) & set(history[index])) >= 3:
                hits += 1
        performance.append((name, hits))
    return performance


def dm_dms_tickets(history: NumberHistory, game: TargetGameSpec) -> TicketSet:
    """Port the Batch-15 DM-DMS top-two dynamic portfolio."""

    performance = _audit_hit_counts(history, game, 15)
    ranked = sorted(performance, key=lambda item: item[1], reverse=True)
    methods: dict[str, TicketPredictor] = dict(_DMS_METHODS)
    tickets: list[Ticket] = []
    for name, _hits in ranked[:2]:
        try:
            tickets.append(methods[name](history, game))
        except ValueError:
            continue
    return tuple(tickets)


def dms_solo_ticket(history: NumberHistory, game: TargetGameSpec) -> Ticket:
    """Port the Batch-15 DMS-solo method-selection gate and audit."""

    if len(history) <= 50:
        return unified_hot_cold_mix_ticket(history, game)
    best_method = "hot_cold_mix"
    best_rate = -1
    methods: dict[str, TicketPredictor] = dict(_DMS_METHODS)
    for name, predictor in _DMS_METHODS:
        hits = 0
        for offset in range(15):
            index = len(history) - 15 + offset
            if index <= 0:
                continue
            try:
                ticket = predictor(history[:index], game)
            except ValueError:
                continue
            if len(set(ticket) & set(history[index])) >= 3:
                hits += 1
        if hits > best_rate:
            best_rate = hits
            best_method = name
        elif hits == best_rate and name == "hot_cold_mix":
            best_method = name
    return methods[best_method](history, game)


def predictor_by_name(name: str) -> Callable[[NumberHistory, TargetGameSpec], Ticket | TicketSet]:
    """Return one named Batch-15 producer for target wrappers."""

    predictors: dict[str, Callable[[NumberHistory, TargetGameSpec], Ticket | TicketSet]] = {
        "cold_hunter": cold_hunter_predict,
        "short_window_deviation": short_window_deviation_predict,
        "rebound_aware": rebound_aware_predict,
        "zone_momentum": zone_momentum_candidate,
        "pure_cold": pure_cold_predict,
        "moderate_rank": moderate_rank_predict,
        "gap_pressure": gap_pressure_predict,
        "dm_dms": dm_dms_tickets,
        "dms": dms_solo_ticket,
    }
    try:
        return predictors[name]
    except KeyError as exc:
        raise KeyError(f"unknown Batch-15 producer: {name}") from exc


__all__ = [
    "DAILY539_GAME",
    "POWERLOTTO_GAME",
    "NumberHistory",
    "TargetGameSpec",
    "Ticket",
    "TicketSet",
    "cold_hunter_predict",
    "dm_dms_tickets",
    "dms_solo_ticket",
    "gap_pressure_predict",
    "moderate_rank_predict",
    "predictor_by_name",
    "pure_cold_predict",
    "rebound_aware_predict",
    "short_window_deviation_predict",
    "unified_deviation_ticket",
    "unified_hot_cold_mix_ticket",
    "unified_markov_ticket",
    "unified_statistical_ticket",
    "unified_trend_ticket",
    "validate_ticket",
    "zone_momentum_candidate",
]
