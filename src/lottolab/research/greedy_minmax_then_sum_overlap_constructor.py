"""Deterministic greedy packing by lexicographic pairwise-collision reduction.

This is ``STRATEGY_MATRIX_PHASE7_CONSTRUCTOR_FRONTIER_NEXT_GENERATION_DESIGN_R1``
arm CANDIDATE (``GREEDY_MINMAX_THEN_SUM_OVERLAP_V1``).  See
``docs/research/strategy-matrix-phase7-constructor-frontier-next-generation-design-r1.md``.

Arm-B (``greedy_min_overlap_portfolio``) minimizes only the worst-case
pairwise overlap and breaks remaining ties by lexicographic scan order.
Under the sealed ``max_pairwise_overlap <= 1`` regime, that secondary lex
scan does not minimize the exact ``S2`` increment: when every ticket-pair
intersection is in ``{0, 1}``, ``S2`` is an affine function of the number
of intersecting pairs, which is exactly the sum of pairwise overlaps.

This constructor therefore uses one frozen lexicographic geometry key:

    ``(max pairwise overlap, sum of pairwise overlaps, ticket)``

There is no weighted score, no random restart, no historical draw, no
outcome label, and no post-result coefficient.  The procedure is
parametrized only by ``(pool_size, draw_size, ticket_count)``.  It makes
no optimality claim and is not a B649-scale execution.
"""

from __future__ import annotations

import itertools
import math

Ticket = tuple[int, ...]
CollisionKey = tuple[int, int, Ticket]


def pairwise_overlap(left: Ticket, right: Ticket) -> int:
    """Cardinality of the intersection of two already-canonical tickets."""

    return len(set(left) & set(right))


def incremental_pairwise_collision_key(
    candidate: Ticket, portfolio: tuple[Ticket, ...] | list[Ticket]
) -> CollisionKey:
    """The frozen incremental key of ``candidate`` against an existing portfolio.

    ``max`` is the Arm-B primary objective.  ``sum`` is the exact ``S2``
    increment (up to the positive constant ``H(1) - H(0)``) whenever every
    pairwise intersection stays in ``{0, 1}``.  The ticket itself is the
    final deterministic total order, never a geometry objective.
    """

    overlaps = [pairwise_overlap(candidate, ticket) for ticket in portfolio]
    maximum = max(overlaps, default=0)
    total = sum(overlaps)
    return (maximum, total, candidate)


def greedy_minmax_then_sum_overlap_portfolio(
    pool_size: int, draw_size: int, ticket_count: int
) -> tuple[Ticket, ...]:
    """The first ``ticket_count`` tickets of the lex pairwise-collision packing.

    Ticket 0 is the lexicographically first ``draw_size``-subset of
    ``1..pool_size``.  Ticket ``i`` (``i >= 1``) is the unused candidate
    whose incremental key
    ``(max overlap, sum overlap, ticket)`` is smallest.  No backtracking
    and no revision of an earlier ticket: the portfolio at ``k`` is always
    the portfolio at ``k - 1`` with one ticket appended.

    While an overlap-0 candidate still exists, its key is ``(0, 0, ticket)``
    and lexicographic scan order therefore selects the same sequential
    disjoint blocks as Arm-B.  The constructors first differ when every
    remaining candidate has positive overlap and a smaller collision *count*
    can beat a lexicographically earlier transversal.
    """

    if pool_size < draw_size:
        raise ValueError("pool_size must be >= draw_size")
    total = math.comb(pool_size, draw_size)
    if not 0 <= ticket_count <= total:
        raise ValueError(f"ticket_count must lie in [0, {total}]")

    portfolio: list[Ticket] = []
    for _ in range(ticket_count):
        used = set(portfolio)
        best_candidate: Ticket | None = None
        best_key: CollisionKey | None = None
        for candidate in itertools.combinations(range(1, pool_size + 1), draw_size):
            if candidate in used:
                continue
            key = incremental_pairwise_collision_key(candidate, portfolio)
            if best_key is None or key < best_key:
                best_key = key
                best_candidate = candidate
                if key[0] == 0:
                    # max = 0 implies sum = 0; any later unused ticket is
                    # lexicographically larger, so the scan may stop.
                    break
        assert best_candidate is not None  # ticket_count <= C(pool_size, draw_size)
        portfolio.append(best_candidate)
    return tuple(portfolio)
