"""Transition parity and failure closure for evolution population crossover."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import cast

import pytest

from lottolab.domain.evolution_population_crossover import (
    DEFAULT_CROSSOVER_POLICY,
    DEFAULT_OFFSPRING_COUNT,
    DONOR_METHOD,
    DONOR_SOURCE,
    DONOR_SOURCE_SHA256,
    MAX_NEGATIVE_FILTER_OFFSPRING,
    MAX_TRIPLE_OFFSPRING,
    NEGATIVE_FILTER_KILL_COUNTS,
    NEGATIVE_FILTER_KILL_WINDOWS,
    PAIR_WEIGHT_MAX,
    PAIR_WEIGHT_MIN,
    TRIPLE_DIRICHLET_ALPHA,
    EvolutionCrossoverMember,
    EvolutionCrossoverPolicy,
    EvolutionCrossoverRandomSource,
    EvolutionPopulationCrossoverError,
    crossover_evolution_population,
)


class _ScriptedRandom:
    def __init__(self, steps: Sequence[tuple[str, object]]) -> None:
        self._steps = tuple(steps)
        self.calls: list[tuple[object, ...]] = []

    def _next(self, method: str) -> object:
        if len(self.calls) > len(self._steps):
            raise AssertionError("scripted random source exhausted")
        expected_method, value = self._steps[len(self.calls) - 1]
        assert method == expected_method
        return value

    def choice(
        self,
        values: object,
        size: int | None = None,
        replace: bool = True,
    ) -> object:
        normalized_values = (
            values if isinstance(values, int) else tuple(cast(Sequence[object], values))
        )
        self.calls.append(("choice", normalized_values, size, replace))
        return self._next("choice")

    def uniform(self, low: float, high: float) -> object:
        self.calls.append(("uniform", low, high))
        return self._next("uniform")

    def dirichlet(self, alpha: Sequence[int]) -> object:
        self.calls.append(("dirichlet", tuple(alpha)))
        return self._next("dirichlet")


class _CycleRandom:
    def __init__(self) -> None:
        self.calls = 0

    def choice(
        self,
        values: object,
        size: int | None = None,
        replace: bool = True,
    ) -> object:
        del replace
        self.calls += 1
        if isinstance(values, int):
            assert size is not None
            return tuple(range(size))
        choices = tuple(cast(Sequence[object], values))
        return choices[0]

    def uniform(self, low: float, high: float) -> object:
        self.calls += 1
        assert (low, high) == (PAIR_WEIGHT_MIN, PAIR_WEIGHT_MAX)
        return 0.4

    def dirichlet(self, alpha: Sequence[int]) -> object:
        self.calls += 1
        assert tuple(alpha) == TRIPLE_DIRICHLET_ALPHA
        return (0.2, 0.3, 0.5)


def _member(name: str, category: str = "base") -> EvolutionCrossoverMember:
    return EvolutionCrossoverMember(name=name, category=category)


def _weighted_factory(
    parents: tuple[EvolutionCrossoverMember, ...],
    weights: tuple[float, ...],
) -> EvolutionCrossoverMember:
    names = "-".join(parent.name for parent in parents)
    rendered_weights = "-".join(f"{weight:.2f}" for weight in weights)
    return _member(f"weighted-{names}-{rendered_weights}", "synergy")


def _negative_factory(
    base: EvolutionCrossoverMember,
    kill_count: int,
    kill_window: int,
) -> EvolutionCrossoverMember:
    return _member(f"negative-{base.name}-{kill_count}-{kill_window}", "conditional")


def test_donor_identity_method_defaults_and_constants_are_frozen() -> None:
    assert DONOR_SOURCE == "tools/evolving_strategy_engine/evolution_engine.py"
    assert DONOR_SOURCE_SHA256 == (
        "3df019c31ce48e38efc7fd8b52d3e6eb5fd6ab1927bc789785e6d1e85c794f54"
    )
    assert DONOR_METHOD == "EvolutionEngine.crossover"
    assert DEFAULT_OFFSPRING_COUNT == 15
    assert EvolutionCrossoverPolicy(15) == DEFAULT_CROSSOVER_POLICY
    assert (MAX_TRIPLE_OFFSPRING, MAX_NEGATIVE_FILTER_OFFSPRING) == (5, 5)
    assert (PAIR_WEIGHT_MIN, PAIR_WEIGHT_MAX) == (0.3, 0.7)
    assert TRIPLE_DIRICHLET_ALPHA == (1, 1, 1)
    assert NEGATIVE_FILTER_KILL_COUNTS == (3, 5, 7)
    assert NEGATIVE_FILTER_KILL_WINDOWS == (20, 30, 50)


def test_transition_preserves_rng_factory_and_append_order() -> None:
    population = [
        _member("first", "alpha"),
        _member("second", "beta"),
        _member("third", "gamma"),
    ]
    before = population.copy()
    steps = (
        ("choice", (0, 1)),
        ("uniform", 0.3),
        ("choice", (2, 0)),
        ("uniform", 0.6),
        ("choice", (1, 2)),
        ("uniform", 0.45),
        ("choice", (2, 1, 0)),
        ("dirichlet", (0.2, 0.3, 0.5)),
        ("choice", population[1]),
        ("choice", 7),
        ("choice", 20),
    )
    random_source = _ScriptedRandom(steps)
    factory_calls: list[tuple[object, ...]] = []

    def make_weighted(
        parents: tuple[EvolutionCrossoverMember, ...],
        weights: tuple[float, ...],
    ) -> EvolutionCrossoverMember:
        factory_calls.append(("weighted", parents, weights))
        return _weighted_factory(parents, weights)

    def make_negative(
        base: EvolutionCrossoverMember,
        kill_count: int,
        kill_window: int,
    ) -> EvolutionCrossoverMember:
        factory_calls.append(("negative", base, kill_count, kill_window))
        return _negative_factory(base, kill_count, kill_window)

    transition = crossover_evolution_population(
        population,
        random_source=random_source,
        make_weighted_offspring=make_weighted,
        make_negative_filter_offspring=make_negative,
        policy=EvolutionCrossoverPolicy(n_offspring=3),
    )

    assert random_source.calls == [
        ("choice", 3, 2, False),
        ("uniform", 0.3, 0.7),
        ("choice", 3, 2, False),
        ("uniform", 0.3, 0.7),
        ("choice", 3, 2, False),
        ("uniform", 0.3, 0.7),
        ("choice", 3, 3, False),
        ("dirichlet", (1, 1, 1)),
        ("choice", tuple(population), None, True),
        ("choice", (3, 5, 7), None, True),
        ("choice", (20, 30, 50), None, True),
    ]
    assert factory_calls == [
        ("weighted", (population[0], population[1]), (0.3, 0.7)),
        ("weighted", (population[2], population[0]), (0.6, 0.4)),
        ("weighted", (population[1], population[2]), (0.45, 0.55)),
        ("weighted", (population[2], population[1], population[0]), (0.2, 0.3, 0.5)),
        ("negative", population[1], 7, 20),
    ]
    assert tuple(record.parent_indices for record in transition.pair_recombinations) == (
        (0, 1),
        (2, 0),
        (1, 2),
    )
    assert tuple(record.parent_indices for record in transition.triple_recombinations) == (
        (2, 1, 0),
    )
    assert transition.negative_filter_wrappings[0].base_index == 1
    assert transition.offspring == tuple(
        record.offspring
        for record in (
            *transition.pair_recombinations,
            *transition.triple_recombinations,
            *transition.negative_filter_wrappings,
        )
    )
    assert transition.resulting_population == tuple(population) + transition.offspring
    assert population == before


def test_generated_quota_matrix_matches_donor_loop_bounds() -> None:
    for population_size in range(6):
        population = tuple(
            _member(f"parent-{index}", f"category-{index}") for index in range(population_size)
        )
        for n_offspring in range(21):
            transition = crossover_evolution_population(
                population,
                random_source=_CycleRandom(),
                make_weighted_offspring=_weighted_factory,
                make_negative_filter_offspring=_negative_factory,
                policy=EvolutionCrossoverPolicy(n_offspring=n_offspring),
            )
            expected_pairs = n_offspring if population_size >= 2 else 0
            expected_triples = (
                min(MAX_TRIPLE_OFFSPRING, n_offspring // 2) if population_size >= 3 else 0
            )
            expected_negative = (
                min(MAX_NEGATIVE_FILTER_OFFSPRING, n_offspring // 3) if population_size >= 2 else 0
            )

            assert len(transition.pair_recombinations) == expected_pairs
            assert len(transition.triple_recombinations) == expected_triples
            assert len(transition.negative_filter_wrappings) == expected_negative
            assert len(transition.offspring) == (
                expected_pairs + expected_triples + expected_negative
            )
            assert transition.resulting_population == population + transition.offspring


def test_fewer_than_two_members_return_before_rng_or_factory_execution() -> None:
    random_source = _CycleRandom()

    def should_not_make_weighted(
        parents: tuple[EvolutionCrossoverMember, ...],
        weights: tuple[float, ...],
    ) -> EvolutionCrossoverMember:
        del parents, weights
        raise AssertionError("weighted factory unexpectedly called")

    def should_not_make_negative(
        base: EvolutionCrossoverMember,
        kill_count: int,
        kill_window: int,
    ) -> EvolutionCrossoverMember:
        del base, kill_count, kill_window
        raise AssertionError("negative factory unexpectedly called")

    transition = crossover_evolution_population(
        (_member("only"),),
        random_source=random_source,
        make_weighted_offspring=should_not_make_weighted,
        make_negative_filter_offspring=should_not_make_negative,
    )

    assert random_source.calls == 0
    assert transition.offspring == ()
    assert transition.resulting_population == transition.original_population


def test_fixed_input_and_scripted_random_state_are_deterministic() -> None:
    population = (_member("first"), _member("second"), _member("third"))

    def execute() -> object:
        return crossover_evolution_population(
            population,
            random_source=_ScriptedRandom(
                (
                    ("choice", (1, 0)),
                    ("uniform", 0.4),
                )
            ),
            make_weighted_offspring=_weighted_factory,
            make_negative_filter_offspring=_negative_factory,
            policy=EvolutionCrossoverPolicy(n_offspring=1),
        )

    first = execute()
    assert all(execute() == first for _ in range(20))


@pytest.mark.parametrize(
    "constructor",
    (
        lambda: EvolutionCrossoverMember("", "category"),
        lambda: EvolutionCrossoverMember("name", ""),
        lambda: EvolutionCrossoverMember(cast(str, 7), "category"),
        lambda: EvolutionCrossoverMember("name", cast(str, 7)),
        lambda: EvolutionCrossoverPolicy(-1),
        lambda: EvolutionCrossoverPolicy(cast(int, True)),
        lambda: EvolutionCrossoverPolicy(cast(int, 1.5)),
    ),
)
def test_invalid_members_and_policies_fail_closed(
    constructor: Callable[[], object],
) -> None:
    with pytest.raises(EvolutionPopulationCrossoverError):
        constructor()


@pytest.mark.parametrize(
    ("population", "random_source", "weighted_factory", "negative_factory", "policy"),
    (
        (
            "not-population",
            _CycleRandom(),
            _weighted_factory,
            _negative_factory,
            DEFAULT_CROSSOVER_POLICY,
        ),
        (
            (object(),),
            _CycleRandom(),
            _weighted_factory,
            _negative_factory,
            DEFAULT_CROSSOVER_POLICY,
        ),
        (
            (),
            object(),
            _weighted_factory,
            _negative_factory,
            DEFAULT_CROSSOVER_POLICY,
        ),
        (
            (),
            _CycleRandom(),
            object(),
            _negative_factory,
            DEFAULT_CROSSOVER_POLICY,
        ),
        (
            (),
            _CycleRandom(),
            _weighted_factory,
            object(),
            DEFAULT_CROSSOVER_POLICY,
        ),
        (
            (),
            _CycleRandom(),
            _weighted_factory,
            _negative_factory,
            object(),
        ),
    ),
)
def test_invalid_transition_inputs_fail_closed(
    population: object,
    random_source: object,
    weighted_factory: object,
    negative_factory: object,
    policy: object,
) -> None:
    with pytest.raises(EvolutionPopulationCrossoverError):
        crossover_evolution_population(
            population,  # type: ignore[arg-type]
            random_source=random_source,  # type: ignore[arg-type]
            make_weighted_offspring=weighted_factory,  # type: ignore[arg-type]
            make_negative_filter_offspring=negative_factory,  # type: ignore[arg-type]
            policy=policy,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "steps",
    (
        (("choice", (0,)),),
        (("choice", (0, 0)),),
        (("choice", (0, 2)),),
        (("choice", (True, 1)),),
        (("choice", (0, 1)), ("uniform", -0.1)),
        (("choice", (0, 1)), ("uniform", float("nan"))),
        (("choice", (0, 1)), ("uniform", "0.4")),
    ),
)
def test_invalid_pair_random_outputs_fail_closed(
    steps: Sequence[tuple[str, object]],
) -> None:
    with pytest.raises(EvolutionPopulationCrossoverError):
        crossover_evolution_population(
            (_member("first"), _member("second")),
            random_source=_ScriptedRandom(steps),
            make_weighted_offspring=_weighted_factory,
            make_negative_filter_offspring=_negative_factory,
            policy=EvolutionCrossoverPolicy(n_offspring=1),
        )


@pytest.mark.parametrize(
    "weights",
    (
        (0.5, 0.5),
        (0.2, 0.3, 0.6),
        (-0.1, 0.6, 0.5),
        (float("nan"), 0.5, 0.5),
        ("0.2", 0.3, 0.5),
    ),
)
def test_invalid_dirichlet_outputs_fail_closed(weights: object) -> None:
    steps = (
        ("choice", (0, 1)),
        ("uniform", 0.4),
        ("choice", (1, 2)),
        ("uniform", 0.5),
        ("choice", (2, 1, 0)),
        ("dirichlet", weights),
    )
    with pytest.raises(EvolutionPopulationCrossoverError):
        crossover_evolution_population(
            (_member("first"), _member("second"), _member("third")),
            random_source=_ScriptedRandom(steps),
            make_weighted_offspring=_weighted_factory,
            make_negative_filter_offspring=_negative_factory,
            policy=EvolutionCrossoverPolicy(n_offspring=2),
        )


def test_factory_failure_propagates_without_mutating_population() -> None:
    population = [_member("first"), _member("second")]
    before = population.copy()

    def failing_factory(
        parents: tuple[EvolutionCrossoverMember, ...],
        weights: tuple[float, ...],
    ) -> EvolutionCrossoverMember:
        del weights
        raise RuntimeError(f"cannot recombine {parents[0].name}")

    with pytest.raises(RuntimeError, match="cannot recombine first"):
        crossover_evolution_population(
            population,
            random_source=_ScriptedRandom((("choice", (0, 1)), ("uniform", 0.4))),
            make_weighted_offspring=failing_factory,
            make_negative_filter_offspring=_negative_factory,
            policy=EvolutionCrossoverPolicy(n_offspring=1),
        )

    assert population == before


def test_invalid_factory_result_fails_closed() -> None:
    def invalid_factory(
        parents: tuple[EvolutionCrossoverMember, ...],
        weights: tuple[float, ...],
    ) -> EvolutionCrossoverMember:
        del parents, weights
        return cast(EvolutionCrossoverMember, object())

    with pytest.raises(
        EvolutionPopulationCrossoverError,
        match="make_weighted_offspring must return an EvolutionCrossoverMember",
    ):
        crossover_evolution_population(
            (_member("first"), _member("second")),
            random_source=_ScriptedRandom((("choice", (0, 1)), ("uniform", 0.4))),
            make_weighted_offspring=invalid_factory,
            make_negative_filter_offspring=_negative_factory,
            policy=EvolutionCrossoverPolicy(n_offspring=1),
        )


def test_negative_filter_random_outputs_fail_closed() -> None:
    class _BadNegativeChoiceRandom(_CycleRandom):
        def choice(
            self,
            values: object,
            size: int | None = None,
            replace: bool = True,
        ) -> object:
            if not isinstance(values, int):
                choices = tuple(cast(Sequence[object], values))
                if choices == NEGATIVE_FILTER_KILL_COUNTS:
                    return 9
            return super().choice(values, size, replace)

    with pytest.raises(EvolutionPopulationCrossoverError, match="kill_count"):
        crossover_evolution_population(
            (_member("first"), _member("second"), _member("third")),
            random_source=_BadNegativeChoiceRandom(),
            make_weighted_offspring=_weighted_factory,
            make_negative_filter_offspring=_negative_factory,
            policy=EvolutionCrossoverPolicy(n_offspring=3),
        )


def test_negative_filter_base_must_come_from_original_population() -> None:
    class _BadBaseRandom(_CycleRandom):
        def choice(
            self,
            values: object,
            size: int | None = None,
            replace: bool = True,
        ) -> object:
            if not isinstance(values, int):
                choices = tuple(cast(Sequence[object], values))
                if choices and isinstance(choices[0], EvolutionCrossoverMember):
                    return _member("outsider")
            return super().choice(values, size, replace)

    with pytest.raises(EvolutionPopulationCrossoverError, match="original population"):
        crossover_evolution_population(
            (_member("first"), _member("second"), _member("third")),
            random_source=_BadBaseRandom(),
            make_weighted_offspring=_weighted_factory,
            make_negative_filter_offspring=_negative_factory,
            policy=EvolutionCrossoverPolicy(n_offspring=3),
        )


def test_random_source_protocol_remains_injectable() -> None:
    source: EvolutionCrossoverRandomSource = _CycleRandom()
    assert source.choice(2, 2, replace=False) == (0, 1)
