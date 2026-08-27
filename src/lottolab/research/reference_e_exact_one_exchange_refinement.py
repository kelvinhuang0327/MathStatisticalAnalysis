"""Exact one-number-exchange neighborhood enumeration and selection for lottery portfolios.

This module implements Phase 9 of the Strategy Matrix research program:
determining exhaustively whether a reference portfolio (specifically Method E,
``GREEDY_MINMAX_THEN_SUM_OVERLAP_V1``) has any strictly better exact
one-number-exchange neighbor at tested exposure rungs (e.g. B649 k=10, 15, 20).

For a portfolio of ``k`` tickets where each ticket contains ``draw_size`` numbers
from ``1..pool_size``:
- A legal single-ticket mutation chooses one slot ``i`` in ``0..k-1``, removes
  exactly one number from ticket ``P[i]``, and adds exactly one number from
  ``1..pool_size`` not already present in ``P[i]``.
- If the mutated ticket is already present in the portfolio, the resulting
  candidate is rejected (all portfolios must contain ``k`` distinct tickets).
- Equivalent resulting portfolios (invariant under ticket order) are de-duplicated.
- Exact coverage (e.g. M3+ for B649) is evaluated for every unique neighbor using
  the exact fast coverage evaluator (``coverage_with_base``).
- The maximum exact-coverage neighbor is selected. Exact ties are broken by
  choosing the lexicographically smallest complete resulting portfolio.
- No second exchange is performed.
"""

from __future__ import annotations

from collections.abc import Iterable
from fractions import Fraction
from typing import Any

from lottolab.research.exact_coverage_fast_evaluator import (
    clear_cache,
    coverage_with_base,
    fast_exact_portfolio_coverage,
    portfolio_qualifying_draws,
)

Ticket = tuple[int, ...]
Portfolio = tuple[Ticket, ...]


def canonicalize_ticket(ticket: Iterable[int]) -> Ticket:
    """Return an ascending-sorted tuple of distinct positive integers."""
    sorted_ticket = tuple(sorted(ticket))
    if len(set(sorted_ticket)) != len(sorted_ticket):
        raise ValueError(f"ticket contains duplicate numbers: {ticket}")
    return sorted_ticket


def canonicalize_portfolio(portfolio: Iterable[Iterable[int]]) -> Portfolio:
    """Return a lexicographically sorted tuple of canonicalized tickets."""
    tickets = [canonicalize_ticket(t) for t in portfolio]
    if len(set(tickets)) != len(tickets):
        raise ValueError("portfolio contains duplicate tickets")
    return tuple(sorted(tickets))


def legal_one_exchange_tickets(pool_size: int, ticket: Ticket) -> list[Ticket]:
    """All legal tickets obtained by removing 1 number from `ticket` and adding 1.

    Given a ticket of size `d` from `1..pool_size`:
    There are `d` choices of number to remove and `pool_size - d` choices of
    number to add, yielding exactly `d * (pool_size - d)` distinct mutated tickets.
    """
    ticket_set = set(ticket)
    complement = [n for n in range(1, pool_size + 1) if n not in ticket_set]
    mutations: list[Ticket] = []

    for r in sorted(ticket_set):
        base_subset = ticket_set - {r}
        for a in complement:
            mutated = tuple(sorted(base_subset | {a}))
            mutations.append(mutated)

    return mutations


def enumerate_legal_one_exchange_neighbors(
    portfolio: Portfolio,
    pool_size: int,
) -> list[Portfolio]:
    """Enumerate all unique legal portfolios obtained by exactly one ticket mutation.

    Parameters:
        portfolio: Canonical reference portfolio of k tickets.
        pool_size: Total numbers in lottery pool.

    Returns:
        List of all unique legal neighbor portfolios, sorted lexicographically.
    """
    if len(portfolio) == 0:
        return []

    portfolio_set = set(portfolio)
    unique_neighbors: set[Portfolio] = set()

    for i, original_ticket in enumerate(portfolio):
        remaining_tickets = portfolio[:i] + portfolio[i + 1 :]
        for mutated_ticket in legal_one_exchange_tickets(pool_size, original_ticket):
            if mutated_ticket in portfolio_set:
                # Reject duplicate tickets in the portfolio
                continue
            neighbor = tuple(sorted((*remaining_tickets, mutated_ticket)))
            unique_neighbors.add(neighbor)

    return sorted(unique_neighbors)


def evaluate_one_exchange_neighborhood(
    pool_size: int,
    draw_size: int,
    minimum_matches: int,
    portfolio: Portfolio,
) -> dict[str, Any]:
    """Exhaustively evaluate all legal 1-exchange neighbors of a portfolio.

    Evaluates exact M3+ coverage using `coverage_with_base` per slot and
    clears the evaluator cache at slot boundaries to maintain strict O(1)
    memory bounds.

    Returns a comprehensive result dictionary with exact fractions:
    - q_reference: baseline coverage of `portfolio`
    - unique_neighbor_count: number of unique legal neighbor portfolios
    - best_neighbor: selected best neighbor portfolio (lexicographic tiebreak)
    - q_best_neighbor: coverage of best neighbor
    - delta_vs_reference: q_best_neighbor - q_reference
    - classification: "ONE_EXCHANGE_IMPROVEMENT_FOUND" if delta > 0
                      else "REFERENCE_E_ONE_EXCHANGE_LOCAL_OPTIMUM"
    - all_neighbors_evaluated: count of unique evaluations performed
    """
    canonical_ref = canonicalize_portfolio(portfolio)
    k = len(canonical_ref)
    if k == 0:
        raise ValueError("portfolio must contain at least 1 ticket")

    for ticket in canonical_ref:
        if len(ticket) != draw_size:
            raise ValueError(f"ticket length {len(ticket)} does not match draw_size {draw_size}")
        if any(n < 1 or n > pool_size for n in ticket):
            raise ValueError(f"ticket number out of range 1..{pool_size}")

    q_reference = fast_exact_portfolio_coverage(
        pool_size, draw_size, minimum_matches, canonical_ref
    )

    portfolio_set = set(canonical_ref)
    neighbor_coverages: dict[Portfolio, Fraction] = {}

    for i, original_ticket in enumerate(canonical_ref):
        remaining_tickets = canonical_ref[:i] + canonical_ref[i + 1 :]
        base_draws = portfolio_qualifying_draws(
            pool_size, draw_size, minimum_matches, remaining_tickets
        )
        for mutated_ticket in legal_one_exchange_tickets(pool_size, original_ticket):
            if mutated_ticket in portfolio_set:
                # Reject duplicate tickets
                continue
            neighbor_portfolio = tuple(sorted((*remaining_tickets, mutated_ticket)))
            if neighbor_portfolio in neighbor_coverages:
                continue
            q_neighbor = coverage_with_base(
                pool_size, draw_size, minimum_matches, base_draws, mutated_ticket
            )
            neighbor_coverages[neighbor_portfolio] = q_neighbor

        # Clear per-ticket cache after slot to keep peak memory strictly bounded
        clear_cache()

    unique_neighbor_count = len(neighbor_coverages)
    if unique_neighbor_count == 0:
        raise ValueError("no legal one-exchange neighbors found")

    # Select maximum exact coverage; break ties with lexicographically smallest portfolio
    best_neighbor, q_best_neighbor = min(
        neighbor_coverages.items(),
        key=lambda item: (-item[1], item[0]),
    )

    delta_vs_reference = q_best_neighbor - q_reference
    if delta_vs_reference > 0:
        classification = "ONE_EXCHANGE_IMPROVEMENT_FOUND"
    else:
        classification = "REFERENCE_E_ONE_EXCHANGE_LOCAL_OPTIMUM"

    return {
        "q_reference": q_reference,
        "unique_neighbor_count": unique_neighbor_count,
        "best_neighbor": best_neighbor,
        "q_best_neighbor": q_best_neighbor,
        "delta_vs_reference": delta_vs_reference,
        "classification": classification,
        "all_neighbors_evaluated": unique_neighbor_count,
    }
