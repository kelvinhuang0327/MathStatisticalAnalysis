# pyright: reportUnnecessaryIsInstance=false

"""Bounded research-only adaptive large neighborhood search for C(v, k, t).

Clean-room orchestration from the frozen behavioral contract of N-Wouda/ALNS
v7.0.0, commit 8ba825e8c435d5f3a9ef1622cf175b90fe5952ac (MIT). No donor source
was copied. Outcome precedence, two-stage roulette, selected-only adaptation
and top-of-loop stopping follow that contract. NumPy trajectory parity is
not claimed: reproducibility is for this implementation, configuration,
Python environment and seed, using one isolated ``random.Random``.

This is a HEURISTIC minimizing block count, with no optimality certificate.
It has no production, Matrix, replay, ranking, UI or database integration.
The existing research extra supplies the public classical-covering guard;
the ILP solver is never invoked. Histories use O(iterations) storage and
stopping uses the caller's iteration budget only.
"""

from __future__ import annotations

import itertools
import json
import math
import random
import sys
from collections import Counter
from dataclasses import dataclass
from enum import StrEnum

from lottolab.research.covering_design_setcover_ilp import (
    UnsupportedSetCoverDomainError,
)
from lottolab.research.covering_design_setcover_ilp import (
    guard_setcover_domain as _guard_setcover_domain,
)

type Block = tuple[int, ...]
type BlockState = tuple[Block, ...]
type OperatorWeights = tuple[tuple[str, float], ...]
type Coupling = tuple[tuple[bool, bool], tuple[bool, bool]]

_DESTROY_NAMES = ("RANDOM_BLOCK_REMOVAL", "REDUNDANCY_BLOCK_REMOVAL")
_REPAIR_NAMES = ("GREEDY_MAX_UNCOVERED_GAIN", "RANDOMIZED_GAIN_REPAIR")


class ALNSOutcome(StrEnum):
    BEST = "BEST"
    BETTER = "BETTER"
    ACCEPT = "ACCEPT"
    REJECT = "REJECT"


_OUTCOMES = tuple(ALNSOutcome)


class ALNSStatus(StrEnum):
    """Budget completion, never an assertion of global optimality."""

    COMPLETED = "COMPLETED"
    UNKNOWN_NOT_COMPLETED = "UNKNOWN_NOT_COMPLETED"


class CoveringDesignALNSInvariantError(RuntimeError):
    """An operator or independent coverage check found an invalid state."""


def _require_integer(name: str, value: object) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")


def _require_nonnegative_number(name: str, value: object) -> None:
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        raise ValueError(f"{name} must be a finite non-negative number")
    try:
        valid = math.isfinite(value) and value >= 0
    except OverflowError:
        valid = False
    if not valid:
        raise ValueError(f"{name} must be a finite non-negative number")


def _validate_weights(weights: tuple[float, ...], eligible: tuple[int, ...]) -> None:
    for weight in weights:
        _require_nonnegative_number("operator weight", weight)
    if not eligible or not any(weights[index] > 0 for index in eligible):
        raise ValueError("zero-total eligible operator weight")


@dataclass(frozen=True, slots=True)
class CoveringDesignALNSConfig:
    """Fixed portfolio order; scores correspond to BEST, BETTER, ACCEPT, REJECT.

    Coupling rows follow destroy registration order and columns follow repair
    registration order. Zero weights are allowed, but each eligible roulette
    distribution must have positive total weight, including after adaptation.
    """

    seed: int
    iterations: int = 100
    outcome_scores: tuple[float, float, float, float] = (5.0, 2.0, 1.0, 0.5)
    decay: float = 0.8
    destroy_fraction: float = 0.25
    destroy_operator_weights: tuple[float, float] = (1.0, 1.0)
    repair_operator_weights: tuple[float, float] = (1.0, 1.0)
    coupling: Coupling = ((True, True), (True, True))

    def __post_init__(self) -> None:
        _require_integer("seed", self.seed)
        _require_integer("iterations", self.iterations)
        if self.iterations < 0:
            raise ValueError("iterations must be >= 0")
        _require_nonnegative_number("decay", self.decay)
        if self.decay > 1:
            raise ValueError("decay must be <= 1")
        _require_nonnegative_number("destroy_fraction", self.destroy_fraction)
        if not 0 < self.destroy_fraction <= 1:
            raise ValueError("destroy_fraction must satisfy 0 < fraction <= 1")
        for name, values, size in (
            ("outcome_scores", self.outcome_scores, 4),
            ("destroy_operator_weights", self.destroy_operator_weights, 2),
            ("repair_operator_weights", self.repair_operator_weights, 2),
        ):
            if not isinstance(values, tuple) or len(values) != size:
                raise ValueError(f"{name} must be a tuple of exactly {size} numbers")
            for value in values:
                _require_nonnegative_number(name, value)
        if (
            not isinstance(self.coupling, tuple)
            or len(self.coupling) != 2
            or any(
                not isinstance(row, tuple)
                or len(row) != 2
                or any(type(flag) is not bool for flag in row)
                for row in self.coupling
            )
        ):
            raise ValueError("coupling must be a 2 by 2 tuple of booleans")
        _validate_weights(self.destroy_operator_weights, (0, 1))
        for row in self.coupling:
            eligible = tuple(index for index, enabled in enumerate(row) if enabled)
            _validate_weights(self.repair_operator_weights, eligible)


@dataclass(frozen=True, slots=True)
class ALNSIteration:
    """One completed iteration, with weights captured after adaptation."""

    iteration: int
    destroy_operator: str
    repair_operator: str
    removed_block_count: int
    candidate_block_count: int
    current_block_count: int
    best_block_count: int
    outcome: ALNSOutcome
    destroy_operator_weights: OperatorWeights
    repair_operator_weights: OperatorWeights


@dataclass(frozen=True, slots=True)
class CoveringDesignALNSResult:
    """Immutable feasible best cover and a budget-bounded research audit."""

    status: ALNSStatus
    best_blocks: BlockState
    best_block_count: int
    iterations_completed: int
    seed: int
    deterministic_configuration_identity: str
    destroy_operator_weights: OperatorWeights
    repair_operator_weights: OperatorWeights
    outcome_counts: tuple[tuple[ALNSOutcome, int], ...]
    best_objective_history: tuple[int, ...]
    operator_selection_history: tuple[ALNSIteration, ...]


@dataclass(frozen=True, slots=True)
class _Problem:
    v: int
    k: int
    t: int
    blocks: BlockState
    targets: tuple[Block, ...]
    coverage: dict[Block, frozenset[Block]]
    guard_identity: str


def _build_problem(v: int, k: int, t: int) -> _Problem:
    size = _guard_setcover_domain(v, k, t)
    blocks = tuple(itertools.combinations(range(v), k))
    targets = tuple(itertools.combinations(range(v), t))
    coverage = {block: frozenset(itertools.combinations(block, t)) for block in blocks}
    return _Problem(v, k, t, blocks, targets, coverage, size.guard_identity)


def _require_feasible(problem: _Problem, state: BlockState) -> None:
    """Validate representation and raw containment independently of gain caches."""

    if (
        not isinstance(state, tuple)
        or any(not isinstance(block, tuple) or block not in problem.blocks for block in state)
        or state != tuple(sorted(set(state)))
    ):
        raise CoveringDesignALNSInvariantError("state is not canonical unique k-blocks")
    block_sets = tuple(frozenset(block) for block in state)
    if not all(
        any(frozenset(target) <= block for block in block_sets) for target in problem.targets
    ):
        raise CoveringDesignALNSInvariantError("candidate is not a feasible covering")


def _roulette(
    weights: tuple[float, ...], eligible: tuple[int, ...], rng: random.Random
) -> int:
    _validate_weights(weights, eligible)
    # Scaling preserves ratios while avoiding overflow for large finite weights.
    maximum = max(weights[index] for index in eligible)
    scaled = tuple(weights[index] / maximum for index in eligible)
    threshold = rng.random() * sum(scaled)
    cumulative = 0.0
    for index, weight in zip(eligible, scaled, strict=True):
        cumulative += weight
        if threshold < cumulative:
            return index
    # Roundoff at the upper boundary must never select a zero-weight entry.
    return next(index for index in reversed(eligible) if weights[index] > 0)


def _select_operators(
    destroy_weights: tuple[float, ...],
    repair_weights: tuple[float, ...],
    coupling: Coupling,
    rng: random.Random,
) -> tuple[int, int]:
    destroy = _roulette(destroy_weights, (0, 1), rng)
    eligible = tuple(index for index, enabled in enumerate(coupling[destroy]) if enabled)
    repair = _roulette(repair_weights, eligible, rng)
    return destroy, repair


def _destroy_size(current: BlockState, fraction: float) -> int:
    if not current:
        raise CoveringDesignALNSInvariantError("cannot destroy an empty current cover")
    return min(len(current), max(1, math.ceil(len(current) * fraction)))


def _random_block_removal(
    problem: _Problem, current: BlockState, q: int, rng: random.Random
) -> BlockState:
    del problem
    removed = set(rng.sample(current, q))
    return tuple(block for block in current if block not in removed)


def _redundancy_block_removal(
    problem: _Problem, current: BlockState, q: int, rng: random.Random
) -> BlockState:
    del rng
    multiplicities = Counter(target for block in current for target in problem.coverage[block])
    ordered = sorted(
        current,
        key=lambda block: (
            -sum(multiplicities[target] >= 2 for target in problem.coverage[block]),
            block,
        ),
    )
    removed = set(ordered[:q])
    return tuple(block for block in current if block not in removed)


def _repair(
    problem: _Problem, destroyed: BlockState, rng: random.Random, *, randomized: bool
) -> BlockState:
    selected = set(destroyed)
    uncovered = set(problem.targets)
    for block in destroyed:
        uncovered.difference_update(problem.coverage[block])
    while uncovered:
        candidates = tuple(block for block in problem.blocks if block not in selected)
        gains = tuple(len(problem.coverage[block] & uncovered) for block in candidates)
        eligible = tuple(index for index, gain in enumerate(gains) if gain > 0)
        if not eligible:
            raise CoveringDesignALNSInvariantError("uncovered targets have no positive-gain block")
        if randomized:
            chosen = _roulette(gains, eligible, rng)
        else:
            # max keeps the first candidate on ties; candidates are lexicographic.
            chosen = max(eligible, key=lambda index: gains[index])
        block = candidates[chosen]
        selected.add(block)
        uncovered.difference_update(problem.coverage[block])
    return tuple(sorted(selected))


def _greedy_max_uncovered_gain(
    problem: _Problem, destroyed: BlockState, rng: random.Random
) -> BlockState:
    return _repair(problem, destroyed, rng, randomized=False)


def _randomized_gain_repair(
    problem: _Problem, destroyed: BlockState, rng: random.Random
) -> BlockState:
    return _repair(problem, destroyed, rng, randomized=True)


def _accept_non_worsening(candidate: int, current: int) -> bool:
    return candidate <= current


def _classify_outcome(candidate: int, current: int, best: int, accepted: bool) -> ALNSOutcome:
    outcome = ALNSOutcome.ACCEPT if accepted else ALNSOutcome.REJECT
    if candidate < current:
        outcome = ALNSOutcome.BETTER
    if candidate < best:
        outcome = ALNSOutcome.BEST
    return outcome


def _transition(
    best: BlockState, current: BlockState, candidate: BlockState, outcome: ALNSOutcome
) -> tuple[BlockState, BlockState]:
    if outcome is ALNSOutcome.BEST:
        return candidate, candidate
    if outcome in (ALNSOutcome.BETTER, ALNSOutcome.ACCEPT):
        return best, candidate
    return best, current


def _update_selected_weights(
    destroy_weights: list[float],
    repair_weights: list[float],
    destroy: int,
    repair: int,
    outcome: ALNSOutcome,
    config: CoveringDesignALNSConfig,
) -> None:
    score = config.outcome_scores[_OUTCOMES.index(outcome)]
    destroy_weights[destroy] = (
        config.decay * destroy_weights[destroy] + (1 - config.decay) * score
    )
    repair_weights[repair] = config.decay * repair_weights[repair] + (1 - config.decay) * score


def _named_weights(names: tuple[str, ...], weights: list[float]) -> OperatorWeights:
    return tuple(zip(names, weights, strict=True))


class _Search:
    """Run-local orchestration; private seams permit deterministic fault injection."""

    def __init__(self, problem: _Problem, config: CoveringDesignALNSConfig) -> None:
        self.problem = problem
        self.config = config
        self.rng = random.Random(config.seed)
        self.current = problem.blocks
        self.best = self.current
        _require_feasible(problem, self.current)
        self.destroy_weights = list(config.destroy_operator_weights)
        self.repair_weights = list(config.repair_operator_weights)
        self.history: list[ALNSIteration] = []

    def _should_stop(self) -> bool:
        return len(self.history) >= self.config.iterations

    def _accept(self, candidate_count: int, current_count: int) -> bool:
        return _accept_non_worsening(candidate_count, current_count)

    def _iterate(self) -> None:
        destroy, repair = _select_operators(
            tuple(self.destroy_weights), tuple(self.repair_weights), self.config.coupling, self.rng
        )
        destroy_operators = (_random_block_removal, _redundancy_block_removal)
        repair_operators = (_greedy_max_uncovered_gain, _randomized_gain_repair)
        q = _destroy_size(self.current, self.config.destroy_fraction)
        destroyed = destroy_operators[destroy](self.problem, self.current, q, self.rng)
        candidate = repair_operators[repair](self.problem, destroyed, self.rng)
        _require_feasible(self.problem, candidate)
        candidate_count = len(candidate)
        accepted = self._accept(candidate_count, len(self.current))
        outcome = _classify_outcome(candidate_count, len(self.current), len(self.best), accepted)
        self.best, self.current = _transition(self.best, self.current, candidate, outcome)
        _update_selected_weights(
            self.destroy_weights, self.repair_weights, destroy, repair, outcome, self.config
        )
        self._record(destroy, repair, q, candidate_count, outcome)

    def _record(
        self, destroy: int, repair: int, q: int, candidate_count: int, outcome: ALNSOutcome
    ) -> None:
        self.history.append(
            ALNSIteration(
                iteration=len(self.history) + 1,
                destroy_operator=_DESTROY_NAMES[destroy],
                repair_operator=_REPAIR_NAMES[repair],
                removed_block_count=q,
                candidate_block_count=candidate_count,
                current_block_count=len(self.current),
                best_block_count=len(self.best),
                outcome=outcome,
                destroy_operator_weights=_named_weights(_DESTROY_NAMES, self.destroy_weights),
                repair_operator_weights=_named_weights(_REPAIR_NAMES, self.repair_weights),
            )
        )

    def run(self) -> CoveringDesignALNSResult:
        while not self._should_stop():
            self._iterate()
        return self.result()

    def result(self) -> CoveringDesignALNSResult:
        _require_feasible(self.problem, self.best)
        identity = json.dumps(
            {
                "implementation": "covering-design-alns-r1",
                "method": "HEURISTIC",
                "domain": (self.problem.v, self.problem.k, self.problem.t),
                "guard": self.problem.guard_identity,
                "python": tuple(sys.version_info[:3]),
                "rng": "stdlib.random.Random",
                "seed": self.config.seed,
                "iterations": self.config.iterations,
                "outcome_order": _OUTCOMES,
                "outcome_scores": self.config.outcome_scores,
                "decay": self.config.decay,
                "destroy_fraction": self.config.destroy_fraction,
                "destroy_order": _DESTROY_NAMES,
                "repair_order": _REPAIR_NAMES,
                "initial_destroy_weights": self.config.destroy_operator_weights,
                "initial_repair_weights": self.config.repair_operator_weights,
                "coupling": self.config.coupling,
                "acceptance": "candidate_block_count<=current_block_count",
                "stopping": "iteration_count",
            },
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        return CoveringDesignALNSResult(
            status=(
                ALNSStatus.COMPLETED
                if len(self.history) == self.config.iterations
                else ALNSStatus.UNKNOWN_NOT_COMPLETED
            ),
            best_blocks=self.best,
            best_block_count=len(self.best),
            iterations_completed=len(self.history),
            seed=self.config.seed,
            deterministic_configuration_identity=identity,
            destroy_operator_weights=_named_weights(_DESTROY_NAMES, self.destroy_weights),
            repair_operator_weights=_named_weights(_REPAIR_NAMES, self.repair_weights),
            outcome_counts=tuple(
                (outcome, sum(row.outcome is outcome for row in self.history))
                for outcome in _OUTCOMES
            ),
            best_objective_history=(
                len(self.problem.blocks),
                *(row.best_block_count for row in self.history),
            ),
            operator_selection_history=tuple(self.history),
        )


def run_covering_design_alns(
    v: int, k: int, t: int, *, config: CoveringDesignALNSConfig
) -> CoveringDesignALNSResult:
    """Run the two-destroy/two-repair heuristic on a guarded classical covering.

    Valid domains satisfy v >= k >= t >= 0 and the existing ILP prebuild
    envelope (v <= 10, at most 252 candidates/targets and 10000 incidences).
    Zero iterations returns the complete feasible candidate universe. Broken
    repairs raise an invariant error before acceptance; a zero-total eligible
    roulette raises ValueError, including when adaptation creates it.
    """

    return _Search(_build_problem(v, k, t), config).run()


__all__ = [
    "ALNSIteration",
    "ALNSOutcome",
    "ALNSStatus",
    "CoveringDesignALNSConfig",
    "CoveringDesignALNSInvariantError",
    "CoveringDesignALNSResult",
    "UnsupportedSetCoverDomainError",
    "run_covering_design_alns",
]
