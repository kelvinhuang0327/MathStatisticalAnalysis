"""``ITERATIVE_EXACT_1EXCHANGE_EXPECTED_MAX_V1``: deterministic exact-fraction
one-number-exchange local ascent on the ``EXPECTED_MAX_MAIN_MATCHES_V1``
objective (``expected_max_main_matches.expected_max_main_matches``).

This reuses the same canonical one-exchange topology already frozen by
``STRATEGY_MATRIX_PHASE9_ONE_EXCHANGE_REFINEMENT`` --
``canonicalize_portfolio`` / ``legal_one_exchange_tickets`` /
``enumerate_legal_one_exchange_neighbors`` in
``reference_e_exact_one_exchange_refinement.py`` -- and applies it to a
different objective than that module's own coverage-at-one-threshold
neighborhood evaluator. No second definition of "legal one-exchange
neighbor" is introduced here.

From an incumbent portfolio, every unique legal one-number-exchange
neighbor is scored by the *exact* ``E[max_t |t (intersect) D|] = sum_{m=1}^{d}
Coverage(m)`` tail sum. The move with strictly the largest score is taken
(ties broken by the lexicographically smallest resulting portfolio); the
search halts the first time no neighbor strictly improves on the incumbent,
which -- because the neighborhood scanned is always complete, never
sampled -- certifies the terminal portfolio as a genuine radius-1 local
optimum for this objective.

Resource design (``m=1``/``m=2`` are the dominant cost at B649 scale --
7,887,362 / 2,111,774 qualifying draws per ticket): ``Coverage(1)`` is
never evaluated via qualifying-draw enumeration at all. It is computed by
the exact closed-form identity

    Coverage(1) = 1 - C(pool_size - |U|, draw_size) / C(pool_size, draw_size)

where ``U`` is the union of every number used anywhere in the portfolio
(a draw fails to match *any* ticket iff it avoids ``U`` entirely) -- an
identity, not an approximation. For ``m = 2..draw_size``,
``exact_coverage_fast_evaluator.coverage_with_base`` is used exactly as
its own docstring recommends for a many-candidates-against-one-fixed-base
call pattern: the (``k - 1``)-ticket base union for the mutated slot is
built once per threshold, and every candidate's own qualifying-draw set is
combined against it by inclusion-exclusion rather than by re-deriving the
whole portfolio's union from scratch per candidate. Because a candidate
ticket's qualifying-draw set is only ever used once (to score that one
candidate, at that one threshold), evicting it from the module-level cache
immediately after use costs nothing in recomputation -- so this module
calls ``clear_cache()`` after the base union is built (freeing the
now-unneeded per-ticket sets that produced it) and again after every single
candidate is scored (freeing that candidate's set). Peak resident memory
is therefore bounded by one threshold's base union plus at most one
in-flight candidate set at a time, never by the number of candidates in
the neighborhood or the number of distinct tickets ever visited across the
whole run.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from fractions import Fraction

from lottolab.research.exact_coverage_fast_evaluator import (
    clear_cache,
    coverage_with_base,
    fast_exact_portfolio_coverage,
    portfolio_qualifying_draws,
)
from lottolab.research.reference_e_exact_one_exchange_refinement import (
    Portfolio,
    Ticket,
    canonicalize_portfolio,
    legal_one_exchange_tickets,
)

METHOD_ID = "ITERATIVE_EXACT_1EXCHANGE_EXPECTED_MAX_V1"


def portfolio_sha256(portfolio: Portfolio) -> str:
    """Same canonical-JSON SHA-256 convention as Phase 9/10's own tooling."""

    payload = json.dumps(portfolio, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _validate_and_canonicalize(pool_size: int, draw_size: int, portfolio: Portfolio) -> Portfolio:
    if not 1 <= draw_size <= pool_size <= 64:
        raise ValueError("require 1 <= draw_size <= pool_size <= 64")

    canonical = canonicalize_portfolio(portfolio)
    if not canonical:
        raise ValueError("portfolio must contain at least one ticket")
    for ticket in canonical:
        if len(ticket) != draw_size:
            raise ValueError(f"ticket length {len(ticket)} does not match draw_size {draw_size}")
        if any(number < 1 or number > pool_size for number in ticket):
            raise ValueError(f"ticket number out of range 1..{pool_size}")
    return canonical


def _diff_removed_added(original: Ticket, mutated: Ticket) -> tuple[int, int]:
    original_set = set(original)
    mutated_set = set(mutated)
    removed = next(iter(original_set - mutated_set))
    added = next(iter(mutated_set - original_set))
    return removed, added


def coverage_at_least_one_exact(pool_size: int, draw_size: int, portfolio: Portfolio) -> Fraction:
    """Exact ``Coverage(1)`` via the closed-form complement identity.

    A draw matches zero tickets iff it avoids every number the portfolio
    ever uses, i.e. iff it is drawn entirely from the ``pool_size - |U|``
    numbers outside the union ``U`` of all ticket numbers. No qualifying-
    draw set is ever built for ``m = 1``.
    """

    used: set[int] = set()
    for ticket in portfolio:
        used.update(ticket)
    total_draws = math.comb(pool_size, draw_size)
    uncovered_pool = max(pool_size - len(used), 0)
    uncovered_draws = 0 if uncovered_pool < draw_size else math.comb(uncovered_pool, draw_size)
    return Fraction(total_draws - uncovered_draws, total_draws)


def expected_max_main_matches_exact(
    pool_size: int, draw_size: int, portfolio: Portfolio
) -> Fraction:
    """``EXPECTED_MAX_MAIN_MATCHES_V1``, ``m=1`` via closed form, ``m>=2`` via
    the fast evaluator. Exact-parity alternative to
    ``expected_max_main_matches.expected_max_main_matches`` -- see
    ``test_expected_max_core_matches_frozen_authority`` for the regression
    proving the two never disagree.
    """

    total = coverage_at_least_one_exact(pool_size, draw_size, portfolio)
    for minimum_matches in range(2, draw_size + 1):
        total += fast_exact_portfolio_coverage(pool_size, draw_size, minimum_matches, portfolio)
    return total


@dataclass(frozen=True, slots=True)
class ExpectedMaxNeighbor:
    """One unique legal neighbor and its exact expected-max score."""

    portfolio: Portfolio
    slot_index: int
    removed_number: int
    added_number: int
    expected_max: Fraction


@dataclass(frozen=True, slots=True)
class ExpectedMaxNeighborhoodResult:
    """Complete exact evaluation of one portfolio's 1-exchange neighborhood."""

    input_portfolio: Portfolio
    input_expected_max: Fraction
    unique_legal_neighbor_count: int
    neighbors: tuple[ExpectedMaxNeighbor, ...]
    best_neighbor_portfolio: Portfolio
    best_neighbor_expected_max: Fraction
    delta: Fraction


@dataclass(frozen=True, slots=True)
class ExpectedMaxAscentIteration:
    """One accepted or terminal iteration in a deterministic ascent trace."""

    iteration_index: int
    input_portfolio: Portfolio
    input_expected_max: Fraction
    unique_legal_neighbor_count: int
    best_neighbor_portfolio: Portfolio
    best_neighbor_expected_max: Fraction
    delta: Fraction
    accepted_move: bool


@dataclass(frozen=True, slots=True)
class ExpectedMaxAscentResult:
    """Terminal result and complete trace for one independently optimized rung."""

    seed_portfolio: Portfolio
    seed_expected_max: Fraction
    iterations: tuple[ExpectedMaxAscentIteration, ...]
    move_count: int
    terminal_portfolio: Portfolio
    terminal_expected_max: Fraction
    total_neighbor_evaluations: int
    terminal_unique_neighbor_count: int


def evaluate_expected_max_one_exchange_neighborhood(
    pool_size: int,
    draw_size: int,
    portfolio: Portfolio,
) -> ExpectedMaxNeighborhoodResult:
    """Exhaustively evaluate every legal 1-exchange neighbor's exact
    ``EXPECTED_MAX_MAIN_MATCHES_V1`` score.

    The neighbor set scanned here is exactly
    ``enumerate_legal_one_exchange_neighbors(portfolio, pool_size)`` (see
    ``test_neighborhood_matches_canonical_topology_enumeration``); this
    function additionally scores each one, which that shared enumerator
    does not do.
    """

    canonical = _validate_and_canonicalize(pool_size, draw_size, portfolio)
    portfolio_set = set(canonical)
    input_expected_max = expected_max_main_matches_exact(pool_size, draw_size, canonical)

    neighbor_totals: dict[Portfolio, Fraction] = {}
    neighbor_origin: dict[Portfolio, tuple[int, int, int]] = {}

    for slot_index, original_ticket in enumerate(canonical):
        remaining = canonical[:slot_index] + canonical[slot_index + 1 :]

        slot_candidates: dict[Portfolio, Ticket] = {}
        for mutated_ticket in legal_one_exchange_tickets(pool_size, original_ticket):
            if mutated_ticket in portfolio_set:
                continue
            neighbor_portfolio = tuple(sorted((*remaining, mutated_ticket)))
            if neighbor_portfolio in slot_candidates or neighbor_portfolio in neighbor_totals:
                continue
            slot_candidates[neighbor_portfolio] = mutated_ticket
            neighbor_origin[neighbor_portfolio] = (
                slot_index,
                *_diff_removed_added(original_ticket, mutated_ticket),
            )

        if not slot_candidates:
            continue

        for neighbor_portfolio in slot_candidates:
            neighbor_totals[neighbor_portfolio] = coverage_at_least_one_exact(
                pool_size, draw_size, neighbor_portfolio
            )

        for minimum_matches in range(2, draw_size + 1):
            base_draws = portfolio_qualifying_draws(
                pool_size, draw_size, minimum_matches, remaining
            )
            clear_cache()
            for neighbor_portfolio, mutated_ticket in slot_candidates.items():
                coverage = coverage_with_base(
                    pool_size, draw_size, minimum_matches, base_draws, mutated_ticket
                )
                neighbor_totals[neighbor_portfolio] += coverage
                clear_cache()
            del base_draws

    if not neighbor_totals:
        raise ValueError("no legal one-exchange neighbors found")

    neighbors = tuple(
        ExpectedMaxNeighbor(
            portfolio=neighbor_portfolio,
            slot_index=neighbor_origin[neighbor_portfolio][0],
            removed_number=neighbor_origin[neighbor_portfolio][1],
            added_number=neighbor_origin[neighbor_portfolio][2],
            expected_max=expected_max,
        )
        for neighbor_portfolio, expected_max in neighbor_totals.items()
    )
    best_neighbor_portfolio, best_neighbor_expected_max = min(
        neighbor_totals.items(), key=lambda item: (-item[1], item[0])
    )
    delta = best_neighbor_expected_max - input_expected_max

    return ExpectedMaxNeighborhoodResult(
        input_portfolio=canonical,
        input_expected_max=input_expected_max,
        unique_legal_neighbor_count=len(neighbor_totals),
        neighbors=neighbors,
        best_neighbor_portfolio=best_neighbor_portfolio,
        best_neighbor_expected_max=best_neighbor_expected_max,
        delta=delta,
    )


def iterative_exact_1exchange_expected_max_ascent(
    pool_size: int,
    draw_size: int,
    seed_portfolio: Portfolio,
) -> ExpectedMaxAscentResult:
    """Deterministic strict-best-improvement 1-exchange ascent on
    ``EXPECTED_MAX_MAIN_MATCHES_V1``. Halts the first time the complete
    neighborhood scan finds no strictly better neighbor -- that final scan
    is the terminal radius-1-local-optimum certificate.
    """

    current = _validate_and_canonicalize(pool_size, draw_size, seed_portfolio)
    iterations: list[ExpectedMaxAscentIteration] = []
    move_count = 0
    total_neighbor_evaluations = 0

    while True:
        neighborhood = evaluate_expected_max_one_exchange_neighborhood(
            pool_size, draw_size, current
        )
        accepted_move = neighborhood.best_neighbor_expected_max > neighborhood.input_expected_max
        total_neighbor_evaluations += neighborhood.unique_legal_neighbor_count
        iterations.append(
            ExpectedMaxAscentIteration(
                iteration_index=len(iterations),
                input_portfolio=current,
                input_expected_max=neighborhood.input_expected_max,
                unique_legal_neighbor_count=neighborhood.unique_legal_neighbor_count,
                best_neighbor_portfolio=neighborhood.best_neighbor_portfolio,
                best_neighbor_expected_max=neighborhood.best_neighbor_expected_max,
                delta=neighborhood.delta,
                accepted_move=accepted_move,
            )
        )

        if not accepted_move:
            return ExpectedMaxAscentResult(
                seed_portfolio=iterations[0].input_portfolio,
                seed_expected_max=iterations[0].input_expected_max,
                iterations=tuple(iterations),
                move_count=move_count,
                terminal_portfolio=current,
                terminal_expected_max=neighborhood.input_expected_max,
                total_neighbor_evaluations=total_neighbor_evaluations,
                terminal_unique_neighbor_count=neighborhood.unique_legal_neighbor_count,
            )

        current = neighborhood.best_neighbor_portfolio
        move_count += 1
