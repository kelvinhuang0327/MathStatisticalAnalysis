"""Pure population-crossover transition from the legacy evolution engine.

The donor is ``tools/evolving_strategy_engine/evolution_engine.py`` in the
preserved ``LotteryNewMeraged`` source snapshot (sha256
``3df019c31ce48e38efc7fd8b52d3e6eb5fd6ab1927bc789785e6d1e85c794f54``).
The accessible snapshot has no Git metadata, so this module does not claim a
donor commit identity.

For valid inputs, :func:`crossover_evolution_population` preserves the donor's
``EvolutionEngine.crossover`` transition.  It creates the configured number
of two-parent weighted offspring first, up to five three-parent Dirichlet-
weighted offspring second, and up to five negative-filter offspring last.
Every selection, weight draw, factory call, and append retains donor order.

The target adaptation injects the random source and both offspring factories,
represents members and the returned transition immutably, and closes malformed
inputs and random outputs.  It has no dependency on concrete strategies,
strategy catalogs, evaluation, history, persistence, schedulers, networks, or
process runtime.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from numbers import Integral, Real
from typing import Protocol, cast

DONOR_SOURCE = "tools/evolving_strategy_engine/evolution_engine.py"
DONOR_SOURCE_SHA256 = "3df019c31ce48e38efc7fd8b52d3e6eb5fd6ab1927bc789785e6d1e85c794f54"
DONOR_METHOD = "EvolutionEngine.crossover"

DEFAULT_OFFSPRING_COUNT = 15
MAX_TRIPLE_OFFSPRING = 5
MAX_NEGATIVE_FILTER_OFFSPRING = 5
PAIR_WEIGHT_MIN = 0.3
PAIR_WEIGHT_MAX = 0.7
TRIPLE_DIRICHLET_ALPHA = (1, 1, 1)
NEGATIVE_FILTER_KILL_COUNTS = (3, 5, 7)
NEGATIVE_FILTER_KILL_WINDOWS = (20, 30, 50)


class EvolutionPopulationCrossoverError(ValueError):
    """Raised when a population-crossover input violates its closed contract."""


@dataclass(frozen=True, slots=True)
class EvolutionCrossoverMember:
    """Immutable identity projected through one crossover transition."""

    name: str
    category: str

    def __post_init__(self) -> None:
        for field_name, value in (("name", self.name), ("category", self.category)):
            if type(value) is not str or not value:
                raise EvolutionPopulationCrossoverError(f"{field_name} must be a non-empty string")


class EvolutionCrossoverRandomSource(Protocol):
    """Minimal NumPy-compatible random-source contract used by the donor."""

    def choice(
        self,
        values: object,
        size: int | None = None,
        replace: bool = True,
    ) -> object:
        """Choose indices, a member, or one value from a fixed option set."""

    def uniform(self, low: float, high: float) -> object:
        """Return one two-parent weight."""

    def dirichlet(self, alpha: Sequence[int]) -> object:
        """Return one three-parent weight vector."""


WeightedOffspringFactory = Callable[
    [tuple[EvolutionCrossoverMember, ...], tuple[float, ...]],
    EvolutionCrossoverMember,
]
NegativeFilterOffspringFactory = Callable[
    [EvolutionCrossoverMember, int, int],
    EvolutionCrossoverMember,
]
_RuntimeWeightedOffspringFactory = Callable[
    [tuple[EvolutionCrossoverMember, ...], tuple[float, ...]],
    object,
]
_RuntimeNegativeFilterOffspringFactory = Callable[
    [EvolutionCrossoverMember, int, int],
    object,
]


@dataclass(frozen=True, slots=True)
class EvolutionCrossoverPolicy:
    """Bounded policy corresponding to the donor method parameter."""

    n_offspring: int = DEFAULT_OFFSPRING_COUNT

    def __post_init__(self) -> None:
        if type(self.n_offspring) is not int or self.n_offspring < 0:
            raise EvolutionPopulationCrossoverError("n_offspring must be a non-negative integer")


DEFAULT_CROSSOVER_POLICY = EvolutionCrossoverPolicy()


@dataclass(frozen=True, slots=True)
class WeightedCrossoverRecord:
    """One donor-ordered pair or triple recombination."""

    parent_indices: tuple[int, ...]
    parents: tuple[EvolutionCrossoverMember, ...]
    weights: tuple[float, ...]
    offspring: EvolutionCrossoverMember


@dataclass(frozen=True, slots=True)
class NegativeFilterCrossoverRecord:
    """One donor-ordered negative-filter wrapping operation."""

    base_index: int
    base: EvolutionCrossoverMember
    kill_count: int
    kill_window: int
    offspring: EvolutionCrossoverMember


@dataclass(frozen=True, slots=True)
class EvolutionCrossoverTransition:
    """Immutable projection of every state change made by the donor method."""

    original_population: tuple[EvolutionCrossoverMember, ...]
    pair_recombinations: tuple[WeightedCrossoverRecord, ...]
    triple_recombinations: tuple[WeightedCrossoverRecord, ...]
    negative_filter_wrappings: tuple[NegativeFilterCrossoverRecord, ...]
    offspring: tuple[EvolutionCrossoverMember, ...]
    resulting_population: tuple[EvolutionCrossoverMember, ...]


def _validated_population(values: object) -> tuple[EvolutionCrossoverMember, ...]:
    if isinstance(values, (str, bytes, bytearray)) or not isinstance(values, Sequence):
        raise EvolutionPopulationCrossoverError("population must be a sequence")
    normalized = tuple(cast(Sequence[object], values))
    if any(not isinstance(value, EvolutionCrossoverMember) for value in normalized):
        raise EvolutionPopulationCrossoverError("population contains an invalid crossover member")
    return tuple(value for value in normalized if isinstance(value, EvolutionCrossoverMember))


def _validated_policy(value: object) -> EvolutionCrossoverPolicy:
    if not isinstance(value, EvolutionCrossoverPolicy):
        raise EvolutionPopulationCrossoverError("policy must be an EvolutionCrossoverPolicy")
    return value


def _validated_random_source(value: object) -> EvolutionCrossoverRandomSource:
    required_methods = ("choice", "uniform", "dirichlet")
    if any(not callable(getattr(value, method, None)) for method in required_methods):
        raise EvolutionPopulationCrossoverError(
            "random_source must provide choice(), uniform(), and dirichlet()"
        )
    return cast(EvolutionCrossoverRandomSource, value)


def _validated_weighted_factory(value: object) -> _RuntimeWeightedOffspringFactory:
    if not callable(value):
        raise EvolutionPopulationCrossoverError("make_weighted_offspring must be callable")
    return cast(_RuntimeWeightedOffspringFactory, value)


def _validated_negative_filter_factory(
    value: object,
) -> _RuntimeNegativeFilterOffspringFactory:
    if not callable(value):
        raise EvolutionPopulationCrossoverError("make_negative_filter_offspring must be callable")
    return cast(_RuntimeNegativeFilterOffspringFactory, value)


def _materialized_iterable(value: object, *, field_name: str) -> tuple[object, ...]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Iterable):
        raise EvolutionPopulationCrossoverError(f"{field_name} must be an iterable")
    return tuple(cast(Iterable[object], value))


def _validated_parent_indices(
    value: object,
    *,
    count: int,
    population_size: int,
) -> tuple[int, ...]:
    raw_indices = _materialized_iterable(value, field_name="choice indices")
    if len(raw_indices) != count:
        raise EvolutionPopulationCrossoverError(
            f"choice must return exactly {count} parent indices"
        )

    indices: list[int] = []
    for raw_index in raw_indices:
        if isinstance(raw_index, bool) or not isinstance(raw_index, Integral):
            raise EvolutionPopulationCrossoverError("parent indices must be integers")
        index = int(raw_index)
        if index < 0 or index >= population_size:
            raise EvolutionPopulationCrossoverError("parent index is outside the population")
        indices.append(index)

    if len(set(indices)) != count:
        raise EvolutionPopulationCrossoverError(
            "parent indices must be unique when replace is false"
        )
    return tuple(indices)


def _validated_finite_real(value: object, *, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise EvolutionPopulationCrossoverError(f"{field_name} must be a finite real number")
    normalized = float(value)
    if not math.isfinite(normalized):
        raise EvolutionPopulationCrossoverError(f"{field_name} must be a finite real number")
    return normalized


def _validated_pair_weight(value: object) -> float:
    weight = _validated_finite_real(value, field_name="uniform weight")
    if weight < PAIR_WEIGHT_MIN or weight > PAIR_WEIGHT_MAX:
        raise EvolutionPopulationCrossoverError(
            f"uniform weight must be between {PAIR_WEIGHT_MIN} and {PAIR_WEIGHT_MAX}"
        )
    return weight


def _validated_dirichlet_weights(value: object) -> tuple[float, float, float]:
    raw_weights = _materialized_iterable(value, field_name="dirichlet weights")
    if len(raw_weights) != len(TRIPLE_DIRICHLET_ALPHA):
        raise EvolutionPopulationCrossoverError("dirichlet must return exactly three weights")
    weights = tuple(
        _validated_finite_real(raw_weight, field_name="dirichlet weight")
        for raw_weight in raw_weights
    )
    if any(weight < 0.0 for weight in weights) or not math.isclose(
        sum(weights),
        1.0,
        rel_tol=1e-12,
        abs_tol=1e-12,
    ):
        raise EvolutionPopulationCrossoverError(
            "dirichlet weights must be non-negative and sum to one"
        )
    return cast(tuple[float, float, float], weights)


def _validated_discrete_choice(
    value: object,
    *,
    options: tuple[int, ...],
    field_name: str,
) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise EvolutionPopulationCrossoverError(f"{field_name} must be an integer")
    normalized = int(value)
    if normalized not in options:
        raise EvolutionPopulationCrossoverError(f"{field_name} must be one of {options}")
    return normalized


def _validated_offspring(value: object, *, factory_name: str) -> EvolutionCrossoverMember:
    if not isinstance(value, EvolutionCrossoverMember):
        raise EvolutionPopulationCrossoverError(
            f"{factory_name} must return an EvolutionCrossoverMember"
        )
    return value


def crossover_evolution_population(
    population: Sequence[EvolutionCrossoverMember],
    *,
    random_source: EvolutionCrossoverRandomSource,
    make_weighted_offspring: WeightedOffspringFactory,
    make_negative_filter_offspring: NegativeFilterOffspringFactory,
    policy: EvolutionCrossoverPolicy = DEFAULT_CROSSOVER_POLICY,
) -> EvolutionCrossoverTransition:
    """Return the donor-equivalent crossover transition without mutating inputs.

    The random source is called in exactly the donor's loop order.  Factories
    execute immediately after the inputs for one offspring are drawn.  Any
    factory exception propagates; malformed random or factory output fails
    closed rather than returning a partially extended population.
    """

    validated_policy = _validated_policy(policy)
    original_population = _validated_population(population)
    validated_random_source = _validated_random_source(random_source)
    validated_weighted_factory = _validated_weighted_factory(make_weighted_offspring)
    validated_negative_factory = _validated_negative_filter_factory(make_negative_filter_offspring)

    pair_records: list[WeightedCrossoverRecord] = []
    triple_records: list[WeightedCrossoverRecord] = []
    negative_filter_records: list[NegativeFilterCrossoverRecord] = []

    if len(original_population) < 2:
        return EvolutionCrossoverTransition(
            original_population=original_population,
            pair_recombinations=(),
            triple_recombinations=(),
            negative_filter_wrappings=(),
            offspring=(),
            resulting_population=original_population,
        )

    for _ in range(validated_policy.n_offspring):
        parent_indices = _validated_parent_indices(
            validated_random_source.choice(
                len(original_population),
                2,
                replace=False,
            ),
            count=2,
            population_size=len(original_population),
        )
        parents = tuple(original_population[index] for index in parent_indices)
        first_weight = _validated_pair_weight(
            validated_random_source.uniform(PAIR_WEIGHT_MIN, PAIR_WEIGHT_MAX)
        )
        weights = (first_weight, 1.0 - first_weight)
        offspring = _validated_offspring(
            validated_weighted_factory(parents, weights),
            factory_name="make_weighted_offspring",
        )
        pair_records.append(
            WeightedCrossoverRecord(
                parent_indices=parent_indices,
                parents=parents,
                weights=weights,
                offspring=offspring,
            )
        )

    if len(original_population) >= 3:
        triple_count = min(
            MAX_TRIPLE_OFFSPRING,
            validated_policy.n_offspring // 2,
        )
        for _ in range(triple_count):
            parent_indices = _validated_parent_indices(
                validated_random_source.choice(
                    len(original_population),
                    3,
                    replace=False,
                ),
                count=3,
                population_size=len(original_population),
            )
            parents = tuple(original_population[index] for index in parent_indices)
            weights = _validated_dirichlet_weights(
                validated_random_source.dirichlet(list(TRIPLE_DIRICHLET_ALPHA))
            )
            offspring = _validated_offspring(
                validated_weighted_factory(parents, weights),
                factory_name="make_weighted_offspring",
            )
            triple_records.append(
                WeightedCrossoverRecord(
                    parent_indices=parent_indices,
                    parents=parents,
                    weights=weights,
                    offspring=offspring,
                )
            )

    negative_filter_count = min(
        MAX_NEGATIVE_FILTER_OFFSPRING,
        validated_policy.n_offspring // 3,
    )
    population_choices = list(original_population)
    for _ in range(negative_filter_count):
        raw_base = validated_random_source.choice(population_choices)
        base_index = next(
            (index for index, member in enumerate(original_population) if raw_base is member),
            None,
        )
        if base_index is None:
            raise EvolutionPopulationCrossoverError(
                "choice(population) must return an original population member"
            )
        base = original_population[base_index]
        kill_count = _validated_discrete_choice(
            validated_random_source.choice(list(NEGATIVE_FILTER_KILL_COUNTS)),
            options=NEGATIVE_FILTER_KILL_COUNTS,
            field_name="kill_count",
        )
        kill_window = _validated_discrete_choice(
            validated_random_source.choice(list(NEGATIVE_FILTER_KILL_WINDOWS)),
            options=NEGATIVE_FILTER_KILL_WINDOWS,
            field_name="kill_window",
        )
        offspring = _validated_offspring(
            validated_negative_factory(base, kill_count, kill_window),
            factory_name="make_negative_filter_offspring",
        )
        negative_filter_records.append(
            NegativeFilterCrossoverRecord(
                base_index=base_index,
                base=base,
                kill_count=kill_count,
                kill_window=kill_window,
                offspring=offspring,
            )
        )

    pair_offspring = tuple(record.offspring for record in pair_records)
    triple_offspring = tuple(record.offspring for record in triple_records)
    negative_filter_offspring = tuple(record.offspring for record in negative_filter_records)
    appended_offspring = pair_offspring + triple_offspring + negative_filter_offspring
    return EvolutionCrossoverTransition(
        original_population=original_population,
        pair_recombinations=tuple(pair_records),
        triple_recombinations=tuple(triple_records),
        negative_filter_wrappings=tuple(negative_filter_records),
        offspring=appended_offspring,
        resulting_population=original_population + appended_offspring,
    )


__all__ = [
    "DEFAULT_CROSSOVER_POLICY",
    "DEFAULT_OFFSPRING_COUNT",
    "DONOR_METHOD",
    "DONOR_SOURCE",
    "DONOR_SOURCE_SHA256",
    "MAX_NEGATIVE_FILTER_OFFSPRING",
    "MAX_TRIPLE_OFFSPRING",
    "NEGATIVE_FILTER_KILL_COUNTS",
    "NEGATIVE_FILTER_KILL_WINDOWS",
    "PAIR_WEIGHT_MAX",
    "PAIR_WEIGHT_MIN",
    "TRIPLE_DIRICHLET_ALPHA",
    "EvolutionCrossoverMember",
    "EvolutionCrossoverPolicy",
    "EvolutionCrossoverRandomSource",
    "EvolutionCrossoverTransition",
    "EvolutionPopulationCrossoverError",
    "NegativeFilterCrossoverRecord",
    "NegativeFilterOffspringFactory",
    "WeightedCrossoverRecord",
    "WeightedOffspringFactory",
    "crossover_evolution_population",
]
