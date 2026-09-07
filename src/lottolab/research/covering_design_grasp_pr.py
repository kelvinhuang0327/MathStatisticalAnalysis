"""Bounded research-only GRASP + path-relinking constructor for C(v, k, t).

Clean-room behavioral reimplementation of the frozen donor characterization of
miguelcocruz/set_covering_problem, commit
4bb08f9f72517384bfa669f67409bf133cd6be27. The donor repository carries no
LICENSE file in any commit of its history, so its license is genuinely
unspecified: no donor source was copied, and the donor's randomized
semi-greedy construction, redundant-block elimination, and forward
path-relinking trajectory are treated as frozen behavioral authority rather
than re-derived here.

Three donor behaviors were deliberately NOT ported, each for a reason
established by bounded donor execution during characterization:

* The donor ``local_search`` 1-for-1 swap is dead under unit costs. It is
  gated on a strict cost improvement while a 1-for-1 exchange preserves
  cardinality, so it fired in 0/60 characterization runs. Phase 2 here is
  strict redundant-block elimination alone.
* The donor keeps no elite pool: its ``P`` is an unbounded, never-deduplicated
  archive. Bounded-pool admission, duplicate rejection, diversity and
  replacement semantics therefore have no donor authority and follow the
  Resende-Ribeiro GRASP-with-path-relinking literature instead.
* The donor's ``best_change_cost`` is seeded with the better of the two
  endpoint costs rather than the initiating cost, which lets a path solution
  displace the better endpoint in its accounting. Characterization found this
  by reading and never reproduced it in 600 bounded pairs, so it is treated as
  a latent defect and is not reproduced: the retained path solution here is
  recomputed directly from the actual current solution over the closed path.

Reproducibility (best cover, objective history, construction choices,
elite-pool evolution, path choices and audit counters) is for THIS
implementation, configuration, Python environment and seed, using one isolated
``random.Random`` instance threaded sequentially through every stochastic draw.
Exact trajectory parity with the donor's Python execution is not claimed.

This is a HEURISTIC minimizing selected block count, with no optimality
certificate: the result status never claims global optimality. The existing
research extra supplies the public classical-covering guard
(``lottolab.research.covering_design_setcover_ilp.guard_setcover_domain``);
the ILP solver is never invoked and CP-SAT is never constructed.

Scope boundary
--------------

Standalone research constructor only: no SQLite, no network access, no B649
wiring, no Matrix/replay/ranking candidate registration. Selected block count
is emergent rather than a fixed ticket count, so this is Matrix-ineligible by
the same reasoning as its covering-design siblings.
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
type Selection = tuple[int, ...]
type SolutionKey = tuple[int, BlockState]

MAX_TOTAL_EVALUATED_SOLUTIONS = 200_000


class CoveringDesignGraspPRInvariantError(RuntimeError):
    """A construction, elimination, elite-pool or path-relinking check failed closed."""


class CoveringDesignGraspPRStatus(StrEnum):
    """Heuristic completion state; never a global-optimality certificate."""

    COMPLETED_HEURISTIC = "COMPLETED_HEURISTIC"
    UNKNOWN_NOT_COMPLETED = "UNKNOWN_NOT_COMPLETED"


def _require_integer(name: str, value: object) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")


def _require_unit_interval(name: str, value: object) -> None:
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        raise ValueError(f"{name} must be a finite number in [0, 1]")
    try:
        valid = math.isfinite(value) and 0.0 <= value <= 1.0
    except OverflowError:
        valid = False
    if not valid:
        raise ValueError(f"{name} must be a finite number in [0, 1]")


@dataclass(frozen=True, slots=True)
class CoveringDesignGraspPRConfig:
    """GRASP + path-relinking parameters; validated before any search runs.

    ``alpha`` is deliberately REQUIRED and has no default. Characterization
    established that the donor exposes no canonical alpha and that alpha is
    inert at construction step 1 under unit costs, so no authority supports
    inventing one here; the caller must state it.

    ``elite_diversity_threshold`` defaults to 1, which is exactly as strong as
    the unconditional duplicate gate and therefore adds no filtering of its
    own. It only becomes a real diversity constraint at configured values of 2
    or more; do not read the default as extra filtering.
    """

    seed: int
    alpha: float
    iteration_count: int = 100
    elite_size: int = 10
    elite_diversity_threshold: int = 1
    max_path_length: int = 64

    def __post_init__(self) -> None:
        _require_integer("seed", self.seed)
        _require_unit_interval("alpha", self.alpha)
        _require_integer("iteration_count", self.iteration_count)
        if self.iteration_count < 1:
            raise ValueError("iteration_count must be >= 1")
        _require_integer("elite_size", self.elite_size)
        if self.elite_size < 1:
            raise ValueError("elite_size must be >= 1")
        _require_integer("elite_diversity_threshold", self.elite_diversity_threshold)
        if self.elite_diversity_threshold < 1:
            raise ValueError("elite_diversity_threshold must be >= 1")
        _require_integer("max_path_length", self.max_path_length)
        if self.max_path_length < 1:
            raise ValueError("max_path_length must be >= 1")


@dataclass(frozen=True, slots=True)
class CoveringDesignGraspPRResult:
    """Immutable feasible best cover and a budget-bounded research audit.

    ``local_improvement_count`` counts invocations of the strict
    redundant-block elimination operator, not the number of blocks it removed.
    ``path_relinking_skipped_count`` counts only paths skipped because the
    initial path length exceeded ``max_path_length``; an iteration with no
    eligible pre-existing elite guide simply performs no relinking and is not
    counted as a skip.
    """

    status: CoveringDesignGraspPRStatus
    best_blocks: BlockState
    best_block_count: int
    seed: int
    deterministic_configuration_identity: str
    candidate_count: int
    target_count: int
    grasp_iterations_completed: int
    constructed_solution_count: int
    local_improvement_count: int
    path_relinking_count: int
    path_relinking_skipped_count: int
    evaluated_solution_count: int
    elite_pool_final_size: int
    best_objective_history: tuple[int, ...]


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
    all_targets_mask: int
    guard_identity: str


class _EvaluationBudget:
    """Hard cap on complete candidate solutions evaluated during one run."""

    __slots__ = ("count", "limit")

    def __init__(self, limit: int) -> None:
        self.limit = limit
        self.count = 0

    def charge(self) -> None:
        self.count += 1
        if self.count > self.limit:
            raise CoveringDesignGraspPRInvariantError(
                f"evaluated solution budget exceeded: limit {self.limit}"
            )


def _coverage_mask(candidate: Block, t: int, target_index: dict[Block, int]) -> int:
    mask = 0
    for target in itertools.combinations(candidate, t):
        mask |= 1 << target_index[target]
    return mask


def _build_problem(v: int, k: int, t: int) -> _Problem:
    """Guard the domain first, then materialize canonical candidates/targets."""

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
        all_targets_mask=(1 << len(targets)) - 1,
        guard_identity=size.guard_identity,
    )


def _derived_total_evaluation_bound(
    candidate_count: int, config: CoveringDesignGraspPRConfig
) -> int:
    """Hard pre-search upper bound on evaluated solutions for this run.

    Per iteration: one construction, at most ``candidate_count`` eliminations
    after construction, at most ``max_path_length`` accepted relinking moves,
    and at most ``candidate_count`` eliminations on the retained path solution.
    """

    per_iteration = 1 + 2 * candidate_count + config.max_path_length
    return config.iteration_count * per_iteration


def _covers_all_targets(problem: _Problem, selection: Selection) -> bool:
    covered = 0
    for index in selection:
        covered |= problem.coverage_masks[index]
    return covered == problem.all_targets_mask


def _independently_verify_cover(v: int, t: int, blocks: BlockState) -> bool:
    """From-scratch postcheck: fresh target enumeration, plain set containment."""

    block_sets = tuple(frozenset(block) for block in blocks)
    return all(
        any(frozenset(target) <= block for block in block_sets)
        for target in itertools.combinations(range(v), t)
    )


def _canonical_block_tuple(problem: _Problem, selection: Selection) -> BlockState:
    return tuple(sorted(problem.candidates[index] for index in selection))


def _solution_key(problem: _Problem, selection: Selection) -> SolutionKey:
    """Canonical solution key: block count, then canonical lexicographic blocks."""

    return len(selection), _canonical_block_tuple(problem, selection)


def _better_solution(
    problem: _Problem, incumbent: Selection | None, candidate: Selection
) -> Selection:
    """Public-best update: the incumbent only ever moves to a smaller key."""

    if incumbent is None:
        return candidate
    if _solution_key(problem, candidate) < _solution_key(problem, incumbent):
        return candidate
    return incumbent


def _distance(left: Selection, right: Selection) -> int:
    """Symmetric-difference distance between two block selections."""

    return len(set(left) ^ set(right))


def _marginal_gain(problem: _Problem, index: int, uncovered_mask: int) -> int:
    """Number of currently uncovered targets newly covered by ``index``."""

    return (problem.coverage_masks[index] & uncovered_mask).bit_count()


def _greedy_ratio(gain: int) -> float:
    """Donor semi-greedy ratio for a unit-cost candidate: ``1 / gain``."""

    if gain <= 0:
        raise CoveringDesignGraspPRInvariantError("ratio is undefined for a non-positive gain")
    return 1.0 / gain


def _rcl_threshold(c_min: float, c_max: float, alpha: float) -> float:
    """Frozen RCL cutoff ``c_min + alpha * (c_max - c_min)``, evaluated exactly.

    The literal expression is not used verbatim because in IEEE-754 doubles
    ``c_min + 1.0 * (c_max - c_min)`` can fall strictly below ``c_max`` for
    reciprocal ratios reachable inside the guarded envelope (gains 3 and 14,
    for example), which would silently drop the minimum-gain candidates from
    the RCL and break the frozen ``alpha=1`` behavior. The algebraically
    identical convex form is exact at both endpoints by construction, and the
    clamp keeps the cutoff inside ``[c_min, c_max]`` so the RCL is never empty.
    """

    return min(max((1.0 - alpha) * c_min + alpha * c_max, c_min), c_max)


def _restricted_candidate_list(
    problem: _Problem,
    available: Selection,
    uncovered_mask: int,
    alpha: float,
) -> Selection:
    """Canonical ascending RCL for the current construction step.

    Only strictly positive marginal gains are eligible. The returned list is
    built in canonical ascending candidate-index order, before any RNG draw.
    """

    eligible: list[tuple[int, float]] = []
    for index in available:
        gain = _marginal_gain(problem, index, uncovered_mask)
        if gain > 0:
            eligible.append((index, _greedy_ratio(gain)))
    if not eligible:
        return ()
    ratios = [ratio for _, ratio in eligible]
    threshold = _rcl_threshold(min(ratios), max(ratios), alpha)
    return tuple(index for index, ratio in eligible if ratio <= threshold)


def _construct_solution(
    problem: _Problem,
    config: CoveringDesignGraspPRConfig,
    rng: random.Random,
    budget: _EvaluationBudget,
) -> Selection:
    """Randomized semi-greedy construction until every target is covered."""

    available = list(range(problem.candidate_count))
    selected: list[int] = []
    uncovered_mask = problem.all_targets_mask
    while uncovered_mask:
        rcl = _restricted_candidate_list(problem, tuple(available), uncovered_mask, config.alpha)
        if not rcl:
            raise CoveringDesignGraspPRInvariantError(
                "construction invariant violated: no positive-gain candidate remains"
            )
        chosen = rng.choice(rcl)
        selected.append(chosen)
        available.remove(chosen)
        uncovered_mask &= ~problem.coverage_masks[chosen]
    budget.charge()
    solution = tuple(sorted(selected))
    if not _covers_all_targets(problem, solution):
        raise CoveringDesignGraspPRInvariantError(
            "construction invariant violated: solution does not cover all targets"
        )
    return solution


def _eliminate_redundant_blocks(
    problem: _Problem, selection: Selection, budget: _EvaluationBudget
) -> Selection:
    """Strict redundant-block elimination to a fixpoint.

    Each full pass walks the selected blocks in canonical ascending order and
    removes the first block whose deletion still covers every target, then
    restarts a new canonical pass. Terminates once a complete pass removes
    nothing. The donor's 1-for-1 swap is deliberately absent.
    """

    current = tuple(sorted(selection))
    while True:
        for index in current:
            trial = tuple(other for other in current if other != index)
            if _covers_all_targets(problem, trial):
                budget.charge()
                current = trial
                break
        else:
            return current


class _ElitePool:
    """Bounded, deduplicated elite pool held in canonical solution-key order."""

    __slots__ = ("_diversity_threshold", "_max_size", "_problem", "members")

    def __init__(self, problem: _Problem, max_size: int, diversity_threshold: int) -> None:
        self._problem = problem
        self._max_size = max_size
        self._diversity_threshold = diversity_threshold
        self.members: list[Selection] = []

    def _resort(self) -> None:
        self.members.sort(key=lambda member: _solution_key(self._problem, member))

    def admit(self, candidate: Selection) -> bool:
        """Apply the duplicate, capacity, cost and diversity gates in order."""

        if any(_distance(member, candidate) == 0 for member in self.members):
            return False
        if len(self.members) < self._max_size:
            self.members.append(candidate)
            self._resort()
            return True
        costs = [len(member) for member in self.members]
        candidate_cost = len(candidate)
        minimum_distance = min(_distance(member, candidate) for member in self.members)
        improves_best = candidate_cost < min(costs)
        keeps_diversity = (
            candidate_cost <= max(costs) and minimum_distance >= self._diversity_threshold
        )
        if not (improves_best or keeps_diversity):
            return False
        self._replace_with(candidate)
        return True

    def _replace_with(self, candidate: Selection) -> None:
        """Evict the closest elite among members no cheaper than ``candidate``."""

        candidate_cost = len(candidate)
        removable = [member for member in self.members if len(member) >= candidate_cost]
        if not removable:
            raise CoveringDesignGraspPRInvariantError(
                "elite replacement invariant violated: no member is removable"
            )
        victim = min(
            removable,
            key=lambda member: (
                _distance(member, candidate),
                _solution_key(self._problem, member),
            ),
        )
        self.members.remove(victim)
        self.members.append(candidate)
        self._resort()


def _select_guide(problem: _Problem, pool: _ElitePool, current: Selection) -> Selection | None:
    """Most distant eligible elite; canonical solution key breaks a distance tie."""

    best: tuple[tuple[int, SolutionKey], Selection] | None = None
    for member in pool.members:
        distance = _distance(member, current)
        if distance == 0:
            continue
        key = (-distance, _solution_key(problem, member))
        if best is None or key < best[0]:
            best = (key, member)
    return None if best is None else best[1]


def _relink_forward(
    problem: _Problem,
    initiating: Selection,
    guide: Selection,
    budget: _EvaluationBudget,
) -> Selection:
    """Forward discrete path relinking from ``initiating`` to ``guide``.

    Only single-block toggles drawn from the current symmetric difference are
    considered, and only those yielding a feasible covering; infeasible
    intermediates are never accepted and never repaired. Every accepted move
    reduces the distance to the guide by exactly one, so the guide is always
    reached. The retained solution is recomputed from the actual current
    solution over the closed path including both endpoints, so it can never be
    worse than the better endpoint.

    Orientation is structural rather than cost-derived: the initiating
    solution is always the iteration's local optimum and the guide is always
    the elite chosen by ``_select_guide``, whatever their costs.

    RULED (CTO ruling, 2026-09-06): EQUAL_COST_ENDPOINT_ORIENTATION is
    structural. The frozen equal-cost tie rule (lexicographically smaller
    canonical key initiates) is abolished for endpoint orientation
    specifically -- lexical tie-breaks remain in force for guide, move and
    best-solution selection elsewhere in this module. Orientation is always
    initiating=local optimum -> guiding=the elite ``_select_guide`` chose
    (read before this iteration's admissions), at equal cost and unequal
    cost alike; the per-iteration sequence assigns these roles before any
    cost comparison could apply, so the tie rule is never reachable here.
    This was not a corner case: equal-cost endpoints make up 355/521 (68%)
    of relinking calls, of which 231/521 (44%) have an orientation the tie
    rule would reverse, changing the retained solution in 48/74 flip-
    eligible pairs and the full result record in 4 of 9 (domain, seed)
    configs -- kept here for provenance. That the choice matters is not
    evidence a cost-oriented rule would be better, and is not grounds to
    reopen this.

    Note on naming: ``_select_guide`` has no cost condition, so the guide is
    sometimes costlier than the initiating solution. ``forward_only`` in the
    configuration identity describes traversal direction (L towards guide),
    not the Resende-Ribeiro forward/backward taxonomy.
    """

    current = initiating
    best = initiating
    distance = _distance(current, guide)
    while distance > 0:
        moves: list[tuple[int, int, Selection]] = []
        for index in sorted(set(current) ^ set(guide)):
            if index in current:
                trial = tuple(other for other in current if other != index)
                delta = -1
            else:
                trial = tuple(sorted((*current, index)))
                delta = 1
            if _covers_all_targets(problem, trial):
                moves.append((delta, index, trial))
        if not moves:
            raise CoveringDesignGraspPRInvariantError(
                "path relinking invariant violated: no feasible single-block toggle"
            )
        moves.sort(key=lambda move: (move[0], move[1]))
        current = moves[0][2]
        new_distance = _distance(current, guide)
        if new_distance != distance - 1:
            raise CoveringDesignGraspPRInvariantError(
                "path relinking invariant violated: distance did not decrease by exactly one"
            )
        distance = new_distance
        budget.charge()
        if _solution_key(problem, current) < _solution_key(problem, best):
            best = current
    if set(current) != set(guide):
        raise CoveringDesignGraspPRInvariantError(
            "path relinking invariant violated: guide was not reached"
        )
    return best


def _configuration_identity(problem: _Problem, config: CoveringDesignGraspPRConfig) -> str:
    payload = {
        "implementation": "covering-design-grasp-pr-r1",
        "method": "HEURISTIC",
        "domain": (problem.v, problem.k, problem.t),
        "guard": problem.guard_identity,
        "python": tuple(sys.version_info[:3]),
        "rng": "stdlib.random.Random",
        "seed": config.seed,
        "alpha": config.alpha,
        "iteration_count": config.iteration_count,
        "elite_size": config.elite_size,
        "elite_diversity_threshold": config.elite_diversity_threshold,
        "max_path_length": config.max_path_length,
        "canonical_ordering": "itertools.combinations_lexicographic_index",
        "rcl": (
            "ratio=1/gain;cutoff=clamp((1-alpha)*c_min+alpha*c_max,c_min,c_max);"
            "inclusive<=;positive_gain_only"
        ),
        "local_improvement": "strict_redundant_block_elimination_to_fixpoint;no_swap",
        "path_relinking": "forward_only;single_block_toggles;feasible_only;min_block_delta",
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)


def run_covering_design_grasp_pr(
    v: int, k: int, t: int, *, config: CoveringDesignGraspPRConfig
) -> CoveringDesignGraspPRResult:
    """Run GRASP with forward path relinking on a guarded classical covering.

    Valid domains satisfy ``v >= k >= t >= 0`` and the existing ILP prebuild
    envelope (v <= 10, at most 252 candidates/targets and 10000 incidences).
    This is a HEURISTIC: the result never certifies a global optimum, and the
    returned cover is independently re-verified from scratch before return.
    """

    problem = _build_problem(v, k, t)
    bound = _derived_total_evaluation_bound(problem.candidate_count, config)
    if bound > MAX_TOTAL_EVALUATED_SOLUTIONS:
        raise ValueError(
            f"derived total evaluation bound {bound} exceeds {MAX_TOTAL_EVALUATED_SOLUTIONS}"
        )

    rng = random.Random(config.seed)
    budget = _EvaluationBudget(bound)
    pool = _ElitePool(problem, config.elite_size, config.elite_diversity_threshold)

    best: Selection | None = None
    history: list[int] = []
    iterations_completed = 0
    constructed_solution_count = 0
    local_improvement_count = 0
    path_relinking_count = 0
    path_relinking_skipped_count = 0

    for _ in range(config.iteration_count):
        # 1. Randomized semi-greedy construction.
        constructed = _construct_solution(problem, config, rng, budget)
        constructed_solution_count += 1
        # 2. Strict redundant-block elimination to the local optimum L.
        local_optimum = _eliminate_redundant_blocks(problem, constructed, budget)
        local_improvement_count += 1
        # 3. Incumbent update from L. Its effect is subsumed by step 7
        #    whenever relinking runs, because eliminating redundant blocks
        #    from a path solution that already dominates L cannot produce a
        #    larger key; it is kept because the sequence is frozen and it is
        #    the only incumbent update on a skipped or guideless iteration.
        best = _better_solution(problem, best, local_optimum)

        # 4. Guide selection reads the pool as it stood BEFORE this
        #    iteration's admissions, so no solution can guide against itself.
        path_result: Selection | None = None
        guide = _select_guide(problem, pool, local_optimum)
        if guide is not None:
            if _distance(local_optimum, guide) > config.max_path_length:
                path_relinking_skipped_count += 1
            else:
                # 5. Forward path relinking from L towards the guide.
                path_best = _relink_forward(problem, local_optimum, guide, budget)
                path_relinking_count += 1
                # 6. Strict redundant elimination on the path result -> R'.
                path_result = _eliminate_redundant_blocks(problem, path_best, budget)
                local_improvement_count += 1
                # 7. Incumbent update from R'.
                best = _better_solution(problem, best, path_result)

        # 8. Elite admission of L, then R'. The pool's own duplicate,
        #    capacity, cost and diversity gates may collapse this to one
        #    admission or to none.
        pool.admit(local_optimum)
        if path_result is not None:
            pool.admit(path_result)

        history.append(len(best))
        iterations_completed += 1

    if best is None:
        raise CoveringDesignGraspPRInvariantError("run produced no best solution")

    best_blocks = _canonical_block_tuple(problem, best)
    if not _independently_verify_cover(v, t, best_blocks):
        raise CoveringDesignGraspPRInvariantError(
            "final result failed independent cover verification"
        )

    status = (
        CoveringDesignGraspPRStatus.COMPLETED_HEURISTIC
        if iterations_completed == config.iteration_count
        else CoveringDesignGraspPRStatus.UNKNOWN_NOT_COMPLETED
    )
    return CoveringDesignGraspPRResult(
        status=status,
        best_blocks=best_blocks,
        best_block_count=len(best_blocks),
        seed=config.seed,
        deterministic_configuration_identity=_configuration_identity(problem, config),
        candidate_count=problem.candidate_count,
        target_count=problem.target_count,
        grasp_iterations_completed=iterations_completed,
        constructed_solution_count=constructed_solution_count,
        local_improvement_count=local_improvement_count,
        path_relinking_count=path_relinking_count,
        path_relinking_skipped_count=path_relinking_skipped_count,
        evaluated_solution_count=budget.count,
        elite_pool_final_size=len(pool.members),
        best_objective_history=tuple(history),
    )


__all__ = [
    "CoveringDesignGraspPRConfig",
    "CoveringDesignGraspPRInvariantError",
    "CoveringDesignGraspPRResult",
    "CoveringDesignGraspPRStatus",
    "UnsupportedSetCoverDomainError",
    "run_covering_design_grasp_pr",
]
