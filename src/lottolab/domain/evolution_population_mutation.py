"""Pure population-mutation transition from the legacy evolution engine.

The donor is ``tools/evolving_strategy_engine/evolution_engine.py`` in the
preserved ``LotteryNewMeraged`` source snapshot (sha256
``3df019c31ce48e38efc7fd8b52d3e6eb5fd6ab1927bc789785e6d1e85c794f54``).
The accessible snapshot has no Git metadata, so this module does not claim a
donor commit identity.

For valid inputs, :func:`mutate_evolution_population` preserves the donor's
``EvolutionEngine.mutate_population`` transition.  It draws once for each
parent in source order, invokes that parent's mutation immediately when the
draw is strictly below the mutation rate, passes the same random source into
the mutation operator, overwrites the mutant category with the parent
category, and appends mutants in parent order after the unchanged population.

The target adaptation injects the random source and mutation operator,
represents members and the returned transition immutably, and closes malformed
inputs before or during execution.  It has no dependency on concrete
strategies, evaluation results, persistence, schedulers, networks, or process
runtime.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from numbers import Real
from typing import Protocol, cast

DONOR_SOURCE = "tools/evolving_strategy_engine/evolution_engine.py"
DONOR_SOURCE_SHA256 = "3df019c31ce48e38efc7fd8b52d3e6eb5fd6ab1927bc789785e6d1e85c794f54"
DONOR_METHOD = "EvolutionEngine.mutate_population"

DEFAULT_MUTATION_RATE = 0.4


class EvolutionPopulationMutationError(ValueError):
    """Raised when a population-mutation input violates its closed contract."""


class EvolutionRandomSource(Protocol):
    """Minimal random-source contract exercised by the donor transition."""

    def random(self) -> object:
        """Return the next selection draw."""


@dataclass(frozen=True, slots=True)
class EvolutionMutationMember:
    """Immutable identity and category projected through one mutation step."""

    name: str
    category: str

    def __post_init__(self) -> None:
        for field_name, value in (("name", self.name), ("category", self.category)):
            if type(value) is not str or not value:
                raise EvolutionPopulationMutationError(f"{field_name} must be a non-empty string")


EvolutionMutationOperator = Callable[
    [EvolutionMutationMember, EvolutionRandomSource],
    EvolutionMutationMember,
]
_RuntimeEvolutionMutationOperator = Callable[
    [EvolutionMutationMember, EvolutionRandomSource],
    object,
]


def _validated_mutation_rate(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise EvolutionPopulationMutationError(
            "mutation_rate must be a finite real number between 0 and 1"
        )
    normalized = float(value)
    if not math.isfinite(normalized) or normalized < 0.0 or normalized > 1.0:
        raise EvolutionPopulationMutationError(
            "mutation_rate must be a finite real number between 0 and 1"
        )
    return normalized


@dataclass(frozen=True, slots=True)
class EvolutionMutationPolicy:
    """Bounded policy corresponding to the donor method parameter."""

    mutation_rate: float = DEFAULT_MUTATION_RATE

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "mutation_rate",
            _validated_mutation_rate(self.mutation_rate),
        )


DEFAULT_MUTATION_POLICY = EvolutionMutationPolicy()


@dataclass(frozen=True, slots=True)
class EvolutionMutationTransition:
    """Immutable projection of the donor's population extension."""

    original_population: tuple[EvolutionMutationMember, ...]
    selection_draws: tuple[float, ...]
    selected_parent_indices: tuple[int, ...]
    mutants: tuple[EvolutionMutationMember, ...]
    resulting_population: tuple[EvolutionMutationMember, ...]


def _validated_population(values: object) -> tuple[EvolutionMutationMember, ...]:
    if isinstance(values, (str, bytes, bytearray)) or not isinstance(values, Sequence):
        raise EvolutionPopulationMutationError("population must be a sequence")
    normalized = tuple(cast(Sequence[object], values))
    if any(not isinstance(value, EvolutionMutationMember) for value in normalized):
        raise EvolutionPopulationMutationError("population contains an invalid mutation member")
    return tuple(value for value in normalized if isinstance(value, EvolutionMutationMember))


def _validated_policy(value: object) -> EvolutionMutationPolicy:
    if not isinstance(value, EvolutionMutationPolicy):
        raise EvolutionPopulationMutationError("policy must be an EvolutionMutationPolicy")
    return value


def _validated_random_source(value: object) -> EvolutionRandomSource:
    if not callable(getattr(value, "random", None)):
        raise EvolutionPopulationMutationError("random_source must provide random()")
    return cast(EvolutionRandomSource, value)


def _validated_mutation_operator(value: object) -> _RuntimeEvolutionMutationOperator:
    if not callable(value):
        raise EvolutionPopulationMutationError("mutate must be callable")
    return cast(_RuntimeEvolutionMutationOperator, value)


def _selection_draw(random_source: EvolutionRandomSource) -> float:
    raw_draw = random_source.random()
    if isinstance(raw_draw, bool) or not isinstance(raw_draw, Real):
        raise EvolutionPopulationMutationError(
            "random_source.random() must return a finite real number in [0, 1)"
        )
    draw = float(raw_draw)
    if not math.isfinite(draw) or draw < 0.0 or draw >= 1.0:
        raise EvolutionPopulationMutationError(
            "random_source.random() must return a finite real number in [0, 1)"
        )
    return draw


def mutate_evolution_population(
    population: Sequence[EvolutionMutationMember],
    *,
    random_source: EvolutionRandomSource,
    mutate: EvolutionMutationOperator,
    policy: EvolutionMutationPolicy = DEFAULT_MUTATION_POLICY,
) -> EvolutionMutationTransition:
    """Return the donor-equivalent mutation transition without mutating inputs.

    Selection uses the donor's strict ``draw < mutation_rate`` comparison.
    The mutation operator runs immediately after a selected draw and receives
    the same stateful random source, preserving donor RNG call order.  Any
    operator exception propagates; invalid operator output fails closed rather
    than returning a partially extended population.
    """

    validated_policy = _validated_policy(policy)
    original_population = _validated_population(population)
    validated_random_source = _validated_random_source(random_source)
    validated_mutate = _validated_mutation_operator(mutate)

    selection_draws: list[float] = []
    selected_parent_indices: list[int] = []
    mutants: list[EvolutionMutationMember] = []

    for index, parent in enumerate(original_population):
        draw = _selection_draw(validated_random_source)
        selection_draws.append(draw)
        if draw < validated_policy.mutation_rate:
            raw_mutant = validated_mutate(parent, validated_random_source)
            if not isinstance(raw_mutant, EvolutionMutationMember):
                raise EvolutionPopulationMutationError(
                    "mutate must return an EvolutionMutationMember"
                )
            mutant = EvolutionMutationMember(
                name=raw_mutant.name,
                category=parent.category,
            )
            selected_parent_indices.append(index)
            mutants.append(mutant)

    appended_mutants = tuple(mutants)
    return EvolutionMutationTransition(
        original_population=original_population,
        selection_draws=tuple(selection_draws),
        selected_parent_indices=tuple(selected_parent_indices),
        mutants=appended_mutants,
        resulting_population=original_population + appended_mutants,
    )


__all__ = [
    "DEFAULT_MUTATION_POLICY",
    "DEFAULT_MUTATION_RATE",
    "DONOR_METHOD",
    "DONOR_SOURCE",
    "DONOR_SOURCE_SHA256",
    "EvolutionMutationMember",
    "EvolutionMutationOperator",
    "EvolutionMutationPolicy",
    "EvolutionMutationTransition",
    "EvolutionPopulationMutationError",
    "EvolutionRandomSource",
    "mutate_evolution_population",
]
