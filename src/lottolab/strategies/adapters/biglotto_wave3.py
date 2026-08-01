"""BigLotto native-strategy wave 3: thin ports of frozen legacy BACKTESTED methods.

Each adapter below is a direct, dependency-free port of one frozen legacy
source file (donor commit ``49a25effa62fc24f40789c16be6f11bdfb41a4a9``, the
same frozen snapshot as waves 1-2; see each class's ``provenance`` in
``strategies/catalog.py`` for the exact path/hash). No algorithm was
changed, tuned, or "improved" during the port.

All three methods below are thin coverage-optimization wrappers around the
donor's own ``lottery_api/models/unified_predictor.py::UnifiedPredictionEngine``
(``deviation_predict``, ``markov_predict``, ``statistical_predict``, and --
for the V2 variant only -- ``bayesian_predict``/``frequency_predict``): each
donor file collects a small, fixed set of the engine's single-ticket outputs
into a weighted ``Counter``, takes its own fixed top-N slice, and carves that
slice into two positional tickets. The five underlying engine methods
(``_unified_deviation_ticket`` / ``_unified_markov_ticket`` /
``_unified_statistical_ticket`` / ``_unified_bayesian_ticket`` /
``_unified_frequency_ticket`` below) are pure scalar/``Counter`` math with
one exception each:

* ``markov_predict`` ranks its transition-probability vector with
  ``numpy.argsort`` (donor line ``sorted_indices = np.argsort(next_probs)``).
  Unlike the two donor families wave 2 rejected for using an unreproducible
  unstable sort, this is not skipped here: ``_numpy_argsort`` below is a
  literal, previously-verified port of NumPy's legacy introsort algorithm
  itself (median-of-3 quicksort with the same insertion-sort fallback below
  16 elements) rather than a substitute stable ``sorted()``, so it reproduces
  NumPy's own tie-break order bit-for-bit instead of approximating it. The
  same reimplementation already backs the separately-tested frozen-source
  research ports at ``lottolab.application.legacy_history_native_portfolios``
  (``legacy_numpy_argsort``); this module copies it verbatim rather than
  importing across the ``strategies`` -> ``application`` layer boundary that
  ``tests/architecture/test_dependency_rules.py`` forbids.
* ``statistical_predict`` draws combinations from a frequency-weighted pool
  via ``random.seed(len(history))`` followed by plain ``random.choice`` --
  seeded directly and only by the causal history's own length, so it is
  fully deterministic and reproducible with the stdlib ``random`` module and
  needs no imposed policy seed (contrast the still-excluded
  ``anti_consensus_strategy.py``, whose donor calls unseeded
  ``numpy.random.choice`` with no reproducible seed of its own).

Each donor script also calls ``self.engine = UnifiedPredictionEngine()``
which pulls in numpy/pandas/scipy/sklearn and several optional torch-backed
sub-predictors; only the five plain-Python statistical entrypoints above are
ever invoked by these three donor files, so this port only needs those five,
all of which reduce to stdlib ``math``/``random``/``collections.Counter``.

Donor parity for the shared engine methods was independently re-derived by
reading ``lottery_api/models/unified_predictor.py`` at the frozen commit (no
numpy/pandas/scipy/sklearn is installed in this environment to execute the
donor class directly) and cross-checked against the separately-verified,
already-tested pure-Python research port of the same methods at
``lottolab.application.legacy_frozen_unified_core`` (2148 causal executions
recorded against the same frozen commit per
``strategies/data/biglotto_full_strategy_catalog_v1.json``); this module's
own test goldens were computed from that already-verified reference.

The donor's ``markov_predict`` defensively reverses ``history`` if
``history[0]``'s draw identifier sorts after ``history[-1]``'s (guarding
against being handed newest-first input). That branch is not ported:
``CausalDrawRow`` history is always oldest-first under this framework's own
contract (every wave 1/2 adapter already relies on ``history[-1]`` being the
most recent draw), so the branch is provably unreachable here -- omitted,
not "improved away".
"""

from __future__ import annotations

import math
import random
from collections import Counter, defaultdict
from typing import cast

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import (
    CausalDrawRow,
    PortfolioBetAdapter,
)

_MIN_NUM = 1
_MAX_NUM = 49
_PICK = 6

_DEVIATION_WEIGHTS = {
    "frequency": 0.30,
    "zone": 0.25,
    "odd_even": 0.20,
    "high_low": 0.15,
    "gap": 0.10,
}
_STATISTICAL_PARAMS = {
    "sum_range_mult": 0.4,
    "ac_min_mult": 0.15,
    "ac_max_mult": 0.35,
    "odd_tolerance": 2,
    "spread_mult": 0.4,
    "unique_last_digits_min": 4,
    "weight_power": 0.5,
}


def _ticket(numbers: list[int]) -> tuple[int, ...]:
    values = tuple(sorted(numbers))
    if len(values) != _PICK or len(set(values)) != _PICK or any(
        type(number) is not int or not _MIN_NUM <= number <= _MAX_NUM for number in values
    ):
        raise ValueError("FROZEN_UNIFIED_INVALID_TICKET")
    return values


# ─── shared UnifiedPredictionEngine port (deviation / markov / statistical /
#     bayesian / frequency) -- see module docstring for the argsort and RNG
#     reproducibility notes. ───────────────────────────────────────────────


def _unified_deviation_ticket(history: tuple[CausalDrawRow, ...]) -> tuple[int, ...]:
    """Port ``UnifiedPredictionEngine.deviation_predict``'s number selection."""

    total_numbers = _MAX_NUM - _MIN_NUM + 1
    expected_frequency = len(history) * _PICK / total_numbers
    all_numbers = [number for draw in history for number in draw.numbers]
    frequency = Counter(all_numbers)
    sum_squared_difference = sum(
        (frequency.get(number, 0) - expected_frequency) ** 2
        for number in range(_MIN_NUM, _MAX_NUM + 1)
    )
    standard_deviation = math.sqrt(sum_squared_difference / total_numbers)
    raw_scores = [0.0] * (_MAX_NUM + 1)
    for number in range(_MIN_NUM, _MAX_NUM + 1):
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
    maximum = max(raw_scores)
    scores = [value / (maximum + 1e-10) * _DEVIATION_WEIGHTS["frequency"] for value in raw_scores]

    zone_size = total_numbers // 5
    zones: dict[int, list[int]] = {}
    for zone_id in range(1, 6):
        start = _MIN_NUM + (zone_id - 1) * zone_size
        end = _MAX_NUM if zone_id == 5 else _MIN_NUM + zone_id * zone_size - 1
        zones[zone_id] = list(range(start, end + 1))
    zone_counts = {zone_id: 0 for zone_id in zones}
    for number in all_numbers:
        for zone_id, zone_numbers in zones.items():
            if number in zone_numbers:
                zone_counts[zone_id] += 1
    for zone_id, zone_numbers in zones.items():
        expected = len(history) * _PICK * len(zone_numbers) / total_numbers
        zone_score = max(0.0, expected - zone_counts[zone_id])
        for number in zone_numbers:
            scores[number] += zone_score * _DEVIATION_WEIGHTS["zone"] / len(zone_numbers)

    odd_count = sum(number % 2 == 1 for number in all_numbers)
    expected_odd = len(all_numbers) / 2
    odd_deviation = expected_odd - odd_count
    for number in range(_MIN_NUM, _MAX_NUM + 1):
        if number % 2 == 1 and odd_deviation > 0:
            scores[number] += _DEVIATION_WEIGHTS["odd_even"] * odd_deviation / expected_odd
        elif number % 2 == 0 and odd_deviation < 0:
            scores[number] += _DEVIATION_WEIGHTS["odd_even"] * abs(odd_deviation) / expected_odd

    midpoint = (_MIN_NUM + _MAX_NUM) // 2
    small_count = sum(number <= midpoint for number in all_numbers)
    expected_small = len(all_numbers) / 2
    small_deviation = expected_small - small_count
    for number in range(_MIN_NUM, _MAX_NUM + 1):
        if number <= midpoint and small_deviation > 0:
            scores[number] += _DEVIATION_WEIGHTS["high_low"] * small_deviation / expected_small
        elif number > midpoint and small_deviation < 0:
            scores[number] += _DEVIATION_WEIGHTS["high_low"] * abs(small_deviation) / expected_small

    gaps: dict[int, int] = {}
    for number in range(_MIN_NUM, _MAX_NUM + 1):
        for index, draw in enumerate(history):
            if number in draw.numbers:
                gaps[number] = index
                break
        if number not in gaps:
            gaps[number] = len(history)
    maximum_gap = max(gaps.values()) if gaps else 1
    for number in range(_MIN_NUM, _MAX_NUM + 1):
        gap_score = gaps.get(number, 0) / maximum_gap if maximum_gap > 0 else 0.0
        scores[number] += gap_score * _DEVIATION_WEIGHTS["gap"]

    ranked = sorted(range(_MIN_NUM, _MAX_NUM + 1), key=lambda number: scores[number], reverse=True)
    return _ticket(ranked[:_PICK])


def _numpy_argsort(values: list[float]) -> list[int]:
    """Port NumPy's legacy float64 indirect introsort for small arrays.

    A literal reimplementation of the median-of-3 quicksort (with a
    16-element insertion-sort fallback) NumPy itself uses, not a
    substitute -- see the module docstring's argsort note.
    """

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


def _markov_order1(draws: tuple[tuple[int, ...], ...]) -> list[float]:
    matrix = [[0.1] * (_MAX_NUM + 1) for _ in range(_MAX_NUM + 1)]
    analysis = draws[-100:]
    for index in range(len(analysis) - 1):
        weight = 1.0 + index / len(analysis)
        for current in analysis[index]:
            for following in analysis[index + 1]:
                matrix[current][following] += weight
    for row_index, row in enumerate(matrix):
        row_sum = sum(row)
        matrix[row_index] = [value / row_sum for value in row]
    probabilities = [0.0] * (_MAX_NUM + 1)
    for number in draws[-1]:
        row = matrix[number]
        for index, value in enumerate(row):
            probabilities[index] += value
    return probabilities


def _markov_order2(draws: tuple[tuple[int, ...], ...]) -> list[float]:
    transitions: dict[tuple[int, int], defaultdict[int, float]] = {}
    analysis = draws[-80:]
    for index in range(len(analysis) - 2):
        weight = 1.0 + index / len(analysis)
        for number2 in analysis[index]:
            for number1 in analysis[index + 1]:
                state = (number2, number1)
                counter = transitions.setdefault(state, defaultdict(float))
                for following in analysis[index + 2]:
                    counter[following] += weight
    if len(draws) < 2:
        return _markov_order1(draws)
    probabilities = [0.0] * (_MAX_NUM + 1)
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


def _markov_order3(draws: tuple[tuple[int, ...], ...]) -> list[float]:
    transitions: dict[tuple[int, int, int], defaultdict[int, float]] = {}
    analysis = draws[-60:]
    for index in range(len(analysis) - 3):
        weight = 1.0 + index / len(analysis)
        for number3 in analysis[index]:
            for number2 in analysis[index + 1]:
                for number1 in analysis[index + 2]:
                    state = (number3, number2, number1)
                    counter = transitions.setdefault(state, defaultdict(float))
                    for following in analysis[index + 3]:
                        counter[following] += weight
    if len(draws) < 3:
        return _markov_order2(draws)
    probabilities = [0.0] * (_MAX_NUM + 1)
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


def _unified_markov_ticket(history: tuple[CausalDrawRow, ...]) -> tuple[int, ...]:
    """Port ``UnifiedPredictionEngine.markov_predict``'s adaptive 1/2/3-order
    transition-matrix number selection (see module docstring for the
    reorder-branch omission and the NumPy-argsort reproduction notes)."""

    draws = tuple(draw.numbers for draw in history)
    if len(draws) < 50:
        probabilities = _markov_order1(draws)
    elif len(draws) < 150:
        probabilities = _markov_order2(draws)
    else:
        probabilities = _markov_order3(draws)
    for number in draws[-1]:
        probabilities[number] *= 0.3
    probabilities[0] = -1.0
    ranked = list(reversed(_numpy_argsort(probabilities)))
    selected = [index for index in ranked if _MIN_NUM <= index <= _MAX_NUM][:_PICK]
    return _ticket(selected)


def _statistical_conditions(numbers: list[int]) -> bool:
    total_numbers = _MAX_NUM - _MIN_NUM + 1
    total = sum(numbers)
    theoretical_min = _MIN_NUM * _PICK + _PICK * (_PICK - 1) / 2
    theoretical_max = _MAX_NUM * _PICK - _PICK * (_PICK - 1) / 2
    ideal_sum = (theoretical_min + theoretical_max) / 2
    sum_range = (theoretical_max - theoretical_min) * _STATISTICAL_PARAMS["sum_range_mult"]
    if not (ideal_sum - sum_range / 2 <= total <= ideal_sum + sum_range / 2):
        return False
    ordered = sorted(numbers)
    differences = {
        ordered[right] - ordered[left]
        for left in range(len(ordered))
        for right in range(left + 1, len(ordered))
    }
    ac_value = len(differences) - (len(numbers) - 1)
    minimum_ac = max(_PICK - 1, int(total_numbers * _STATISTICAL_PARAMS["ac_min_mult"]))
    maximum_ac = min(
        _PICK * (_PICK - 1) / 2, int(total_numbers * _STATISTICAL_PARAMS["ac_max_mult"])
    )
    if not minimum_ac <= ac_value <= maximum_ac:
        return False
    odd_count = sum(number % 2 == 1 for number in numbers)
    if abs(odd_count - round(_PICK / 2)) > _STATISTICAL_PARAMS["odd_tolerance"]:
        return False
    if max(numbers) - min(numbers) < int(total_numbers * _STATISTICAL_PARAMS["spread_mult"]):
        return False
    return len({number % 10 for number in numbers}) >= _STATISTICAL_PARAMS["unique_last_digits_min"]


def _unified_statistical_ticket(history: tuple[CausalDrawRow, ...]) -> tuple[int, ...]:
    """Port ``UnifiedPredictionEngine.statistical_predict``, including its
    ``random.seed(len(history))``-reproducible candidate search."""

    frequency = Counter(number for draw in history for number in draw.numbers)
    pool: list[int] = []
    for number in range(_MIN_NUM, _MAX_NUM + 1):
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
        while len(combination) < _PICK:
            combination.add(rng.choice(pool))
        candidate = list(combination)
        if _statistical_conditions(candidate):
            valid.append(candidate)
    if not valid:
        raise ValueError("FROZEN_STATISTICAL_FREQUENCY_FALLBACK_REQUIRED")
    best = max(valid, key=lambda candidate: sum(frequency.get(number, 0) for number in candidate))
    return _ticket(best)


def _population_stability(history: tuple[CausalDrawRow, ...]) -> float:
    if len(history) < 5:
        return 0.5
    frequencies = list(Counter(number for draw in history for number in draw.numbers).values())
    if len(frequencies) < 2:
        return 0.5
    mean = sum(frequencies) / len(frequencies)
    if mean == 0:
        return 0.5
    variance = sum((frequency - mean) ** 2 for frequency in frequencies) / len(frequencies)
    return 1 / (1 + math.sqrt(variance) / mean)


def _unified_bayesian_ticket(history: tuple[CausalDrawRow, ...]) -> tuple[int, ...]:
    """Port ``UnifiedPredictionEngine.bayesian_predict``'s number selection."""

    if not history:
        raise ValueError("FROZEN_BAYESIAN_REQUIRES_HISTORY")
    long_term_frequency = Counter(number for draw in history for number in draw.numbers)
    recent_history = history[-20:]
    recent_frequency = Counter(number for draw in recent_history for number in draw.numbers)
    stability = _population_stability(recent_history)
    if len(history) < 50:
        likelihood_weight, prior_weight = 0.75, 0.25
    elif len(history) < 100:
        likelihood_weight, prior_weight = (0.65, 0.35) if stability > 0.7 else (0.55, 0.45)
    else:
        likelihood_weight, prior_weight = (0.6, 0.4) if stability > 0.7 else (0.5, 0.5)
    denominator = len(history) * _PICK
    scores: dict[int, float] = {}
    for number in range(_MIN_NUM, _MAX_NUM + 1):
        prior = long_term_frequency.get(number, 0) / denominator
        if prior == 0:
            prior = 1 / (denominator * 10)
        likelihood = recent_frequency.get(number, 0) / len(recent_history)
        scores[number] = likelihood * likelihood_weight + prior * prior_weight
    ranked = sorted(scores, key=lambda number: scores[number], reverse=True)
    return _ticket(ranked[:_PICK])


def _unified_frequency_ticket(history: tuple[CausalDrawRow, ...]) -> tuple[int, ...]:
    """Port ``UnifiedPredictionEngine.frequency_predict``'s number selection."""

    if not history:
        raise ValueError("FROZEN_FREQUENCY_REQUIRES_HISTORY")
    basic_frequency = Counter(number for draw in history for number in draw.numbers)
    theoretical_average = len(history) * _PICK / (_MAX_NUM - _MIN_NUM + 1)
    gaps: dict[int, int] = {}
    for number in range(_MIN_NUM, _MAX_NUM + 1):
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
                basic_frequency.get(number, 0) / theoretical_average if theoretical_average else 0.0
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
    average_weight = total_weight / (_MAX_NUM - _MIN_NUM + 1)
    scores = {
        number: (
            0.4 * (weighted_counts.get(number, 0.0) / average_weight if total_weight > 0 else 0.0)
            + 0.6 * (gaps.get(number, 0) / maximum_gap if maximum_gap > 0 else 0.0)
        )
        for number in range(_MIN_NUM, _MAX_NUM + 1)
    }
    ranked = sorted(scores, key=lambda number: scores[number], reverse=True)
    return _ticket(ranked[:_PICK])


# ─── legacy_biglotto__biglotto_2bet_final__7eaedb330a07 ─────────────────────
# Donor: lottery_api/models/biglotto_2bet_final.py —
# BigLotto2BetOptimizerV3.predict_2bets_final. Top-3 engine methods
# (deviation/markov/statistical, weight 2.0 each) into a weighted Counter,
# top-15 candidate pool. Bet 1 is the top 6. Bet 2 is built from
# candidates[3:12]: large numbers (>24) are greedily taken first (up to 3),
# then the remaining slots are filled from the same slice in its own order.


class BigLottoTwoBetFinalAdapter(PortfolioBetAdapter):
    """Top-3 engine coverage optimizer (V3 final): top-15 pool, bet 2 favors
    large numbers (>24) -- a 2-native-ticket portfolio."""

    strategy_id = "legacy_biglotto__biglotto_2bet_final__7eaedb330a07"
    strategy_name = "大樂透 雙注優化 V3 最終版（Top15+大號加強）"  # noqa: RUF001
    strategy_version = "v0.1"
    min_history = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)
    native_ticket_count = 2

    def _predict_all(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[tuple[int, ...], ...]:
        deviation = _unified_deviation_ticket(history)
        markov = _unified_markov_ticket(history)
        statistical = _unified_statistical_ticket(history)
        candidates: Counter[int] = Counter()
        for ticket in (deviation, markov, statistical):
            for number in ticket:
                candidates[number] += cast(int, 2.0)
        top_candidates = [number for number, _score in candidates.most_common(15)]
        bet1 = top_candidates[:6]
        second_candidates = top_candidates[3:12]
        bet2: list[int] = []
        for number in second_candidates:
            if number > 24 and sum(item > 24 for item in bet2) < 3:
                bet2.append(number)
        for number in second_candidates:
            if number not in bet2 and len(bet2) < 6:
                bet2.append(number)
        return (_ticket(bet1), _ticket(bet2))


# ─── legacy_biglotto__biglotto_2bet_optimizer__898ac9e38876 ─────────────────
# Donor: lottery_api/models/biglotto_2bet_optimizer.py —
# BigLotto2BetOptimizer.predict_2bets. Top-3 engine methods (deviation 2.0,
# markov 1.5, statistical 1.0) into a weighted Counter, top-12 candidate
# pool, bet 1 = pool[0:6], bet 2 = pool[3:9].


class BigLottoTwoBetOptimizerAdapter(PortfolioBetAdapter):
    """Top-3 engine coverage optimizer (V1): top-12 pool sliced at [0:6] and
    [3:9] -- a 2-native-ticket portfolio."""

    strategy_id = "legacy_biglotto__biglotto_2bet_optimizer__898ac9e38876"
    strategy_name = "大樂透 雙注覆蓋優化"
    strategy_version = "v0.1"
    min_history = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)
    native_ticket_count = 2

    def _predict_all(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[tuple[int, ...], ...]:
        deviation = _unified_deviation_ticket(history)
        markov = _unified_markov_ticket(history)
        statistical = _unified_statistical_ticket(history)
        candidates: Counter[int] = Counter()
        for ticket, weight in ((deviation, 2.0), (markov, 1.5), (statistical, 1.0)):
            for number in ticket:
                candidates[number] += cast(int, weight)
        top_candidates = [number for number, _score in candidates.most_common(12)]
        return (_ticket(top_candidates[0:6]), _ticket(top_candidates[3:9]))


# ─── legacy_biglotto__biglotto_2bet_optimizer_v2__783226366ac3 ──────────────
# Donor: lottery_api/models/biglotto_2bet_optimizer_v2.py —
# BigLotto2BetOptimizerV2.predict_2bets_optimized. Five engine methods
# (deviation 1.5, markov 1.5, statistical 1.2, bayesian 1.0, frequency 1.0,
# in the donor's own dict-literal insertion order) into a weighted Counter,
# top-18 candidate pool, bet 1 = pool[0:6], bet 2 = pool[4:10].


class BigLottoTwoBetOptimizerV2Adapter(PortfolioBetAdapter):
    """Five-engine-method coverage optimizer (V2): top-18 pool sliced at
    [0:6] and [4:10] -- a 2-native-ticket portfolio."""

    strategy_id = "legacy_biglotto__biglotto_2bet_optimizer_v2__783226366ac3"
    strategy_name = "大樂透 雙注覆蓋優化 V2"
    strategy_version = "v0.1"
    min_history = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)
    native_ticket_count = 2

    def _predict_all(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[tuple[int, ...], ...]:
        deviation = _unified_deviation_ticket(history)
        markov = _unified_markov_ticket(history)
        statistical = _unified_statistical_ticket(history)
        bayesian = _unified_bayesian_ticket(history)
        frequency = _unified_frequency_ticket(history)
        candidates: Counter[int] = Counter()
        for ticket, weight in (
            (deviation, 1.5),
            (markov, 1.5),
            (statistical, 1.2),
            (bayesian, 1.0),
            (frequency, 1.0),
        ):
            for number in ticket:
                candidates[number] += cast(int, weight)
        top_candidates = [number for number, _score in candidates.most_common(18)]
        return (_ticket(top_candidates[0:6]), _ticket(top_candidates[4:10]))


__all__ = [
    "BigLottoTwoBetFinalAdapter",
    "BigLottoTwoBetOptimizerAdapter",
    "BigLottoTwoBetOptimizerV2Adapter",
]
