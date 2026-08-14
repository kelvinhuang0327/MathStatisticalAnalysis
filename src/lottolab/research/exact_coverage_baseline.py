"""Exact combinatorial random-portfolio coverage baseline (no simulation).

For a fixed lottery rule (pool size `N_pool`, main draw size `draw_size`),
computes -- as an exact `fractions.Fraction`, never a float approximation
-- the probability that at least one of `k` distinct, uniformly randomly
selected tickets achieves at least `m` main-number matches against a
single winning draw. This is the closed-form baseline
`ALLOCATION_EXPOSURE_EFFICIENCY_B649_V1` compares fixed ticket portfolios
against; see
`docs/research/allocation-exposure-efficiency-b649-v1-preregistration.md`.

The derivation: for a *fixed* winning combination, the number of tickets
(6-subsets of the pool) achieving exactly `j` matches is
`C(draw_size, j) * C(N_pool - draw_size, draw_size - j)` (choose `j` of the
`draw_size` winning numbers and the rest from the non-winning pool).
Summing over `j >= m` gives `K(m)`, the count of "qualifying" tickets out
of the `N = C(N_pool, draw_size)` total possible tickets. Sampling `k`
distinct tickets uniformly without replacement, `P(zero qualify)` is the
hypergeometric zero-success probability `C(N-K(m), k) / C(N, k)`, so
`P(at least one qualifies) = 1 - C(N-K(m), k) / C(N, k)`. This holds for
every possible winning combination by symmetry (the pool has no
distinguished numbers), so it is also the unconditional probability over
the draw's own randomness -- no enumeration or simulation of draws is
needed for this side of the comparison.
"""

from __future__ import annotations

import math
from fractions import Fraction


def qualifying_ticket_count(pool_size: int, draw_size: int, minimum_matches: int) -> int:
    """K(m): count of tickets (6-subsets of the pool) with >= m matches

    against any one fixed winning combination.
    """

    if not 0 <= minimum_matches <= draw_size:
        raise ValueError("minimum_matches must lie in [0, draw_size]")
    return sum(
        math.comb(draw_size, j) * math.comb(pool_size - draw_size, draw_size - j)
        for j in range(minimum_matches, draw_size + 1)
    )


def exact_random_portfolio_coverage(
    pool_size: int, draw_size: int, minimum_matches: int, ticket_count: int
) -> Fraction:
    """Q_random_m(k): exact P(>= 1 of `ticket_count` distinct random tickets

    achieves >= `minimum_matches` matches), as an exact `Fraction`.
    """

    if ticket_count < 0:
        raise ValueError("ticket_count must be non-negative")
    total_tickets = math.comb(pool_size, draw_size)
    if ticket_count > total_tickets:
        raise ValueError("ticket_count cannot exceed the total number of possible tickets")
    qualifying = qualifying_ticket_count(pool_size, draw_size, minimum_matches)
    non_qualifying = total_tickets - qualifying
    if ticket_count > non_qualifying:
        return Fraction(1)
    probability_all_fail = Fraction(
        math.comb(non_qualifying, ticket_count), math.comb(total_tickets, ticket_count)
    )
    return 1 - probability_all_fail
