# pyright: reportPrivateUsage=false

"""Bounded B649 adapter for the frozen hard pairwise-overlap method.

The adapter starts every supported ticket count independently from the
canonical ``CYCLIC_SIDON_SHIFT_V1`` prefix, enumerates the repository's complete
one-number-exchange neighborhood, removes candidates whose portfolio violates
the permanent pairwise-intersection cap of one, and only then invokes the
existing simultaneous exact M3+ evaluator.  Strict exact improvements are
accepted until the complete hard-feasible radius-1 neighborhood contains no
better portfolio.

This module is deliberately not a global optimizer.  It never materializes the
full B649 ticket universe or a conflict graph, and every successful result keeps
global optimality ``UNKNOWN``.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import math
from dataclasses import dataclass
from enum import StrEnum
from fractions import Fraction
from typing import Final

from lottolab.research.cyclic_sidon_shift import sidon_shift_portfolio
from lottolab.research.global_exact_coverage_solver import (
    HARD_DIV_PAIRWISE_OVERLAP_R1_METHOD_ID,
    PAIRWISE_MAX_INTERSECTION,
)
from lottolab.research.reference_e_exact_one_exchange_refinement import (
    Portfolio,
    canonicalize_portfolio,
)
from lottolab.research.reference_e_iterative_exact_one_exchange_ascent import (
    _exact_neighbor_coverages,
    _exchange_candidates,
    _ExchangeCandidate,
)

BIG_LOTTO: Final = "BIG_LOTTO"
POOL_SIZE: Final = 49
DRAW_SIZE: Final = 6
MINIMUM_MATCHES: Final = 3
SUPPORTED_K: Final = (2, 3, 5, 10, 20)
WINNING_DRAW_COUNT: Final = math.comb(POOL_SIZE, DRAW_SIZE)

METHOD_ID: Final = HARD_DIV_PAIRWISE_OVERLAP_R1_METHOD_ID
REFERENCE_STRATEGY_ID: Final = "CYCLIC_SIDON_SHIFT_V1"
LOCAL_OPTIMUM_STATUS: Final = "CERTIFIED_ONE_NUMBER_EXCHANGE"
PROOF_STATUS: Final = (
    "LOCAL_OPTIMUM_CERTIFIED_EXACT_RADIUS_1_WITHIN_HARD_FEASIBLE_SET_NO_GLOBAL_PROOF"
)
GLOBAL_OPTIMUM_STATUS: Final = "UNKNOWN"
GLOBAL_EXACT_REUSE_ROLE: Final = "ORACLE_ONLY"
FULL_DOMAIN_B649_GLOBAL_OPTIMALITY: Final = "UNPROVEN"
EXACT_ONE_EXCHANGE_REUSE: Final = "BOUNDED_ADAPTER"
NEIGHBORHOOD_UNIT: Final = "REMOVE_ONE_ADD_ONE_NUMBER_IN_ONE_TICKET"
UNSUPPORTED_REASON: Final = "UNSUPPORTED_LOTTERY_OR_K"


class AdapterStatus(StrEnum):
    """Stable Matrix-facing execution status."""

    MEASURED = "MEASURED"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    NOT_RUN = "NOT_RUN"


class HardDivPairwiseAdapterInvariantError(RuntimeError):
    """Raised internally when exact reuse or postcheck evidence is inconsistent."""


@dataclass(frozen=True, slots=True)
class HardDivPairwiseAdapterDispatch:
    """One Matrix dispatch cell; V1 accepts only the single frozen B649 shape.

    These fields describe the caller's cell identity.  They do not tune the
    method: any value outside the frozen contract is rejected before seed or
    exact-neighborhood work begins.
    """

    lottery: str
    pool_size: int
    draw_size: int
    minimum_matches: int
    k: int


@dataclass(frozen=True, slots=True)
class HardDivPairwiseIteration:
    """One accepted or terminal complete hard-feasible neighborhood scan."""

    iteration_index: int
    input_portfolio: Portfolio
    input_q: Fraction
    complete_neighbor_count: int
    hard_feasible_neighbor_count: int
    exact_evaluated_neighbor_count: int
    best_neighbor_portfolio: Portfolio | None
    best_neighbor_q: Fraction | None
    delta: Fraction | None
    accepted_move: bool


@dataclass(frozen=True, slots=True)
class HardDivPairwiseSearchEvidence:
    """Deterministic evidence for the accepted chain and terminal certificate."""

    neighborhood_unit: str
    iterations: tuple[HardDivPairwiseIteration, ...]
    iteration_count: int
    move_count: int
    complete_neighbor_count_total: int
    hard_feasible_neighbor_count_total: int
    exact_evaluated_neighbor_count_total: int
    terminal_no_strict_improvement: bool
    complete_neighborhood_certified: bool
    hard_feasible_filter_before_exact_evaluation: bool


@dataclass(frozen=True, slots=True)
class HardDivPairwiseBoundedCandidateResult:
    """Measured B649 local optimum or a fail-closed non-measured result."""

    status: AdapterStatus
    status_reason: str | None
    method_id: str
    reference_strategy_id: str
    lottery: str
    pool_size: int
    draw_size: int
    minimum_matches: int
    k: int
    seed_portfolio: Portfolio | None
    seed_portfolio_sha256: str | None
    seed_exact_q: Fraction | None
    seed_covered_draw_count: int | None
    portfolio: Portfolio | None
    portfolio_sha256: str | None
    exact_q: Fraction | None
    covered_draw_count: int | None
    total_draw_count: int
    delta_vs_reference: Fraction | None
    geometry_max_pairwise_overlap: int | None
    local_optimum_status: str | None
    proof_status: str | None
    global_optimum_status: str
    search_evidence: HardDivPairwiseSearchEvidence | None


@dataclass(frozen=True, slots=True)
class _HardFeasibleNeighborhoodResult:
    input_portfolio: Portfolio
    input_q: Fraction
    complete_neighbor_count: int
    hard_feasible_neighbor_count: int
    exact_evaluated_neighbor_count: int
    best_neighbor_portfolio: Portfolio | None
    best_neighbor_q: Fraction | None
    delta: Fraction | None


@dataclass(frozen=True, slots=True)
class _HardDivAscentResult:
    seed_portfolio: Portfolio
    seed_q: Fraction
    iterations: tuple[HardDivPairwiseIteration, ...]
    move_count: int
    terminal_portfolio: Portfolio
    terminal_q: Fraction


def big_lotto_dispatch(k: int) -> HardDivPairwiseAdapterDispatch:
    """Return the frozen B649 dispatch identity for ``k``."""

    return HardDivPairwiseAdapterDispatch(
        lottery=BIG_LOTTO,
        pool_size=POOL_SIZE,
        draw_size=DRAW_SIZE,
        minimum_matches=MINIMUM_MATCHES,
        k=k,
    )


def _is_supported_dispatch(dispatch: HardDivPairwiseAdapterDispatch) -> bool:
    return (
        dispatch.lottery == BIG_LOTTO
        and type(dispatch.pool_size) is int
        and dispatch.pool_size == POOL_SIZE
        and type(dispatch.draw_size) is int
        and dispatch.draw_size == DRAW_SIZE
        and type(dispatch.minimum_matches) is int
        and dispatch.minimum_matches == MINIMUM_MATCHES
        and type(dispatch.k) is int
        and dispatch.k in SUPPORTED_K
    )


def _canonical_legal_portfolio(
    portfolio: Portfolio,
    *,
    expected_k: int,
    pool_size: int,
    draw_size: int,
) -> Portfolio:
    canonical = canonicalize_portfolio(portfolio)
    if len(canonical) != expected_k:
        raise ValueError("portfolio must contain exactly k tickets")
    if len(set(canonical)) != expected_k:
        raise ValueError("portfolio tickets must be distinct")
    for ticket in canonical:
        if len(ticket) != draw_size:
            raise ValueError("each ticket must contain exactly draw_size numbers")
        if any(type(number) is not int or not 1 <= number <= pool_size for number in ticket):
            raise ValueError("ticket contains a number outside the frozen legal pool")
    return canonical


def _portfolio_max_pairwise_intersection(portfolio: Portfolio) -> int:
    return max(
        (
            len(set(left_ticket).intersection(right_ticket))
            for left_ticket, right_ticket in itertools.combinations(portfolio, 2)
        ),
        default=0,
    )


def _canonical_hard_feasible_candidate(
    portfolio: Portfolio,
    *,
    expected_k: int,
    pool_size: int,
    draw_size: int,
) -> Portfolio | None:
    try:
        canonical = _canonical_legal_portfolio(
            portfolio,
            expected_k=expected_k,
            pool_size=pool_size,
            draw_size=draw_size,
        )
    except (TypeError, ValueError):
        return None
    if _portfolio_max_pairwise_intersection(canonical) > PAIRWISE_MAX_INTERSECTION:
        return None
    return canonical


def _evaluate_hard_feasible_neighborhood(
    pool_size: int,
    draw_size: int,
    minimum_matches: int,
    portfolio: Portfolio,
) -> _HardFeasibleNeighborhoodResult:
    """Evaluate every and only hard-feasible member of the complete neighborhood."""

    canonical = _canonical_legal_portfolio(
        portfolio,
        expected_k=len(portfolio),
        pool_size=pool_size,
        draw_size=draw_size,
    )
    if canonical != portfolio:
        raise HardDivPairwiseAdapterInvariantError("current portfolio is not canonical")
    if _portfolio_max_pairwise_intersection(canonical) > PAIRWISE_MAX_INTERSECTION:
        raise HardDivPairwiseAdapterInvariantError("current portfolio violates hard overlap cap")
    if minimum_matches != MINIMUM_MATCHES:
        raise HardDivPairwiseAdapterInvariantError("exact bounded adapter requires M3_PLUS")

    complete_candidates = _exchange_candidates(canonical, pool_size)
    complete_portfolios = tuple(candidate.portfolio for candidate in complete_candidates)
    if complete_portfolios != tuple(sorted(set(complete_portfolios))):
        raise HardDivPairwiseAdapterInvariantError(
            "one-exchange authority returned a non-unique or non-canonical neighborhood"
        )

    feasible_by_portfolio: dict[Portfolio, _ExchangeCandidate] = {}
    for candidate in complete_candidates:
        feasible_portfolio = _canonical_hard_feasible_candidate(
            candidate.portfolio,
            expected_k=len(canonical),
            pool_size=pool_size,
            draw_size=draw_size,
        )
        if feasible_portfolio is None:
            continue
        feasible_by_portfolio.setdefault(
            feasible_portfolio,
            _ExchangeCandidate(
                portfolio=feasible_portfolio,
                slot_index=candidate.slot_index,
                removed_number=candidate.removed_number,
                added_number=candidate.added_number,
            ),
        )

    feasible_candidates = tuple(
        feasible_by_portfolio[neighbor] for neighbor in sorted(feasible_by_portfolio)
    )
    covered_draw_count, exact_neighbors = _exact_neighbor_coverages(
        pool_size,
        draw_size,
        minimum_matches,
        canonical,
        feasible_candidates,
    )
    total_draw_count = math.comb(pool_size, draw_size)
    if not 0 <= covered_draw_count <= total_draw_count:
        raise HardDivPairwiseAdapterInvariantError("exact input coverage count is invalid")

    expected_portfolios = set(feasible_by_portfolio)
    actual_portfolios = {neighbor.portfolio for neighbor in exact_neighbors}
    if len(exact_neighbors) != len(feasible_candidates) or actual_portfolios != expected_portfolios:
        raise HardDivPairwiseAdapterInvariantError(
            "exact evaluator did not return every hard-feasible neighbor exactly once"
        )
    if any(
        not isinstance(neighbor.exact_q, Fraction)  # pyright: ignore[reportUnnecessaryIsInstance]
        or not 0 <= neighbor.exact_q <= 1
        for neighbor in exact_neighbors
    ):
        raise HardDivPairwiseAdapterInvariantError("exact neighbor coverage is invalid")

    input_q = Fraction(covered_draw_count, total_draw_count)
    best_neighbor = (
        min(exact_neighbors, key=lambda neighbor: (-neighbor.exact_q, neighbor.portfolio))
        if exact_neighbors
        else None
    )
    best_neighbor_q = best_neighbor.exact_q if best_neighbor is not None else None
    delta = best_neighbor_q - input_q if best_neighbor_q is not None else None
    return _HardFeasibleNeighborhoodResult(
        input_portfolio=canonical,
        input_q=input_q,
        complete_neighbor_count=len(complete_candidates),
        hard_feasible_neighbor_count=len(feasible_candidates),
        exact_evaluated_neighbor_count=len(exact_neighbors),
        best_neighbor_portfolio=(best_neighbor.portfolio if best_neighbor is not None else None),
        best_neighbor_q=best_neighbor_q,
        delta=delta,
    )


def _iterative_hard_feasible_ascent(
    pool_size: int,
    draw_size: int,
    minimum_matches: int,
    seed_portfolio: Portfolio,
) -> _HardDivAscentResult:
    """Take strict deterministic best-neighbor moves to a hard-feasible local optimum."""

    current = _canonical_legal_portfolio(
        seed_portfolio,
        expected_k=len(seed_portfolio),
        pool_size=pool_size,
        draw_size=draw_size,
    )
    if current != seed_portfolio:
        raise HardDivPairwiseAdapterInvariantError("seed portfolio is not canonical")
    if _portfolio_max_pairwise_intersection(current) > PAIRWISE_MAX_INTERSECTION:
        raise HardDivPairwiseAdapterInvariantError("seed portfolio violates hard overlap cap")

    iterations: list[HardDivPairwiseIteration] = []
    visited: set[Portfolio] = set()
    move_count = 0
    expected_input_q: Fraction | None = None

    while True:
        if current in visited:
            raise HardDivPairwiseAdapterInvariantError("strict ascent revisited a portfolio")
        visited.add(current)

        neighborhood = _evaluate_hard_feasible_neighborhood(
            pool_size,
            draw_size,
            minimum_matches,
            current,
        )
        if expected_input_q is not None and neighborhood.input_q != expected_input_q:
            raise HardDivPairwiseAdapterInvariantError("accepted-neighbor exact Q chain mismatch")

        accepted_move = (
            neighborhood.best_neighbor_q is not None
            and neighborhood.best_neighbor_q > neighborhood.input_q
        )
        iterations.append(
            HardDivPairwiseIteration(
                iteration_index=len(iterations),
                input_portfolio=current,
                input_q=neighborhood.input_q,
                complete_neighbor_count=neighborhood.complete_neighbor_count,
                hard_feasible_neighbor_count=neighborhood.hard_feasible_neighbor_count,
                exact_evaluated_neighbor_count=neighborhood.exact_evaluated_neighbor_count,
                best_neighbor_portfolio=neighborhood.best_neighbor_portfolio,
                best_neighbor_q=neighborhood.best_neighbor_q,
                delta=neighborhood.delta,
                accepted_move=accepted_move,
            )
        )

        if not accepted_move:
            return _HardDivAscentResult(
                seed_portfolio=seed_portfolio,
                seed_q=iterations[0].input_q,
                iterations=tuple(iterations),
                move_count=move_count,
                terminal_portfolio=current,
                terminal_q=neighborhood.input_q,
            )

        if neighborhood.best_neighbor_portfolio is None or neighborhood.best_neighbor_q is None:
            raise HardDivPairwiseAdapterInvariantError(
                "accepted move lacks exact neighbor evidence"
            )
        current = neighborhood.best_neighbor_portfolio
        expected_input_q = neighborhood.best_neighbor_q
        move_count += 1


def _terminal_hard_postcheck(portfolio: Portfolio, *, expected_k: int) -> bool:
    """Independently check exact-k, legality, canonical order, and the hard cap."""

    try:
        if len(portfolio) != expected_k or len(set(portfolio)) != expected_k:
            return False
        if portfolio != tuple(sorted(portfolio)):
            return False
        for ticket in portfolio:
            if len(ticket) != DRAW_SIZE or ticket != tuple(sorted(ticket)):
                return False
            if len(set(ticket)) != DRAW_SIZE:
                return False
            if any(type(number) is not int or not 1 <= number <= POOL_SIZE for number in ticket):
                return False
        return all(
            len(set(left_ticket).intersection(right_ticket)) <= PAIRWISE_MAX_INTERSECTION
            for left_ticket, right_ticket in itertools.combinations(portfolio, 2)
        )
    except (TypeError, ValueError):
        return False


def _portfolio_sha256(portfolio: Portfolio) -> str:
    canonical_bytes = json.dumps(portfolio, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical_bytes).hexdigest()


def _covered_draw_count(exact_q: Fraction) -> int:
    covered = exact_q * WINNING_DRAW_COUNT
    if covered.denominator != 1:
        raise HardDivPairwiseAdapterInvariantError(
            "exact coverage is not an integer count over the frozen B649 draw space"
        )
    return covered.numerator


def _non_measured_result(
    dispatch: HardDivPairwiseAdapterDispatch,
    *,
    status: AdapterStatus,
    reason: str,
) -> HardDivPairwiseBoundedCandidateResult:
    return HardDivPairwiseBoundedCandidateResult(
        status=status,
        status_reason=reason,
        method_id=METHOD_ID,
        reference_strategy_id=REFERENCE_STRATEGY_ID,
        lottery=dispatch.lottery,
        pool_size=dispatch.pool_size,
        draw_size=dispatch.draw_size,
        minimum_matches=dispatch.minimum_matches,
        k=dispatch.k,
        seed_portfolio=None,
        seed_portfolio_sha256=None,
        seed_exact_q=None,
        seed_covered_draw_count=None,
        portfolio=None,
        portfolio_sha256=None,
        exact_q=None,
        covered_draw_count=None,
        total_draw_count=WINNING_DRAW_COUNT,
        delta_vs_reference=None,
        geometry_max_pairwise_overlap=None,
        local_optimum_status=None,
        proof_status=None,
        global_optimum_status=GLOBAL_OPTIMUM_STATUS,
        search_evidence=None,
    )


def run_hard_div_pairwise_bounded_candidate_adapter(
    dispatch: HardDivPairwiseAdapterDispatch,
) -> HardDivPairwiseBoundedCandidateResult:
    """Execute one frozen B649 cell and fail closed without a measured payload."""

    if not _is_supported_dispatch(dispatch):
        return _non_measured_result(
            dispatch,
            status=AdapterStatus.NOT_APPLICABLE,
            reason=UNSUPPORTED_REASON,
        )

    try:
        seed = canonicalize_portfolio(sidon_shift_portfolio(dispatch.k))
        if not _terminal_hard_postcheck(seed, expected_k=dispatch.k):
            raise HardDivPairwiseAdapterInvariantError("invalid or hard-infeasible Sidon seed")

        ascent = _iterative_hard_feasible_ascent(
            POOL_SIZE,
            DRAW_SIZE,
            MINIMUM_MATCHES,
            seed,
        )
        if ascent.seed_portfolio != seed or not ascent.iterations:
            raise HardDivPairwiseAdapterInvariantError("ascent seed or trace mismatch")
        if ascent.move_count != len(ascent.iterations) - 1:
            raise HardDivPairwiseAdapterInvariantError("ascent move/iteration count mismatch")
        if any(
            not iteration.accepted_move or iteration.delta is None or iteration.delta <= 0
            for iteration in ascent.iterations[:-1]
        ):
            raise HardDivPairwiseAdapterInvariantError("non-strict accepted move in ascent trace")
        terminal_iteration = ascent.iterations[-1]
        if terminal_iteration.accepted_move:
            raise HardDivPairwiseAdapterInvariantError("terminal iteration accepted a move")
        if (
            terminal_iteration.best_neighbor_q is not None
            and terminal_iteration.best_neighbor_q > terminal_iteration.input_q
        ):
            raise HardDivPairwiseAdapterInvariantError(
                "terminal iteration retained a strict-improvement neighbor"
            )
        if (
            terminal_iteration.input_portfolio != ascent.terminal_portfolio
            or terminal_iteration.input_q != ascent.terminal_q
        ):
            raise HardDivPairwiseAdapterInvariantError("terminal trace/result mismatch")
        if not _terminal_hard_postcheck(ascent.terminal_portfolio, expected_k=dispatch.k):
            raise HardDivPairwiseAdapterInvariantError("terminal hard postcheck mismatch")

        seed_covered_draw_count = _covered_draw_count(ascent.seed_q)
        terminal_covered_draw_count = _covered_draw_count(ascent.terminal_q)
        search_evidence = HardDivPairwiseSearchEvidence(
            neighborhood_unit=NEIGHBORHOOD_UNIT,
            iterations=ascent.iterations,
            iteration_count=len(ascent.iterations),
            move_count=ascent.move_count,
            complete_neighbor_count_total=sum(
                iteration.complete_neighbor_count for iteration in ascent.iterations
            ),
            hard_feasible_neighbor_count_total=sum(
                iteration.hard_feasible_neighbor_count for iteration in ascent.iterations
            ),
            exact_evaluated_neighbor_count_total=sum(
                iteration.exact_evaluated_neighbor_count for iteration in ascent.iterations
            ),
            terminal_no_strict_improvement=True,
            complete_neighborhood_certified=True,
            hard_feasible_filter_before_exact_evaluation=True,
        )
        return HardDivPairwiseBoundedCandidateResult(
            status=AdapterStatus.MEASURED,
            status_reason=None,
            method_id=METHOD_ID,
            reference_strategy_id=REFERENCE_STRATEGY_ID,
            lottery=BIG_LOTTO,
            pool_size=POOL_SIZE,
            draw_size=DRAW_SIZE,
            minimum_matches=MINIMUM_MATCHES,
            k=dispatch.k,
            seed_portfolio=seed,
            seed_portfolio_sha256=_portfolio_sha256(seed),
            seed_exact_q=ascent.seed_q,
            seed_covered_draw_count=seed_covered_draw_count,
            portfolio=ascent.terminal_portfolio,
            portfolio_sha256=_portfolio_sha256(ascent.terminal_portfolio),
            exact_q=ascent.terminal_q,
            covered_draw_count=terminal_covered_draw_count,
            total_draw_count=WINNING_DRAW_COUNT,
            delta_vs_reference=ascent.terminal_q - ascent.seed_q,
            geometry_max_pairwise_overlap=_portfolio_max_pairwise_intersection(
                ascent.terminal_portfolio
            ),
            local_optimum_status=LOCAL_OPTIMUM_STATUS,
            proof_status=PROOF_STATUS,
            global_optimum_status=GLOBAL_OPTIMUM_STATUS,
            search_evidence=search_evidence,
        )
    except Exception as error:
        return _non_measured_result(
            dispatch,
            status=AdapterStatus.NOT_RUN,
            reason=f"EXISTING_NATIVE_EXECUTION_FAILED:{type(error).__name__}:{error}",
        )
