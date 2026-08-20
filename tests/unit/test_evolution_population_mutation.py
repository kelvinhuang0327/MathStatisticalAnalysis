"""Transition parity and failure closure for evolution population mutation."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from itertools import product
from typing import cast

import pytest

from lottolab.domain.evolution_population_mutation import (
    DEFAULT_MUTATION_POLICY,
    DEFAULT_MUTATION_RATE,
    DONOR_METHOD,
    DONOR_SOURCE,
    DONOR_SOURCE_SHA256,
    EvolutionMutationMember,
    EvolutionMutationPolicy,
    EvolutionPopulationMutationError,
    EvolutionRandomSource,
    mutate_evolution_population,
)


class _ScriptedRandom:
    def __init__(self, values: Sequence[object]) -> None:
        self._values = tuple(values)
        self.calls = 0

    def random(self) -> object:
        if self.calls >= len(self._values):
            raise AssertionError("scripted random source exhausted")
        value = self._values[self.calls]
        self.calls += 1
        return value


def _member(name: str, category: str = "base") -> EvolutionMutationMember:
    return EvolutionMutationMember(name=name, category=category)


def _renamed_mutant(
    parent: EvolutionMutationMember,
    random_source: EvolutionRandomSource,
) -> EvolutionMutationMember:
    del random_source
    return EvolutionMutationMember(name=f"{parent.name}-mutant", category="overwritten")


def test_donor_identity_method_and_default_parameter_are_frozen() -> None:
    assert DONOR_SOURCE == "tools/evolving_strategy_engine/evolution_engine.py"
    assert DONOR_SOURCE_SHA256 == (
        "3df019c31ce48e38efc7fd8b52d3e6eb5fd6ab1927bc789785e6d1e85c794f54"
    )
    assert DONOR_METHOD == "EvolutionEngine.mutate_population"
    assert DEFAULT_MUTATION_RATE == 0.4
    assert EvolutionMutationPolicy(0.4) == DEFAULT_MUTATION_POLICY


def test_transition_preserves_rng_call_order_category_and_append_order() -> None:
    population = [
        _member("first", "alpha"),
        _member("second", "beta"),
        _member("third", "gamma"),
    ]
    before = population.copy()
    random_source = _ScriptedRandom((0.1, 0.71, 0.9, 0.2, 0.82))
    mutation_calls: list[tuple[str, float]] = []

    def mutate(
        parent: EvolutionMutationMember,
        shared_random_source: EvolutionRandomSource,
    ) -> EvolutionMutationMember:
        mutation_draw = cast(float, shared_random_source.random())
        mutation_calls.append((parent.name, mutation_draw))
        return EvolutionMutationMember(
            name=f"{parent.name}-mutant-{mutation_draw}",
            category="must-be-overwritten",
        )

    transition = mutate_evolution_population(
        population,
        random_source=random_source,
        mutate=mutate,
    )

    assert random_source.calls == 5
    assert mutation_calls == [("first", 0.71), ("third", 0.82)]
    assert transition.selection_draws == (0.1, 0.9, 0.2)
    assert transition.selected_parent_indices == (0, 2)
    assert transition.mutants == (
        _member("first-mutant-0.71", "alpha"),
        _member("third-mutant-0.82", "gamma"),
    )
    assert transition.resulting_population == tuple(population) + transition.mutants
    assert population == before


def test_strict_threshold_does_not_mutate_when_draw_equals_rate() -> None:
    random_source = _ScriptedRandom((DEFAULT_MUTATION_RATE,))

    transition = mutate_evolution_population(
        (_member("boundary"),),
        random_source=random_source,
        mutate=_renamed_mutant,
    )

    assert transition.selected_parent_indices == ()
    assert transition.mutants == ()
    assert transition.resulting_population == transition.original_population
    assert random_source.calls == 1


def test_empty_population_does_not_consume_rng_or_call_operator() -> None:
    random_source = _ScriptedRandom(())

    def should_not_run(
        parent: EvolutionMutationMember,
        shared_random_source: EvolutionRandomSource,
    ) -> EvolutionMutationMember:
        del parent, shared_random_source
        raise AssertionError("mutation operator unexpectedly called")

    transition = mutate_evolution_population(
        (),
        random_source=random_source,
        mutate=should_not_run,
    )

    assert transition.original_population == ()
    assert transition.selection_draws == ()
    assert transition.selected_parent_indices == ()
    assert transition.mutants == ()
    assert transition.resulting_population == ()
    assert random_source.calls == 0


def test_exhaustive_selection_matrix_matches_donor_threshold_and_order() -> None:
    draws = (0.0, 0.399999, 0.4, 0.999999)

    for size in range(5):
        population = tuple(_member(f"parent-{index}", f"category-{index}") for index in range(size))
        for selection_draws in product(draws, repeat=size):
            transition = mutate_evolution_population(
                population,
                random_source=_ScriptedRandom(selection_draws),
                mutate=_renamed_mutant,
            )
            expected_indices = tuple(
                index for index, draw in enumerate(selection_draws) if draw < DEFAULT_MUTATION_RATE
            )
            expected_mutants = tuple(
                _member(
                    f"parent-{index}-mutant",
                    f"category-{index}",
                )
                for index in expected_indices
            )

            assert transition.selection_draws == selection_draws
            assert transition.selected_parent_indices == expected_indices
            assert transition.mutants == expected_mutants
            assert transition.resulting_population == population + expected_mutants


@pytest.mark.parametrize(
    ("rate", "expected_indices"),
    (
        (0.0, ()),
        (1.0, (0, 1)),
    ),
)
def test_closed_rate_boundaries_preserve_donor_comparison(
    rate: float,
    expected_indices: tuple[int, ...],
) -> None:
    transition = mutate_evolution_population(
        (_member("first"), _member("second")),
        random_source=_ScriptedRandom((0.0, 0.999999)),
        mutate=_renamed_mutant,
        policy=EvolutionMutationPolicy(rate),
    )

    assert transition.selected_parent_indices == expected_indices


def test_fixed_input_and_scripted_random_state_are_deterministic() -> None:
    population = (_member("first", "one"), _member("second", "two"))

    def execute() -> object:
        return mutate_evolution_population(
            population,
            random_source=_ScriptedRandom((0.2, 0.8)),
            mutate=_renamed_mutant,
        )

    first = execute()
    assert all(execute() == first for _ in range(20))


def test_operator_failure_propagates_without_mutating_population() -> None:
    population = [_member("first"), _member("second")]
    before = population.copy()

    def failing_operator(
        parent: EvolutionMutationMember,
        random_source: EvolutionRandomSource,
    ) -> EvolutionMutationMember:
        del random_source
        raise RuntimeError(f"cannot mutate {parent.name}")

    with pytest.raises(RuntimeError, match="cannot mutate first"):
        mutate_evolution_population(
            population,
            random_source=_ScriptedRandom((0.1,)),
            mutate=failing_operator,
        )

    assert population == before


@pytest.mark.parametrize(
    "constructor",
    (
        lambda: EvolutionMutationMember("", "category"),
        lambda: EvolutionMutationMember("name", ""),
        lambda: EvolutionMutationMember(cast(str, 7), "category"),
        lambda: EvolutionMutationMember("name", cast(str, 7)),
        lambda: EvolutionMutationPolicy(-0.1),
        lambda: EvolutionMutationPolicy(1.1),
        lambda: EvolutionMutationPolicy(float("nan")),
        lambda: EvolutionMutationPolicy(float("inf")),
        lambda: EvolutionMutationPolicy(cast(float, True)),
    ),
)
def test_invalid_members_and_policies_fail_closed(
    constructor: Callable[[], object],
) -> None:
    with pytest.raises(EvolutionPopulationMutationError):
        constructor()


@pytest.mark.parametrize(
    "draw",
    (
        -0.1,
        1.0,
        float("nan"),
        float("inf"),
        True,
        "0.2",
    ),
)
def test_invalid_random_draws_fail_closed(draw: object) -> None:
    with pytest.raises(EvolutionPopulationMutationError):
        mutate_evolution_population(
            (_member("parent"),),
            random_source=_ScriptedRandom((draw,)),
            mutate=_renamed_mutant,
        )


@pytest.mark.parametrize(
    ("population", "random_source", "mutate", "policy"),
    (
        ("not-population", _ScriptedRandom(()), _renamed_mutant, DEFAULT_MUTATION_POLICY),
        ((object(),), _ScriptedRandom(()), _renamed_mutant, DEFAULT_MUTATION_POLICY),
        ((), object(), _renamed_mutant, DEFAULT_MUTATION_POLICY),
        ((), _ScriptedRandom(()), object(), DEFAULT_MUTATION_POLICY),
        ((), _ScriptedRandom(()), _renamed_mutant, object()),
    ),
)
def test_invalid_transition_inputs_fail_closed(
    population: object,
    random_source: object,
    mutate: object,
    policy: object,
) -> None:
    with pytest.raises(EvolutionPopulationMutationError):
        mutate_evolution_population(
            population,  # type: ignore[arg-type]
            random_source=random_source,  # type: ignore[arg-type]
            mutate=mutate,  # type: ignore[arg-type]
            policy=policy,  # type: ignore[arg-type]
        )


def test_invalid_operator_result_fails_closed() -> None:
    def invalid_operator(
        parent: EvolutionMutationMember,
        random_source: EvolutionRandomSource,
    ) -> EvolutionMutationMember:
        del parent, random_source
        return cast(EvolutionMutationMember, object())

    with pytest.raises(
        EvolutionPopulationMutationError,
        match="mutate must return an EvolutionMutationMember",
    ):
        mutate_evolution_population(
            (_member("parent"),),
            random_source=_ScriptedRandom((0.1,)),
            mutate=invalid_operator,
        )
