"""Transition parity and failure closure for evolution survivor selection."""

from __future__ import annotations

from collections.abc import Callable
from itertools import product
from typing import cast

import pytest

from lottolab.domain.evolution_survivor_selection import (
    DEFAULT_ELITE_COUNT,
    DEFAULT_KEEP_RATIO,
    DEFAULT_SURVIVOR_POLICY,
    DONOR_METHOD,
    DONOR_SOURCE,
    DONOR_SOURCE_SHA256,
    EvolutionCandidateEvaluation,
    EvolutionPopulationMember,
    EvolutionSurvivorPolicy,
    EvolutionSurvivorSelectionError,
    select_evolution_survivors,
)


def _evaluation(
    name: str,
    score: float,
    *,
    leaked: bool = False,
) -> EvolutionCandidateEvaluation:
    return EvolutionCandidateEvaluation(
        name=name,
        score=score,
        leakage_detected=leaked,
    )


def _population(*names: str) -> tuple[EvolutionPopulationMember, ...]:
    return tuple(EvolutionPopulationMember(name) for name in names)


def test_donor_identity_and_default_parameters_are_frozen() -> None:
    assert DONOR_SOURCE == "tools/evolving_strategy_engine/evolution_engine.py"
    assert DONOR_SOURCE_SHA256 == (
        "3df019c31ce48e38efc7fd8b52d3e6eb5fd6ab1927bc789785e6d1e85c794f54"
    )
    assert DONOR_METHOD == "EvolutionEngine.select_survivors"
    assert (DEFAULT_KEEP_RATIO, DEFAULT_ELITE_COUNT) == (0.5, 5)
    assert EvolutionSurvivorPolicy(0.5, 5) == DEFAULT_SURVIVOR_POLICY


def test_transition_preserves_donor_ordering_and_state_projection() -> None:
    results = (
        _evaluation("first-tie", 0.2),
        _evaluation("leaked-best", 9.0, leaked=True),
        _evaluation("later-tie", 0.2),
        _evaluation("zero", 0.0),
        _evaluation("negative", -0.5),
        _evaluation("middle", 0.1),
    )
    population = _population(
        "unscored",
        "later-tie",
        "leaked-best",
        "first-tie",
        "later-tie",
        "middle",
    )

    transition = select_evolution_survivors(
        results,
        population,
        policy=EvolutionSurvivorPolicy(keep_ratio=0.5, elite_count=2),
    )

    assert tuple(result.name for result in transition.ranked_eligible_results) == (
        "first-tie",
        "later-tie",
        "middle",
        "zero",
        "negative",
    )
    assert transition.retention_limit == 2
    assert tuple(result.name for result in transition.elite_results) == (
        "first-tie",
        "later-tie",
    )
    assert tuple(result.name for result in transition.survivor_results) == (
        "first-tie",
        "later-tie",
    )
    assert tuple(result.name for result in transition.hall_of_fame_additions) == (
        "first-tie",
        "later-tie",
    )
    assert tuple(result.name for result in transition.eliminated_results) == (
        "middle",
        "zero",
        "negative",
        "leaked-best",
    )
    assert transition.graveyard_additions == (
        "middle",
        "zero",
        "negative",
        "leaked-best",
    )
    assert tuple(member.name for member in transition.surviving_population) == (
        "later-tie",
        "first-tie",
        "later-tie",
    )


def test_default_elite_floor_keeps_all_when_fewer_than_five_are_eligible() -> None:
    results = (
        _evaluation("positive", 1.0),
        _evaluation("zero", 0.0),
        _evaluation("negative", -1.0),
    )

    transition = select_evolution_survivors(
        results,
        _population("negative", "positive", "zero"),
    )

    assert transition.retention_limit == DEFAULT_ELITE_COUNT
    assert transition.survivor_results == results
    assert transition.hall_of_fame_additions == (results[0],)
    assert transition.eliminated_results == ()
    assert tuple(member.name for member in transition.surviving_population) == (
        "negative",
        "positive",
        "zero",
    )


def test_empty_results_preserve_population_without_state_additions() -> None:
    population = _population("one", "two")

    transition = select_evolution_survivors((), population)

    assert transition.ranked_eligible_results == ()
    assert transition.elite_results == ()
    assert transition.survivor_results == ()
    assert transition.eliminated_results == ()
    assert transition.surviving_population == population
    assert transition.hall_of_fame_additions == ()
    assert transition.graveyard_additions == ()
    assert transition.retention_limit == 0


def test_all_leaked_results_close_with_empty_survivors() -> None:
    results = (
        _evaluation("first", 2.0, leaked=True),
        _evaluation("second", 1.0, leaked=True),
    )

    transition = select_evolution_survivors(
        results,
        _population("first", "second"),
    )

    assert transition.ranked_eligible_results == ()
    assert transition.survivor_results == ()
    assert transition.eliminated_results == results
    assert transition.surviving_population == ()
    assert transition.hall_of_fame_additions == ()
    assert transition.graveyard_additions == ("first", "second")
    assert transition.retention_limit == DEFAULT_ELITE_COUNT


def test_inputs_are_not_mutated_or_reordered_and_execution_is_deterministic() -> None:
    results = [
        _evaluation("low", -1.0),
        _evaluation("high", 1.0),
        _evaluation("leaked", 8.0, leaked=True),
    ]
    population = [
        EvolutionPopulationMember("low"),
        EvolutionPopulationMember("high"),
        EvolutionPopulationMember("leaked"),
    ]
    results_before = results.copy()
    population_before = population.copy()
    policy = EvolutionSurvivorPolicy(keep_ratio=0.5, elite_count=1)

    first = select_evolution_survivors(results, population, policy=policy)

    assert results == results_before
    assert population == population_before
    assert all(
        select_evolution_survivors(results, population, policy=policy) == first for _ in range(20)
    )


def test_large_exhaustive_transition_matrix_matches_donor_rules() -> None:
    score_and_leakage = tuple(product((-0.5, 0.0, 0.5), (False, True)))
    policies = (
        EvolutionSurvivorPolicy(keep_ratio=0.0, elite_count=0),
        EvolutionSurvivorPolicy(keep_ratio=0.5, elite_count=1),
        EvolutionSurvivorPolicy(keep_ratio=1.0, elite_count=5),
    )

    for size in range(1, 5):
        for specifications in product(score_and_leakage, repeat=size):
            results = tuple(
                _evaluation(f"candidate-{index}", score, leaked=leaked)
                for index, (score, leaked) in enumerate(specifications)
            )
            population = _population(
                *(result.name for result in reversed(results)),
                "unscored",
            )
            for policy in policies:
                transition = select_evolution_survivors(
                    results,
                    population,
                    policy=policy,
                )

                eligible_indices = tuple(
                    index for index, (_, leaked) in enumerate(specifications) if not leaked
                )
                ranked_indices = tuple(
                    sorted(
                        eligible_indices,
                        key=lambda index: specifications[index][0],
                        reverse=True,
                    )
                )
                retention_limit = max(
                    policy.elite_count,
                    int(len(ranked_indices) * policy.keep_ratio),
                )
                survivor_indices = ranked_indices[:retention_limit]
                leaked_indices = tuple(
                    index for index, (_, leaked) in enumerate(specifications) if leaked
                )
                eliminated_indices = ranked_indices[retention_limit:] + leaked_indices
                survivor_names = {results[index].name for index in survivor_indices}

                assert transition.ranked_eligible_results == tuple(
                    results[index] for index in ranked_indices
                )
                assert transition.elite_results == tuple(
                    results[index] for index in ranked_indices[: policy.elite_count]
                )
                assert transition.survivor_results == tuple(
                    results[index] for index in survivor_indices
                )
                assert transition.eliminated_results == tuple(
                    results[index] for index in eliminated_indices
                )
                assert transition.hall_of_fame_additions == tuple(
                    results[index]
                    for index in ranked_indices[: policy.elite_count]
                    if results[index].score > 0.0
                )
                assert transition.graveyard_additions == tuple(
                    results[index].name for index in eliminated_indices
                )
                assert transition.surviving_population == tuple(
                    member for member in population if member.name in survivor_names
                )
                assert transition.retention_limit == retention_limit


@pytest.mark.parametrize(
    "constructor",
    (
        lambda: EvolutionCandidateEvaluation("", 0.0),
        lambda: EvolutionCandidateEvaluation(cast(str, 7), 0.0),
        lambda: EvolutionCandidateEvaluation("candidate", float("nan")),
        lambda: EvolutionCandidateEvaluation("candidate", float("inf")),
        lambda: EvolutionCandidateEvaluation("candidate", cast(float, True)),
        lambda: EvolutionCandidateEvaluation(
            "candidate",
            0.0,
            leakage_detected=cast(bool, 1),
        ),
        lambda: EvolutionPopulationMember(""),
        lambda: EvolutionPopulationMember(cast(str, 7)),
        lambda: EvolutionSurvivorPolicy(keep_ratio=-0.1),
        lambda: EvolutionSurvivorPolicy(keep_ratio=1.1),
        lambda: EvolutionSurvivorPolicy(keep_ratio=float("nan")),
        lambda: EvolutionSurvivorPolicy(keep_ratio=cast(float, True)),
        lambda: EvolutionSurvivorPolicy(elite_count=-1),
        lambda: EvolutionSurvivorPolicy(elite_count=cast(int, True)),
        lambda: EvolutionSurvivorPolicy(elite_count=cast(int, 1.5)),
    ),
)
def test_invalid_values_fail_closed(constructor: Callable[[], object]) -> None:
    with pytest.raises(EvolutionSurvivorSelectionError):
        constructor()


@pytest.mark.parametrize(
    ("results", "population", "policy"),
    (
        ("not-results", (), DEFAULT_SURVIVOR_POLICY),
        ((object(),), (), DEFAULT_SURVIVOR_POLICY),
        ((), "not-population", DEFAULT_SURVIVOR_POLICY),
        ((), (object(),), DEFAULT_SURVIVOR_POLICY),
        ((), (), object()),
    ),
)
def test_invalid_transition_containers_fail_closed(
    results: object,
    population: object,
    policy: object,
) -> None:
    with pytest.raises(EvolutionSurvivorSelectionError):
        select_evolution_survivors(
            results,  # type: ignore[arg-type]
            population,  # type: ignore[arg-type]
            policy=policy,  # type: ignore[arg-type]
        )
