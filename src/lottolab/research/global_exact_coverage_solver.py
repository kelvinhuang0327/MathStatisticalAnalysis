# pyright: reportMissingTypeStubs=false

"""Certified global-exact coverage optimization on a guarded toy domain.

This research-only first port deliberately supports only the frozen
n=8, d=4, minimum_matches in {2, 3}, k in {2, 3} envelope. The
prebuild guard runs before any legal-ticket, winning-draw, or incidence
enumeration, so production-sized lottery rules cannot accidentally
materialize a global model.

Certification requires an OPTIMAL CP-SAT objective result, complete
feasibility-probed lexicographic fixing, and an independent exact
Fraction postcheck through the repository's canonical evaluator.
No incumbent is exposed as optimal when any phase is unresolved.
"""

from __future__ import annotations

import itertools
import math
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from fractions import Fraction
from typing import Protocol

import ortools
from ortools.sat.python import cp_model

from lottolab.research.bounded_coverage_optimizer import exact_portfolio_coverage

type Ticket = tuple[int, ...]
type Portfolio = tuple[Ticket, ...]

SUPPORTED_N = 8
SUPPORTED_D = 4
SUPPORTED_MINIMUM_MATCHES = frozenset({2, 3})
SUPPORTED_K = frozenset({2, 3})
MAX_LEGAL_TICKET_COUNT = math.comb(SUPPORTED_N, SUPPORTED_D)
MAX_LEGAL_DRAW_COUNT = MAX_LEGAL_TICKET_COUNT
MAX_TICKET_DRAW_INCIDENCE_PAIRS = MAX_LEGAL_TICKET_COUNT * MAX_LEGAL_DRAW_COUNT

ORTOOLS_LOCKED_VERSION = "9.15.6755"
SOLVER_RANDOM_SEED = 20260815
SOLVER_NUM_SEARCH_WORKERS = 1
DETERMINISTIC_CONFIGURATION_IDENTITY = (
    f"ortools={ORTOOLS_LOCKED_VERSION};"
    f"random_seed={SOLVER_RANDOM_SEED};"
    f"num_search_workers={SOLVER_NUM_SEARCH_WORKERS};"
    "randomize_search=false;time_limit=none"
)
PREBUILD_GUARD_IDENTITY = (
    "toy-envelope:n=8,d=4,minimum_matches={2,3},k={2,3};"
    f"max_legal_tickets={MAX_LEGAL_TICKET_COUNT};"
    f"max_legal_draws={MAX_LEGAL_DRAW_COUNT};"
    f"max_ticket_draw_pairs={MAX_TICKET_DRAW_INCIDENCE_PAIRS}"
)


class UnsupportedGlobalExactDomainError(ValueError):
    """Raised before enumeration when a request is outside the toy envelope."""


class GlobalExactResultStatus(StrEnum):
    """Certification state exposed by the research solver."""

    CERTIFIED_GLOBAL_OPTIMUM = "CERTIFIED_GLOBAL_OPTIMUM"
    UNKNOWN_NOT_CERTIFIED = "UNKNOWN_NOT_CERTIFIED"


class SolverStatus(StrEnum):
    """Stable project-level rendering of CP-SAT statuses."""

    UNKNOWN = "UNKNOWN"
    MODEL_INVALID = "MODEL_INVALID"
    FEASIBLE = "FEASIBLE"
    INFEASIBLE = "INFEASIBLE"
    OPTIMAL = "OPTIMAL"


class CertificateBasis(StrEnum):
    """Mathematical basis for a certified result."""

    CP_SAT_GLOBAL_OPTIMAL_PLUS_EXACT_POSTCHECK = (
        "CP_SAT_GLOBAL_OPTIMAL_PLUS_EXACT_POSTCHECK"
    )
    EXACT_POSTCHECK_PLUS_UNIVERSAL_UPPER_BOUND = (
        "EXACT_POSTCHECK_PLUS_UNIVERSAL_UPPER_BOUND"
    )


@dataclass(frozen=True)
class PrebuildDomainSize:
    """Combinatorial size information computed without domain enumeration."""

    legal_ticket_count: int
    legal_draw_count: int
    maximum_ticket_draw_pairs: int
    guard_identity: str


@dataclass(frozen=True)
class GlobalExactModelMetadata:
    """Auditable domain/model sizes for one constructed toy problem."""

    n: int
    d: int
    minimum_matches: int
    k: int
    legal_ticket_count: int
    legal_draw_count: int
    coverage_incidence_count: int
    ticket_selection_variable_count: int
    covered_draw_variable_count: int
    prebuild_guard_identity: str


@dataclass(frozen=True)
class GlobalExactCoverageResult:
    """Certified optimum or a fail-closed unknown result."""

    status: GlobalExactResultStatus
    optimal_portfolio: Portfolio | None
    covered_draw_count: int | None
    total_draw_count: int
    exact_coverage: Fraction | None
    solver_objective_status: SolverStatus
    certificate_basis: CertificateBasis | None
    lex_fixing_complete: bool
    deterministic_configuration_identity: str
    model_metadata: GlobalExactModelMetadata
    lex_probe_statuses: tuple[SolverStatus, ...]
    diagnostic_solver_status: str


@dataclass(frozen=True)
class _MaterializedDomain:
    tickets: tuple[Ticket, ...]
    draws: tuple[Ticket, ...]
    covering_ticket_indices_by_draw: tuple[tuple[int, ...], ...]
    coverage_incidence_count: int


@dataclass(frozen=True)
class _BuiltModel:
    model: cp_model.CpModel
    ticket_selected: tuple[cp_model.IntVar, ...]
    draw_covered: tuple[cp_model.IntVar, ...]


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


type _CoverageEvaluator = Callable[[int, int, int, Portfolio], object]


def guard_global_exact_domain(
    n: int, d: int, minimum_matches: int, k: int
) -> PrebuildDomainSize:
    """Validate parameters and reject unsupported sizes before enumeration."""

    _validate_parameters(n, d, minimum_matches, k)
    if (
        n != SUPPORTED_N
        or d != SUPPORTED_D
        or minimum_matches not in SUPPORTED_MINIMUM_MATCHES
        or k not in SUPPORTED_K
    ):
        raise UnsupportedGlobalExactDomainError(
            "global-exact CP-SAT first port supports only "
            "n=8, d=4, minimum_matches in {2, 3}, and k in {2, 3}"
        )

    legal_ticket_count = math.comb(n, d)
    legal_draw_count = legal_ticket_count
    maximum_ticket_draw_pairs = legal_ticket_count * legal_draw_count
    if (
        legal_ticket_count > MAX_LEGAL_TICKET_COUNT
        or legal_draw_count > MAX_LEGAL_DRAW_COUNT
        or maximum_ticket_draw_pairs > MAX_TICKET_DRAW_INCIDENCE_PAIRS
    ):
        raise UnsupportedGlobalExactDomainError("global-exact prebuild size limit exceeded")
    return PrebuildDomainSize(
        legal_ticket_count=legal_ticket_count,
        legal_draw_count=legal_draw_count,
        maximum_ticket_draw_pairs=maximum_ticket_draw_pairs,
        guard_identity=PREBUILD_GUARD_IDENTITY,
    )


def solve_global_exact_coverage(
    n: int,
    d: int,
    minimum_matches: int,
    k: int,
    *,
    _solve_driver: _SolveDriver | None = None,
    _coverage_evaluator: _CoverageEvaluator = exact_portfolio_coverage,
) -> GlobalExactCoverageResult:
    """Return the lexicographically smallest certified global maximizer.

    Private keyword seams exist only for deterministic fail-closed tests;
    callers use the fixed OR-Tools driver and existing exact evaluator.
    """

    prebuild_size = guard_global_exact_domain(n, d, minimum_matches, k)
    _require_locked_ortools_version()
    domain = _materialize_domain(n, d, minimum_matches)
    metadata = _model_metadata(n, d, minimum_matches, k, prebuild_size, domain)
    built = _build_cp_sat_model(domain, k)
    driver = _solve_driver if _solve_driver is not None else _OrToolsSolveDriver()

    objective_observation = driver.solve(built.model, phase="objective")
    objective_diagnostic = f"OBJECTIVE:{objective_observation.status.value}"
    if (
        objective_observation.status is not SolverStatus.OPTIMAL
        or objective_observation.termination_was_limited
    ):
        if objective_observation.termination_was_limited:
            objective_diagnostic += ":RESOURCE_LIMITED"
        return _unknown_result(
            metadata,
            objective_observation.status,
            objective_diagnostic,
        )

    optimal_covered_draws = _integer_objective_value(
        objective_observation.objective_value,
        maximum=metadata.legal_draw_count,
    )
    if optimal_covered_draws is None:
        return _unknown_result(
            metadata,
            objective_observation.status,
            "OBJECTIVE:NON_INTEGER_OR_MISSING_VALUE",
        )

    built.model.add(sum(built.draw_covered) == optimal_covered_draws)
    built.model.clear_objective()
    selected_indices: list[int] = []
    lex_statuses: list[SolverStatus] = []

    for ticket_index, selected_var in enumerate(built.ticket_selected):
        if len(selected_indices) == k:
            built.model.add(selected_var == 0)
            continue

        probe_model = built.model.clone()
        probe_selected = probe_model.get_bool_var_from_proto_index(selected_var.index)
        probe_model.add(probe_selected == 1)
        probe = driver.solve(probe_model, phase=f"lex:{ticket_index}")
        lex_statuses.append(probe.status)
        decision = _classify_lex_probe(probe)
        if decision is _LexProbeDecision.ABORT_NOT_CERTIFIED:
            suffix = ":RESOURCE_LIMITED" if probe.termination_was_limited else ""
            return _unknown_result(
                metadata,
                objective_observation.status,
                f"LEX:{ticket_index}:{probe.status.value}{suffix}",
                lex_probe_statuses=tuple(lex_statuses),
            )
        if decision is _LexProbeDecision.FIX_SELECTED:
            built.model.add(selected_var == 1)
            selected_indices.append(ticket_index)
        else:
            built.model.add(selected_var == 0)

    if len(selected_indices) != k:
        return _unknown_result(
            metadata,
            objective_observation.status,
            "LEX:INCOMPLETE_SELECTION",
            lex_probe_statuses=tuple(lex_statuses),
        )

    try:
        canonical_portfolio = _canonicalize_portfolio(
            tuple(domain.tickets[index] for index in selected_indices),
            n=n,
            d=d,
            expected_ticket_count=k,
        )
    except ValueError:
        return _unknown_result(
            metadata,
            objective_observation.status,
            "LEX:INVALID_CANONICAL_PORTFOLIO",
            lex_probe_statuses=tuple(lex_statuses),
        )

    try:
        exact_coverage = _coverage_evaluator(n, d, minimum_matches, canonical_portfolio)
    except Exception as error:
        return _unknown_result(
            metadata,
            objective_observation.status,
            f"EXACT_POSTCHECK_ERROR:{type(error).__name__}",
            lex_probe_statuses=tuple(lex_statuses),
        )
    expected_coverage = Fraction(optimal_covered_draws, metadata.legal_draw_count)
    if not isinstance(exact_coverage, Fraction) or exact_coverage != expected_coverage:
        return _unknown_result(
            metadata,
            objective_observation.status,
            "EXACT_POSTCHECK_MISMATCH",
            lex_probe_statuses=tuple(lex_statuses),
        )

    certificate_basis = (
        CertificateBasis.EXACT_POSTCHECK_PLUS_UNIVERSAL_UPPER_BOUND
        if exact_coverage == 1
        else CertificateBasis.CP_SAT_GLOBAL_OPTIMAL_PLUS_EXACT_POSTCHECK
    )
    return GlobalExactCoverageResult(
        status=GlobalExactResultStatus.CERTIFIED_GLOBAL_OPTIMUM,
        optimal_portfolio=canonical_portfolio,
        covered_draw_count=optimal_covered_draws,
        total_draw_count=metadata.legal_draw_count,
        exact_coverage=exact_coverage,
        solver_objective_status=objective_observation.status,
        certificate_basis=certificate_basis,
        lex_fixing_complete=True,
        deterministic_configuration_identity=DETERMINISTIC_CONFIGURATION_IDENTITY,
        model_metadata=metadata,
        lex_probe_statuses=tuple(lex_statuses),
        diagnostic_solver_status="CERTIFIED",
    )


def _validate_parameters(n: int, d: int, minimum_matches: int, k: int) -> None:
    if n < 1:
        raise ValueError("n must be >= 1")
    if d < 1 or d > n:
        raise ValueError("d must lie in [1, n]")
    if minimum_matches < 1 or minimum_matches > d:
        raise ValueError("minimum_matches must lie in [1, d]")
    if k < 1:
        raise ValueError("k must be >= 1")
    if k > math.comb(n, d):
        raise ValueError("k cannot exceed the number of distinct legal tickets")


def _require_locked_ortools_version() -> None:
    actual_version = str(ortools.__version__)
    if actual_version != ORTOOLS_LOCKED_VERSION:
        raise RuntimeError(
            "deterministic certification requires OR-Tools "
            f"{ORTOOLS_LOCKED_VERSION}; found {actual_version}"
        )


def _ticket_bitmask(ticket: Ticket) -> int:
    mask = 0
    for number in ticket:
        mask |= 1 << (number - 1)
    return mask


def _materialize_domain(n: int, d: int, minimum_matches: int) -> _MaterializedDomain:
    tickets = tuple(itertools.combinations(range(1, n + 1), d))
    draws = tuple(itertools.combinations(range(1, n + 1), d))
    ticket_masks = tuple(_ticket_bitmask(ticket) for ticket in tickets)
    draw_masks = tuple(_ticket_bitmask(draw) for draw in draws)
    covering_ticket_indices_by_draw = tuple(
        tuple(
            ticket_index
            for ticket_index, ticket_mask in enumerate(ticket_masks)
            if (draw_mask & ticket_mask).bit_count() >= minimum_matches
        )
        for draw_mask in draw_masks
    )
    coverage_incidence_count = sum(
        len(indices) for indices in covering_ticket_indices_by_draw
    )
    return _MaterializedDomain(
        tickets=tickets,
        draws=draws,
        covering_ticket_indices_by_draw=covering_ticket_indices_by_draw,
        coverage_incidence_count=coverage_incidence_count,
    )


def _model_metadata(
    n: int,
    d: int,
    minimum_matches: int,
    k: int,
    prebuild_size: PrebuildDomainSize,
    domain: _MaterializedDomain,
) -> GlobalExactModelMetadata:
    if (
        len(domain.tickets) != prebuild_size.legal_ticket_count
        or len(domain.draws) != prebuild_size.legal_draw_count
    ):
        raise RuntimeError("materialized domain size does not match the prebuild guard")
    return GlobalExactModelMetadata(
        n=n,
        d=d,
        minimum_matches=minimum_matches,
        k=k,
        legal_ticket_count=len(domain.tickets),
        legal_draw_count=len(domain.draws),
        coverage_incidence_count=domain.coverage_incidence_count,
        ticket_selection_variable_count=len(domain.tickets),
        covered_draw_variable_count=len(domain.draws),
        prebuild_guard_identity=prebuild_size.guard_identity,
    )


def _build_cp_sat_model(domain: _MaterializedDomain, k: int) -> _BuiltModel:
    model = cp_model.CpModel()
    ticket_selected = tuple(
        model.new_bool_var(f"ticket_selected_{index:02d}")
        for index in range(len(domain.tickets))
    )
    draw_covered = tuple(
        model.new_bool_var(f"draw_covered_{index:02d}") for index in range(len(domain.draws))
    )
    model.add(sum(ticket_selected) == k)
    for draw_index, covering_indices in enumerate(domain.covering_ticket_indices_by_draw):
        covering_selection = tuple(ticket_selected[index] for index in covering_indices)
        model.add_max_equality(draw_covered[draw_index], *covering_selection)
    model.maximize(sum(draw_covered))
    return _BuiltModel(
        model=model,
        ticket_selected=ticket_selected,
        draw_covered=draw_covered,
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


def _canonicalize_portfolio(
    portfolio: Portfolio,
    *,
    n: int,
    d: int,
    expected_ticket_count: int,
) -> Portfolio:
    if len(portfolio) != expected_ticket_count:
        raise ValueError("portfolio must contain exactly k tickets")
    canonical_tickets: list[Ticket] = []
    for ticket in portfolio:
        canonical_ticket = tuple(sorted(ticket))
        if len(canonical_ticket) != d or len(set(canonical_ticket)) != d:
            raise ValueError("each ticket must contain d distinct numbers")
        if any(number < 1 or number > n for number in canonical_ticket):
            raise ValueError("ticket number outside legal pool")
        canonical_tickets.append(canonical_ticket)
    canonical_portfolio = tuple(sorted(canonical_tickets))
    if len(set(canonical_portfolio)) != expected_ticket_count:
        raise ValueError("portfolio tickets must be distinct")
    return canonical_portfolio


def _unknown_result(
    metadata: GlobalExactModelMetadata,
    objective_status: SolverStatus,
    diagnostic_status: str,
    *,
    lex_probe_statuses: tuple[SolverStatus, ...] = (),
) -> GlobalExactCoverageResult:
    return GlobalExactCoverageResult(
        status=GlobalExactResultStatus.UNKNOWN_NOT_CERTIFIED,
        optimal_portfolio=None,
        covered_draw_count=None,
        total_draw_count=metadata.legal_draw_count,
        exact_coverage=None,
        solver_objective_status=objective_status,
        certificate_basis=None,
        lex_fixing_complete=False,
        deterministic_configuration_identity=DETERMINISTIC_CONFIGURATION_IDENTITY,
        model_metadata=metadata,
        lex_probe_statuses=lex_probe_statuses,
        diagnostic_solver_status=diagnostic_status,
    )
