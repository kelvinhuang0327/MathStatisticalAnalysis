"""Pure survivor transition from the legacy strategy evolution engine.

The donor is ``tools/evolving_strategy_engine/evolution_engine.py`` in the
preserved ``LotteryNewMeraged`` source snapshot (sha256
``3df019c31ce48e38efc7fd8b52d3e6eb5fd6ab1927bc789785e6d1e85c794f54``).
The accessible snapshot has no Git metadata, so this module does not claim a
donor commit identity.

For valid inputs, :func:`select_evolution_survivors` preserves the donor's
``EvolutionEngine.select_survivors`` transition: leakage-flagged evaluations
are excluded, eligible evaluations are stably ranked by descending score, an
elite floor controls retention, only positive elites enter the hall of fame,
and population members retain their original order when filtered by survivor
name.  The target adaptation represents the mutation as an immutable result
and closes malformed inputs before the transition runs.

The mechanism is independent of strategy catalogs, evaluators, historical
performance conclusions, persistence, schedulers, networks, and process
runtime.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from numbers import Real
from typing import cast

DONOR_SOURCE = "tools/evolving_strategy_engine/evolution_engine.py"
DONOR_SOURCE_SHA256 = (
    "3df019c31ce48e38efc7fd8b52d3e6eb5fd6ab1927bc789785e6d1e85c794f54"
)
DONOR_METHOD = "EvolutionEngine.select_survivors"

DEFAULT_KEEP_RATIO = 0.5
DEFAULT_ELITE_COUNT = 5


class EvolutionSurvivorSelectionError(ValueError):
    """Raised when a survivor-transition input violates its closed contract."""


def _validated_name(name: object, *, field_name: str) -> str:
    if type(name) is not str or not name:
        raise EvolutionSurvivorSelectionError(f"{field_name} must be a non-empty string")
    return name


def _validated_finite_score(score: object) -> float:
    if isinstance(score, bool) or not isinstance(score, Real):
        raise EvolutionSurvivorSelectionError("score must be a finite real number")
    normalized = float(score)
    if not math.isfinite(normalized):
        raise EvolutionSurvivorSelectionError("score must be a finite real number")
    return normalized


@dataclass(frozen=True, slots=True)
class EvolutionCandidateEvaluation:
    """The donor fields used to decide whether one evaluated candidate survives."""

    name: str
    score: float
    leakage_detected: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _validated_name(self.name, field_name="name"))
        object.__setattr__(self, "score", _validated_finite_score(self.score))
        if type(self.leakage_detected) is not bool:
            raise EvolutionSurvivorSelectionError("leakage_detected must be a boolean")


@dataclass(frozen=True, slots=True)
class EvolutionPopulationMember:
    """A population identity projected through the donor's name-based filter."""

    name: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _validated_name(self.name, field_name="name"))


@dataclass(frozen=True, slots=True)
class EvolutionSurvivorPolicy:
    """Bounded policy corresponding to the donor method parameters."""

    keep_ratio: float = DEFAULT_KEEP_RATIO
    elite_count: int = DEFAULT_ELITE_COUNT

    def __post_init__(self) -> None:
        normalized_ratio = _validated_finite_score(self.keep_ratio)
        if normalized_ratio < 0.0 or normalized_ratio > 1.0:
            raise EvolutionSurvivorSelectionError("keep_ratio must be between 0 and 1")
        if type(self.elite_count) is not int or self.elite_count < 0:
            raise EvolutionSurvivorSelectionError(
                "elite_count must be a non-negative integer"
            )
        object.__setattr__(self, "keep_ratio", normalized_ratio)


DEFAULT_SURVIVOR_POLICY = EvolutionSurvivorPolicy()


@dataclass(frozen=True, slots=True)
class EvolutionSurvivorTransition:
    """Immutable projection of every state change made by the donor method."""

    ranked_eligible_results: tuple[EvolutionCandidateEvaluation, ...]
    elite_results: tuple[EvolutionCandidateEvaluation, ...]
    survivor_results: tuple[EvolutionCandidateEvaluation, ...]
    eliminated_results: tuple[EvolutionCandidateEvaluation, ...]
    surviving_population: tuple[EvolutionPopulationMember, ...]
    hall_of_fame_additions: tuple[EvolutionCandidateEvaluation, ...]
    graveyard_additions: tuple[str, ...]
    retention_limit: int


def _validated_results(
    values: object,
) -> tuple[EvolutionCandidateEvaluation, ...]:
    if isinstance(values, (str, bytes, bytearray)) or not isinstance(values, Sequence):
        raise EvolutionSurvivorSelectionError("results must be a sequence")
    normalized = tuple(cast(Sequence[object], values))
    if any(not isinstance(value, EvolutionCandidateEvaluation) for value in normalized):
        raise EvolutionSurvivorSelectionError(
            "results contains an invalid transition item"
        )
    return tuple(
        value for value in normalized if isinstance(value, EvolutionCandidateEvaluation)
    )


def _validated_population(
    values: object,
) -> tuple[EvolutionPopulationMember, ...]:
    if isinstance(values, (str, bytes, bytearray)) or not isinstance(values, Sequence):
        raise EvolutionSurvivorSelectionError("population must be a sequence")
    normalized = tuple(cast(Sequence[object], values))
    if any(not isinstance(value, EvolutionPopulationMember) for value in normalized):
        raise EvolutionSurvivorSelectionError(
            "population contains an invalid transition item"
        )
    return tuple(
        value for value in normalized if isinstance(value, EvolutionPopulationMember)
    )


def _validated_policy(value: object) -> EvolutionSurvivorPolicy:
    if not isinstance(value, EvolutionSurvivorPolicy):
        raise EvolutionSurvivorSelectionError("policy must be an EvolutionSurvivorPolicy")
    return value


def select_evolution_survivors(
    results: Sequence[EvolutionCandidateEvaluation],
    population: Sequence[EvolutionPopulationMember],
    *,
    policy: EvolutionSurvivorPolicy = DEFAULT_SURVIVOR_POLICY,
) -> EvolutionSurvivorTransition:
    """Return the donor-equivalent survivor transition without mutating inputs.

    Ties preserve evaluation source order because the donor uses Python's
    stable ``sorted``.  Leaked evaluations are always eliminated after ranked
    eligible losers, in their original evaluation order.  When ``results`` is
    empty, the donor returns before mutation, so the population is unchanged.
    """

    validated_policy = _validated_policy(policy)
    candidate_results = _validated_results(results)
    population_members = _validated_population(population)

    if not candidate_results:
        return EvolutionSurvivorTransition(
            ranked_eligible_results=(),
            elite_results=(),
            survivor_results=(),
            eliminated_results=(),
            surviving_population=population_members,
            hall_of_fame_additions=(),
            graveyard_additions=(),
            retention_limit=0,
        )

    eligible_results = tuple(
        result for result in candidate_results if not result.leakage_detected
    )
    ranked = tuple(
        sorted(
            eligible_results,
            key=lambda result: result.score,
            reverse=True,
        )
    )
    elites = ranked[: validated_policy.elite_count]
    hall_of_fame_additions = tuple(elite for elite in elites if elite.score > 0.0)

    retention_limit = max(
        validated_policy.elite_count,
        int(len(ranked) * validated_policy.keep_ratio),
    )
    survivors = ranked[:retention_limit]
    leaked_results = tuple(
        result for result in candidate_results if result.leakage_detected
    )
    eliminated = ranked[retention_limit:] + leaked_results

    survivor_names = {result.name for result in survivors}
    surviving_population = tuple(
        member for member in population_members if member.name in survivor_names
    )

    return EvolutionSurvivorTransition(
        ranked_eligible_results=ranked,
        elite_results=elites,
        survivor_results=survivors,
        eliminated_results=eliminated,
        surviving_population=surviving_population,
        hall_of_fame_additions=hall_of_fame_additions,
        graveyard_additions=tuple(result.name for result in eliminated),
        retention_limit=retention_limit,
    )


__all__ = [
    "DEFAULT_ELITE_COUNT",
    "DEFAULT_KEEP_RATIO",
    "DEFAULT_SURVIVOR_POLICY",
    "DONOR_METHOD",
    "DONOR_SOURCE",
    "DONOR_SOURCE_SHA256",
    "EvolutionCandidateEvaluation",
    "EvolutionPopulationMember",
    "EvolutionSurvivorPolicy",
    "EvolutionSurvivorSelectionError",
    "EvolutionSurvivorTransition",
    "select_evolution_survivors",
]
