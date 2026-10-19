"""Research-only classical covering-design Lagrangian-relaxation heuristic.

Clean-room behavioral reimplementation: no donor source code was read or
copied. The dual/primal update equations and the specific quirks preserved
below were characterized from observing ``guangtunbenzhu/SetCoverPy`` at
commit ``a1ff3c5cec45cc1b16541999a4adb593fa652363`` (MIT License) in a prior,
separate characterization task. This module reimplements that characterized
behavioral contract independently in pure Python; it does not port, translate,
or reuse any donor NumPy/SciPy code, and it depends on neither NumPy nor
SciPy.

* ``PYTHON_IMPLEMENTATION_REPRODUCIBLE: YES`` for identical inputs, config,
  and seed;
* ``DONOR_EXACT_TRAJECTORY_PARITY: NOT_CLAIMED`` (the donor uses a global
  NumPy RNG with unspecified seeding; this module uses one isolated
  ``random.Random(seed)`` instead);
* ``DONOR_SOURCE_COPIED: NO``.

The covering-design mapping is exact: the ground set is ``range(v)``, every
target is a canonical lexicographic ``t``-subset, every candidate ("block")
is a canonical lexicographic ``k``-subset, every candidate has unit cost, and
a candidate covers a target iff the target is a subset of the candidate. The
objective is the minimum number of candidates whose union of covered targets
is the full target universe.

This is a heuristic: the returned ``best_block_count`` is never labeled a
certified bound or a certified optimum. Use
``lottolab.research.covering_design_setcover_ilp`` for a certified-optimal
result within its own guarded envelope.

Scope boundary
--------------

This module is not a Matrix method, replay method, ranking candidate,
fixed-ticket strategy, or production API surface. No SQLite, no network
access, no CP-SAT invocation, no B649 wiring.
"""

from __future__ import annotations

import itertools
import math
import random
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Literal

from lottolab.research.covering_design_setcover_ilp import guard_setcover_domain

type Block = tuple[int, ...]
type Multiplier = tuple[float, ...]
type _OuterTerminationReason = Literal["RELATIVE_GAP_CONVERGED", "MAX_OUTER_ITERATIONS_REACHED"]
type _PassTerminationReason = Literal["CONVERGED", "MAX_PASSES_REACHED"]

# Shared safe-denominator floor. The Packet specifies this exact value for the
# adaptive-window spread denominator and the greedy mu_effective floor; the
# same value is reused for the other two "deterministic safe denominator"
# spots (pass fractional-change, outer relative-gap) since no distinct value
# was specified there and reusing one constant keeps behavior uniform.
_EPSILON_FLOOR = 1e-5


class LagrangianConfigurationError(ValueError):
    """Raised when a ``CoveringDesignLagrangianConfig`` value is invalid."""


class LagrangianInvariantError(RuntimeError):
    """Raised when an internal incidence, degree, or core-mapping invariant is violated."""


class LagrangianNumericalError(RuntimeError):
    """Raised for a non-finite multiplier, non-finite dual value, or invalid step denominator."""


class LagrangianPrimalInfeasibleError(RuntimeError):
    """Raised when greedy primal construction cannot reach an independently verified cover."""


class CoveringDesignLagrangianStatus(StrEnum):
    """Heuristic completion state. Never a certified-bound or certified-optimum claim."""

    COMPLETED_HEURISTIC = "COMPLETED_HEURISTIC"
    UNKNOWN_NOT_COMPLETED = "UNKNOWN_NOT_COMPLETED"


def _require_integer(name: str, value: object) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise LagrangianConfigurationError(f"{name} must be an integer, got {value!r}")


def _require_positive_finite(name: str, value: object) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise LagrangianConfigurationError(f"{name} must be a finite number, got {value!r}")
    if not math.isfinite(value):
        raise LagrangianConfigurationError(f"{name} must be finite, got {value!r}")
    if value <= 0:
        raise LagrangianConfigurationError(f"{name} must be > 0, got {value!r}")


def _require_nonnegative_finite(name: str, value: object) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise LagrangianConfigurationError(f"{name} must be a finite number, got {value!r}")
    if not math.isfinite(value):
        raise LagrangianConfigurationError(f"{name} must be finite, got {value!r}")
    if value < 0:
        raise LagrangianConfigurationError(f"{name} must be >= 0, got {value!r}")


@dataclass(frozen=True, slots=True)
class CoveringDesignLagrangianConfig:
    """Immutable, validated, caller-owned run configuration.

    ``greedy_iteration_cap`` of ``None`` derives a safe default from the
    instance's own core candidate count at solve time (sufficient to select
    every core candidate at most once); it deliberately does not expose the
    donor's arbitrary fixed 1000 cap.
    """

    seed: int
    max_outer_iterations: int = 20
    subgradient_steps_per_window: int = 20
    subgradient_window_count: int = 15
    subgradient_max_passes: int = 100
    initial_stepsize: float = 0.1
    subgradient_max_fractional_change: float = 0.000020
    subgradient_max_absolute_change: float = 0.010
    adaptive_high_threshold: float = 0.06
    adaptive_low_threshold: float = 0.002
    multiplier_perturbation: float = 0.06
    outer_gap_threshold: float = 0.001
    tracked_dual_regression_tolerance: float = 0.050
    greedy_iteration_cap: int | None = None

    def __post_init__(self) -> None:
        _require_integer("seed", self.seed)
        for name in (
            "max_outer_iterations",
            "subgradient_steps_per_window",
            "subgradient_window_count",
            "subgradient_max_passes",
        ):
            value = getattr(self, name)
            _require_integer(name, value)
            if value < 1:
                raise LagrangianConfigurationError(f"{name} must be >= 1, got {value!r}")

        _require_positive_finite("initial_stepsize", self.initial_stepsize)
        for name in (
            "subgradient_max_fractional_change",
            "subgradient_max_absolute_change",
            "adaptive_high_threshold",
            "adaptive_low_threshold",
            "multiplier_perturbation",
            "outer_gap_threshold",
            "tracked_dual_regression_tolerance",
        ):
            _require_nonnegative_finite(name, getattr(self, name))

        if self.adaptive_low_threshold >= self.adaptive_high_threshold:
            raise LagrangianConfigurationError(
                "adaptive_low_threshold must be < adaptive_high_threshold"
            )

        if self.greedy_iteration_cap is not None:
            _require_integer("greedy_iteration_cap", self.greedy_iteration_cap)
            if self.greedy_iteration_cap < 1:
                raise LagrangianConfigurationError("greedy_iteration_cap must be >= 1")

    @property
    def steps_per_pass(self) -> int:
        return self.subgradient_steps_per_window * self.subgradient_window_count


@dataclass(frozen=True, slots=True)
class CoveringDesignLagrangianResult:
    """Observable heuristic run state. No certified-bound or certified-optimum field."""

    status: CoveringDesignLagrangianStatus
    best_blocks: tuple[Block, ...]
    best_block_count: int
    seed: int
    deterministic_configuration_identity: str

    candidate_count: int
    target_count: int
    fixed_block_count: int
    core_candidate_count: int
    core_target_count: int

    outer_iterations_completed: int
    subgradient_call_count: int
    primal_solutions_evaluated: int

    tracked_accepted_dual_value: float
    best_observed_lagrangian_value: float

    best_primal_history: tuple[int, ...]
    tracked_dual_history: tuple[float, ...]
    working_stepsize_history: tuple[float, ...]
    termination_reason: _OuterTerminationReason


# ---------------------------------------------------------------------------
# Full instance: canonical enumeration and full incidence.
# ---------------------------------------------------------------------------


def _bitmask(block: Block) -> int:
    mask = 0
    for element in block:
        mask |= 1 << element
    return mask


@dataclass(frozen=True, slots=True)
class _FullInstance:
    v: int
    k: int
    t: int
    candidates: tuple[Block, ...]
    targets: tuple[Block, ...]
    covering_candidate_indices_by_target: tuple[tuple[int, ...], ...]


def _build_full_instance(v: int, k: int, t: int) -> _FullInstance:
    """Enumerate the guarded candidate/target universe and full incidence.

    Callers must invoke ``guard_setcover_domain`` first; this function performs
    no size guarding of its own.
    """

    candidates = tuple(itertools.combinations(range(v), k))
    targets = tuple(itertools.combinations(range(v), t))
    candidate_masks = tuple(_bitmask(block) for block in candidates)
    target_masks = tuple(_bitmask(block) for block in targets)

    covering_candidate_indices_by_target = tuple(
        tuple(
            cand_idx
            for cand_idx, cand_mask in enumerate(candidate_masks)
            if (target_mask & cand_mask) == target_mask
        )
        for target_mask in target_masks
    )
    return _FullInstance(
        v=v,
        k=k,
        t=t,
        candidates=candidates,
        targets=targets,
        covering_candidate_indices_by_target=covering_candidate_indices_by_target,
    )


# ---------------------------------------------------------------------------
# Fixed/unique-block preprocessing and full<->core index mapping.
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _CoreInstance:
    fixed_candidate_indices: tuple[int, ...]
    fixed_cost: int
    core_candidate_full_indices: tuple[int, ...]
    core_target_full_indices: tuple[int, ...]
    core_covering_candidate_indices_by_target: tuple[tuple[int, ...], ...]
    core_covering_target_indices_by_candidate: tuple[tuple[int, ...], ...]


def _build_core_instance(full: _FullInstance) -> _CoreInstance:
    candidate_masks = tuple(_bitmask(block) for block in full.candidates)
    target_masks = tuple(_bitmask(block) for block in full.targets)

    fixed: set[int] = set()
    for coverers in full.covering_candidate_indices_by_target:
        if len(coverers) == 0:
            raise LagrangianInvariantError(
                "internal incidence invariant violated: a target has zero covering candidates"
            )
        if len(coverers) == 1:
            fixed.add(coverers[0])
    fixed_candidate_indices = tuple(sorted(fixed))
    fixed_candidate_masks = tuple(candidate_masks[idx] for idx in fixed_candidate_indices)

    def _is_fixed_covered(target_mask: int) -> bool:
        return any(
            (target_mask & fixed_mask) == target_mask for fixed_mask in fixed_candidate_masks
        )

    core_target_full_indices = tuple(
        t_idx for t_idx, mask in enumerate(target_masks) if not _is_fixed_covered(mask)
    )
    core_candidate_full_indices = tuple(
        c_idx for c_idx in range(len(full.candidates)) if c_idx not in fixed
    )

    core_covering_candidate_indices_by_target = tuple(
        tuple(
            core_c_idx
            for core_c_idx, full_c_idx in enumerate(core_candidate_full_indices)
            if (target_masks[full_t_idx] & candidate_masks[full_c_idx]) == target_masks[full_t_idx]
        )
        for full_t_idx in core_target_full_indices
    )
    if any(len(coverers) == 0 for coverers in core_covering_candidate_indices_by_target):
        raise LagrangianInvariantError(
            "impossible core mapping: a core target has no remaining core covering candidate"
        )

    core_covering_target_indices_by_candidate = tuple(
        tuple(
            core_t_idx
            for core_t_idx, full_t_idx in enumerate(core_target_full_indices)
            if (target_masks[full_t_idx] & candidate_masks[full_c_idx]) == target_masks[full_t_idx]
        )
        for full_c_idx in core_candidate_full_indices
    )

    return _CoreInstance(
        fixed_candidate_indices=fixed_candidate_indices,
        fixed_cost=len(fixed_candidate_indices),
        core_candidate_full_indices=core_candidate_full_indices,
        core_target_full_indices=core_target_full_indices,
        core_covering_candidate_indices_by_target=core_covering_candidate_indices_by_target,
        core_covering_target_indices_by_candidate=core_covering_target_indices_by_candidate,
    )


# ---------------------------------------------------------------------------
# Initial multipliers.
# ---------------------------------------------------------------------------


def _default_initial_multiplier(core: _CoreInstance) -> Multiplier:
    """Per-target minimum adjusted cost among its core coverers (unit cost -> 1/degree)."""

    u: list[float] = []
    for coverers in core.core_covering_candidate_indices_by_target:
        if not coverers:
            raise LagrangianInvariantError(
                "impossible core mapping: core target has no coverer for initial multiplier"
            )
        best: float | None = None
        for core_c_idx in coverers:
            degree = len(core.core_covering_target_indices_by_candidate[core_c_idx])
            if degree <= 0:
                # A candidate that covers this target has, by definition, degree
                # >= 1; this branch defends against a broken core mapping rather
                # than reproducing the donor's zero-degree-column NaN/inf path.
                raise LagrangianNumericalError(
                    "zero-degree core candidate encountered while computing initial multiplier"
                )
            adjusted_cost = 1.0 / degree
            if best is None or adjusted_cost < best:
                best = adjusted_cost
        assert best is not None
        u.append(best)
    return tuple(u)


def _random_initial_multiplier(core: _CoreInstance, rng: random.Random) -> Multiplier:
    return tuple(rng.random() for _ in core.core_target_full_indices)


# ---------------------------------------------------------------------------
# Reduced cost, relaxed selection, Lagrangian value.
# ---------------------------------------------------------------------------


def _validate_multiplier(u: Sequence[float]) -> None:
    for value in u:
        if not math.isfinite(value) or value < 0.0:
            raise LagrangianNumericalError(f"invalid multiplier component: {value!r}")


def _reduced_costs(core: _CoreInstance, u: Multiplier) -> tuple[float, ...]:
    return tuple(
        1.0 - sum(u[core_t_idx] for core_t_idx in covered_targets)
        for covered_targets in core.core_covering_target_indices_by_candidate
    )


def _relaxed_selected_indices(reduced_costs: Sequence[float]) -> tuple[int, ...]:
    return tuple(idx for idx, cost in enumerate(reduced_costs) if cost < 0.0)


def _core_lagrangian_value(u: Multiplier, reduced_costs: Sequence[float]) -> float:
    value = math.fsum(u) + math.fsum(cost for cost in reduced_costs if cost < 0.0)
    if not math.isfinite(value):
        raise LagrangianNumericalError("non-finite core Lagrangian value encountered")
    return value


# ---------------------------------------------------------------------------
# Subgradient step.
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _StepOutcome:
    u: Multiplier
    lagrangian_value: float
    was_stationary: bool


def _subgradient_vector(core: _CoreInstance, selected_indices: Sequence[int]) -> tuple[float, ...]:
    coverage_count = [0] * len(core.core_target_full_indices)
    for core_c_idx in selected_indices:
        for core_t_idx in core.core_covering_target_indices_by_candidate[core_c_idx]:
            coverage_count[core_t_idx] += 1
    return tuple(1.0 - count for count in coverage_count)


def _apply_subgradient_step(
    core: _CoreInstance,
    u: Multiplier,
    stepsize: float,
    ub_core: float,
) -> _StepOutcome:
    _validate_multiplier(u)
    reduced = _reduced_costs(core, u)
    selected = _relaxed_selected_indices(reduced)
    l_value = _core_lagrangian_value(u, reduced)

    subgradient = _subgradient_vector(core, selected)
    norm_sq = math.fsum(component * component for component in subgradient)

    if norm_sq == 0.0:
        # Frozen contract: a zero subgradient means this multiplier already
        # satisfies every relaxed constraint at equality; treat it as
        # stationary for this step rather than dividing by zero.
        return _StepOutcome(u=u, lagrangian_value=l_value, was_stationary=True)

    scale = stepsize * (ub_core - l_value) / norm_sq
    next_u = tuple(max(0.0, ui + scale * gi) for ui, gi in zip(u, subgradient, strict=True))
    _validate_multiplier(next_u)

    next_reduced = _reduced_costs(core, next_u)
    next_l_value = _core_lagrangian_value(next_u, next_reduced)
    return _StepOutcome(u=next_u, lagrangian_value=next_l_value, was_stationary=False)


# ---------------------------------------------------------------------------
# Subgradient pass: perturbation, windows, adaptive stepsize, promotion.
# ---------------------------------------------------------------------------


def _perturb_multiplier(u: Multiplier, amount: float, rng: random.Random) -> Multiplier:
    perturbed = tuple(max(0.0, ui * (1.0 + rng.uniform(-1.0, 1.0) * amount)) for ui in u)
    _validate_multiplier(perturbed)
    return perturbed


def _argmax_first_index(values: Sequence[float]) -> int:
    best_index = 0
    best_value = values[0]
    for index in range(1, len(values)):
        if values[index] > best_value:
            best_value = values[index]
            best_index = index
    return best_index


@dataclass(frozen=True, slots=True)
class _PassOutcome:
    snapshots: tuple[tuple[Multiplier, float], ...]
    best_u: Multiplier
    best_l: float
    stepsize_after: float


def _run_subgradient_pass(
    core: _CoreInstance,
    u_start: Multiplier,
    stepsize_start: float,
    ub_core: float,
    config: CoveringDesignLagrangianConfig,
    rng: random.Random,
) -> _PassOutcome:
    u = _perturb_multiplier(u_start, config.multiplier_perturbation, rng)
    stepsize = stepsize_start

    pass_l: list[float] = []
    pass_u: list[Multiplier] = []

    for _window in range(config.subgradient_window_count):
        window_l: list[float] = []
        window_u: list[Multiplier] = []
        for _step in range(config.subgradient_steps_per_window):
            outcome = _apply_subgradient_step(core, u, stepsize, ub_core)
            u = outcome.u
            window_l.append(outcome.lagrangian_value)
            window_u.append(u)

        window_max = max(window_l)
        window_min = min(window_l)
        # Donor-equivalent floor: only the denominator is protected, never the
        # raw spread, matching "window_max_adjusted" in the frozen contract.
        denom = window_max if window_max > 0 else _EPSILON_FLOOR
        fractional_spread = (window_max - window_min) / abs(denom)
        if fractional_spread > config.adaptive_high_threshold:
            stepsize *= 0.5
        elif fractional_spread < config.adaptive_low_threshold and stepsize < 1.5:
            # Intentionally not post-clamped: this multiplication may push
            # stepsize slightly above 1.5 exactly once, per frozen contract.
            stepsize *= 1.5

        # Best-in-window promotion: continue the next window from the highest
        # L observed in this window rather than its chronologically-last step.
        best_in_window = _argmax_first_index(window_l)
        u = window_u[best_in_window]

        pass_l.extend(window_l)
        pass_u.extend(window_u)

    best_in_pass = _argmax_first_index(pass_l)
    return _PassOutcome(
        snapshots=tuple(zip(pass_u, pass_l, strict=True)),
        best_u=pass_u[best_in_pass],
        best_l=pass_l[best_in_pass],
        stepsize_after=stepsize,
    )


# ---------------------------------------------------------------------------
# Subgradient call: a bounded sequence of passes with both-small convergence.
# ---------------------------------------------------------------------------


def _pass_convergence_metrics(previous_best_l: float, current_best_l: float) -> tuple[float, float]:
    absolute_change = current_best_l - previous_best_l
    denom = current_best_l if current_best_l != 0.0 else _EPSILON_FLOOR
    fractional_change = absolute_change / abs(denom)
    return absolute_change, fractional_change


def _pass_has_converged(
    absolute_change: float, fractional_change: float, config: CoveringDesignLagrangianConfig
) -> bool:
    return (
        abs(fractional_change) <= config.subgradient_max_fractional_change
        and abs(absolute_change) <= config.subgradient_max_absolute_change
    )


@dataclass(frozen=True, slots=True)
class _SubgradientCallResult:
    snapshots: tuple[tuple[Multiplier, float], ...]
    final_u: Multiplier
    final_stepsize: float
    passes_completed: int
    termination: _PassTerminationReason


def _run_subgradient_call(
    core: _CoreInstance,
    u_entry: Multiplier,
    stepsize_entry: float,
    ub_core: float,
    config: CoveringDesignLagrangianConfig,
    rng: random.Random,
) -> _SubgradientCallResult:
    previous_best_l = _core_lagrangian_value(u_entry, _reduced_costs(core, u_entry))

    current_u = u_entry
    stepsize = stepsize_entry
    snapshots: tuple[tuple[Multiplier, float], ...] = ()
    termination: _PassTerminationReason = "MAX_PASSES_REACHED"
    passes_completed = 0

    for _pass_index in range(config.subgradient_max_passes):
        outcome = _run_subgradient_pass(core, current_u, stepsize, ub_core, config, rng)
        passes_completed += 1
        snapshots = outcome.snapshots

        absolute_change, fractional_change = _pass_convergence_metrics(
            previous_best_l, outcome.best_l
        )
        current_u = outcome.best_u
        stepsize = outcome.stepsize_after
        previous_best_l = outcome.best_l

        if _pass_has_converged(absolute_change, fractional_change, config):
            termination = "CONVERGED"
            break

    return _SubgradientCallResult(
        snapshots=snapshots,
        final_u=current_u,
        final_stepsize=stepsize,
        passes_completed=passes_completed,
        termination=termination,
    )


# ---------------------------------------------------------------------------
# Dual-guided greedy primal construction.
# ---------------------------------------------------------------------------


def _effective_greedy_cap(config: CoveringDesignLagrangianConfig, core_candidate_count: int) -> int:
    if config.greedy_iteration_cap is not None:
        return config.greedy_iteration_cap
    return core_candidate_count


def _greedy_score(gamma: float, mu_effective: float) -> float:
    if gamma >= 0.0:
        return gamma / mu_effective
    return gamma * mu_effective


def _construct_greedy_primal(core: _CoreInstance, u: Multiplier, cap: int) -> tuple[int, ...]:
    """Return selected CORE candidate indices covering every core target.

    Always starts from an empty selection (fixed blocks are tracked
    separately and added back by the caller). Raises
    ``LagrangianPrimalInfeasibleError`` rather than returning an incomplete
    cover.
    """

    core_target_count = len(core.core_target_full_indices)
    core_candidate_count = len(core.core_candidate_full_indices)
    uncovered = set(range(core_target_count))
    selected: list[int] = []
    selected_set: set[int] = set()
    iterations = 0

    while uncovered:
        if len(selected_set) >= core_candidate_count or iterations >= cap:
            raise LagrangianPrimalInfeasibleError(
                "greedy primal construction failed to reach a feasible cover "
                "within the safe iteration cap"
            )
        iterations += 1

        best_candidate: int | None = None
        best_score: float | None = None
        for core_c_idx in range(core_candidate_count):
            if core_c_idx in selected_set:
                continue
            covered_targets = core.core_covering_target_indices_by_candidate[core_c_idx]
            newly_covered = [idx for idx in covered_targets if idx in uncovered]
            mu_effective = max(float(len(newly_covered)), _EPSILON_FLOOR)
            gamma = 1.0 - math.fsum(u[idx] for idx in newly_covered)
            score = _greedy_score(gamma, mu_effective)
            if best_score is None or score < best_score:
                best_score = score
                best_candidate = core_c_idx

        assert best_candidate is not None  # guaranteed by the guard above
        selected.append(best_candidate)
        selected_set.add(best_candidate)
        uncovered.difference_update(core.core_covering_target_indices_by_candidate[best_candidate])

    return tuple(selected)


def _core_solution_is_feasible(core: _CoreInstance, selected: Sequence[int]) -> bool:
    covered: set[int] = set()
    for core_c_idx in selected:
        covered.update(core.core_covering_target_indices_by_candidate[core_c_idx])
    return len(covered) == len(core.core_target_full_indices)


def _full_blocks_from_core_selection(
    full: _FullInstance, core: _CoreInstance, core_selected: Sequence[int]
) -> tuple[Block, ...]:
    full_indices = sorted(
        [
            *core.fixed_candidate_indices,
            *(core.core_candidate_full_indices[i] for i in core_selected),
        ]
    )
    return tuple(full.candidates[idx] for idx in full_indices)


@dataclass(frozen=True, slots=True)
class _PrimalObservation:
    core_selected: tuple[int, ...]
    full_blocks: tuple[Block, ...]
    block_count: int


def _full_solution_is_feasible(full: _FullInstance, blocks: Sequence[Block]) -> bool:
    """Verify a returned cover independently of the reduced core mapping."""

    if any(block not in full.candidates for block in blocks):
        return False
    block_masks = tuple(_bitmask(block) for block in blocks)
    return all(
        any((target_mask & block_mask) == target_mask for block_mask in block_masks)
        for target_mask in (_bitmask(target) for target in full.targets)
    )


def _observe_primal(
    full: _FullInstance, core: _CoreInstance, u: Multiplier, cap: int
) -> _PrimalObservation:
    core_selected = _construct_greedy_primal(core, u, cap)
    if not _core_solution_is_feasible(core, core_selected):
        raise LagrangianPrimalInfeasibleError(
            "constructed core primal solution failed independent feasibility verification"
        )
    full_blocks = _full_blocks_from_core_selection(full, core, core_selected)
    if len(full_blocks) != len(set(full_blocks)):
        raise LagrangianInvariantError("constructed full solution contains duplicate blocks")
    if not _full_solution_is_feasible(full, full_blocks):
        raise LagrangianPrimalInfeasibleError(
            "constructed full primal solution failed independent feasibility verification"
        )
    return _PrimalObservation(
        core_selected=core_selected, full_blocks=full_blocks, block_count=len(full_blocks)
    )


# ---------------------------------------------------------------------------
# Outer loop: restart, double-subgradient, snapshot enumeration, acceptance.
# ---------------------------------------------------------------------------


def _relative_gap(best_primal_cost: int, tracked_dual_value: float) -> float:
    denom = best_primal_cost if best_primal_cost != 0 else _EPSILON_FLOOR
    return (best_primal_cost - tracked_dual_value) / abs(denom)


def _select_best_snapshot_index(
    block_counts: Sequence[int], lagrangian_values: Sequence[float]
) -> int:
    """Minimum block count; ties broken by maximum L; ties broken by earliest index."""

    best_index = 0
    for index in range(1, len(block_counts)):
        if block_counts[index] < block_counts[best_index] or (
            block_counts[index] == block_counts[best_index]
            and lagrangian_values[index] > lagrangian_values[best_index]
        ):
            best_index = index
    return best_index


def _dual_regressed_too_much(
    candidate_dual_value: float, tracked_dual_value: float, config: CoveringDesignLagrangianConfig
) -> bool:
    return candidate_dual_value - tracked_dual_value < -(
        abs(tracked_dual_value) * config.tracked_dual_regression_tolerance
    )


def _is_strictly_better_public_solution(
    candidate_block_count: int,
    candidate_blocks: tuple[Block, ...],
    current_best_block_count: int | None,
    current_best_blocks: tuple[Block, ...] | None,
) -> bool:
    if current_best_block_count is None or current_best_blocks is None:
        return True
    if candidate_block_count != current_best_block_count:
        return candidate_block_count < current_best_block_count
    return candidate_blocks < current_best_blocks


def _deterministic_configuration_identity(
    config: CoveringDesignLagrangianConfig, core_candidate_count: int, core_target_count: int
) -> str:
    return (
        "covering-design-lagrangian-v1;"
        f"seed={config.seed};"
        f"max_outer_iterations={config.max_outer_iterations};"
        f"subgradient_steps_per_window={config.subgradient_steps_per_window};"
        f"subgradient_window_count={config.subgradient_window_count};"
        f"subgradient_max_passes={config.subgradient_max_passes};"
        f"initial_stepsize={config.initial_stepsize!r};"
        f"subgradient_max_fractional_change={config.subgradient_max_fractional_change!r};"
        f"subgradient_max_absolute_change={config.subgradient_max_absolute_change!r};"
        f"adaptive_high_threshold={config.adaptive_high_threshold!r};"
        f"adaptive_low_threshold={config.adaptive_low_threshold!r};"
        f"multiplier_perturbation={config.multiplier_perturbation!r};"
        f"outer_gap_threshold={config.outer_gap_threshold!r};"
        f"tracked_dual_regression_tolerance={config.tracked_dual_regression_tolerance!r};"
        f"greedy_iteration_cap={config.greedy_iteration_cap!r};"
        f"core_candidate_count={core_candidate_count};"
        f"core_target_count={core_target_count}"
    )


def run_covering_design_lagrangian(
    v: int,
    k: int,
    t: int,
    *,
    config: CoveringDesignLagrangianConfig,
) -> CoveringDesignLagrangianResult:
    """Run the research-only Lagrangian-relaxation covering-design heuristic.

    Requires ``v >= k >= t >= 0`` and a size within
    ``covering_design_setcover_ilp.guard_setcover_domain``. Never returns a
    certified bound or certified optimum; ``best_block_count`` is the best
    independently-verified feasible cover observed during this run.
    """

    guard_setcover_domain(v, k, t)
    full = _build_full_instance(v, k, t)
    core = _build_core_instance(full)
    cap = _effective_greedy_cap(config, len(core.core_candidate_full_indices))
    rng = random.Random(config.seed)

    default_u = _default_initial_multiplier(core)
    stepsize = config.initial_stepsize

    initial_observation = _observe_primal(full, core, default_u, cap)
    tracked_best_block_count = initial_observation.block_count
    tracked_best_dual_value = core.fixed_cost + _core_lagrangian_value(
        default_u, _reduced_costs(core, default_u)
    )
    best_observed_lagrangian_value = tracked_best_dual_value

    public_best_block_count: int | None = initial_observation.block_count
    public_best_blocks: tuple[Block, ...] | None = initial_observation.full_blocks

    best_primal_history: list[int] = [tracked_best_block_count]
    tracked_dual_history: list[float] = [tracked_best_dual_value]
    working_stepsize_history: list[float] = [stepsize]

    subgradient_call_count = 0
    primal_solutions_evaluated = 1

    outer_iteration = 0
    termination_reason: _OuterTerminationReason = "MAX_OUTER_ITERATIONS_REACHED"

    while outer_iteration < config.max_outer_iterations:
        relative_gap = _relative_gap(tracked_best_block_count, tracked_best_dual_value)
        if relative_gap <= config.outer_gap_threshold:
            termination_reason = "RELATIVE_GAP_CONVERGED"
            break

        # Multiplier restart: even outer_iteration (including 0) uses random;
        # odd uses the deterministic default.
        restart_u = _random_initial_multiplier(core, rng) if outer_iteration % 2 == 0 else default_u

        ub_core = float(tracked_best_block_count - core.fixed_cost)

        # Donor-frozen double call: the first call's returned sequence is
        # discarded for primal enumeration; only its mutated (u, stepsize)
        # state seeds the second call, which supplies the real snapshots.
        first_call = _run_subgradient_call(core, restart_u, stepsize, ub_core, config, rng)
        subgradient_call_count += 1
        second_call = _run_subgradient_call(
            core, first_call.final_u, first_call.final_stepsize, ub_core, config, rng
        )
        subgradient_call_count += 1
        stepsize = second_call.final_stepsize  # working stepsize is never reset here

        candidate_observations: list[_PrimalObservation] = []
        for snapshot_u, _snapshot_l in second_call.snapshots:
            observation = _observe_primal(full, core, snapshot_u, cap)
            primal_solutions_evaluated += 1
            candidate_observations.append(observation)
            if _is_strictly_better_public_solution(
                observation.block_count,
                observation.full_blocks,
                public_best_block_count,
                public_best_blocks,
            ):
                public_best_block_count = observation.block_count
                public_best_blocks = observation.full_blocks

        snapshot_lagrangian_values = [l_value for (_u, l_value) in second_call.snapshots]
        best_snapshot_index = _select_best_snapshot_index(
            [observation.block_count for observation in candidate_observations],
            snapshot_lagrangian_values,
        )
        chosen_observation = candidate_observations[best_snapshot_index]
        chosen_l_value = snapshot_lagrangian_values[best_snapshot_index]
        candidate_primal_cost = chosen_observation.block_count
        candidate_dual_value = core.fixed_cost + chosen_l_value

        accept = outer_iteration == 0 or (
            candidate_primal_cost <= tracked_best_block_count
            and not _dual_regressed_too_much(candidate_dual_value, tracked_best_dual_value, config)
        )
        if accept:
            tracked_best_block_count = candidate_primal_cost
            tracked_best_dual_value = candidate_dual_value

        iteration_lagrangian_values = [
            l_value for (_u, l_value) in (*first_call.snapshots, *second_call.snapshots)
        ]
        best_observed_lagrangian_value = max(
            best_observed_lagrangian_value, core.fixed_cost + max(iteration_lagrangian_values)
        )

        best_primal_history.append(tracked_best_block_count)
        tracked_dual_history.append(tracked_best_dual_value)
        working_stepsize_history.append(stepsize)
        outer_iteration += 1

    assert public_best_block_count is not None
    assert public_best_blocks is not None

    return CoveringDesignLagrangianResult(
        status=CoveringDesignLagrangianStatus.COMPLETED_HEURISTIC,
        best_blocks=public_best_blocks,
        best_block_count=public_best_block_count,
        seed=config.seed,
        deterministic_configuration_identity=_deterministic_configuration_identity(
            config, len(core.core_candidate_full_indices), len(core.core_target_full_indices)
        ),
        candidate_count=len(full.candidates),
        target_count=len(full.targets),
        fixed_block_count=core.fixed_cost,
        core_candidate_count=len(core.core_candidate_full_indices),
        core_target_count=len(core.core_target_full_indices),
        outer_iterations_completed=outer_iteration,
        subgradient_call_count=subgradient_call_count,
        primal_solutions_evaluated=primal_solutions_evaluated,
        tracked_accepted_dual_value=tracked_best_dual_value,
        best_observed_lagrangian_value=best_observed_lagrangian_value,
        best_primal_history=tuple(best_primal_history),
        tracked_dual_history=tuple(tracked_dual_history),
        working_stepsize_history=tuple(working_stepsize_history),
        termination_reason=termination_reason,
    )


__all__ = [
    "CoveringDesignLagrangianConfig",
    "CoveringDesignLagrangianResult",
    "CoveringDesignLagrangianStatus",
    "LagrangianConfigurationError",
    "LagrangianInvariantError",
    "LagrangianNumericalError",
    "LagrangianPrimalInfeasibleError",
    "run_covering_design_lagrangian",
]
