"""Nested sample limits, determinism and legacy-compatible legal requests."""

from __future__ import annotations

import copy
import random

import pytest

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters import biglotto_batch16 as legacy
from lottolab.strategies.adapters import biglotto_evolution_bounded as bounded
from lottolab.strategies.adapters.base import CausalDrawRow
from lottolab.strategies.adapters.biglotto_evolution_causal import _candidate_identity


def draws(n: int = 120) -> list[list[int]]:
    return [[((i + 7 * j) % 49) + 1 for j in range(6)] for i in range(n)]


@pytest.mark.parametrize("count", [1, 6, 12, 20])
def test_sum_target_preserves_legacy_output_when_pool_was_sufficient(count: int) -> None:
    old = legacy._SumTargetStrategy(window=59, tolerance=18)
    fixed = bounded._SumTargetStrategy(window=59, tolerance=18)
    assert _candidate_identity(old) == _candidate_identity(fixed)
    assert old.predict(draws(), count) == fixed.predict(draws(), count)


@pytest.mark.parametrize("count", [21, 22, 30, 39, 40, 48, 49])
def test_expanded_sum_pool_returns_requested_distinct_numbers(count: int) -> None:
    fixed = bounded._SumTargetStrategy(window=59, tolerance=18)
    first = fixed.predict(draws(), count)
    assert first == fixed.predict(draws(), count)
    assert len(first) == len(set(first)) == count
    assert all(1 <= n <= 49 for n in first)


@pytest.mark.parametrize("count", [0, 50, -1])
def test_impossible_sum_request_fails_explicitly(count: int) -> None:
    with pytest.raises(ValueError, match="between 1 and 49"):
        bounded._SumTargetStrategy().predict(draws(), count)


def test_reported_weighted_nested_failure_is_fixed_and_repeatable() -> None:
    base = legacy._SumTargetStrategy(window=59, tolerance=18)
    filt = legacy._NegativeFilterStrategy(base, kill_count=10, kill_window=24)
    weighted = legacy._WeightedEnsembleStrategy([legacy._FrequencyStrategy(), filt], [0.4, 0.6])
    with pytest.raises(ValueError, match="Sample larger"):
        weighted.predict(draws(), 6)
    identity = _candidate_identity(weighted)
    bounded._upgrade_owned_population([weighted])
    assert _candidate_identity(weighted) == identity
    first = weighted.predict(draws(), 6)
    assert first == weighted.predict(draws(), 6)
    assert len(first) == len(set(first)) == 6 and all(1 <= n <= 49 for n in first)


def test_deep_nested_filters_bound_requests_and_fill_deterministically() -> None:
    candidate: legacy._EvoStrategy = legacy._SumTargetStrategy(window=59)
    for _ in range(6):
        candidate = legacy._NegativeFilterStrategy(candidate, kill_count=10, kill_window=24)
    bounded._upgrade_owned_population([candidate])
    for count in (6, 22, 39, 40, 49):
        first = candidate.predict(draws(), count)
        assert first == candidate.predict(draws(), count)
        assert len(first) == len(set(first)) == count and all(1 <= n <= 49 for n in first)


def test_expanded_sampling_does_not_consume_process_random_state() -> None:
    state = random.getstate()
    bounded._SumTargetStrategy().predict(draws(), 22)
    assert random.getstate() == state


def test_v04_holdout_predictions_only_receive_earlier_history(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Candidate(legacy._EvoStrategy):
        name = "test"

        def __init__(self) -> None:
            self.params: dict = {}
            self.lengths: list[int] = []

        def predict(self, history: list[list[int]], n_select: int = 6) -> list[int]:
            self.lengths.append(len(history))
            return [1, 2, 3, 4, 5, 6]

    candidate = Candidate()
    fitted: list[int] = []

    def fit(
        _self: object, development: tuple[CausalDrawRow, ...]
    ) -> tuple[legacy._EvoStrategy, ...]:
        fitted.append(len(development))
        return (candidate,)

    monkeypatch.setattr(bounded.BigLottoBoundedEvolutionAdapter, "_fit_candidates", fit)
    history = tuple(
        CausalDrawRow(str(i), "2020-01-01", tuple(row)) for i, row in enumerate(draws(551))
    )
    tickets = bounded.BigLottoBoundedEvolutionAdapter().get_bets(history, LotteryType.BIG_LOTTO)
    assert tickets == ((1, 2, 3, 4, 5, 6),)
    assert fitted == [501]
    assert candidate.lengths == [*range(501, 551), 551]


def test_negative_filter_matches_legacy_when_request_remains_feasible() -> None:
    old = legacy._NegativeFilterStrategy(
        legacy._SumTargetStrategy(window=59), kill_count=5, kill_window=24
    )
    fixed = copy.deepcopy(old)
    bounded._upgrade_owned_population([fixed])
    assert _candidate_identity(old) == _candidate_identity(fixed)
    assert old.predict(draws(), 6) == fixed.predict(draws(), 6)


def test_seed_and_crossover_create_only_upgraded_nested_nodes() -> None:
    engine = bounded._BoundedDevelopmentEngine(draws(), seed=42)
    engine.initialize()
    engine.crossover()
    seen: set[int] = set()

    def check(candidate: legacy._EvoStrategy) -> None:
        if id(candidate) in seen:
            return
        seen.add(id(candidate))
        assert type(candidate) not in (legacy._SumTargetStrategy, legacy._NegativeFilterStrategy)
        for child in getattr(candidate, "strategies", ()):
            check(child)
        base = getattr(candidate, "base", None)
        if base is not None:
            check(base)

    for candidate in engine.population:
        check(candidate)
