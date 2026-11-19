"""Evolution v0.3: reject a development candidate on any failed prediction."""

from __future__ import annotations

from collections import Counter

from lottolab.strategies.adapters.base import CausalDrawRow
from lottolab.strategies.adapters.biglotto_batch16 import (
    _EVOLUTION_BASELINE_M3,
    _EVOLUTION_MIN_TRAIN,
    _EVOLUTION_N_TEST,
    _EvolutionEngine,
    _EvoMetrics,
    _EvoResult,
    _EvoStrategy,
)
from lottolab.strategies.adapters.biglotto_evolution_causal import (
    SEED_CONTRACT,
    BigLottoCausalEvolutionAdapter,
    _candidate_identity,
    _valid_ticket,
)


class DevelopmentPredictionFailure(Exception):
    """A candidate has no comparable development score."""


def _evaluate_development(
    strategy: _EvoStrategy, draws: list[list[int]], n_test: int = _EVOLUTION_N_TEST
) -> _EvoMetrics:
    """Match legacy fitness when valid, but reject exceptions and invalid tickets."""
    total = len(draws)
    actual_n_test = min(n_test, total - _EVOLUTION_MIN_TRAIN)
    if actual_n_test <= 0:
        raise DevelopmentPredictionFailure("INSUFFICIENT_DEVELOPMENT_HISTORY")
    sample_count = min(actual_n_test, 200)
    if sample_count == 1:
        test_indices = [_EVOLUTION_MIN_TRAIN]
    else:
        step = (total - 1 - _EVOLUTION_MIN_TRAIN) / (sample_count - 1)
        test_indices = [int(_EVOLUTION_MIN_TRAIN + step * i) for i in range(sample_count)]
    hits: list[int] = []
    recent_overlap_count = 0
    for index in test_indices:
        try:
            ticket = strategy.predict(draws[:index], 6)
        except Exception as exc:
            raise DevelopmentPredictionFailure("PREDICTION_" + type(exc).__name__) from exc
        if not _valid_ticket(ticket):
            raise DevelopmentPredictionFailure("INVALID_TICKET")
        predicted = set(ticket)
        if len(predicted.intersection(draws[index - 1])) >= 4:
            recent_overlap_count += 1
        hits.append(len(predicted.intersection(draws[index])))
    hit_rate = sum(1 for hit in hits if hit >= 3) / len(hits)
    penalty = 0.5 if recent_overlap_count > len(test_indices) * 0.1 else 0.0
    return _EvoMetrics(
        hit_ge3=hit_rate,
        edge_ge3=(hit_rate - _EVOLUTION_BASELINE_M3) - penalty,
        leakage_flag=recent_overlap_count > 0,
        hits_array=hits,
    )


class _StrictDevelopmentEngine(_EvolutionEngine):
    def __init__(self, draws: list[list[int]], seed: int = 42) -> None:
        super().__init__(draws, seed)
        self.development_failures: Counter[str] = Counter()

    def evaluate_population(self, n_test: int = _EVOLUTION_N_TEST) -> None:
        self.results = []
        rejected: set[str] = set()
        for candidate in self.population:
            key = _candidate_identity(candidate)
            if key in rejected:
                continue
            try:
                metrics = _evaluate_development(candidate, self.draws, n_test)
            except DevelopmentPredictionFailure as exc:
                rejected.add(key)
                self.development_failures[str(exc)] += 1
                continue
            result = _EvoResult(
                name=candidate.name,
                strategy_ref=candidate,
                relative_random_edge=metrics.edge_ge3,
                hit_ge3=metrics.hit_ge3,
                leakage_flag=metrics.leakage_flag,
                hits_array=metrics.hits_array,
            )
            self.results.append(result)
            if result.relative_random_edge > 0.001 and not metrics.leakage_flag:
                self.hof_hits[self._strategy_key(candidate)] = metrics.hits_array
        if rejected:
            self.population = [s for s in self.population if _candidate_identity(s) not in rejected]
            self.results = [
                r for r in self.results if _candidate_identity(r.strategy_ref) not in rejected
            ]
            self.hall_of_fame = [
                r for r in self.hall_of_fame if _candidate_identity(r.strategy_ref) not in rejected
            ]


class BigLottoStrictEvolutionAdapter(BigLottoCausalEvolutionAdapter):
    """Chronological selection without scoring failed training predictions as misses."""

    strategy_version = "v0.3"
    replay_seed_contract = SEED_CONTRACT

    def __init__(self) -> None:
        super().__init__()
        self.last_development_failures: dict[str, int] = {}

    def _fit_candidates(self, development: tuple[CausalDrawRow, ...]) -> tuple[_EvoStrategy, ...]:
        engine = _StrictDevelopmentEngine([list(row.numbers) for row in development], seed=42)
        engine.initialize()
        for _ in range(10):
            engine.evolve_one_generation()
        self.last_development_failures = dict(engine.development_failures)
        candidates = [result.strategy_ref for result in engine.hall_of_fame]
        if not candidates:
            candidates = list(engine.population)
        unique: dict[str, _EvoStrategy] = {}
        for candidate in candidates:
            unique.setdefault(_candidate_identity(candidate), candidate)
        return tuple(unique.values())
