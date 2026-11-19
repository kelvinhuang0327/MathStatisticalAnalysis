"""Replay the frozen BIG_LOTTO optimization runs and the two weighted recipes."""

from __future__ import annotations

import random
from abc import abstractmethod
from collections import Counter
from copy import deepcopy
from itertools import combinations, pairwise
from statistics import median

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import CausalDrawRow, PortfolioBetAdapter
from lottolab.strategies.adapters.biglotto_batch16 import _gum_validate_combination
from lottolab.strategies.adapters.biglotto_constraint_filter import _numpy_pairwise_sum
from lottolab.strategies.adapters.biglotto_quad_strike import _legacy_numpy_argsort
from lottolab.strategies.adapters.biglotto_selected import _historical_frequency, _unpopular_scores
from lottolab.strategies.adapters.biglotto_wave3 import _unified_frequency_ticket
from lottolab.strategies.adapters.biglotto_wave12 import LegacyNumpyRandomState

type History = tuple[CausalDrawRow, ...]
type Portfolio = tuple[tuple[int, ...], ...]
NUMBERS = range(1, 50)


class _FrozenOptimization(PortfolioBetAdapter):
    """Rebuild the seed-42 stream from the first eligible history on random access."""

    supported_lottery_types = (LotteryType.BIG_LOTTO,)
    min_history = 1999

    def __init__(self) -> None:
        self._previous: tuple[History, Portfolio, LegacyNumpyRandomState] | None = None

    def _predict_all(self, history: History, lottery_type: LotteryType) -> Portfolio:
        previous = self._previous
        if previous and history[: len(previous[0])] == previous[0]:
            prior_history, tickets, state = previous
            if len(history) == len(prior_history):
                return tickets
            start = len(prior_history) + 1
            rng = deepcopy(state)
        else:
            start = self.min_history
            rng = LegacyNumpyRandomState(42)
        for cutoff in range(start, len(history)):
            self._sample(history[:cutoff], rng)
        tickets = self._sample(history, rng)
        self._previous = history, tickets, rng
        return tickets

    @abstractmethod
    def _sample(self, history: History, rng: LegacyNumpyRandomState) -> Portfolio: ...


class OptimizeCluster(_FrozenOptimization):
    strategy_name = "Temperature-weighted cluster pivots with a cold exclusion pool"
    strategy_id = "legacy_biglotto__optimize_biglotto_cluster__b2a833918f95"
    strategy_version = "legacy-source-49a25effa62f-b2a833918f95"
    native_ticket_count = 4

    def _sample(self, history: History, rng: LegacyNumpyRandomState) -> Portfolio:
        pairs = Counter(pair for row in history for pair in combinations(sorted(row.numbers), 2))
        centrality: Counter[int] = Counter()
        for (a, b), weight in pairs.items():
            centrality[a] += weight
            centrality[b] += weight
        recent = Counter(n for row in history[-50:] for n in row.numbers)
        excluded = set(sorted(NUMBERS, key=recent.__getitem__)[:5])
        bets = []
        for index, (anchor, _) in enumerate(centrality.most_common(9)):
            if anchor in excluded:
                continue
            unavailable = excluded.union(bets[0]) if bets else excluded
            pool = [n for n in NUMBERS if n != anchor and n not in unavailable]
            weights = [pairs.get((min(n, anchor), max(n, anchor)), 0.1) for n in pool]
            total = _numpy_pairwise_sum(weights)
            temperature = 0.1 if index == 0 else 0.8
            sharpened = [(w / total) ** (1 / temperature) for w in weights]
            norm = _numpy_pairwise_sum(sharpened)
            picks = rng.choice_without_replacement(
                pool, 5, probabilities=[w / norm for w in sharpened]
            )
            bets.append(tuple(sorted((anchor, *picks))))
            if len(bets) == 4:
                break
        return tuple(bets)


class OptimizeDeviation(_FrozenOptimization):
    strategy_name = "Deviation extreme, 500 weighted candidates"
    strategy_id = "legacy_biglotto__optimize_deviation_extreme_generic__87e19bb3514a"
    strategy_version = "legacy-source-49a25effa62f-87e19bb3514a"
    native_ticket_count = 1

    def _sample(self, history: History, rng: LegacyNumpyRandomState) -> Portfolio:
        freq = Counter(n for row in history[-200:] for n in row.numbers)
        cold = Counter(n for row in history[-100:] for n in row.numbers)
        average = sum(freq.values()) / 49
        scores = {}
        for n in NUMBERS:
            z = (freq[n] - average) / average**0.5
            base = 2.0 if z < -1.5 else 1.2 if z > 2.0 else 1.5
            scores[n] = base * (1.5 if cold[n] < 10 else 1.0)
        # Python 3.9 accumulated the donor's positive float weights left-to-right.
        total = 0.0
        for value in scores.values():
            total += value
        probabilities = [scores[n] / total for n in NUMBERS]
        pool = list(NUMBERS)
        best = ()
        best_score = -1.0
        for _ in range(500):
            candidate = tuple(
                sorted(rng.choice_without_replacement(pool, 6, probabilities=probabilities))
            )
            adjacent = [b == a + 1 for a, b in pairwise(candidate)]
            clustered = any(x and y for x, y in pairwise(adjacent))
            zones = Counter(0 if n <= 17 else 1 if n <= 33 else 2 for n in candidate)
            quality = 2.0 * clustered + (sum(adjacent) >= 2) + 1.5 * (max(zones.values()) >= 4)
            if quality:
                score = 0.0
                for n in candidate:
                    score += scores[n]
                score += 5 * quality
                if score > best_score:
                    best, best_score = candidate, score
        return (best or tuple(sorted(sorted(NUMBERS, key=scores.__getitem__, reverse=True)[:6])),)


def _recipe(history: History, window: int, skip_intervals: int) -> Portfolio:
    rows = history[-window:]
    rng = random.Random(42)
    for _ in range(skip_intervals * 6):
        rng.choice((-1, 0, 1))
    gaps = [tuple(b - a for a, b in pairwise((0, *sorted(row.numbers)))) for row in rows]
    interval = []
    previous = 0
    for group in zip(*gaps, strict=True):
        value = max(previous + 1, previous + int(median(group)) + rng.choice((-1, 0, 1)))
        if value > 49:
            value = 49 - (6 - len(interval))
        interval.append(value)
        previous = value
    social = [
        0.7 * u + 0.3 * f
        for u, f in zip(_unpopular_scores(), _historical_frequency(rows), strict=True)
    ]
    social_ticket = [i + 1 for i in _legacy_numpy_argsort(tuple(social))[-6:]]
    scores: Counter[int] = Counter()
    for component, weight in (
        (_unified_frequency_ticket(rows), 3),
        (set(interval), 2),
        (social_ticket, 1),
    ):
        for n in component:
            scores[n] += weight
    ranking = [i + 1 for i in reversed(_legacy_numpy_argsort(tuple(scores[n] for n in NUMBERS)))]
    bets = []
    for start in (0, 6):
        first = ranking[start : start + 5]
        candidates = [sorted((*first, other)) for other in ranking[start + 5 : start + 12]]
        bets.append(
            tuple(next((b for b in candidates if _gum_validate_combination(b)), candidates[0]))
        )
    return tuple(bets)


class HistoricalAudit(PortfolioBetAdapter):
    strategy_name = "Pruned deep-model recipe, continuous seed-42 interval stream"
    strategy_id = "legacy_biglotto__historical_audit_rigorous__bfb679104f60"
    strategy_version = "legacy-source-49a25effa62f-bfb679104f60"
    supported_lottery_types = (LotteryType.BIG_LOTTO,)
    native_ticket_count = 2
    min_history = 200

    def _predict_all(self, history: History, lottery_type: LotteryType) -> Portfolio:
        return _recipe(history, 100, len(history) - self.min_history)


class ConsensusEnsemble(PortfolioBetAdapter):
    strategy_name = "Pruned consensus recipe, 50 draws and per-target seed 42"
    strategy_id = "legacy_biglotto__predict_consensus_ensemble__3ceb975a355c"
    strategy_version = "legacy-source-49a25effa62f-3ceb975a355c"
    supported_lottery_types = (LotteryType.BIG_LOTTO,)
    native_ticket_count = 2
    min_history = 50

    def _predict_all(self, history: History, lottery_type: LotteryType) -> Portfolio:
        return _recipe(history, 50, 0)
