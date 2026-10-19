"""Deterministic iterative exact one-number-exchange portfolio ascent.

The Phase 10 method implemented here starts from an independently supplied
portfolio, evaluates its complete legal one-number-exchange neighborhood, and
accepts the unique deterministic best neighbor only when its exact coverage is
strictly greater.  It repeats until the best neighbor is no better than the
current portfolio, yielding a terminal one-exchange-local-optimum certificate.

Neighborhood coverage is evaluated exactly in one scan of the finite winning
space.  For each draw, the evaluator records whether removing a ticket would
leave the draw uncovered and aggregates the exact effect of every possible
remove-one/add-one mutation.  All coverage values therefore remain integer
counts over ``C(pool_size, draw_size)``; no sampling or floating-point ranking
is used.
"""

from __future__ import annotations

import itertools
import math
from array import array
from dataclasses import dataclass
from fractions import Fraction
from functools import cache

from lottolab.research.reference_e_exact_one_exchange_refinement import (
    Portfolio,
    Ticket,
    canonicalize_portfolio,
)

type CoverageRow = list[int]
type SubsetCoverageRows = dict[int, CoverageRow]


@dataclass(frozen=True, slots=True)
class ExactOneExchangeNeighbor:
    """One unique legal neighbor and its exact coverage."""

    portfolio: Portfolio
    slot_index: int
    removed_number: int
    added_number: int
    exact_q: Fraction


@dataclass(frozen=True, slots=True)
class ExactOneExchangeNeighborhoodResult:
    """Complete exact evaluation of one portfolio's 1-exchange neighborhood."""

    input_portfolio: Portfolio
    input_q: Fraction
    unique_legal_neighbor_count: int
    neighbors: tuple[ExactOneExchangeNeighbor, ...]
    best_neighbor_portfolio: Portfolio
    best_neighbor_q: Fraction
    delta: Fraction


@dataclass(frozen=True, slots=True)
class ExactOneExchangeAscentIteration:
    """One accepted or terminal iteration in a deterministic ascent trace."""

    iteration_index: int
    input_portfolio: Portfolio
    input_q: Fraction
    unique_legal_neighbor_count: int
    best_neighbor_portfolio: Portfolio
    best_neighbor_q: Fraction
    delta: Fraction
    accepted_move: bool


@dataclass(frozen=True, slots=True)
class ExactOneExchangeAscentResult:
    """Terminal result and complete trace for one independently optimized rung."""

    seed_portfolio: Portfolio
    seed_q: Fraction
    iterations: tuple[ExactOneExchangeAscentIteration, ...]
    move_count: int
    terminal_portfolio: Portfolio
    terminal_q: Fraction


@dataclass(frozen=True, slots=True)
class _ExchangeCandidate:
    portfolio: Portfolio
    slot_index: int
    removed_number: int
    added_number: int


def _validate_and_canonicalize(
    pool_size: int,
    draw_size: int,
    minimum_matches: int,
    portfolio: Portfolio,
) -> Portfolio:
    if not 1 <= draw_size <= pool_size <= 64:
        raise ValueError("require 1 <= draw_size <= pool_size <= 64")
    if not 1 <= minimum_matches <= draw_size:
        raise ValueError("minimum_matches must lie in [1, draw_size]")

    canonical = canonicalize_portfolio(portfolio)
    if not canonical:
        raise ValueError("portfolio must contain at least one ticket")
    for ticket in canonical:
        if len(ticket) != draw_size:
            raise ValueError(
                f"ticket length {len(ticket)} does not match draw_size {draw_size}"
            )
        if any(number < 1 or number > pool_size for number in ticket):
            raise ValueError(f"ticket number out of range 1..{pool_size}")
    return canonical


def _ticket_mask(ticket: Ticket) -> int:
    mask = 0
    for number in ticket:
        mask |= 1 << (number - 1)
    return mask


@cache
def _winning_draw_masks(pool_size: int, draw_size: int) -> array[int]:
    """Return every draw mask once, in deterministic increasing-mask order."""
    if not 1 <= draw_size <= pool_size <= 64:
        raise ValueError("require 1 <= draw_size <= pool_size <= 64")

    masks = array("Q")
    current = (1 << draw_size) - 1
    limit = 1 << pool_size
    while current < limit:
        masks.append(current)
        smallest_bit = current & -current
        ripple = current + smallest_bit
        current = ripple | (((ripple ^ current) >> 2) // smallest_bit)

    expected_count = math.comb(pool_size, draw_size)
    if len(masks) != expected_count:
        raise RuntimeError(
            f"winning-space enumeration mismatch: expected {expected_count}, got {len(masks)}"
        )
    return masks


def enumerate_unique_legal_one_exchange_neighbors(
    portfolio: Portfolio,
    pool_size: int,
) -> tuple[Portfolio, ...]:
    """Return every unique legal exact-one-number-exchange portfolio in order."""
    canonical = canonicalize_portfolio(portfolio)
    return tuple(candidate.portfolio for candidate in _exchange_candidates(canonical, pool_size))


def _exchange_candidates(
    portfolio: Portfolio,
    pool_size: int,
) -> tuple[_ExchangeCandidate, ...]:
    portfolio_set = set(portfolio)
    by_portfolio: dict[Portfolio, _ExchangeCandidate] = {}

    for slot_index, original_ticket in enumerate(portfolio):
        original_set = set(original_ticket)
        remaining = portfolio[:slot_index] + portfolio[slot_index + 1 :]
        for removed_number in original_ticket:
            retained = original_set - {removed_number}
            for added_number in range(1, pool_size + 1):
                if added_number in original_set:
                    continue
                mutated_ticket = tuple(sorted((*retained, added_number)))
                if mutated_ticket in portfolio_set:
                    continue
                neighbor = tuple(sorted((*remaining, mutated_ticket)))
                by_portfolio.setdefault(
                    neighbor,
                    _ExchangeCandidate(
                        portfolio=neighbor,
                        slot_index=slot_index,
                        removed_number=removed_number,
                        added_number=added_number,
                    ),
                )

    return tuple(by_portfolio[neighbor] for neighbor in sorted(by_portfolio))


def _subset_masks(ticket: Ticket, subset_size: int) -> tuple[int, ...]:
    return tuple(_ticket_mask(subset) for subset in itertools.combinations(ticket, subset_size))


def _empty_subset_rows(
    portfolio: Portfolio,
    subset_size: int,
    pool_size: int,
) -> list[SubsetCoverageRows]:
    return [
        {subset_mask: [0] * pool_size for subset_mask in _subset_masks(ticket, subset_size)}
        for ticket in portfolio
    ]


def _increment_added_number_rows(row: CoverageRow, outside_mask: int) -> None:
    while outside_mask:
        number_bit = outside_mask & -outside_mask
        row[number_bit.bit_length() - 1] += 1
        outside_mask ^= number_bit


def _exact_neighbor_coverages(
    pool_size: int,
    draw_size: int,
    minimum_matches: int,
    portfolio: Portfolio,
    candidates: tuple[_ExchangeCandidate, ...],
) -> tuple[int, tuple[ExactOneExchangeNeighbor, ...]]:
    """Return input covered-draw count and exact counts for all candidates.

    A candidate differs from its source ticket ``T`` by ``T - {r} + {a}``.
    Relative to the portfolio without ``T``:

    * a uniquely covered draw matching at least four numbers in ``T`` remains
      covered for every candidate;
    * a uniquely covered three-match draw remains covered when ``r`` is not
      one of those three numbers, or when the added ``a`` is in the draw;
    * a currently uncovered two-match draw becomes covered when ``r`` is not
      one of those two numbers and ``a`` is in the draw.

    Aggregating precisely those mutually exhaustive cases evaluates all legal
    candidates without approximation.
    """
    ticket_masks = tuple(_ticket_mask(ticket) for ticket in portfolio)
    ticket_count = len(portfolio)

    unique_covered_by_slot = [0] * ticket_count
    unique_four_plus_by_slot = [0] * ticket_count
    unique_three_counts = [
        {subset_mask: 0 for subset_mask in _subset_masks(ticket, 3)}
        for ticket in portfolio
    ]
    unique_three_added_counts = _empty_subset_rows(portfolio, 3, pool_size)
    uncovered_two_added_counts = _empty_subset_rows(portfolio, 2, pool_size)

    covered_draw_count = 0
    two_match_slots: list[int] = []
    two_match_intersections: list[int] = []

    for draw_mask in _winning_draw_masks(pool_size, draw_size):
        qualifying_slot = -1
        qualifying_matches = 0
        qualifying_intersection = 0
        multiple_qualifiers = False
        two_match_slots.clear()
        two_match_intersections.clear()

        for slot_index in range(ticket_count):
            intersection = draw_mask & ticket_masks[slot_index]
            match_count = intersection.bit_count()
            if match_count >= minimum_matches:
                if qualifying_slot >= 0:
                    multiple_qualifiers = True
                    break
                qualifying_slot = slot_index
                qualifying_matches = match_count
                qualifying_intersection = intersection
                two_match_slots.clear()
                two_match_intersections.clear()
            elif qualifying_slot < 0 and minimum_matches == 3 and match_count == 2:
                two_match_slots.append(slot_index)
                two_match_intersections.append(intersection)

        if multiple_qualifiers:
            covered_draw_count += 1
            continue

        if qualifying_slot >= 0:
            covered_draw_count += 1
            unique_covered_by_slot[qualifying_slot] += 1
            if qualifying_matches >= minimum_matches + 1:
                unique_four_plus_by_slot[qualifying_slot] += 1
            elif minimum_matches == 3:
                unique_three_counts[qualifying_slot][qualifying_intersection] += 1
                outside_mask = draw_mask ^ qualifying_intersection
                row = unique_three_added_counts[qualifying_slot][qualifying_intersection]
                _increment_added_number_rows(row, outside_mask)
            else:
                raise ValueError("the simultaneous exact evaluator currently requires M3_PLUS")
            continue

        if minimum_matches != 3:
            raise ValueError("the simultaneous exact evaluator currently requires M3_PLUS")
        for index, slot_index in enumerate(two_match_slots):
            intersection = two_match_intersections[index]
            outside_mask = draw_mask ^ intersection
            row = uncovered_two_added_counts[slot_index][intersection]
            _increment_added_number_rows(row, outside_mask)

    total_draws = len(_winning_draw_masks(pool_size, draw_size))
    neighbors: list[ExactOneExchangeNeighbor] = []
    for candidate in candidates:
        slot_index = candidate.slot_index
        removed_bit = 1 << (candidate.removed_number - 1)
        added_index = candidate.added_number - 1
        newly_covered_over_base = unique_four_plus_by_slot[slot_index]

        for triple_mask, triple_count in unique_three_counts[slot_index].items():
            if triple_mask & removed_bit:
                newly_covered_over_base += unique_three_added_counts[slot_index][triple_mask][
                    added_index
                ]
            else:
                newly_covered_over_base += triple_count

        for pair_mask, added_counts in uncovered_two_added_counts[slot_index].items():
            if not pair_mask & removed_bit:
                newly_covered_over_base += added_counts[added_index]

        base_coverage = covered_draw_count - unique_covered_by_slot[slot_index]
        candidate_covered_draws = base_coverage + newly_covered_over_base
        neighbors.append(
            ExactOneExchangeNeighbor(
                portfolio=candidate.portfolio,
                slot_index=slot_index,
                removed_number=candidate.removed_number,
                added_number=candidate.added_number,
                exact_q=Fraction(candidate_covered_draws, total_draws),
            )
        )

    return covered_draw_count, tuple(neighbors)


def evaluate_exact_one_exchange_neighborhood(
    pool_size: int,
    draw_size: int,
    minimum_matches: int,
    portfolio: Portfolio,
) -> ExactOneExchangeNeighborhoodResult:
    """Evaluate every unique legal 1-exchange neighbor exactly."""
    canonical = _validate_and_canonicalize(
        pool_size, draw_size, minimum_matches, portfolio
    )
    if minimum_matches != 3:
        raise ValueError("the simultaneous exact evaluator currently requires M3_PLUS")

    candidates = _exchange_candidates(canonical, pool_size)
    if not candidates:
        raise ValueError("no legal one-exchange neighbors found")

    covered_draw_count, neighbors = _exact_neighbor_coverages(
        pool_size,
        draw_size,
        minimum_matches,
        canonical,
        candidates,
    )
    total_draws = math.comb(pool_size, draw_size)
    input_q = Fraction(covered_draw_count, total_draws)
    best_neighbor = min(neighbors, key=lambda neighbor: (-neighbor.exact_q, neighbor.portfolio))
    delta = best_neighbor.exact_q - input_q
    return ExactOneExchangeNeighborhoodResult(
        input_portfolio=canonical,
        input_q=input_q,
        unique_legal_neighbor_count=len(neighbors),
        neighbors=neighbors,
        best_neighbor_portfolio=best_neighbor.portfolio,
        best_neighbor_q=best_neighbor.exact_q,
        delta=delta,
    )


def iterative_exact_one_exchange_ascent(
    pool_size: int,
    draw_size: int,
    minimum_matches: int,
    seed_portfolio: Portfolio,
) -> ExactOneExchangeAscentResult:
    """Take deterministic strict best-neighbor moves until local optimality."""
    current = _validate_and_canonicalize(
        pool_size, draw_size, minimum_matches, seed_portfolio
    )
    iterations: list[ExactOneExchangeAscentIteration] = []
    move_count = 0

    while True:
        neighborhood = evaluate_exact_one_exchange_neighborhood(
            pool_size,
            draw_size,
            minimum_matches,
            current,
        )
        accepted_move = neighborhood.best_neighbor_q > neighborhood.input_q
        iterations.append(
            ExactOneExchangeAscentIteration(
                iteration_index=len(iterations),
                input_portfolio=current,
                input_q=neighborhood.input_q,
                unique_legal_neighbor_count=neighborhood.unique_legal_neighbor_count,
                best_neighbor_portfolio=neighborhood.best_neighbor_portfolio,
                best_neighbor_q=neighborhood.best_neighbor_q,
                delta=neighborhood.delta,
                accepted_move=accepted_move,
            )
        )

        if not accepted_move:
            return ExactOneExchangeAscentResult(
                seed_portfolio=iterations[0].input_portfolio,
                seed_q=iterations[0].input_q,
                iterations=tuple(iterations),
                move_count=move_count,
                terminal_portfolio=current,
                terminal_q=neighborhood.input_q,
            )

        current = neighborhood.best_neighbor_portfolio
        move_count += 1
