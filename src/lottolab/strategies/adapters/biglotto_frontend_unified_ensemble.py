"""Target-native port of the legacy frontend Unified Ensemble strategy.

The donor is ``LotteryNewMeraged/src/engine/strategies/UnifiedEnsembleStrategy.js``.
Frontend data is newest-first; LottoLab causal histories are oldest-first, so
each adapter reverses the validated history before applying donor scoring.
Architecture C: leaf probability vectors, missing maps, and Monte Carlo
simulations are reproduced locally in this module. Existing frontend leaf
adapters are not imported or called.

Donor ``probabilities``, ``confidence``, ``method``, and ``report`` fields have
no native single-ticket counterpart and are not invented here.
"""

from __future__ import annotations

import math
import random
from collections import Counter
from typing import Final, Literal, Protocol

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import BetAdapter, CausalDrawRow

_WEIGHTED_ID: Final = "legacy_biglotto__frontend_unified_ensemble_weighted__8f1183a9d8a7"
_COMBINED_ID: Final = "legacy_biglotto__frontend_unified_ensemble_combined__8f1183a9d8a7"
_ADVANCED_ID: Final = "legacy_biglotto__frontend_unified_ensemble_advanced__8f1183a9d8a7"
_MIN_NUMBER: Final = 1
_MAX_NUMBER: Final = 49
_PICK_COUNT: Final = 6
_SIMULATION_COUNT: Final = 10_000
_TREND_LAMBDA: Final = 0.05
_BOOSTING_LEARNING_RATE: Final = 0.3
_BOOSTING_ROUNDS: Final = 3
_NUMBER_RANGE: Final = range(_MIN_NUMBER, _MAX_NUMBER + 1)

EnsembleMode = Literal[
    "weighted",
    "boosting",
    "combined",
    "cooccurrence",
    "feature_weighted",
    "advanced",
]


class _RandomSource(Protocol):
    """The one random operation used by the donor's ``Math.random`` calls."""

    def random(self) -> float:
        """Return one unseeded value in the half-open interval [0, 1)."""

        ...


def _frequency_map(newest_first: tuple[CausalDrawRow, ...]) -> dict[int, int]:
    """Sync stub for donor ``calculateFrequency(data)`` on newest-first rows."""

    frequency = {number: 0 for number in _NUMBER_RANGE}
    frequency.update(
        Counter(number for row in newest_first for number in row.numbers)
    )
    return frequency


def _missing_map(newest_first: tuple[CausalDrawRow, ...]) -> dict[int, int]:
    """Newest-first first-hit index, else ``n``, matching the donor stub."""

    history_length = len(newest_first)
    missing: dict[int, int] = {}
    for number in _NUMBER_RANGE:
        missing[number] = history_length
        for index, row in enumerate(newest_first):
            if number in row.numbers:
                missing[number] = index
                break
    return missing


def _frequency_probabilities(
    newest_first: tuple[CausalDrawRow, ...],
) -> dict[int, float]:
    """Donor ``FrequencyStrategy.predict`` probability vector."""

    history_length = len(newest_first)
    frequency = _frequency_map(newest_first)
    return {
        number: frequency[number] / history_length for number in _NUMBER_RANGE
    }


def _trend_probabilities(
    newest_first: tuple[CausalDrawRow, ...],
) -> dict[int, float]:
    """Donor ``TrendStrategy.predict`` exponential-decay probability vector."""

    weighted_frequency = {number: 0.0 for number in _NUMBER_RANGE}
    for age, row in enumerate(newest_first):
        weight = math.exp(-_TREND_LAMBDA * age)
        for number in row.numbers:
            if number in weighted_frequency:
                weighted_frequency[number] += weight
    total_weight = sum(weighted_frequency.values())
    return {
        number: weighted_frequency[number] / total_weight for number in _NUMBER_RANGE
    }


def _markov_probabilities(
    newest_first: tuple[CausalDrawRow, ...],
) -> dict[int, float]:
    """Donor ``MarkovStrategy.predict`` transition probability vector."""

    transition_matrix = {
        current: {next_number: 0 for next_number in _NUMBER_RANGE}
        for current in _NUMBER_RANGE
    }
    for index in range(len(newest_first) - 1, 0, -1):
        current_draw = newest_first[index].numbers
        next_draw = newest_first[index - 1].numbers
        for current_number in current_draw:
            for next_number in next_draw:
                transition_matrix[current_number][next_number] += 1

    last_draw = newest_first[0].numbers
    next_probabilities = {number: 0.0 for number in _NUMBER_RANGE}
    for previous_number in last_draw:
        transitions = transition_matrix[previous_number]
        total_transitions = sum(transitions.values()) or 1
        for next_number in _NUMBER_RANGE:
            next_probabilities[next_number] += (
                transitions[next_number] / total_transitions
            )

    total_probability = sum(next_probabilities.values())
    if total_probability > 0:
        return {
            number: probability / total_probability
            for number, probability in next_probabilities.items()
        }
    uniform = 1 / (_MAX_NUMBER - _MIN_NUMBER + 1)
    return dict.fromkeys(next_probabilities, uniform)


def _monte_carlo_probabilities(
    newest_first: tuple[CausalDrawRow, ...],
    rng: _RandomSource,
) -> dict[int, float]:
    """Donor ``MonteCarloStrategy.predict`` inclusion-rate vector."""

    frequency = _frequency_map(newest_first)
    history_length = len(newest_first)
    pool: list[int] = []
    for number in _NUMBER_RANGE:
        weight = 1 + (frequency[number] / history_length) * 10
        pool.extend([number] * math.floor(weight * 10))

    simulation_results = {number: 0 for number in _NUMBER_RANGE}
    for _ in range(_SIMULATION_COUNT):
        simulated_draw: set[int] = set()
        while len(simulated_draw) < _PICK_COUNT:
            random_index = math.floor(rng.random() * len(pool))
            simulated_draw.add(pool[random_index])
        for number in simulated_draw:
            simulation_results[number] += 1
    return {
        number: count / _SIMULATION_COUNT
        for number, count in simulation_results.items()
    }


def _deviation_probabilities(
    newest_first: tuple[CausalDrawRow, ...],
) -> dict[int, float]:
    """Donor ``DeviationStrategy.predict`` z-score probability vector."""

    frequency = _frequency_map(newest_first)
    total_numbers = _MAX_NUMBER - _MIN_NUMBER + 1
    expected_frequency = len(newest_first) * _PICK_COUNT / total_numbers
    sum_squared_difference = sum(
        (frequency[number] - expected_frequency) ** 2 for number in _NUMBER_RANGE
    )
    standard_deviation = math.sqrt(sum_squared_difference / total_numbers)

    scores: dict[int, float] = {}
    for number in _NUMBER_RANGE:
        z_score = (
            (frequency[number] - expected_frequency) / standard_deviation
            if standard_deviation > 0
            else 0.0
        )
        if z_score < -1.5:
            score = 0.8 + abs(z_score) * 0.1
        elif z_score > 2.0:
            score = 0.2
        elif z_score > 0.5 and z_score < 1.5:
            score = 0.6 + z_score * 0.1
        else:
            score = 0.4
        scores[number] = score

    total_score = sum(scores.values())
    if total_score > 0:
        return {number: score / total_score for number, score in scores.items()}
    uniform = 1 / total_numbers
    return {number: uniform for number in _NUMBER_RANGE}


def _top_ticket(probabilities: dict[int, float]) -> tuple[int, ...]:
    """Descending probability, ascending integer-key tie-break, then sort."""

    ranked = sorted(
        probabilities.items(),
        key=lambda item: (-item[1], item[0]),
    )[:_PICK_COUNT]
    return tuple(sorted(number for number, _probability in ranked))


def _normalize(probabilities: dict[int, float], *, zero_guard: bool) -> dict[int, float]:
    """Divide by the vector sum; ``zero_guard`` matches donor ``|| 1``."""

    total = sum(probabilities.values())
    if zero_guard:
        total = total or 1
    return {number: value / total for number, value in probabilities.items()}


def _weighted_probabilities(
    newest_first: tuple[CausalDrawRow, ...],
    rng: _RandomSource,
) -> dict[int, float]:
    """Donor ``predictWeighted`` including sequential leaf order and truthy skip."""

    leaf_vectors = (
        (_frequency_probabilities(newest_first), 1.2),
        (_trend_probabilities(newest_first), 1.2),
        (_markov_probabilities(newest_first), 1.3),
        (_monte_carlo_probabilities(newest_first, rng), 1.2),
        (_deviation_probabilities(newest_first), 1.3),
    )
    totals = {number: 0.0 for number in _NUMBER_RANGE}
    for probabilities, weight in leaf_vectors:
        for number in _NUMBER_RANGE:
            leaf_probability = probabilities[number]
            if leaf_probability:
                totals[number] += leaf_probability * weight
    return _normalize(totals, zero_guard=True)


def _boosting_probabilities(
    newest_first: tuple[CausalDrawRow, ...],
) -> dict[int, float]:
    """Donor ``predictBoosting`` (Frequency/Trend/Markov + missing only)."""

    frequency = _frequency_probabilities(newest_first)
    trend = _trend_probabilities(newest_first)
    markov = _markov_probabilities(newest_first)
    missing = _missing_map(newest_first)
    max_missing = max(missing.values()) or 1
    probabilities = {number: 1 / _MAX_NUMBER for number in _NUMBER_RANGE}
    for _round in range(_BOOSTING_ROUNDS):
        for number in _NUMBER_RANGE:
            average = (
                trend[number] * 0.3
                + (missing[number] / max_missing) * 0.2
                + markov[number] * 0.3
                + frequency[number] * 0.2
            )
            probabilities[number] += _BOOSTING_LEARNING_RATE * (
                average - probabilities[number]
            )
    return _normalize(probabilities, zero_guard=False)


def _combined_probabilities(
    newest_first: tuple[CausalDrawRow, ...],
) -> dict[int, float]:
    """Donor ``predictCombined``. ``tail: 0.15`` is assigned and never applied."""

    history_length = len(newest_first)
    frequency = {number: 0 for number in _NUMBER_RANGE}
    weighted = {number: 0.0 for number in _NUMBER_RANGE}
    missing = _missing_map(newest_first)
    for age, row in enumerate(newest_first):
        exp_weight = math.exp(-_TREND_LAMBDA * age)
        for number in row.numbers:
            frequency[number] += 1
            weighted[number] += exp_weight

    is_small_sample = history_length < 50
    is_large_sample = history_length > 300
    weights = {
        "frequency": 0.40 if is_large_sample else 0.25 if is_small_sample else 0.35,
        "trend": 0.40 if is_small_sample else 0.25 if is_large_sample else 0.30,
        "missing": 0.20,
        "tail": 0.15,
    }

    max_missing = max(missing.values()) or 1
    total_weighted = sum(weighted.values()) or 1
    probabilities: dict[int, float] = {}
    for number in _NUMBER_RANGE:
        freq_score = (frequency[number] / history_length) * weights["frequency"]
        trend_score = (weighted[number] / total_weighted) * weights["trend"]
        missing_score = (missing[number] / max_missing) * weights["missing"]
        probabilities[number] = freq_score + trend_score + missing_score
    return _normalize(probabilities, zero_guard=False)


def _cooccurrence_probabilities(
    newest_first: tuple[CausalDrawRow, ...],
) -> dict[int, float]:
    """Donor ``predictCoOccurrence`` using ``data[0]`` as newest leaders."""

    leaders = newest_first[0].numbers
    cooccurrence = {number: 0 for number in _NUMBER_RANGE}
    for row in newest_first:
        leaders_in_draw = [number for number in row.numbers if number in leaders]
        if leaders_in_draw:
            for number in row.numbers:
                if number not in leaders:
                    cooccurrence[number] += len(leaders_in_draw)
    total_score = sum(cooccurrence.values())
    if total_score > 0:
        return {
            number: cooccurrence[number] / total_score for number in _NUMBER_RANGE
        }
    return {number: 0.0 for number in _NUMBER_RANGE}


def _tail_bonus(newest_first: tuple[CausalDrawRow, ...]) -> dict[int, float]:
    """Donor ``getTailBonus``."""

    tail_counts = {digit: 0 for digit in range(10)}
    for row in newest_first:
        for number in row.numbers:
            tail_counts[number % 10] += 1
    total = len(newest_first) * _PICK_COUNT
    return {
        number: tail_counts[number % 10] / total for number in _NUMBER_RANGE
    }


def _feature_weighted_probabilities(
    newest_first: tuple[CausalDrawRow, ...],
) -> dict[int, float]:
    """Donor ``predictFeatureWeighted`` with ball-vs-candidate zone split."""

    history_length = len(newest_first)
    frequency = _frequency_map(newest_first)
    missing = _missing_map(newest_first)
    max_missing = max(missing.values()) or 1
    tail_bonus = _tail_bonus(newest_first)

    zone_counts = {zone: 0 for zone in range(5)}
    for row in newest_first:
        for number in row.numbers:
            zone_counts[math.floor((number - 1) / 10)] += 1
    average_per_zone = (history_length * _PICK_COUNT) / 5

    odd_count = sum(
        1 for row in newest_first for number in row.numbers if number % 2 != 0
    )
    total_nums = history_length * _PICK_COUNT
    odd_ratio = odd_count / total_nums

    recent_window = min(20, history_length)
    recent_frequency = {number: 0 for number in _NUMBER_RANGE}
    for index in range(recent_window):
        for number in newest_first[index].numbers:
            recent_frequency[number] += 1

    probabilities: dict[int, float] = {}
    for number in _NUMBER_RANGE:
        freq_score = (frequency[number] / history_length) * 0.25
        missing_score = (missing[number] / max_missing) * 0.20
        tail_score = (tail_bonus.get(number) or 0) * 0.15
        zone_index = math.floor((number - 1) / 10)
        zone_count = zone_counts.get(zone_index) or 0
        zone_score = (average_per_zone / (zone_count + 1)) * 0.15 / average_per_zone
        odd_even_score = 0.0
        if (number % 2 == 1 and odd_ratio < 0.5) or (
            number % 2 == 0 and odd_ratio > 0.5
        ):
            odd_even_score = 0.1
        trend_score = (recent_frequency[number] / recent_window) * 0.15
        probabilities[number] = (
            freq_score
            + missing_score
            + tail_score
            + zone_score
            + odd_even_score
            + trend_score
        )
    return _normalize(probabilities, zero_guard=False)


def ticket_for_mode(
    newest_first: tuple[CausalDrawRow, ...],
    mode: EnsembleMode,
    rng: _RandomSource | None = None,
) -> tuple[int, ...]:
    """Reproduce ``UnifiedEnsembleStrategy.predict`` for one newest-first window."""

    resolved: EnsembleMode
    if mode in {"weighted", "advanced"}:
        resolved = "weighted"
    elif mode in {
        "boosting",
        "combined",
        "cooccurrence",
        "feature_weighted",
    }:
        resolved = mode
    else:
        resolved = "weighted"

    if resolved == "boosting":
        return _top_ticket(_boosting_probabilities(newest_first))
    if resolved == "combined":
        return _top_ticket(_combined_probabilities(newest_first))
    if resolved == "cooccurrence":
        return _top_ticket(_cooccurrence_probabilities(newest_first))
    if resolved == "feature_weighted":
        return _top_ticket(_feature_weighted_probabilities(newest_first))
    source = random if rng is None else rng
    return _top_ticket(_weighted_probabilities(newest_first, source))


def _from_oldest_first(
    history: tuple[CausalDrawRow, ...],
    mode: EnsembleMode,
    rng: _RandomSource | None = None,
) -> tuple[int, ...]:
    """Reverse LottoLab oldest-first history, then apply donor scoring."""

    return ticket_for_mode(tuple(reversed(history)), mode, rng)


class BigLottoFrontendUnifiedEnsembleWeightedAdapter(BetAdapter):
    """Reproduce ``UnifiedEnsembleStrategy`` mode ``weighted`` for Big Lotto."""

    strategy_id = _WEIGHTED_ID
    strategy_name = "大樂透 Frontend Unified Ensemble Weighted"
    strategy_version = "v0.1"
    min_history = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)

    def __init__(self, rng: _RandomSource | None = None) -> None:
        self._rng: _RandomSource = random if rng is None else rng

    def _predict(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[int, ...]:
        del lottery_type
        return _from_oldest_first(history, "weighted", self._rng)


class BigLottoFrontendUnifiedEnsembleCombinedAdapter(BetAdapter):
    """Reproduce ``UnifiedEnsembleStrategy`` mode ``combined`` for Big Lotto."""

    strategy_id = _COMBINED_ID
    strategy_name = "大樂透 Frontend Unified Ensemble Combined"
    strategy_version = "v0.1"
    min_history = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)

    def _predict(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[int, ...]:
        del lottery_type
        return _from_oldest_first(history, "combined")


class BigLottoFrontendUnifiedEnsembleAdvancedAdapter(BetAdapter):
    """Reproduce ``ensemble_advanced``: donor default, which is ``predictWeighted``."""

    strategy_id = _ADVANCED_ID
    strategy_name = "大樂透 Frontend Unified Ensemble Advanced"
    strategy_version = "v0.1"
    min_history = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)

    def __init__(self, rng: _RandomSource | None = None) -> None:
        self._rng: _RandomSource = random if rng is None else rng

    def _predict(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[int, ...]:
        del lottery_type
        return _from_oldest_first(history, "advanced", self._rng)


__all__ = [
    "BigLottoFrontendUnifiedEnsembleAdvancedAdapter",
    "BigLottoFrontendUnifiedEnsembleCombinedAdapter",
    "BigLottoFrontendUnifiedEnsembleWeightedAdapter",
    "ticket_for_mode",
]
