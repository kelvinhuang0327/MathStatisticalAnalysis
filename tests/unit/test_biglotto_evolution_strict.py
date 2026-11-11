"""Training failures are excluded, while valid development scores are unchanged."""

# These adapter tests pin the frozen legacy engine's internal selection contract.
# pyright: reportPrivateUsage=false

from __future__ import annotations

import pytest

from lottolab.strategies.adapters import biglotto_batch16 as legacy
from lottolab.strategies.adapters import biglotto_evolution_strict as strict


class Candidate(legacy._EvoStrategy):
    def __init__(self, name: str, mode: str) -> None:
        self.name = name
        self.params = {"mode": mode}
        self.mode = mode
        self.seen: list[int] = []

    def predict(self, draws: list[list[int]], n_select: int = 6) -> list[int]:
        self.seen.append(len(draws))
        if self.mode == "raise" and len(draws) == 503:
            raise ValueError("unavailable")
        if self.mode == "invalid":
            return [1, 1, 2, 3, 4, 5]
        return [1, 2, 3, 4, 5, 6][:n_select]


def draws() -> list[list[int]]:
    return [[((i + j * 7) % 49) + 1 for j in range(6)] for i in range(510)]


def test_valid_scores_match_legacy_and_use_only_earlier_prefixes() -> None:
    candidate = Candidate("valid", "valid")
    original = legacy._evo_evaluate_m3_edge(candidate, draws())
    candidate.seen.clear()
    result = strict._evaluate_development(candidate, draws())
    assert result == original
    assert candidate.seen == list(range(500, 510))


@pytest.mark.parametrize("mode", ["raise", "invalid"])
def test_any_failed_development_prediction_excludes_candidate(mode: str) -> None:
    candidate = Candidate("bad", mode)
    with pytest.raises(strict.DevelopmentPredictionFailure):
        strict._evaluate_development(candidate, draws())


def test_failure_is_removed_from_population_results_and_previous_hall() -> None:
    good = Candidate("good", "valid")
    bad = Candidate("bad", "raise")
    engine = strict._StrictDevelopmentEngine(draws())
    engine.population = [bad, good]
    engine.hall_of_fame = [legacy._EvoResult(name=bad.name, strategy_ref=bad)]
    engine.evaluate_population()
    assert engine.population == [good]
    assert [r.strategy_ref for r in engine.results] == [good]
    assert engine.hall_of_fame == []
    assert engine.development_failures == {"PREDICTION_ValueError": 1}
    assert len(engine.results[0].hits_array) == 10


def test_all_failed_population_cannot_be_fallback() -> None:
    engine = strict._StrictDevelopmentEngine(draws())
    engine.population = [Candidate("bad", "invalid")]
    engine.evaluate_population()
    engine.select_survivors()
    engine.mutate_population()
    engine.crossover()
    assert engine.results == engine.population == engine.hall_of_fame == []
    assert engine.development_failures == {"INVALID_TICKET": 1}
