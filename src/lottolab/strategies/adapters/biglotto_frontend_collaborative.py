"""Target-native port of the legacy frontend Collaborative strategy.

The donor is ``LotteryNewMeraged/src/engine/strategies/CollaborativeStrategy.js``.
It composes eleven expert results whose probability vectors and confidence values
are load-bearing in collaborative voting. LottoLab's public leaf adapters expose
only tickets, so this R18 adapter freezes the donor-local expert calculations
instead of changing the protected R16/R17 or leaf-adapter contracts.

Frontend history is newest-first; LottoLab causal history is oldest-first and is
reversed once at the adapter boundary. All stochastic experts share one unseeded
process-global random stream, matching the donor's global ``Math.random`` call
order. The constructor seam is injectable only for executable parity tests.
"""

from __future__ import annotations

import math
import random
from collections import Counter
from dataclasses import dataclass
from typing import Final, Literal, Protocol

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import BetAdapter, CausalDrawRow

_STRATEGY_ID: Final = "legacy_biglotto__frontend_collaborative_hybrid__97d79db161ba"
_MIN_NUMBER: Final = 1
_MAX_NUMBER: Final = 49
_PICK_COUNT: Final = 6
_SIMULATION_COUNT: Final = 10_000
_RANDOM_FOREST_TREES: Final = 50
_GENETIC_POPULATION: Final = 50
_GENETIC_GENERATIONS: Final = 30
_TREND_LAMBDA: Final = 0.05
_NUMBER_RANGE: Final = range(_MIN_NUMBER, _MAX_NUMBER + 1)

CollaborativeMode = Literal["relay", "cooperative", "hybrid"]


class _RandomSource(Protocol):
    """The one operation used by every donor ``Math.random`` call."""

    def random(self) -> float:
        """Return one unseeded value in the half-open interval [0, 1)."""

        ...


@dataclass(frozen=True, slots=True)
class CollaborativeOutcome:
    """Full donor result retained for parity; the adapter emits only ``numbers``."""

    numbers: tuple[int, ...]
    probabilities: dict[int, float]
    confidence: float
    method: str
    report: str


@dataclass(frozen=True, slots=True)
class _ModelOutcome:
    numbers: tuple[int, ...]
    probabilities: dict[int, float]
    confidence: float


@dataclass(frozen=True, slots=True)
class _ExpertResult:
    name: str
    group: str
    weight: float
    numbers: tuple[int, ...]
    probabilities: dict[int, float]
    confidence: float


@dataclass(frozen=True, slots=True)
class _Consensus:
    level: float
    high_consensus: tuple[int, ...]
    low_consensus: tuple[int, ...]


def _js_round(value: float) -> float:
    """Match JavaScript ``Math.round`` for the donor's non-negative values."""

    if math.isnan(value):
        return value
    return float(math.floor(value + 0.5))


def _ranked_numbers(scores: dict[int, float], top_n: int) -> list[int]:
    """JS integer-key enumeration followed by stable descending-score sorting."""

    return sorted(scores, key=lambda number: (-scores[number], number))[:top_n]


def _top_ticket(probabilities: dict[int, float]) -> tuple[int, ...]:
    return tuple(sorted(_ranked_numbers(probabilities, _PICK_COUNT)))


def _frequency_map(newest_first: tuple[CausalDrawRow, ...]) -> dict[int, int]:
    frequency = {number: 0 for number in _NUMBER_RANGE}
    frequency.update(Counter(number for row in newest_first for number in row.numbers))
    return frequency


def _missing_map(newest_first: tuple[CausalDrawRow, ...]) -> dict[int, int]:
    history_length = len(newest_first)
    missing: dict[int, int] = {}
    for number in _NUMBER_RANGE:
        missing[number] = history_length
        for index, row in enumerate(newest_first):
            if number in row.numbers:
                missing[number] = index
                break
    return missing


def _normalized(probabilities: dict[int, float], *, zero_guard: bool) -> dict[int, float]:
    total = sum(probabilities.values())
    if zero_guard:
        total = total or 1.0
    return {number: value / total for number, value in probabilities.items()}


def _frequency_outcome(newest_first: tuple[CausalDrawRow, ...]) -> _ModelOutcome:
    frequency = _frequency_map(newest_first)
    history_length = len(newest_first)
    probabilities = {
        number: frequency[number] / history_length for number in _NUMBER_RANGE
    }
    numbers = _top_ticket(probabilities)
    top_probability_sum = sum(probabilities[number] for number in numbers)
    expected_sum = (1 / len(_NUMBER_RANGE)) * _PICK_COUNT
    confidence = min(_js_round((top_probability_sum / expected_sum) * 50), 95.0)
    return _ModelOutcome(numbers, probabilities, confidence)


def _trend_outcome(newest_first: tuple[CausalDrawRow, ...]) -> _ModelOutcome:
    weighted_frequency = {number: 0.0 for number in _NUMBER_RANGE}
    for age, row in enumerate(newest_first):
        weight = math.exp(-_TREND_LAMBDA * age)
        for number in row.numbers:
            if number in weighted_frequency:
                weighted_frequency[number] += weight
    total_weight = sum(weighted_frequency.values())
    probabilities = {
        number: weighted_frequency[number] / total_weight for number in _NUMBER_RANGE
    }
    return _ModelOutcome(_top_ticket(probabilities), probabilities, 75.0)


def _combined_outcome(newest_first: tuple[CausalDrawRow, ...]) -> _ModelOutcome:
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
    frequency_weight = 0.40 if is_large_sample else 0.25 if is_small_sample else 0.35
    trend_weight = 0.40 if is_small_sample else 0.25 if is_large_sample else 0.30
    missing_weight = 0.20
    # The donor also assigns tail: 0.15, but never applies it.

    max_missing = max(missing.values()) or 1
    total_weighted = sum(weighted.values()) or 1.0
    probabilities: dict[int, float] = {}
    for number in _NUMBER_RANGE:
        frequency_score = (frequency[number] / history_length) * frequency_weight
        trend_score = (weighted[number] / total_weighted) * trend_weight
        missing_score = (missing[number] / max_missing) * missing_weight
        probabilities[number] = frequency_score + trend_score + missing_score
    probabilities = _normalized(probabilities, zero_guard=False)
    return _ModelOutcome(_top_ticket(probabilities), probabilities, 85.0)


def _bayesian_outcome(newest_first: tuple[CausalDrawRow, ...]) -> _ModelOutcome:
    history_length = len(newest_first)
    frequency = _frequency_map(newest_first)
    prior_probability = {
        number: frequency[number] / (history_length * _PICK_COUNT)
        for number in _NUMBER_RANGE
    }
    last_draw = newest_first[0].numbers

    transition_counts: dict[int, dict[int, int]] = {}
    for index in range(history_length - 1):
        current = newest_first[index].numbers
        previous = newest_first[index + 1].numbers
        for previous_number in previous:
            transitions = transition_counts.setdefault(previous_number, {})
            for current_number in current:
                transitions[current_number] = transitions.get(current_number, 0) + 1

    probabilities: dict[int, float] = {}
    for number in _NUMBER_RANGE:
        likelihood_score = 0.0
        for previous_number in last_draw:
            count = transition_counts.get(previous_number, {}).get(number, 0)
            total_occurrences = frequency[previous_number] or 1
            likelihood_score += count / total_occurrences
        probabilities[number] = prior_probability[number] * (1 + likelihood_score)

    total_probability = sum(probabilities.values())
    if total_probability > 0:
        probabilities = {
            number: probability / total_probability
            for number, probability in probabilities.items()
        }
    else:
        uniform = 1 / len(_NUMBER_RANGE)
        probabilities = {number: uniform for number in _NUMBER_RANGE}
    return _ModelOutcome(_top_ticket(probabilities), probabilities, 85.0)


def _deviation_outcome(newest_first: tuple[CausalDrawRow, ...]) -> _ModelOutcome:
    frequency = _frequency_map(newest_first)
    total_numbers = len(_NUMBER_RANGE)
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
        elif 0.5 < z_score < 1.5:
            score = 0.6 + z_score * 0.1
        else:
            score = 0.4
        scores[number] = score

    probabilities = _normalized(scores, zero_guard=False)
    return _ModelOutcome(_top_ticket(probabilities), probabilities, 76.0)


def _monte_carlo_outcome(
    newest_first: tuple[CausalDrawRow, ...],
    rng: _RandomSource,
) -> _ModelOutcome:
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

    probabilities = {
        number: count / _SIMULATION_COUNT
        for number, count in simulation_results.items()
    }
    return _ModelOutcome(_top_ticket(probabilities), probabilities, 75.0)


def _markov_outcome(newest_first: tuple[CausalDrawRow, ...]) -> _ModelOutcome:
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
    probabilities = {number: 0.0 for number in _NUMBER_RANGE}
    for previous_number in last_draw:
        transitions = transition_matrix[previous_number]
        total_transitions = sum(transitions.values()) or 1
        for next_number in _NUMBER_RANGE:
            probabilities[next_number] += transitions[next_number] / total_transitions

    total_probability = sum(probabilities.values())
    if total_probability > 0:
        probabilities = {
            number: probability / total_probability
            for number, probability in probabilities.items()
        }
    else:
        uniform = 1 / len(_NUMBER_RANGE)
        probabilities = {number: uniform for number in _NUMBER_RANGE}
    return _ModelOutcome(_top_ticket(probabilities), probabilities, 78.0)


def _cooccurrence_outcome(newest_first: tuple[CausalDrawRow, ...]) -> _ModelOutcome:
    leaders = newest_first[0].numbers
    cooccurrence = {number: 0 for number in _NUMBER_RANGE}
    for row in newest_first:
        leaders_in_draw = [number for number in row.numbers if number in leaders]
        if leaders_in_draw:
            for number in row.numbers:
                if number not in leaders:
                    cooccurrence[number] += len(leaders_in_draw)

    total_score = sum(cooccurrence.values())
    probabilities = {
        number: cooccurrence[number] / total_score if total_score > 0 else 0.0
        for number in _NUMBER_RANGE
    }
    return _ModelOutcome(_top_ticket(probabilities), probabilities, 72.0)


def _tail_bonus(newest_first: tuple[CausalDrawRow, ...]) -> dict[int, float]:
    tail_counts = {digit: 0 for digit in range(10)}
    for row in newest_first:
        for number in row.numbers:
            tail_counts[number % 10] += 1
    total = len(newest_first) * _PICK_COUNT
    return {
        number: tail_counts[number % 10] / total for number in _NUMBER_RANGE
    }


def _feature_weighted_outcome(
    newest_first: tuple[CausalDrawRow, ...],
) -> _ModelOutcome:
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
    odd_ratio = odd_count / (history_length * _PICK_COUNT)

    recent_window = min(20, history_length)
    recent_frequency = {number: 0 for number in _NUMBER_RANGE}
    for index in range(recent_window):
        for number in newest_first[index].numbers:
            recent_frequency[number] += 1

    probabilities: dict[int, float] = {}
    for number in _NUMBER_RANGE:
        frequency_score = (frequency[number] / history_length) * 0.25
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
            frequency_score
            + missing_score
            + tail_score
            + zone_score
            + odd_even_score
            + trend_score
        )

    probabilities = _normalized(probabilities, zero_guard=False)
    return _ModelOutcome(_top_ticket(probabilities), probabilities, 82.0)


def _random_forest_outcome(
    newest_first: tuple[CausalDrawRow, ...],
    rng: _RandomSource,
) -> _ModelOutcome:
    frequency = _frequency_map(newest_first)
    missing = _missing_map(newest_first)
    total_draws = len(newest_first)
    recent_frequency = _frequency_map(newest_first[:10])

    zone_counts = {zone: 0 for zone in range(5)}
    for row in newest_first:
        for number in row.numbers:
            zone_counts[math.floor((number - 1) / 10)] += 1
    average_per_zone = (total_draws * _PICK_COUNT) / 5

    tree_predictions: list[dict[int, float]] = []
    for _ in range(_RANDOM_FOREST_TREES):
        frequency_gate = rng.random()
        frequency_weight = rng.random() * 0.3 * 2 if frequency_gate > 0.2 else 0.0
        missing_gate = rng.random()
        missing_weight = rng.random() * 0.2 * 2 if missing_gate > 0.2 else 0.0
        recent_gate = rng.random()
        recent_weight = rng.random() * 0.4 * 2 if recent_gate > 0.2 else 0.0
        zone_gate = rng.random()
        zone_weight = rng.random() * 0.1 * 3 if zone_gate > 0.5 else 0.0
        random_weight = rng.random() * 0.1

        if frequency_weight + missing_weight + recent_weight == 0:
            frequency_weight = 0.3

        tree_probability: dict[int, float] = {}
        for number in _NUMBER_RANGE:
            score = 0.0
            if frequency_weight > 0:
                score += (frequency[number] / total_draws) * frequency_weight
            if missing_weight > 0:
                missing_value = missing[number]
                if 5 <= missing_value <= 15:
                    missing_score = 1.0
                elif missing_value > 15:
                    missing_score = 0.4
                else:
                    missing_score = 0.2
                score += missing_score * missing_weight
            if recent_weight > 0:
                score += (recent_frequency[number] / 10) * recent_weight
            if zone_weight > 0:
                zone_index = math.floor((number - 1) / 10)
                if zone_counts[zone_index] < average_per_zone:
                    score += 0.5 * zone_weight
            score += rng.random() * random_weight
            tree_probability[number] = score
        tree_predictions.append(tree_probability)

    probabilities = {
        number: sum(tree[number] for tree in tree_predictions) / _RANDOM_FOREST_TREES
        for number in _NUMBER_RANGE
    }
    probabilities = _normalized(probabilities, zero_guard=True)
    return _ModelOutcome(_top_ticket(probabilities), probabilities, 85.0)


def _random_selection(
    range_max: int,
    pick_count: int,
    frequency: dict[int, int],
    rng: _RandomSource,
) -> list[int]:
    selected: list[int] = []
    selected_set: set[int] = set()
    frequency_sum = sum(frequency[number] for number in range(1, range_max + 1))

    while len(selected) < pick_count:
        remaining_random = rng.random() * frequency_sum
        for number in range(1, range_max + 1):
            remaining_random -= frequency[number]
            if remaining_random <= 0 and number not in selected_set:
                selected.append(number)
                selected_set.add(number)
                break

        if len(selected) < pick_count:
            remaining = [
                number for number in range(1, range_max + 1) if number not in selected_set
            ]
            if remaining:
                selected_number = remaining[math.floor(rng.random() * len(remaining))]
                selected.append(selected_number)
                selected_set.add(selected_number)
    return selected


def _calculate_fitness(
    individual: list[int],
    frequency: dict[int, int],
    missing: dict[int, int],
) -> float:
    fitness = sum(frequency[number] * 0.3 for number in individual)
    for number in individual:
        if 5 <= missing[number] <= 15:
            fitness += 10
    odd_count = sum(1 for number in individual if number % 2 == 1)
    if odd_count == 3:
        fitness += 20
    elif odd_count in (2, 4):
        fitness += 10
    fitness += len({math.floor((number - 1) / 10) for number in individual}) * 5
    if 120 <= sum(individual) <= 180:
        fitness += 15
    return fitness


def _tournament_selection(
    population: list[list[int]],
    fitness: list[float],
    rng: _RandomSource,
) -> list[int]:
    first_index = math.floor(rng.random() * len(population))
    second_index = math.floor(rng.random() * len(population))
    selected = (
        population[first_index]
        if fitness[first_index] > fitness[second_index]
        else population[second_index]
    )
    return list(selected)


def _crossover(parent_one: list[int], parent_two: list[int], rng: _RandomSource) -> list[int]:
    child: list[int] = []
    used: set[int] = set()
    all_genes = list(parent_one) + list(parent_two)
    while len(child) < _PICK_COUNT and all_genes:
        gene_index = math.floor(rng.random() * len(all_genes))
        gene = all_genes.pop(gene_index)
        if gene not in used:
            child.append(gene)
            used.add(gene)
    return child


def _mutate(individual: list[int], range_max: int, rng: _RandomSource) -> list[int]:
    mutated = list(individual)
    index = math.floor(rng.random() * len(mutated))
    while True:
        new_gene = math.floor(rng.random() * range_max) + 1
        if new_gene not in mutated:
            break
    mutated[index] = new_gene
    return mutated


def _genetic_outcome(
    newest_first: tuple[CausalDrawRow, ...],
    rng: _RandomSource,
) -> _ModelOutcome:
    frequency = _frequency_map(newest_first)
    missing = _missing_map(newest_first)
    population = [
        _random_selection(_MAX_NUMBER, _PICK_COUNT, frequency, rng)
        for _ in range(_GENETIC_POPULATION)
    ]

    for _ in range(_GENETIC_GENERATIONS):
        fitness = [
            _calculate_fitness(individual, frequency, missing)
            for individual in population
        ]
        new_population: list[list[int]] = []
        for _ in range(_GENETIC_POPULATION):
            parent_one = _tournament_selection(population, fitness, rng)
            parent_two = _tournament_selection(population, fitness, rng)
            child = (
                _crossover(parent_one, parent_two, rng)
                if rng.random() > 0.2
                else list(parent_one)
            )
            if rng.random() < 0.1:
                child = _mutate(child, _MAX_NUMBER, rng)
            new_population.append(child)
        population = new_population

    final_fitness = [
        _calculate_fitness(individual, frequency, missing)
        for individual in population
    ]
    best_index = final_fitness.index(max(final_fitness))
    best_individual = population[best_index]

    probabilities = {number: 0.0 for number in _NUMBER_RANGE}
    for index, individual in enumerate(population):
        weight = final_fitness[index]
        for number in individual:
            probabilities[number] += weight
    total_probability = sum(probabilities.values())
    if total_probability > 0:
        probabilities = {
            number: probability / total_probability
            for number, probability in probabilities.items()
        }
    return _ModelOutcome(tuple(sorted(best_individual)), probabilities, 81.0)


def _model_outcome(
    name: str,
    newest_first: tuple[CausalDrawRow, ...],
    rng: _RandomSource,
) -> _ModelOutcome:
    if name == "Frequency":
        return _frequency_outcome(newest_first)
    if name == "Trend":
        return _trend_outcome(newest_first)
    if name == "Combined":
        return _combined_outcome(newest_first)
    if name == "Bayesian":
        return _bayesian_outcome(newest_first)
    if name == "Deviation":
        return _deviation_outcome(newest_first)
    if name == "MonteCarlo":
        return _monte_carlo_outcome(newest_first, rng)
    if name == "Markov":
        return _markov_outcome(newest_first)
    if name == "CoOccurrence":
        return _cooccurrence_outcome(newest_first)
    if name == "FeatureWeighted":
        return _feature_weighted_outcome(newest_first)
    if name == "RandomForest":
        return _random_forest_outcome(newest_first, rng)
    if name == "GeneticAlgorithm":
        return _genetic_outcome(newest_first, rng)
    raise KeyError(name)


_EXPERT_GROUPS: Final[dict[str, tuple[tuple[str, float], ...]]] = {
    "statistical": (("Frequency", 1.0), ("Trend", 1.2), ("Combined", 1.5)),
    "probabilistic": (("Bayesian", 1.3), ("Deviation", 1.2), ("MonteCarlo", 1.4)),
    "sequential": (("Markov", 1.3), ("CoOccurrence", 1.1)),
    "feature": (("FeatureWeighted", 1.4), ("RandomForest", 1.5)),
    "optimizer": (("GeneticAlgorithm", 1.6),),
}


def _run_expert_groups(
    group_names: tuple[str, ...],
    newest_first: tuple[CausalDrawRow, ...],
    rng: _RandomSource,
) -> list[_ExpertResult]:
    results: list[_ExpertResult] = []
    for group_name in group_names:
        group = _EXPERT_GROUPS.get(group_name)
        if group is None:
            continue
        for expert_name, weight in group:
            try:
                outcome = _model_outcome(expert_name, newest_first, rng)
            except Exception:
                # The donor logs and omits one failed expert, then continues.
                continue
            results.append(
                _ExpertResult(
                    name=expert_name,
                    group=group_name,
                    weight=weight,
                    numbers=outcome.numbers,
                    probabilities=outcome.probabilities,
                    confidence=outcome.confidence,
                )
            )
    return results


def _merge_candidates(
    results: list[_ExpertResult],
    max_number: int,
    top_n: int,
) -> list[int]:
    scores = {number: 0.0 for number in range(1, max_number + 1)}
    for result in results:
        for number in range(1, max_number + 1):
            scores[number] += result.probabilities.get(number, 0.0) * result.weight
        for index, number in enumerate(result.numbers):
            scores[number] += (_PICK_COUNT - index) * result.weight * 0.5
    return _ranked_numbers(scores, top_n)


def _refine_candidates(
    candidates: list[int],
    refinement_results: list[_ExpertResult],
    top_n: int,
) -> list[int]:
    scores = {number: 0.0 for number in candidates}
    for result in refinement_results:
        for number in candidates:
            scores[number] += result.probabilities.get(number, 0.0) * result.weight
            try:
                rank = result.numbers.index(number)
            except ValueError:
                rank = -1
            if rank != -1:
                scores[number] += (_PICK_COUNT - rank) * result.weight * 0.3
    return _ranked_numbers(scores, top_n)


def _final_decision(
    candidates: list[int],
    decision_results: list[_ExpertResult],
) -> list[int]:
    scores = {number: 0.0 for number in candidates}
    for result in decision_results:
        for index, number in enumerate(result.numbers):
            if number in scores:
                scores[number] += (_PICK_COUNT - index) * result.weight

    if decision_results:
        optimizer_numbers = decision_results[0].numbers
        if all(number in candidates for number in optimizer_numbers):
            return list(optimizer_numbers)
    return _ranked_numbers(scores, _PICK_COUNT)


def _weighted_voting(
    results: list[_ExpertResult],
    max_number: int,
) -> dict[int, float]:
    votes = {number: 0.0 for number in range(1, max_number + 1)}
    for result in results:
        for number in range(1, max_number + 1):
            probability = result.probabilities.get(number, 0.0)
            votes[number] += probability * result.weight * result.confidence / 100
        for index, number in enumerate(result.numbers):
            votes[number] += (10 - index) * result.weight
    return votes


def _detect_consensus(
    results: list[_ExpertResult],
    votes: dict[int, float],
) -> _Consensus:
    top_numbers = _ranked_numbers(votes, _PICK_COUNT)
    recommendation_count = {number: 0 for number in top_numbers}
    for result in results:
        for number in top_numbers:
            if number in result.numbers:
                recommendation_count[number] += 1

    average_recommendations = sum(recommendation_count.values()) / len(top_numbers)
    consensus_level = average_recommendations / len(results)
    high_consensus = tuple(
        number
        for number in top_numbers
        if recommendation_count[number] >= len(results) * 0.5
    )
    low_consensus = tuple(
        number
        for number in top_numbers
        if recommendation_count[number] < len(results) * 0.3
    )
    return _Consensus(consensus_level, high_consensus, low_consensus)


def _balance_odd_even(
    numbers: list[int],
    candidate_votes: dict[int, float],
    current_odd_count: int,
) -> list[int]:
    need_more = current_odd_count < 3
    ranked = _ranked_numbers(candidate_votes, len(candidate_votes))
    replacement_pool = [
        number
        for number in ranked
        if (number % 2 == 1 if need_more else number % 2 == 0)
        and number not in numbers
    ]
    if not replacement_pool:
        return numbers

    result = list(numbers)
    to_replace = [
        number
        for number in numbers
        if (number % 2 == 0 if need_more else number % 2 == 1)
    ]
    to_replace.sort(key=lambda number: candidate_votes.get(number, 0.0))
    if to_replace:
        index = result.index(to_replace[0])
        result[index] = replacement_pool[0]
    return result


def _balance_zones(
    numbers: list[int],
    candidate_votes: dict[int, float],
    current_zones: set[int],
) -> list[int]:
    ranked = _ranked_numbers(candidate_votes, len(candidate_votes))
    missing_zones = [zone for zone in range(5) if zone not in current_zones]
    if not missing_zones:
        return numbers

    result = list(numbers)
    for zone in missing_zones:
        zone_numbers = [
            number
            for number in ranked
            if math.floor((number - 1) / 10) == zone and number not in result
        ]
        if zone_numbers:
            # JS ``result.sort`` mutates the order before selecting index zero.
            result.sort(key=lambda number: candidate_votes.get(number, 0.0))
            lowest_number = result[0]
            index = result.index(lowest_number)
            result[index] = zone_numbers[0]
            break
    return result


def _balance_sum(
    numbers: list[int],
    candidate_votes: dict[int, float],
    current_sum: int,
) -> list[int]:
    need_higher = current_sum < 150
    ranked = [
        number
        for number in _ranked_numbers(candidate_votes, len(candidate_votes))
        if number not in numbers
    ]
    result = list(numbers)
    for replacement in ranked:
        for index, original in enumerate(result):
            difference = replacement - original
            if (need_higher and difference > 0) or (not need_higher and difference < 0):
                new_sum = current_sum + difference
                if 120 <= new_sum <= 180:
                    result[index] = replacement
                    return result
    return result


def _apply_constraints(
    numbers: list[int],
    candidate_votes: dict[int, float],
) -> list[int]:
    optimized = list(numbers)
    odd_count = sum(1 for number in optimized if number % 2 == 1)
    if odd_count < 2 or odd_count > 4:
        optimized = _balance_odd_even(optimized, candidate_votes, odd_count)

    zones = {math.floor((number - 1) / 10) for number in optimized}
    if len(zones) < 3:
        optimized = _balance_zones(optimized, candidate_votes, zones)

    current_sum = sum(optimized)
    if current_sum < 120 or current_sum > 180:
        optimized = _balance_sum(optimized, candidate_votes, current_sum)
    return optimized


def _vote_probabilities(votes: dict[int, float]) -> dict[int, float]:
    total = sum(votes.values())
    if total == 0:
        return {number: math.nan for number in votes}
    return {number: vote / total for number, vote in votes.items()}


def _relay_outcome(
    newest_first: tuple[CausalDrawRow, ...],
    rng: _RandomSource,
) -> CollaborativeOutcome:
    exploration_groups = ("statistical", "probabilistic")
    exploration_results = _run_expert_groups(exploration_groups, newest_first, rng)
    exploration_candidates = _merge_candidates(exploration_results, _MAX_NUMBER, 25)

    refinement_groups = ("sequential", "feature")
    refinement_results = _run_expert_groups(refinement_groups, newest_first, rng)
    refinement_candidates = _refine_candidates(
        exploration_candidates, refinement_results, 12
    )

    decision_groups = ("optimizer",)
    decision_results = _run_expert_groups(decision_groups, newest_first, rng)
    final_numbers = _final_decision(refinement_candidates, decision_results)

    all_results = exploration_results + refinement_results + decision_results
    probabilities = _vote_probabilities(_weighted_voting(all_results, _MAX_NUMBER))
    filter_efficiency = (_MAX_NUMBER - _PICK_COUNT) / (25 - _PICK_COUNT)
    confidence = min(max(_js_round(filter_efficiency * 60 + 35), 70.0), 95.0)
    report = (
        "【接力模式】三階段協作過濾\n"
        "探索層: 25 個候選 → 精煉層: 12 個候選 → 決策層: 6 個候選\n"
        "專家組: statistical, probabilistic, sequential, feature, optimizer"
    )
    return CollaborativeOutcome(
        tuple(sorted(final_numbers)),
        probabilities,
        confidence,
        "協作預測 (接力模式)",
        report,
    )


def _cooperative_outcome(
    newest_first: tuple[CausalDrawRow, ...],
    rng: _RandomSource,
) -> CollaborativeOutcome:
    results = _run_expert_groups(tuple(_EXPERT_GROUPS), newest_first, rng)
    votes = _weighted_voting(results, _MAX_NUMBER)
    consensus = _detect_consensus(results, votes)
    final_numbers = tuple(sorted(_ranked_numbers(votes, _PICK_COUNT)))
    probabilities = _vote_probabilities(votes)

    base_confidence = consensus.level * 100
    model_bonus = min(len(results) * 2, 20)
    confidence = min(
        max(_js_round(base_confidence * 0.6 + model_bonus + 50), 65.0),
        92.0,
    )
    level = "高" if consensus.level > 0.6 else "中" if consensus.level > 0.3 else "低"
    high_numbers = ", ".join(str(number) for number in consensus.high_consensus)
    report = (
        f"【合作模式】{len(results)} 個專家模型投票\n"
        f"共識度: {level} ({consensus.level * 100:.1f}%)\n"
        f"高共識號碼: [{high_numbers}]"
    )
    return CollaborativeOutcome(
        final_numbers,
        probabilities,
        confidence,
        "協作預測 (合作模式)",
        report,
    )


def _hybrid_outcome(
    newest_first: tuple[CausalDrawRow, ...],
    rng: _RandomSource,
) -> CollaborativeOutcome:
    exploration_results = _run_expert_groups(
        ("statistical", "probabilistic"), newest_first, rng
    )
    exploration_votes = _weighted_voting(exploration_results, _MAX_NUMBER)
    candidates_25 = _ranked_numbers(exploration_votes, 25)

    refinement_results = _run_expert_groups(("sequential", "feature"), newest_first, rng)
    candidates_15 = _refine_candidates(candidates_25, refinement_results, 15)

    decision_results = _run_expert_groups(("optimizer",), newest_first, rng)
    all_results = exploration_results + refinement_results + decision_results
    final_votes = _weighted_voting(all_results, _MAX_NUMBER)
    candidate_votes = {
        number: final_votes.get(number, 0.0) for number in candidates_15
    }
    final_numbers = _ranked_numbers(candidate_votes, _PICK_COUNT)
    optimized_numbers = _apply_constraints(final_numbers, candidate_votes)
    probabilities = _vote_probabilities(final_votes)

    coverage = sum(1 for number in optimized_numbers if number in candidates_15)
    confidence = min(max(_js_round((coverage / 6) * 30 + 65), 70.0), 93.0)
    report = (
        "【混合模式】接力過濾 + 合作決策\n"
        "過濾流程: 49 → 25 → 15 → 6\n"
        f"參與模型: {len(all_results)} 個"
    )
    return CollaborativeOutcome(
        tuple(sorted(optimized_numbers)),
        probabilities,
        confidence,
        "協作預測 (混合模式)",
        report,
    )


def outcome_for_mode(
    newest_first: tuple[CausalDrawRow, ...],
    mode: str,
    rng: _RandomSource | None = None,
) -> CollaborativeOutcome:
    """Execute one donor mode; unknown values use the donor's hybrid default."""

    source = random if rng is None else rng
    if mode == "relay":
        return _relay_outcome(newest_first, source)
    if mode == "cooperative":
        return _cooperative_outcome(newest_first, source)
    return _hybrid_outcome(newest_first, source)


class BigLottoFrontendCollaborativeHybridAdapter(BetAdapter):
    """Reproduce the live/remap target ``collaborative_hybrid`` for Big Lotto."""

    strategy_id = _STRATEGY_ID
    strategy_name = "大樂透 Frontend Collaborative Hybrid"
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
        newest_first = tuple(reversed(history))
        return outcome_for_mode(newest_first, "hybrid", self._rng).numbers


__all__ = [
    "BigLottoFrontendCollaborativeHybridAdapter",
    "CollaborativeOutcome",
    "outcome_for_mode",
]
