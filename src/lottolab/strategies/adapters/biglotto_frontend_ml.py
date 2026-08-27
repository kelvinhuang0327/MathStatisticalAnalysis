"""Target-native port of the legacy frontend ML strategy.

The donor is ``LotteryNewMeraged/src/engine/strategies/MLStrategy.js``.
Frontend data is newest-first; LottoLab causal histories are oldest-first, so
each adapter reverses the validated history before applying donor scoring.
Architecture C: feature calculation, random forest decision trees, and genetic
evolution simulations are reproduced locally in this module. Existing frontend leaf
adapters are not imported or called.

Donor ``probabilities``, ``confidence``, ``method``, and ``report`` fields have
no native single-ticket counterpart and are not invented here.
"""

from __future__ import annotations

import random
from collections import Counter
from typing import Final, Literal, Protocol

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import BetAdapter, CausalDrawRow

_FEATURE_WEIGHTED_ID: Final = "legacy_biglotto__frontend_ml_features__3a4324bc2aa9"
_RANDOM_FOREST_ID: Final = "legacy_biglotto__frontend_ml_forest__3a4324bc2aa9"
_GENETIC_ID: Final = "legacy_biglotto__frontend_ml_genetic__3a4324bc2aa9"
_MIN_NUMBER: Final = 1
_MAX_NUMBER: Final = 49
_PICK_COUNT: Final = 6
_NUMBER_RANGE: Final = range(_MIN_NUMBER, _MAX_NUMBER + 1)

MLAlgorithm = Literal[
    "feature_weighted",
    "random_forest",
    "genetic",
]


class _RandomSource(Protocol):
    """The one random operation used by the donor's ``Math.random`` calls."""

    def random(self) -> float:
        """Return one unseeded value in the half-open interval [0, 1)."""
        ...


def _frequency_map(newest_first: tuple[CausalDrawRow, ...]) -> dict[int, int]:
    """Sync stub for donor ``calculateFrequency(data)`` on newest-first rows."""
    frequency = {number: 0 for number in _NUMBER_RANGE}
    frequency.update(Counter(number for row in newest_first for number in row.numbers))
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


def _predict_feature_weighted(
    newest_first: tuple[CausalDrawRow, ...],
    rng: _RandomSource,
) -> tuple[int, ...]:
    """Reproduce ``MLStrategy.predictFeatureWeighted``."""
    scores = {i: 0.0 for i in _NUMBER_RANGE}

    # Feature 1: frequency (weight = 0.3)
    frequency = _frequency_map(newest_first)
    max_freq = max(frequency.values()) if frequency else 1
    for i in _NUMBER_RANGE:
        scores[i] += (frequency[i] / max_freq) * 0.3

    # Feature 2: recent trend (weight = 0.4)
    recent_data = newest_first[:10]
    recent_freq = _frequency_map(recent_data)
    max_recent = max(recent_freq.values()) if recent_freq else 1
    for i in _NUMBER_RANGE:
        scores[i] += (recent_freq[i] / max_recent) * 0.4

    # Feature 3: missing values (weight = 0.2)
    missing = _missing_map(newest_first)
    for i in _NUMBER_RANGE:
        m = missing[i]
        if 5 <= m <= 15:
            score = 1.0
        elif m > 15:
            score = 0.5
        else:
            score = 0.2
        scores[i] += score * 0.2

    # Feature 4: random perturbation (weight = 0.1)
    for i in _NUMBER_RANGE:
        scores[i] += rng.random() * 0.1

    total_score = sum(scores.values())
    probabilities = {i: scores[i] / total_score for i in _NUMBER_RANGE}

    ranked = sorted(
        probabilities.items(),
        key=lambda item: (-item[1], item[0]),
    )[:_PICK_COUNT]
    return tuple(sorted(number for number, _ in ranked))


def _predict_random_forest(
    newest_first: tuple[CausalDrawRow, ...],
    rng: _RandomSource,
) -> tuple[int, ...]:
    """Reproduce ``MLStrategy.predictRandomForest``."""
    num_trees = 50
    frequency = _frequency_map(newest_first)
    missing = _missing_map(newest_first)
    total_draws = len(newest_first)

    recent_data = newest_first[:10]
    recent_freq = _frequency_map(recent_data)

    zone_counts = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0}
    for draw in newest_first:
        for n in draw.numbers:
            zone_counts[(n - 1) // 10] += 1
    avg_per_zone = (len(newest_first) * _PICK_COUNT) / 5

    tree_predictions: list[dict[int, float]] = []
    for _ in range(num_trees):
        tree_prob: dict[int, float] = {}

        r1 = rng.random()
        freq_w = rng.random() * 0.3 * 2 if r1 > 0.2 else 0.0

        r2 = rng.random()
        missing_w = rng.random() * 0.2 * 2 if r2 > 0.2 else 0.0

        r3 = rng.random()
        recent_w = rng.random() * 0.4 * 2 if r3 > 0.2 else 0.0

        r4 = rng.random()
        zone_w = rng.random() * 0.1 * 3 if r4 > 0.5 else 0.0

        random_w = rng.random() * 0.1

        if freq_w + missing_w + recent_w == 0.0:
            freq_w = 0.3

        for num in _NUMBER_RANGE:
            score = 0.0
            if freq_w > 0.0:
                score += (frequency[num] / total_draws) * freq_w
            if missing_w > 0.0:
                m = missing[num]
                if 5 <= m <= 15:
                    m_score = 1.0
                elif m > 15:
                    m_score = 0.4
                else:
                    m_score = 0.2
                score += m_score * missing_w
            if recent_w > 0.0:
                score += (recent_freq[num] / 10) * recent_w
            if zone_w > 0.0:
                z_idx = (num - 1) // 10
                if zone_counts[z_idx] < avg_per_zone:
                    score += 0.5 * zone_w
            score += rng.random() * random_w
            tree_prob[num] = score

        tree_predictions.append(tree_prob)

    probabilities: dict[int, float] = {}
    for i in _NUMBER_RANGE:
        avg_score = sum(tree[i] for tree in tree_predictions) / num_trees
        probabilities[i] = avg_score

    total_prob = sum(probabilities.values()) or 1.0
    for i in _NUMBER_RANGE:
        probabilities[i] /= total_prob

    ranked = sorted(
        probabilities.items(),
        key=lambda item: (-item[1], item[0]),
    )[:_PICK_COUNT]
    return tuple(sorted(number for number, _ in ranked))


def _random_selection(
    range_max: int,
    pick_count: int,
    frequency: dict[int, int],
    rng: _RandomSource,
) -> list[int]:
    """Reproduce ``MLStrategy.randomSelection`` roulette-wheel + fallback selection."""
    selected: list[int] = []
    selected_set: set[int] = set()
    freq_sum = sum(frequency[n] for n in range(1, range_max + 1))

    while len(selected) < pick_count:
        r = rng.random() * freq_sum
        for num in range(1, range_max + 1):
            r -= frequency[num]
            if r <= 0 and num not in selected_set:
                selected.append(num)
                selected_set.add(num)
                break
        if len(selected) < pick_count:
            remaining = [n for n in range(1, range_max + 1) if n not in selected_set]
            if remaining:
                pick = remaining[int(rng.random() * len(remaining))]
                selected.append(pick)
                selected_set.add(pick)
    return selected


def _calculate_fitness(
    individual: list[int],
    frequency: dict[int, int],
    missing: dict[int, int],
) -> float:
    """Reproduce ``MLStrategy.calculateFitness``."""
    fitness = 0.0
    for num in individual:
        fitness += frequency[num] * 0.3
    for num in individual:
        m = missing[num]
        if 5 <= m <= 15:
            fitness += 10.0
    odd_count = sum(1 for n in individual if n % 2 == 1)
    if odd_count == 3:
        fitness += 20.0
    elif odd_count in (2, 4):
        fitness += 10.0
    zones = set((n - 1) // 10 for n in individual)
    fitness += len(zones) * 5.0
    s = sum(individual)
    if 120 <= s <= 180:
        fitness += 15.0
    return fitness


def _tournament_selection(
    population: list[list[int]],
    fitness: list[float],
    rng: _RandomSource,
) -> list[int]:
    """Reproduce ``MLStrategy.tournamentSelection``."""
    idx1 = int(rng.random() * len(population))
    idx2 = int(rng.random() * len(population))
    return list(population[idx1]) if fitness[idx1] > fitness[idx2] else list(population[idx2])


def _crossover(
    parent1: list[int],
    parent2: list[int],
    rng: _RandomSource,
) -> list[int]:
    """Reproduce ``MLStrategy.crossover``."""
    child: list[int] = []
    used: set[int] = set()
    all_genes = list(parent1) + list(parent2)
    while len(child) < _PICK_COUNT and len(all_genes) > 0:
        r_idx = int(rng.random() * len(all_genes))
        gene = all_genes.pop(r_idx)
        if gene not in used:
            child.append(gene)
            used.add(gene)
    return child


def _mutate(
    individual: list[int],
    range_max: int,
    rng: _RandomSource,
) -> list[int]:
    """Reproduce ``MLStrategy.mutate``."""
    mutated = list(individual)
    idx = int(rng.random() * len(mutated))
    while True:
        new_gene = int(rng.random() * range_max) + 1
        if new_gene not in mutated:
            break
    mutated[idx] = new_gene
    return mutated


def _predict_genetic(
    newest_first: tuple[CausalDrawRow, ...],
    rng: _RandomSource,
) -> tuple[int, ...]:
    """Reproduce ``MLStrategy.predictGenetic``."""
    population_size = 50
    generations = 30
    frequency = _frequency_map(newest_first)
    missing = _missing_map(newest_first)

    population: list[list[int]] = []
    for _ in range(population_size):
        population.append(_random_selection(_MAX_NUMBER, _PICK_COUNT, frequency, rng))

    for _ in range(generations):
        fitness = [_calculate_fitness(ind, frequency, missing) for ind in population]
        new_population: list[list[int]] = []
        for _ in range(population_size):
            p1 = _tournament_selection(population, fitness, rng)
            p2 = _tournament_selection(population, fitness, rng)

            child = _crossover(p1, p2, rng) if rng.random() > 0.2 else list(p1)

            if rng.random() < 0.1:
                child = _mutate(child, _MAX_NUMBER, rng)

            new_population.append(child)
        population = new_population

    final_fitness = [_calculate_fitness(ind, frequency, missing) for ind in population]
    max_fit = max(final_fitness)
    best_index = final_fitness.index(max_fit)
    best_individual = population[best_index]
    return tuple(sorted(best_individual))


def ticket_for_mode(
    newest_first: tuple[CausalDrawRow, ...],
    algorithm: MLAlgorithm,
    rng: _RandomSource | None = None,
) -> tuple[int, ...]:
    """Reproduce ``MLStrategy.predict`` for one newest-first window."""
    source = random if rng is None else rng
    if algorithm == "random_forest":
        return _predict_random_forest(newest_first, source)
    if algorithm == "genetic":
        return _predict_genetic(newest_first, source)
    return _predict_feature_weighted(newest_first, source)


def _from_oldest_first(
    history: tuple[CausalDrawRow, ...],
    algorithm: MLAlgorithm,
    rng: _RandomSource | None = None,
) -> tuple[int, ...]:
    """Reverse LottoLab oldest-first history, then apply donor scoring."""
    return ticket_for_mode(tuple(reversed(history)), algorithm, rng)


class BigLottoFrontendMLFeatureWeightedAdapter(BetAdapter):
    """Reproduce ``MLStrategy`` mode ``feature_weighted`` for Big Lotto."""

    strategy_id = _FEATURE_WEIGHTED_ID
    strategy_name = "大樂透 Frontend ML Feature Weighted"
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
        return _from_oldest_first(history, "feature_weighted", self._rng)


class BigLottoFrontendMLRandomForestAdapter(BetAdapter):
    """Reproduce ``MLStrategy`` mode ``random_forest`` for Big Lotto."""

    strategy_id = _RANDOM_FOREST_ID
    strategy_name = "大樂透 Frontend ML Random Forest"
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
        return _from_oldest_first(history, "random_forest", self._rng)


class BigLottoFrontendMLGeneticAdapter(BetAdapter):
    """Reproduce ``MLStrategy`` mode ``genetic`` for Big Lotto."""

    strategy_id = _GENETIC_ID
    strategy_name = "大樂透 Frontend ML Genetic"
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
        return _from_oldest_first(history, "genetic", self._rng)


__all__ = [
    "BigLottoFrontendMLFeatureWeightedAdapter",
    "BigLottoFrontendMLGeneticAdapter",
    "BigLottoFrontendMLRandomForestAdapter",
    "ticket_for_mode",
]
