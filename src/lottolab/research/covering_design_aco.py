"""Bounded research-only ant colony optimization constructor for C(v, k, t).

Clean-room behavioral reimplementation of the frozen donor Ant-System + SROM
characterization of cptanalatriste/aco-set-covering, commit
025828fa54efe7f4d09297e7e7a43eecc016caa2 (MIT), layered on the Isula v2.0.1
ant-colony framework (cptanalatriste/isula, commit
434d5dabc6d90b314b960a9e2831eef35801e207). No donor Java source of either
project was copied or consulted while writing this file; the donor's
Ant-System construction, one-pass redundant-candidate local search, every-ant
pheromone reinforcement, and multi-colony orchestration are treated as frozen
behavioral authority and are not re-derived here.

Reproducibility (best solution, ant audit trajectory, pheromone trajectory)
is for THIS implementation, configuration, Python environment and seed,
using one isolated ``random.Random`` instance threaded sequentially through
every colony, iteration, ant, and stochastic draw. Exact trajectory parity
with the donor's Java execution is not claimed.

This is a HEURISTIC minimizing selected block count, with no optimality
certificate: the result status never claims global optimality. It has no
production, Matrix, replay, ranking, UI, or database integration. The
existing research extra supplies the public classical-covering guard
(``lottolab.research.covering_design_setcover_ilp.guard_setcover_domain``);
the ILP solver is never invoked.

Scope boundary
--------------

Standalone research constructor only: no SQLite, no network access, no B649
wiring, no Matrix/replay/ranking candidate registration.
"""

from __future__ import annotations

import itertools
import json
import math
import random
import sys
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

MAX_TOTAL_ANT_CONSTRUCTIONS = 10_000


class CoveringDesignACOInvariantError(RuntimeError):
    """A preprocessing, construction, roulette, or coverage check failed closed."""


class CoveringDesignACOStatus(StrEnum):
    """Heuristic completion state; never a global-optimality certificate."""

    COMPLETED_HEURISTIC = "COMPLETED_HEURISTIC"
    UNKNOWN_NOT_COMPLETED = "UNKNOWN_NOT_COMPLETED"


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


def _require_positive_number(name: str, value: object) -> None:
    _require_nonnegative_number(name, value)
    if value == 0:
        raise ValueError(f"{name} must be > 0")


@dataclass(frozen=True, slots=True)
class CoveringDesignACOConfig:
    """Donor Ant-System + SROM parameters; validated before any search runs.

    ``q`` is the donor's pheromone deposit constant Q. Every candidate,
    including dominated ones, starts at ``initial_pheromone``.
    ``colony_count * ant_count * iteration_count`` must not exceed
    ``MAX_TOTAL_ANT_CONSTRUCTIONS``. Defaults are the donor's characterized
    final run: ``alpha=1.0, beta=5.0, rho=0.8, q=1.0, initial_pheromone=1.0,
    ant_count=20, colony_count=3, iteration_count=150`` (9000 total ant
    constructions).
    """

    seed: int
    alpha: float = 1.0
    beta: float = 5.0
    rho: float = 0.8
    q: float = 1.0
    initial_pheromone: float = 1.0
    ant_count: int = 20
    colony_count: int = 3
    iteration_count: int = 150

    def __post_init__(self) -> None:
        _require_integer("seed", self.seed)
        _require_nonnegative_number("alpha", self.alpha)
        _require_nonnegative_number("beta", self.beta)
        _require_nonnegative_number("rho", self.rho)
        if self.rho > 1:
            raise ValueError("rho must be <= 1")
        _require_positive_number("q", self.q)
        _require_positive_number("initial_pheromone", self.initial_pheromone)
        _require_integer("ant_count", self.ant_count)
        if self.ant_count < 1:
            raise ValueError("ant_count must be >= 1")
        _require_integer("colony_count", self.colony_count)
        if self.colony_count < 1:
            raise ValueError("colony_count must be >= 1")
        _require_integer("iteration_count", self.iteration_count)
        if self.iteration_count < 1:
            raise ValueError("iteration_count must be >= 1")
        total = self.colony_count * self.ant_count * self.iteration_count
        if total > MAX_TOTAL_ANT_CONSTRUCTIONS:
            raise ValueError(
                "colony_count*ant_count*iteration_count must be "
                f"<= {MAX_TOTAL_ANT_CONSTRUCTIONS}"
            )


@dataclass(frozen=True, slots=True)
class CoveringDesignACOResult:
    """Immutable feasible best cover and a budget-bounded research audit."""

    status: CoveringDesignACOStatus
    best_blocks: BlockState
    best_block_count: int
    seed: int
    deterministic_configuration_identity: str
    candidate_count: int
    target_count: int
    dominated_candidate_count: int
    mandatory_candidate_count: int
    colony_count: int
    ant_count: int
    iteration_count: int
    generated_solution_count: int
    best_objective_history: tuple[int, ...]
    final_pheromone_vectors: tuple[tuple[float, ...], ...]


@dataclass(frozen=True, slots=True)
class _Problem:
    v: int
    k: int
    t: int
    candidates: tuple[Block, ...]
    targets: tuple[Block, ...]
    candidate_count: int
    target_count: int
    coverage_masks: tuple[int, ...]
    all_rows_mask: int
    guard_identity: str


@dataclass(frozen=True, slots=True)
class _AntOutcome:
    """One ant's pre- and post-local-search selection, in construction order."""

    constructed: tuple[int, ...]
    kept: tuple[int, ...]
    removed: tuple[int, ...]


def _coverage_mask(candidate: Block, t: int, target_index: dict[Block, int]) -> int:
    mask = 0
    for target in itertools.combinations(candidate, t):
        mask |= 1 << target_index[target]
    return mask


def _build_problem(v: int, k: int, t: int) -> _Problem:
    size = _guard_setcover_domain(v, k, t)
    candidates = tuple(itertools.combinations(range(v), k))
    targets = tuple(itertools.combinations(range(v), t))
    target_index = {target: index for index, target in enumerate(targets)}
    coverage_masks = tuple(_coverage_mask(candidate, t, target_index) for candidate in candidates)
    return _Problem(
        v=v,
        k=k,
        t=t,
        candidates=candidates,
        targets=targets,
        candidate_count=len(candidates),
        target_count=len(targets),
        coverage_masks=coverage_masks,
        all_rows_mask=(1 << len(targets)) - 1,
        guard_identity=size.guard_identity,
    )


def _compute_dominance(coverage_masks: tuple[int, ...]) -> tuple[bool, ...]:
    """Pairwise coverage dominance; earlier index dominated on exact ties.

    Rows/columns are never physically removed: this only marks indices, and
    all candidate indices, incidence data, and pheromone entries remain
    full-size.
    """

    count = len(coverage_masks)
    dominated = [False] * count
    popcounts = tuple(mask.bit_count() for mask in coverage_masks)
    for i in range(count):
        mask_i = coverage_masks[i]
        card_i = popcounts[i]
        for j in range(i + 1, count):
            mask_j = coverage_masks[j]
            card_j = popcounts[j]
            if (mask_i | mask_j) == mask_j and card_j >= card_i:
                dominated[i] = True
            elif (mask_i | mask_j) == mask_i and card_i >= card_j:
                dominated[j] = True
    return tuple(dominated)


def _compute_mandatory(
    coverage_masks: tuple[int, ...], dominated: tuple[bool, ...], target_count: int
) -> tuple[int, ...]:
    """Canonical sorted union of unique non-dominated coverers, one row at a time."""

    mandatory: set[int] = set()
    for row in range(target_count):
        bit = 1 << row
        coverers = [
            index
            for index, mask in enumerate(coverage_masks)
            if not dominated[index] and mask & bit
        ]
        if not coverers:
            raise CoveringDesignACOInvariantError(
                f"preprocessing invariant violated: row {row} has zero non-dominated coverers"
            )
        if len(coverers) == 1:
            mandatory.add(coverers[0])
    return tuple(sorted(mandatory))


def _selection_weight(eta: float, pheromone_value: float, alpha: float, beta: float) -> float:
    """The donor SROM transition weight: ``eta**beta * pheromone**alpha``."""

    return eta**beta * pheromone_value**alpha


def _uncovered_gain_ratio(coverage_mask: int, uncovered_mask: int, total_row_count: int) -> float:
    """eta: rows this candidate currently covers, divided by the TOTAL row count.

    The denominator is the constant ``total_row_count``, never the shrinking
    count of currently-uncovered rows.
    """

    return (coverage_mask & uncovered_mask).bit_count() / total_row_count


def _weighted_roulette(weights: tuple[float, ...], rng: random.Random) -> int:
    """Return an index into ``weights``, selected proportional to positive entries."""

    total = sum(weights)
    if not math.isfinite(total) or total <= 0:
        raise CoveringDesignACOInvariantError("invalid roulette weight total")
    threshold = rng.random() * total
    cumulative = 0.0
    for index, weight in enumerate(weights):
        cumulative += weight
        if threshold < cumulative:
            return index
    # Roundoff at the upper boundary must never select a zero-weight entry.
    return next(index for index in range(len(weights) - 1, -1, -1) if weights[index] > 0)


def _construct_ant(
    problem: _Problem,
    dominated: tuple[bool, ...],
    pheromone: tuple[float, ...],
    mandatory: tuple[int, ...],
    alpha: float,
    beta: float,
    rng: random.Random,
) -> tuple[int, ...]:
    """Preload mandatory candidates, then run SROM until every row is covered.

    No backtracking: each stochastic draw uses canonical (ascending index)
    ordering of the uncovered-row population and the eligible-candidate
    population.
    """

    selected = list(mandatory)
    visited = set(mandatory)
    uncovered_mask = problem.all_rows_mask
    for index in mandatory:
        uncovered_mask &= ~problem.coverage_masks[index]

    while uncovered_mask:
        uncovered_rows = [
            row for row in range(problem.target_count) if (uncovered_mask >> row) & 1
        ]
        row = rng.choice(uncovered_rows)
        row_bit = 1 << row
        eligible = [
            index
            for index in range(problem.candidate_count)
            if index not in visited
            and not dominated[index]
            and (problem.coverage_masks[index] & row_bit)
        ]
        if not eligible:
            raise CoveringDesignACOInvariantError(
                f"solution-construction failure: no eligible candidate covers row {row}"
            )
        weights = tuple(
            _selection_weight(
                _uncovered_gain_ratio(
                    problem.coverage_masks[index], uncovered_mask, problem.target_count
                ),
                pheromone[index],
                alpha,
                beta,
            )
            for index in eligible
        )
        chosen = eligible[_weighted_roulette(weights, rng)]
        selected.append(chosen)
        visited.add(chosen)
        uncovered_mask &= ~problem.coverage_masks[chosen]

    return tuple(selected)


def _covers_all_rows(problem: _Problem, indices: tuple[int, ...]) -> bool:
    union = 0
    for index in indices:
        union |= problem.coverage_masks[index]
    return union == problem.all_rows_mask


def _local_search(problem: _Problem, constructed: tuple[int, ...]) -> _AntOutcome:
    """One redundant-candidate pass over ``constructed``, in its own list order.

    A candidate already marked for removal earlier in this same pass may
    never act as an alternative coverer for a later candidate. Exactly one
    pass runs; repeating is never attempted.
    """

    marked: set[int] = set()
    removed_order: list[int] = []
    for position, index in enumerate(constructed):
        alternative_mask = 0
        for other_position, other_index in enumerate(constructed):
            if other_position == position or other_index in marked:
                continue
            alternative_mask |= problem.coverage_masks[other_index]
        own_mask = problem.coverage_masks[index]
        if own_mask & alternative_mask == own_mask:
            marked.add(index)
            removed_order.append(index)

    kept = tuple(index for index in constructed if index not in marked)
    if not _covers_all_rows(problem, kept):
        raise CoveringDesignACOInvariantError(
            "post-local-search feasibility failure: coverage was lost"
        )
    return _AntOutcome(constructed=constructed, kept=kept, removed=tuple(removed_order))


def _independently_verify_cover(v: int, t: int, blocks: BlockState) -> bool:
    """From-scratch postcheck: fresh target enumeration, plain set containment."""

    block_sets = tuple(frozenset(block) for block in blocks)
    return all(
        any(frozenset(target) <= block for block in block_sets)
        for target in itertools.combinations(range(v), t)
    )


def _canonical_block_tuple(problem: _Problem, indices: tuple[int, ...]) -> BlockState:
    return tuple(sorted(problem.candidates[index] for index in indices))


def _best_key(problem: _Problem, indices: tuple[int, ...]) -> tuple[int, BlockState]:
    """Minimum block count, then canonical lexicographic block tuple."""

    return len(indices), _canonical_block_tuple(problem, indices)


class _Colony:
    """One colony's isolated pheromone vector; ants/iterations run sequentially.

    No ant state or pheromone leaks between colonies; every colony reads
    from the single run-owned RNG in deterministic sequential order.
    """

    def __init__(
        self,
        problem: _Problem,
        dominated: tuple[bool, ...],
        mandatory: tuple[int, ...],
        config: CoveringDesignACOConfig,
        rng: random.Random,
    ) -> None:
        self.problem = problem
        self.dominated = dominated
        self.mandatory = mandatory
        self.config = config
        self.rng = rng
        self.pheromone: list[float] = [config.initial_pheromone] * problem.candidate_count
        self.best_indices: tuple[int, ...] | None = None
        self.best_history: list[tuple[int, ...]] = []
        self.generated_solution_count = 0

    def _construct_one_ant(self, pheromone_snapshot: tuple[float, ...]) -> _AntOutcome:
        constructed = _construct_ant(
            self.problem,
            self.dominated,
            pheromone_snapshot,
            self.mandatory,
            self.config.alpha,
            self.config.beta,
            self.rng,
        )
        return _local_search(self.problem, constructed)

    def _evaporate(self) -> None:
        rho = self.config.rho
        for index in range(self.problem.candidate_count):
            self.pheromone[index] *= rho

    def _reinforce(self, outcomes: tuple[_AntOutcome, ...]) -> None:
        q = self.config.q
        for outcome in outcomes:
            deposit = q / len(outcome.kept)
            for index in outcome.kept:
                self.pheromone[index] += deposit

    def _update_best(self, outcomes: tuple[_AntOutcome, ...]) -> None:
        for outcome in outcomes:
            if self.best_indices is None or _best_key(self.problem, outcome.kept) < _best_key(
                self.problem, self.best_indices
            ):
                self.best_indices = outcome.kept
        if self.best_indices is None:
            raise CoveringDesignACOInvariantError("iteration produced no ready ant solutions")
        self.best_history.append(self.best_indices)

    def run_iteration(self) -> tuple[_AntOutcome, ...]:
        snapshot = tuple(self.pheromone)
        outcomes = tuple(self._construct_one_ant(snapshot) for _ in range(self.config.ant_count))
        self.generated_solution_count += len(outcomes)
        self._evaporate()
        self._reinforce(outcomes)
        self._update_best(outcomes)
        return outcomes

    def run(self) -> None:
        for _ in range(self.config.iteration_count):
            self.run_iteration()


def _configuration_identity(problem: _Problem, config: CoveringDesignACOConfig) -> str:
    payload = {
        "implementation": "covering-design-aco-r1",
        "method": "HEURISTIC",
        "domain": (problem.v, problem.k, problem.t),
        "guard": problem.guard_identity,
        "python": tuple(sys.version_info[:3]),
        "rng": "stdlib.random.Random",
        "seed": config.seed,
        "alpha": config.alpha,
        "beta": config.beta,
        "rho": config.rho,
        "q": config.q,
        "initial_pheromone": config.initial_pheromone,
        "ant_count": config.ant_count,
        "colony_count": config.colony_count,
        "iteration_count": config.iteration_count,
        "canonical_ordering": "itertools.combinations_lexicographic_index",
        "preprocessing": (
            "pairwise_coverage_dominance:superset_and_cardinality_with_earlier_index_tiebreak;"
            "mandatory:non_dominated_unique_row_coverers"
        ),
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)


def run_covering_design_aco(
    v: int, k: int, t: int, *, config: CoveringDesignACOConfig
) -> CoveringDesignACOResult:
    """Run the donor Ant-System + SROM heuristic on a guarded classical covering.

    Valid domains satisfy ``v >= k >= t >= 0`` and the existing ILP prebuild
    envelope (v <= 10, at most 252 candidates/targets and 10000 incidences).
    This is a HEURISTIC: the result never certifies a global optimum, and the
    returned cover is independently re-verified from scratch before return.
    """

    problem = _build_problem(v, k, t)
    dominated = _compute_dominance(problem.coverage_masks)
    mandatory = _compute_mandatory(problem.coverage_masks, dominated, problem.target_count)

    rng = random.Random(config.seed)
    colonies: list[_Colony] = []
    for _ in range(config.colony_count):
        colony = _Colony(problem, dominated, mandatory, config, rng)
        colony.run()
        colonies.append(colony)

    history: list[int] = []
    running_best: tuple[int, ...] | None = None
    for colony in colonies:
        for candidate_indices in colony.best_history:
            if running_best is None or _best_key(problem, candidate_indices) < _best_key(
                problem, running_best
            ):
                running_best = candidate_indices
            history.append(len(running_best))

    if running_best is None:
        raise CoveringDesignACOInvariantError("run produced no best solution")

    best_blocks = _canonical_block_tuple(problem, running_best)
    if not _independently_verify_cover(v, t, best_blocks):
        raise CoveringDesignACOInvariantError("final result failed independent cover verification")

    generated_solution_count = sum(colony.generated_solution_count for colony in colonies)
    iterations_completed = sum(len(colony.best_history) for colony in colonies)
    expected_iterations = config.colony_count * config.iteration_count
    status = (
        CoveringDesignACOStatus.COMPLETED_HEURISTIC
        if iterations_completed == expected_iterations
        else CoveringDesignACOStatus.UNKNOWN_NOT_COMPLETED
    )

    return CoveringDesignACOResult(
        status=status,
        best_blocks=best_blocks,
        best_block_count=len(best_blocks),
        seed=config.seed,
        deterministic_configuration_identity=_configuration_identity(problem, config),
        candidate_count=problem.candidate_count,
        target_count=problem.target_count,
        dominated_candidate_count=sum(dominated),
        mandatory_candidate_count=len(mandatory),
        colony_count=config.colony_count,
        ant_count=config.ant_count,
        iteration_count=config.iteration_count,
        generated_solution_count=generated_solution_count,
        best_objective_history=tuple(history),
        final_pheromone_vectors=tuple(tuple(colony.pheromone) for colony in colonies),
    )


__all__ = [
    "CoveringDesignACOConfig",
    "CoveringDesignACOInvariantError",
    "CoveringDesignACOResult",
    "CoveringDesignACOStatus",
    "UnsupportedSetCoverDomainError",
    "run_covering_design_aco",
]
