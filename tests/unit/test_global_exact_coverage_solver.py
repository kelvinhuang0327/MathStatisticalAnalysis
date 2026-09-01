# pyright: reportMissingTypeStubs=false, reportPrivateUsage=false

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass
from fractions import Fraction
from functools import cache

import ortools
import pytest
from ortools.sat.python import cp_model

from lottolab.research import global_exact_coverage_solver as solver_module
from lottolab.research.global_exact_coverage_solver import (
    CertificateBasis,
    GlobalExactCoverageResult,
    GlobalExactResultStatus,
    SolverStatus,
    UnsupportedGlobalExactDomainError,
    solve_global_exact_coverage,
)

type Ticket = tuple[int, ...]
type Portfolio = tuple[Ticket, ...]


@dataclass(frozen=True)
class _OracleResult:
    optimal_portfolio: Portfolio
    covered_draw_count: int
    total_draw_count: int
    exact_coverage: Fraction
    optimal_portfolio_count: int


def _ticket_mask(ticket: Ticket) -> int:
    mask = 0
    for number in ticket:
        mask |= 1 << (number - 1)
    return mask


@cache
def _exhaustive_oracle(n: int, d: int, minimum_matches: int, k: int) -> _OracleResult:
    """Independent direct enumeration of every legal portfolio and draw."""

    tickets = tuple(itertools.combinations(range(1, n + 1), d))
    draws = tuple(itertools.combinations(range(1, n + 1), d))
    draw_masks = tuple(_ticket_mask(draw) for draw in draws)
    coverage_bits_by_ticket: list[int] = []
    for ticket in tickets:
        ticket_mask = _ticket_mask(ticket)
        coverage_bits = 0
        for draw_index, draw_mask in enumerate(draw_masks):
            if (ticket_mask & draw_mask).bit_count() >= minimum_matches:
                coverage_bits |= 1 << draw_index
        coverage_bits_by_ticket.append(coverage_bits)

    best_count = -1
    best_portfolio: Portfolio | None = None
    optimal_portfolio_count = 0
    for portfolio_indices in itertools.combinations(range(len(tickets)), k):
        covered_bits = 0
        for ticket_index in portfolio_indices:
            covered_bits |= coverage_bits_by_ticket[ticket_index]
        covered_count = covered_bits.bit_count()
        portfolio = tuple(tickets[index] for index in portfolio_indices)
        if covered_count > best_count:
            best_count = covered_count
            best_portfolio = portfolio
            optimal_portfolio_count = 1
        elif covered_count == best_count:
            optimal_portfolio_count += 1
            if best_portfolio is None or portfolio < best_portfolio:
                best_portfolio = portfolio

    assert best_portfolio is not None
    return _OracleResult(
        optimal_portfolio=best_portfolio,
        covered_draw_count=best_count,
        total_draw_count=len(draws),
        exact_coverage=Fraction(best_count, len(draws)),
        optimal_portfolio_count=optimal_portfolio_count,
    )


@cache
def _certified_result(minimum_matches: int, k: int) -> GlobalExactCoverageResult:
    return solve_global_exact_coverage(8, 4, minimum_matches, k)


class _ScriptedSolveDriver:
    def __init__(self, *observations: solver_module._SolveObservation) -> None:
        self._observations = list(observations)
        self.phases: list[str] = []

    def solve(
        self, model: cp_model.CpModel, *, phase: str
    ) -> solver_module._SolveObservation:
        del model
        self.phases.append(phase)
        if not self._observations:
            raise AssertionError("scripted solve observation exhausted")
        return self._observations.pop(0)


@pytest.mark.parametrize(("minimum_matches", "k"), [(2, 2), (3, 2), (3, 3)])
def test_cp_sat_matches_independent_exhaustive_oracle(
    minimum_matches: int, k: int
) -> None:
    expected = _exhaustive_oracle(8, 4, minimum_matches, k)
    actual = _certified_result(minimum_matches, k)

    assert actual.status is GlobalExactResultStatus.CERTIFIED_GLOBAL_OPTIMUM
    assert actual.covered_draw_count == expected.covered_draw_count
    assert actual.total_draw_count == expected.total_draw_count
    assert actual.exact_coverage == expected.exact_coverage
    assert actual.optimal_portfolio == expected.optimal_portfolio
    assert actual.solver_objective_status is SolverStatus.OPTIMAL
    assert actual.lex_fixing_complete is True
    assert actual.diagnostic_solver_status == "CERTIFIED"


def test_q_one_and_q_less_than_one_use_the_required_certificate_bases() -> None:
    q_one_oracle = _exhaustive_oracle(8, 4, 2, 2)
    q_one_result = _certified_result(2, 2)
    assert q_one_oracle.exact_coverage == 1
    assert (
        q_one_result.certificate_basis
        is CertificateBasis.EXACT_POSTCHECK_PLUS_UNIVERSAL_UPPER_BOUND
    )

    q_less_oracle = _exhaustive_oracle(8, 4, 3, 2)
    q_less_result = _certified_result(3, 2)
    assert q_less_oracle.exact_coverage < 1
    assert (
        q_less_result.certificate_basis
        is CertificateBasis.CP_SAT_GLOBAL_OPTIMAL_PLUS_EXACT_POSTCHECK
    )


def test_multiple_global_maximizers_resolve_to_oracle_lexicographic_minimum() -> None:
    expected = _exhaustive_oracle(8, 4, 3, 3)
    actual = _certified_result(3, 3)
    assert expected.optimal_portfolio_count > 1
    assert actual.optimal_portfolio == expected.optimal_portfolio


@pytest.mark.parametrize(
    ("n", "d", "minimum_matches", "k", "message"),
    [
        (0, 1, 1, 1, "n must"),
        (8, 0, 1, 1, "d must"),
        (8, 9, 1, 1, "d must"),
        (8, 4, 0, 2, "minimum_matches"),
        (8, 4, 5, 2, "minimum_matches"),
        (8, 4, 2, 0, "k must"),
        (4, 4, 2, 2, "cannot exceed"),
    ],
)
def test_invalid_parameters_are_rejected(
    n: int, d: int, minimum_matches: int, k: int, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        solve_global_exact_coverage(n, d, minimum_matches, k)


@pytest.mark.parametrize(
    ("n", "d", "minimum_matches", "k"),
    [(7, 3, 2, 2), (8, 4, 1, 2), (8, 4, 2, 4)],
)
def test_valid_but_unsupported_domains_are_rejected_by_prebuild_guard(
    n: int, d: int, minimum_matches: int, k: int
) -> None:
    with pytest.raises(UnsupportedGlobalExactDomainError, match="supports only"):
        solve_global_exact_coverage(n, d, minimum_matches, k)


def test_b649_is_rejected_before_domain_materialization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    materializer_called = False

    def fail_if_materialized(n: int, d: int, minimum_matches: int) -> None:
        del n, d, minimum_matches
        nonlocal materializer_called
        materializer_called = True
        raise AssertionError("B649 domain must not be materialized")

    monkeypatch.setattr(solver_module, "_materialize_domain", fail_if_materialized)
    with pytest.raises(UnsupportedGlobalExactDomainError, match="supports only"):
        solve_global_exact_coverage(49, 6, 3, 2)
    assert materializer_called is False


def test_output_is_exact_k_canonical_and_distinct() -> None:
    for minimum_matches, k in ((2, 2), (3, 2), (3, 3)):
        result = _certified_result(minimum_matches, k)
        assert result.optimal_portfolio is not None
        assert len(result.optimal_portfolio) == k
        assert len(set(result.optimal_portfolio)) == k
        assert result.optimal_portfolio == tuple(sorted(result.optimal_portfolio))
        for ticket in result.optimal_portfolio:
            assert len(ticket) == 4
            assert len(set(ticket)) == 4
            assert ticket == tuple(sorted(ticket))


def test_canonicalizer_enforces_exact_k_and_duplicate_ticket_validation() -> None:
    with pytest.raises(ValueError, match="exactly k"):
        solver_module._canonicalize_portfolio(
            ((1, 2, 3, 4),),
            n=8,
            d=4,
            expected_ticket_count=2,
        )
    with pytest.raises(ValueError, match="distinct"):
        solver_module._canonicalize_portfolio(
            ((1, 2, 3, 4), (1, 2, 3, 4)),
            n=8,
            d=4,
            expected_ticket_count=2,
        )


def test_repeated_runs_are_deterministic() -> None:
    first = solve_global_exact_coverage(8, 4, 3, 3)
    second = solve_global_exact_coverage(8, 4, 3, 3)
    assert first == second


def test_fixed_solver_configuration_is_frozen_and_identified() -> None:
    configured = solver_module._build_deterministic_solver()
    assert configured.parameters.num_search_workers == 1
    assert configured.parameters.random_seed == 20260815
    assert configured.parameters.randomize_search is False
    assert configured.parameters.log_search_progress is False
    assert ortools.__version__ == solver_module.ORTOOLS_LOCKED_VERSION
    identity = solver_module.DETERMINISTIC_CONFIGURATION_IDENTITY
    assert "ortools=9.15.6755" in identity
    assert "random_seed=20260815" in identity
    assert "num_search_workers=1" in identity


def test_model_metadata_records_guard_and_complete_domain_sizes() -> None:
    result = _certified_result(3, 2)
    metadata = result.model_metadata
    assert metadata.legal_ticket_count == math.comb(8, 4)
    assert metadata.legal_draw_count == math.comb(8, 4)
    assert metadata.ticket_selection_variable_count == metadata.legal_ticket_count
    assert metadata.covered_draw_variable_count == metadata.legal_draw_count
    assert metadata.coverage_incidence_count > 0
    assert "max_ticket_draw_pairs=4900" in metadata.prebuild_guard_identity


@pytest.mark.parametrize("status", [SolverStatus.UNKNOWN, SolverStatus.MODEL_INVALID])
def test_unresolved_objective_status_returns_unknown_without_incumbent(
    status: SolverStatus,
) -> None:
    driver = _ScriptedSolveDriver(solver_module._SolveObservation(status=status))
    result = solve_global_exact_coverage(8, 4, 3, 2, _solve_driver=driver)
    assert result.status is GlobalExactResultStatus.UNKNOWN_NOT_CERTIFIED
    assert result.optimal_portfolio is None
    assert result.covered_draw_count is None
    assert result.exact_coverage is None
    assert result.lex_fixing_complete is False
    assert driver.phases == ["objective"]


def test_feasible_objective_incumbent_is_not_certified_or_exposed() -> None:
    driver = _ScriptedSolveDriver(
        solver_module._SolveObservation(
            status=SolverStatus.FEASIBLE,
            objective_value=float(_exhaustive_oracle(8, 4, 2, 2).covered_draw_count),
        )
    )
    result = solve_global_exact_coverage(8, 4, 2, 2, _solve_driver=driver)
    assert result.status is GlobalExactResultStatus.UNKNOWN_NOT_CERTIFIED
    assert result.optimal_portfolio is None
    assert result.solver_objective_status is SolverStatus.FEASIBLE
    assert driver.phases == ["objective"]


def test_objective_resource_limit_fails_closed_even_with_optimal_status() -> None:
    driver = _ScriptedSolveDriver(
        solver_module._SolveObservation(
            status=SolverStatus.OPTIMAL,
            objective_value=float(_exhaustive_oracle(8, 4, 3, 2).covered_draw_count),
            termination_was_limited=True,
        )
    )
    result = solve_global_exact_coverage(8, 4, 3, 2, _solve_driver=driver)
    assert result.status is GlobalExactResultStatus.UNKNOWN_NOT_CERTIFIED
    assert result.optimal_portfolio is None
    assert result.diagnostic_solver_status.endswith("RESOURCE_LIMITED")


def test_lex_unknown_returns_unknown_without_optimal_portfolio() -> None:
    expected = _exhaustive_oracle(8, 4, 3, 2)
    driver = _ScriptedSolveDriver(
        solver_module._SolveObservation(
            status=SolverStatus.OPTIMAL,
            objective_value=float(expected.covered_draw_count),
        ),
        solver_module._SolveObservation(status=SolverStatus.UNKNOWN),
    )
    result = solve_global_exact_coverage(8, 4, 3, 2, _solve_driver=driver)
    assert result.status is GlobalExactResultStatus.UNKNOWN_NOT_CERTIFIED
    assert result.optimal_portfolio is None
    assert result.lex_probe_statuses == (SolverStatus.UNKNOWN,)
    assert driver.phases == ["objective", "lex:0"]


def test_lex_resource_limit_fails_closed() -> None:
    expected = _exhaustive_oracle(8, 4, 3, 2)
    driver = _ScriptedSolveDriver(
        solver_module._SolveObservation(
            status=SolverStatus.OPTIMAL,
            objective_value=float(expected.covered_draw_count),
        ),
        solver_module._SolveObservation(
            status=SolverStatus.FEASIBLE,
            termination_was_limited=True,
        ),
    )
    result = solve_global_exact_coverage(8, 4, 3, 2, _solve_driver=driver)
    assert result.status is GlobalExactResultStatus.UNKNOWN_NOT_CERTIFIED
    assert result.optimal_portfolio is None
    assert result.diagnostic_solver_status.endswith("RESOURCE_LIMITED")


def test_earlier_lex_ticket_is_skipped_only_after_infeasible_proof() -> None:
    decisions = {
        status: solver_module._classify_lex_probe(
            solver_module._SolveObservation(status=status)
        )
        for status in SolverStatus
    }
    skipped = {
        status
        for status, decision in decisions.items()
        if decision is solver_module._LexProbeDecision.FIX_SKIPPED
    }
    assert skipped == {SolverStatus.INFEASIBLE}
    assert (
        decisions[SolverStatus.FEASIBLE]
        is solver_module._LexProbeDecision.FIX_SELECTED
    )
    assert decisions[SolverStatus.OPTIMAL] is solver_module._LexProbeDecision.FIX_SELECTED


def test_non_integer_objective_fails_closed() -> None:
    driver = _ScriptedSolveDriver(
        solver_module._SolveObservation(
            status=SolverStatus.OPTIMAL,
            objective_value=12.5,
        )
    )
    result = solve_global_exact_coverage(8, 4, 3, 2, _solve_driver=driver)
    assert result.status is GlobalExactResultStatus.UNKNOWN_NOT_CERTIFIED
    assert result.optimal_portfolio is None
    assert result.diagnostic_solver_status == "OBJECTIVE:NON_INTEGER_OR_MISSING_VALUE"


def test_independent_exact_postcheck_mismatch_fails_closed() -> None:
    def wrong_coverage(
        n: int,
        d: int,
        minimum_matches: int,
        portfolio: Portfolio,
    ) -> Fraction:
        del n, d, minimum_matches, portfolio
        return Fraction(0)

    result = solve_global_exact_coverage(
        8,
        4,
        3,
        2,
        _coverage_evaluator=wrong_coverage,
    )
    assert result.status is GlobalExactResultStatus.UNKNOWN_NOT_CERTIFIED
    assert result.optimal_portfolio is None
    assert result.covered_draw_count is None
    assert result.exact_coverage is None
    assert result.diagnostic_solver_status == "EXACT_POSTCHECK_MISMATCH"
