# pyright: reportMissingTypeStubs=false

"""Exact classical covering-design construction via the standard set-cover ILP.

Clean-room implementation of the textbook Set-Covering integer-program
formulation for the covering number C(v, k, t): given a v-element ground set
0..v-1, choose the minimum number of k-subsets ("blocks") such that every
t-subset ("target") is contained in at least one selected block. There is no
donor-code dependence of any kind and no external covering-design repository
was consulted; the model is the standard formulation found in any integer
programming reference (binary choice per candidate block, one "at least one
selected covering block" constraint per target, minimize the block count).

This research first-port deliberately supports only a small guarded envelope
(see ``guard_setcover_domain``) so that no unbounded model can be built by
accident. It reuses the repository's existing CP-SAT determinism and
fail-closed certification idiom from
``lottolab.research.global_exact_coverage_solver`` (deterministic single
worker solve, an injectable solve-driver seam for tests, and lexicographic
tie-break via fixed-cardinality feasibility probes) without importing from
it, and cross-checks every certified result against the independent
Schoenheim lower bound and GKP upper bound in
``lottolab.research.covering_design_gkp_bound``.

Scope boundary
--------------

This is a standalone research constructor: it returns certified-optimal (or
fail-closed unknown) block tuples, never a Matrix method, replay method,
ranking candidate, fixed-ticket strategy, or production API surface. No
SQLite, no network access, no B649 wiring.
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

import ortools
from ortools.sat.python import cp_model

from lottolab.research.covering_design_gkp_bound import (
    covering_number_upper_bound,
    schoenheim_lower_bound,
)

type Block = tuple[int, ...]

ORTOOLS_LOCKED_VERSION = "9.15.6755"
SOLVER_RANDOM_SEED = 20260815
SOLVER_NUM_SEARCH_WORKERS = 1
DETERMINISTIC_CONFIGURATION_IDENTITY = (
    f"ortools={ORTOOLS_LOCKED_VERSION};"
    f"random_seed={SOLVER_RANDOM_SEED};"
    f"num_search_workers={SOLVER_NUM_SEARCH_WORKERS};"
    "randomize_search=false;time_limit=none"
)

SUPPORTED_MAX_V = 10
MAX_CANDIDATE_BLOCK_COUNT = 252
MAX_TARGET_SUBSET_COUNT = 252
MAX_COVERAGE_INCIDENCE_COUNT = 10_000
PREBUILD_GUARD_IDENTITY = (
    f"setcover-ilp-envelope:max_v={SUPPORTED_MAX_V};"
    f"max_candidate_block_count={MAX_CANDIDATE_BLOCK_COUNT};"
    f"max_target_subset_count={MAX_TARGET_SUBSET_COUNT};"
    f"max_coverage_incidence_count={MAX_COVERAGE_INCIDENCE_COUNT}"
)


class UnsupportedSetCoverDomainError(ValueError):
    """Raised before enumeration when a request is outside the guarded envelope."""


class SetCoverResultStatus(StrEnum):
    """Certification state exposed by the research constructor."""

    CERTIFIED_GLOBAL_OPTIMUM = "CERTIFIED_GLOBAL_OPTIMUM"
    UNKNOWN_NOT_CERTIFIED = "UNKNOWN_NOT_CERTIFIED"


class SolverStatus(StrEnum):
    """Stable project-level rendering of CP-SAT statuses.

    ``NOT_INVOKED`` covers a trivial closed-form result, where no CP-SAT
    solve ever ran; it is never used to describe an actual solver outcome.
    """

    UNKNOWN = "UNKNOWN"
    MODEL_INVALID = "MODEL_INVALID"
    FEASIBLE = "FEASIBLE"
    INFEASIBLE = "INFEASIBLE"
    OPTIMAL = "OPTIMAL"
    NOT_INVOKED = "NOT_INVOKED"


class CertificateBasis(StrEnum):
    """Mathematical basis for a certified result."""

    TRIVIAL_EXACT_CLOSED_FORM = "TRIVIAL_EXACT_CLOSED_FORM"
    CP_SAT_GLOBAL_OPTIMAL_PLUS_INDEPENDENT_POSTCHECK = (
        "CP_SAT_GLOBAL_OPTIMAL_PLUS_INDEPENDENT_POSTCHECK"
    )


@dataclass(frozen=True)
class PrebuildDomainSize:
    """Combinatorial size information computed without domain enumeration."""

    candidate_block_count: int
    target_subset_count: int
    coverage_incidence_count: int
    guard_identity: str


@dataclass(frozen=True)
class SetCoverModelMetadata:
    """Auditable domain/model sizes for one constructed covering instance."""

    v: int
    k: int
    t: int
    candidate_block_count: int
    target_subset_count: int
    coverage_incidence_count: int
    block_selection_variable_count: int
    coverage_constraint_count: int
    prebuild_guard_identity: str


@dataclass(frozen=True)
class SetCoverResult:
    """Certified minimum covering, or a fail-closed unknown result."""

    status: SetCoverResultStatus
    blocks: tuple[Block, ...] | None
    block_count: int | None
    solver_status: SolverStatus
    best_objective_bound: int | None
    certificate_basis: CertificateBasis | None
    lex_fixing_complete: bool
    deterministic_configuration_identity: str
    model_metadata: SetCoverModelMetadata
    lex_probe_statuses: tuple[SolverStatus, ...]
    diagnostic_solver_status: str


@dataclass(frozen=True)
class _SolveObservation:
    status: SolverStatus
    objective_value: float | None = None
    termination_was_limited: bool = False


class _SolveDriver(Protocol):
    def solve(self, model: cp_model.CpModel, *, phase: str) -> _SolveObservation:
        """Solve one objective or lex-feasibility model."""

        raise NotImplementedError


class _LexProbeDecision(StrEnum):
    FIX_SELECTED = "FIX_SELECTED"
    FIX_SKIPPED = "FIX_SKIPPED"
    ABORT_NOT_CERTIFIED = "ABORT_NOT_CERTIFIED"


def _require_int(name: str, value: object) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer, got {value!r}")


def _validate_parameters(v: int, k: int, t: int) -> None:
    _require_int("v", v)
    _require_int("k", k)
    _require_int("t", t)
    if t < 0:
        raise ValueError("t must be >= 0")
    if k < t:
        raise ValueError("k must be >= t")
    if v < k:
        raise ValueError("v must be >= k")


def guard_setcover_domain(v: int, k: int, t: int) -> PrebuildDomainSize:
    """Validate parameters and reject unsupported sizes before enumeration.

    Uses only cheap combinatorial-size arithmetic (``math.comb``); no
    candidate block, target subset, or incidence pair is ever materialized
    here.
    """

    _validate_parameters(v, k, t)
    if v > SUPPORTED_MAX_V:
        raise UnsupportedSetCoverDomainError(
            f"covering-design set-cover first port supports only v <= {SUPPORTED_MAX_V}"
        )
    candidate_block_count = math.comb(v, k)
    target_subset_count = math.comb(v, t)
    coverage_incidence_count = math.comb(v, t) * math.comb(v - t, k - t)
    if (
        candidate_block_count > MAX_CANDIDATE_BLOCK_COUNT
        or target_subset_count > MAX_TARGET_SUBSET_COUNT
        or coverage_incidence_count > MAX_COVERAGE_INCIDENCE_COUNT
    ):
        raise UnsupportedSetCoverDomainError(
            "covering-design set-cover prebuild size limit exceeded"
        )
    return PrebuildDomainSize(
        candidate_block_count=candidate_block_count,
        target_subset_count=target_subset_count,
        coverage_incidence_count=coverage_incidence_count,
        guard_identity=PREBUILD_GUARD_IDENTITY,
    )


def solve_setcover_ilp(
    v: int,
    k: int,
    t: int,
    *,
    _solve_driver: _SolveDriver | None = None,
) -> SetCoverResult:
    """Return the lexicographically smallest certified minimum covering.

    Requires ``v >= k >= t >= 0`` and a size within ``guard_setcover_domain``.
    The private ``_solve_driver`` keyword exists only for deterministic
    fail-closed unit tests; callers use the fixed OR-Tools driver.
    """

    prebuild_size = guard_setcover_domain(v, k, t)
    trivial_result = _try_trivial_exact_case(v, k, t, prebuild_size)
    if trivial_result is not None:
        return trivial_result
    return _solve_general_setcover_ilp(v, k, t, prebuild_size, solve_driver=_solve_driver)


def _block_bitmask(block: Block) -> int:
    mask = 0
    for number in block:
        mask |= 1 << number
    return mask


def _model_metadata_from_prebuild(
    v: int, k: int, t: int, prebuild_size: PrebuildDomainSize
) -> SetCoverModelMetadata:
    return SetCoverModelMetadata(
        v=v,
        k=k,
        t=t,
        candidate_block_count=prebuild_size.candidate_block_count,
        target_subset_count=prebuild_size.target_subset_count,
        coverage_incidence_count=prebuild_size.coverage_incidence_count,
        block_selection_variable_count=prebuild_size.candidate_block_count,
        coverage_constraint_count=prebuild_size.target_subset_count,
        prebuild_guard_identity=prebuild_size.guard_identity,
    )


def _try_trivial_exact_case(
    v: int, k: int, t: int, prebuild_size: PrebuildDomainSize
) -> SetCoverResult | None:
    if t == 0:
        return _finalize_trivial_result(
            v, k, t, (tuple(range(k)),), prebuild_size, rule="TRIVIAL_T_ZERO"
        )
    if k == v:
        return _finalize_trivial_result(
            v, k, t, (tuple(range(v)),), prebuild_size, rule="TRIVIAL_K_EQUALS_V"
        )
    if t == k:
        blocks = tuple(itertools.combinations(range(v), k))
        return _finalize_trivial_result(
            v, k, t, blocks, prebuild_size, rule="TRIVIAL_T_EQUALS_K"
        )
    return None


def _finalize_trivial_result(
    v: int,
    k: int,
    t: int,
    blocks: tuple[Block, ...],
    prebuild_size: PrebuildDomainSize,
    *,
    rule: str,
) -> SetCoverResult:
    metadata = _model_metadata_from_prebuild(v, k, t, prebuild_size)
    return _finalize_certified_result(
        v,
        t,
        blocks,
        len(blocks),
        metadata,
        certificate_basis=CertificateBasis.TRIVIAL_EXACT_CLOSED_FORM,
        lex_probe_statuses=(),
        solver_status=SolverStatus.NOT_INVOKED,
        diagnostic_prefix=f"TRIVIAL_CLOSED_FORM:{rule}",
    )


def _require_locked_ortools_version() -> None:
    actual_version = str(ortools.__version__)
    if actual_version != ORTOOLS_LOCKED_VERSION:
        raise RuntimeError(
            "deterministic certification requires OR-Tools "
            f"{ORTOOLS_LOCKED_VERSION}; found {actual_version}"
        )


def _solve_general_setcover_ilp(
    v: int,
    k: int,
    t: int,
    prebuild_size: PrebuildDomainSize,
    *,
    solve_driver: _SolveDriver | None,
) -> SetCoverResult:
    _require_locked_ortools_version()
    metadata = _model_metadata_from_prebuild(v, k, t, prebuild_size)
    candidates = tuple(itertools.combinations(range(v), k))
    targets = tuple(itertools.combinations(range(v), t))
    candidate_masks = tuple(_block_bitmask(block) for block in candidates)
    covering_indices_by_target = tuple(
        tuple(
            block_index
            for block_index, block_mask in enumerate(candidate_masks)
            if (target_mask & block_mask) == target_mask
        )
        for target_mask in (_block_bitmask(target) for target in targets)
    )

    model = cp_model.CpModel()
    block_selected = tuple(
        model.new_bool_var(f"block_selected_{index:03d}") for index in range(len(candidates))
    )
    for covering_indices in covering_indices_by_target:
        model.add(sum(block_selected[index] for index in covering_indices) >= 1)
    model.minimize(sum(block_selected))

    driver = solve_driver if solve_driver is not None else _OrToolsSolveDriver()
    objective_observation = driver.solve(model, phase="objective")

    if (
        objective_observation.status is SolverStatus.INFEASIBLE
        and not objective_observation.termination_was_limited
    ):
        return _unknown_result(
            metadata,
            objective_observation.status,
            "OBJECTIVE:INFEASIBLE:UNEXPECTED_FOR_COMPLETE_CANDIDATE_UNIVERSE",
        )
    if (
        objective_observation.status is not SolverStatus.OPTIMAL
        or objective_observation.termination_was_limited
    ):
        diagnostic = f"OBJECTIVE:{objective_observation.status.value}"
        if objective_observation.termination_was_limited:
            diagnostic += ":RESOURCE_LIMITED"
        return _unknown_result(metadata, objective_observation.status, diagnostic)

    exact_block_count = _integer_objective_value(
        objective_observation.objective_value, maximum=len(candidates)
    )
    if exact_block_count is None:
        return _unknown_result(
            metadata,
            objective_observation.status,
            "OBJECTIVE:NON_INTEGER_OR_MISSING_VALUE",
        )

    model.add(sum(block_selected) == exact_block_count)
    model.clear_objective()
    selected_indices: list[int] = []
    lex_statuses: list[SolverStatus] = []

    for block_index, selected_var in enumerate(block_selected):
        if len(selected_indices) == exact_block_count:
            model.add(selected_var == 0)
            continue

        probe_model = model.clone()
        probe_selected = probe_model.get_bool_var_from_proto_index(selected_var.index)
        probe_model.add(probe_selected == 1)
        probe = driver.solve(probe_model, phase=f"lex:{block_index}")
        lex_statuses.append(probe.status)
        decision = _classify_lex_probe(probe)
        if decision is _LexProbeDecision.ABORT_NOT_CERTIFIED:
            suffix = ":RESOURCE_LIMITED" if probe.termination_was_limited else ""
            return _unknown_result(
                metadata,
                objective_observation.status,
                f"LEX:{block_index}:{probe.status.value}{suffix}",
                lex_probe_statuses=tuple(lex_statuses),
            )
        if decision is _LexProbeDecision.FIX_SELECTED:
            model.add(selected_var == 1)
            selected_indices.append(block_index)
        else:
            model.add(selected_var == 0)

    if len(selected_indices) != exact_block_count:
        return _unknown_result(
            metadata,
            objective_observation.status,
            "LEX:INCOMPLETE_SELECTION",
            lex_probe_statuses=tuple(lex_statuses),
        )

    selected_blocks = tuple(candidates[index] for index in selected_indices)
    return _finalize_certified_result(
        v,
        t,
        selected_blocks,
        exact_block_count,
        metadata,
        certificate_basis=CertificateBasis.CP_SAT_GLOBAL_OPTIMAL_PLUS_INDEPENDENT_POSTCHECK,
        lex_probe_statuses=tuple(lex_statuses),
        solver_status=objective_observation.status,
        diagnostic_prefix="CERTIFIED",
    )


def _finalize_certified_result(
    v: int,
    t: int,
    blocks: tuple[Block, ...],
    block_count: int,
    metadata: SetCoverModelMetadata,
    *,
    certificate_basis: CertificateBasis,
    lex_probe_statuses: tuple[SolverStatus, ...],
    solver_status: SolverStatus,
    diagnostic_prefix: str,
) -> SetCoverResult:
    if len(blocks) != block_count or len(set(blocks)) != block_count:
        return _unknown_result(
            metadata,
            solver_status,
            "CANONICAL_BLOCK_COUNT_MISMATCH",
            lex_probe_statuses=lex_probe_statuses,
        )
    if not _covers_every_target(v, t, blocks):
        return _unknown_result(
            metadata,
            solver_status,
            "INDEPENDENT_COVERAGE_POSTCHECK_MISMATCH",
            lex_probe_statuses=lex_probe_statuses,
        )
    lower = schoenheim_lower_bound(v, metadata.k, t)
    upper = covering_number_upper_bound(v, metadata.k, t).upper_bound
    if block_count < lower or (upper is not None and block_count > upper):
        return _unknown_result(
            metadata,
            solver_status,
            "BOUND_CROSSCHECK_MISMATCH",
            lex_probe_statuses=lex_probe_statuses,
        )
    return SetCoverResult(
        status=SetCoverResultStatus.CERTIFIED_GLOBAL_OPTIMUM,
        blocks=blocks,
        block_count=block_count,
        solver_status=solver_status,
        best_objective_bound=block_count,
        certificate_basis=certificate_basis,
        lex_fixing_complete=True,
        deterministic_configuration_identity=DETERMINISTIC_CONFIGURATION_IDENTITY,
        model_metadata=metadata,
        lex_probe_statuses=lex_probe_statuses,
        diagnostic_solver_status=diagnostic_prefix,
    )


def _covers_every_target(v: int, t: int, blocks: tuple[Block, ...]) -> bool:
    """Independent pure-Python postcheck, separate from the CP-SAT constraints."""

    block_masks = tuple(_block_bitmask(block) for block in blocks)
    for target in itertools.combinations(range(v), t):
        target_mask = _block_bitmask(target)
        if not any((target_mask & block_mask) == target_mask for block_mask in block_masks):
            return False
    return True


def _unknown_result(
    metadata: SetCoverModelMetadata,
    solver_status: SolverStatus,
    diagnostic_status: str,
    *,
    lex_probe_statuses: tuple[SolverStatus, ...] = (),
) -> SetCoverResult:
    return SetCoverResult(
        status=SetCoverResultStatus.UNKNOWN_NOT_CERTIFIED,
        blocks=None,
        block_count=None,
        solver_status=solver_status,
        best_objective_bound=None,
        certificate_basis=None,
        lex_fixing_complete=False,
        deterministic_configuration_identity=DETERMINISTIC_CONFIGURATION_IDENTITY,
        model_metadata=metadata,
        lex_probe_statuses=lex_probe_statuses,
        diagnostic_solver_status=diagnostic_status,
    )


def _build_deterministic_solver() -> cp_model.CpSolver:
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = SOLVER_NUM_SEARCH_WORKERS
    solver.parameters.random_seed = SOLVER_RANDOM_SEED
    solver.parameters.randomize_search = False
    solver.parameters.log_search_progress = False
    return solver


class _OrToolsSolveDriver:
    def solve(self, model: cp_model.CpModel, *, phase: str) -> _SolveObservation:
        del phase
        solver = _build_deterministic_solver()
        raw_status = solver.solve(model)
        status = _stable_solver_status(raw_status)
        objective_value = (
            solver.objective_value
            if status in {SolverStatus.FEASIBLE, SolverStatus.OPTIMAL}
            else None
        )
        return _SolveObservation(status=status, objective_value=objective_value)


def _stable_solver_status(status: cp_model.CpSolverStatus) -> SolverStatus:
    if status == cp_model.OPTIMAL:
        return SolverStatus.OPTIMAL
    if status == cp_model.FEASIBLE:
        return SolverStatus.FEASIBLE
    if status == cp_model.INFEASIBLE:
        return SolverStatus.INFEASIBLE
    if status == cp_model.MODEL_INVALID:
        return SolverStatus.MODEL_INVALID
    return SolverStatus.UNKNOWN


def _integer_objective_value(value: float | None, *, maximum: int) -> int | None:
    if value is None or not math.isfinite(value):
        return None
    rounded = round(value)
    if not math.isclose(value, rounded, rel_tol=0.0, abs_tol=1e-6):
        return None
    if rounded < 0 or rounded > maximum:
        return None
    return rounded


def _classify_lex_probe(observation: _SolveObservation) -> _LexProbeDecision:
    if observation.termination_was_limited:
        return _LexProbeDecision.ABORT_NOT_CERTIFIED
    if observation.status in {SolverStatus.FEASIBLE, SolverStatus.OPTIMAL}:
        return _LexProbeDecision.FIX_SELECTED
    if observation.status is SolverStatus.INFEASIBLE:
        return _LexProbeDecision.FIX_SKIPPED
    return _LexProbeDecision.ABORT_NOT_CERTIFIED
