"""Evolution v0.4 with bounded nested sampling and causal development."""

from __future__ import annotations

import random

from lottolab.strategies.adapters import biglotto_batch16 as legacy
from lottolab.strategies.adapters.base import CausalDrawRow
from lottolab.strategies.adapters.biglotto_batch16 import _EvoStrategy
from lottolab.strategies.adapters.biglotto_evolution_causal import _candidate_identity
from lottolab.strategies.adapters.biglotto_evolution_strict import (
    BigLottoStrictEvolutionAdapter,
    _StrictDevelopmentEngine,
)


class _SumTargetStrategy(legacy._SumTargetStrategy):
    """Expand the frequency pool when a nested caller requests over 20 numbers."""

    def predict(self, draws: list[list[int]], n_select: int = 6) -> list[int]:
        if type(n_select) is not int or not 1 <= n_select <= legacy._MAX_NUM:
            raise ValueError("requested selection count must be between 1 and 49")
        sums = legacy._evo_sum_trend(draws, self.params["window"])
        target_sum = sum(sums) / len(sums)
        freq = legacy._evo_frequency(draws, self.params["window"])
        candidates = sorted(range(legacy._MAX_NUM), key=lambda i: freq[i], reverse=True)[
            : max(20, n_select)
        ]
        best_combo: list[int] | None = None
        best_diff = float("inf")
        rng = random.Random(42)
        for _ in range(100):
            combo = sorted(n + 1 for n in rng.sample(candidates, n_select))
            diff = abs(sum(combo) - target_sum)
            if diff < best_diff:
                best_diff = diff
                best_combo = combo
        return best_combo or sorted(i + 1 for i in candidates[:n_select])


class _NegativeFilterStrategy(legacy._NegativeFilterStrategy):
    """Prefer exclusions, but bound requests and fill if exclusions leave too few."""

    def predict(self, draws: list[list[int]], n_select: int = 6) -> list[int]:
        if type(n_select) is not int or not 1 <= n_select <= legacy._MAX_NUM:
            raise ValueError("requested selection count must be between 1 and 49")
        freq = legacy._evo_frequency(draws, self.params["kill_window"])
        kill_count = self.params["kill_count"]
        kill_set = set(
            i + 1 for i in sorted(range(legacy._MAX_NUM), key=lambda i: freq[i])[-kill_count:]
        )
        candidates = self.base.predict(draws, n_select=min(legacy._MAX_NUM, n_select + kill_count))
        filtered = [n for n in candidates if n not in kill_set]
        if len(filtered) < n_select:
            ranked = sorted(range(legacy._MAX_NUM), key=lambda i: freq[i])
            filtered_set = set(filtered)
            extras = [
                i + 1 for i in ranked if (i + 1) not in filtered_set and (i + 1) not in kill_set
            ]
            filtered.extend(extras[: n_select - len(filtered)])
        if len(filtered) < n_select:
            # Only needed when the requested count exceeds the non-killed pool.
            # Keep the least frequent excluded numbers first, deterministically.
            used = set(filtered)
            ranked = sorted(range(legacy._MAX_NUM), key=lambda i: freq[i])
            filtered.extend(i + 1 for i in ranked if i + 1 not in used)
        return sorted(filtered[:n_select])


def _upgrade_owned_population(population: list[_EvoStrategy]) -> None:
    """Upgrade only strategies owned by this engine, including shared nested nodes."""
    seen: set[int] = set()

    def visit(candidate: _EvoStrategy) -> None:
        if id(candidate) in seen:
            return
        seen.add(id(candidate))
        if type(candidate) is legacy._SumTargetStrategy:
            candidate.__class__ = _SumTargetStrategy
        elif type(candidate) is legacy._NegativeFilterStrategy:
            candidate.__class__ = _NegativeFilterStrategy
        for child in getattr(candidate, "strategies", ()):
            visit(child)
        base = getattr(candidate, "base", None)
        if base is not None:
            visit(base)

    for candidate in population:
        visit(candidate)


class _BoundedDevelopmentEngine(_StrictDevelopmentEngine):
    def initialize(self, pop_size: int = legacy._EVOLUTION_POP_SIZE) -> None:
        super().initialize(pop_size)
        _upgrade_owned_population(self.population)

    def mutate_population(self, mutation_rate: float = 0.4) -> None:
        super().mutate_population(mutation_rate)
        _upgrade_owned_population(self.population)

    def crossover(self, n_offspring: int = 15) -> None:
        super().crossover(n_offspring)
        _upgrade_owned_population(self.population)


class BigLottoBoundedEvolutionAdapter(BigLottoStrictEvolutionAdapter):
    """Fixed-seed chronological evolution with safe nested sample sizes."""

    strategy_version = "v0.4"

    def _fit_candidates(self, development: tuple[CausalDrawRow, ...]) -> tuple[_EvoStrategy, ...]:
        engine = _BoundedDevelopmentEngine([list(row.numbers) for row in development], seed=42)
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
