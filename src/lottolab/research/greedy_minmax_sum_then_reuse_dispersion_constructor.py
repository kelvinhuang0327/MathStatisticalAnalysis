"""Deterministic greedy packing extending Reference E with a reuse-dispersion tiebreak.

This is ``MATRIX_PHASE8_METHOD_F_DISCOVERY_R1`` Candidate F
(``GREEDY_MINMAX_SUM_THEN_REUSE_DISPERSION_V1``). See
``docs/research/matrix-native-results/
method-f-reuse-dispersion-tiebreak-b649-v1-preregistration.md``.

Reference E (``greedy_minmax_then_sum_overlap_constructor
.greedy_minmax_then_sum_overlap_portfolio``) already minimizes, in order,
the incremental max pairwise overlap and then the incremental sum of
pairwise overlaps, breaking any remaining tie by lexicographic ticket
order. Whenever more than one unused legal ticket shares Reference E's
minimal ``(max, sum)`` pair, Reference E's own tie-break is arbitrary scan
order -- it carries no geometric meaning.

Candidate F asks whether a *specific* geometric tiebreak among those
already-tied candidates -- prefer the ticket that leaves per-number reuse
least concentrated -- changes exact primary-event coverage. It inserts two
new lexicographic coordinates between Reference E's ``sum`` coordinate and
the final lex-ticket coordinate:

    ``(max overlap, sum overlap, resulting peak reuse,
       resulting SUM_i C(reuse_i, 3), ticket)``

"Resulting" means: evaluated on the portfolio that would exist if the
candidate were appended next, not the portfolio built so far. Peak reuse is
``max`` over every pool number of how many chosen tickets contain it.
``SUM_i C(reuse_i, 3)`` sums, over every pool number, the number of chosen
*triples* of tickets that all reuse that number -- the same reuse-triple
count Phase 6 already isolated as the ``S3`` residual term, used here only
as a tiebreak key, never as an independent scored objective and never
allowed to override ``(max, sum)``.

There is no weight, no random restart, no historical draw, no outcome
label, and no post-result coefficient. The procedure is parametrized only
by ``(pool_size, draw_size, ticket_count)``, exactly like Reference E. It
makes no optimality claim.
"""

from __future__ import annotations

import itertools
import math

Ticket = tuple[int, ...]
ReuseDispersionKey = tuple[int, int, int, int, Ticket]


def pairwise_overlap(left: Ticket, right: Ticket) -> int:
    """Cardinality of the intersection of two already-canonical tickets."""

    return len(set(left) & set(right))


def peak_reuse_after(candidate: Ticket, reuse: list[int]) -> int:
    """The portfolio-wide maximum per-number reuse count if ``candidate`` were appended.

    ``reuse`` holds the current per-pool-number usage counts (index ``i``
    is pool number ``i + 1``) for the portfolio built so far. Appending
    ``candidate`` can only increase the counts at its own ``draw_size``
    positions, so the new peak is the larger of the current portfolio-wide
    peak and the largest incremented count among ``candidate``'s own
    numbers -- no other position can newly hold the maximum.
    """

    return max(max(reuse), max(reuse[number - 1] + 1 for number in candidate))


def sum_c3_reuse_after(candidate: Ticket, reuse: list[int], current_sum_c3: int) -> int:
    """The portfolio-wide ``SUM_i C(reuse_i, 3)`` if ``candidate`` were appended.

    Only ``candidate``'s own ``draw_size`` positions change, each from
    ``reuse[i]`` to ``reuse[i] + 1``, so the new total is the current total
    plus the sum of each position's ``C(count + 1, 3) - C(count, 3)`` delta.
    """

    delta = sum(
        math.comb(reuse[number - 1] + 1, 3) - math.comb(reuse[number - 1], 3)
        for number in candidate
    )
    return current_sum_c3 + delta


def incremental_reuse_dispersion_key(
    candidate: Ticket,
    portfolio: tuple[Ticket, ...] | list[Ticket],
    reuse: list[int],
    current_sum_c3: int,
) -> ReuseDispersionKey:
    """The frozen incremental key of ``candidate`` against an existing portfolio.

    ``max`` and ``sum`` are exactly Reference E's coordinates. The two
    reuse coordinates only ever discriminate among tickets Reference E
    already considers tied; they can never make a worse ``(max, sum)``
    win. The ticket itself remains the final total-order tiebreak.
    """

    overlaps = [pairwise_overlap(candidate, ticket) for ticket in portfolio]
    maximum = max(overlaps, default=0)
    total = sum(overlaps)
    peak_after = peak_reuse_after(candidate, reuse)
    sum_c3_after = sum_c3_reuse_after(candidate, reuse, current_sum_c3)
    return (maximum, total, peak_after, sum_c3_after, candidate)


def greedy_minmax_sum_then_reuse_dispersion_portfolio(
    pool_size: int, draw_size: int, ticket_count: int
) -> tuple[Ticket, ...]:
    """The first ``ticket_count`` tickets of the lex reuse-dispersion-tiebreak packing.

    Ticket 0 is the lexicographically first ``draw_size``-subset of
    ``1..pool_size`` -- with an empty portfolio, every candidate ties at
    ``(0, 0, 1, 0, ticket)`` (peak reuse becomes 1 and ``SUM C(reuse, 3)``
    stays 0 for any first ticket), so only lexicographic order can decide,
    exactly reproducing Reference E's ticket 0. Ticket ``i`` (``i >= 1``) is
    the unused candidate whose incremental key
    ``(max overlap, sum overlap, resulting peak reuse,
    resulting SUM_i C(reuse_i, 3), ticket)`` is smallest. No backtracking
    and no revision of an earlier ticket.

    Whenever an unused candidate fully disjoint from the current portfolio
    exists (incremental max overlap 0), it is the unique-up-to-lex-order
    minimizer of the entire key: every such candidate's own ``draw_size``
    numbers currently have reuse count exactly 0 (any existing reuse would
    force an overlap with the ticket that created it), so *every* disjoint
    candidate yields the same ``peak_reuse_after`` and the same
    ``sum_c3_reuse_after`` as every other disjoint candidate -- the reuse
    coordinates cannot separate them. The lexicographically first disjoint
    candidate found is therefore globally optimal, so the scan may stop
    there, exactly as Reference E's own early exit does.
    """

    if pool_size < draw_size:
        raise ValueError("pool_size must be >= draw_size")
    total = math.comb(pool_size, draw_size)
    if not 0 <= ticket_count <= total:
        raise ValueError(f"ticket_count must lie in [0, {total}]")

    portfolio: list[Ticket] = []
    reuse = [0] * pool_size
    sum_c3 = 0
    for _ in range(ticket_count):
        used = set(portfolio)
        best_candidate: Ticket | None = None
        best_key: ReuseDispersionKey | None = None
        for candidate in itertools.combinations(range(1, pool_size + 1), draw_size):
            if candidate in used:
                continue
            key = incremental_reuse_dispersion_key(candidate, portfolio, reuse, sum_c3)
            if best_key is None or key < best_key:
                best_key = key
                best_candidate = candidate
                if key[0] == 0:
                    break
        assert best_candidate is not None  # ticket_count <= C(pool_size, draw_size)
        sum_c3 = sum_c3_reuse_after(best_candidate, reuse, sum_c3)
        for number in best_candidate:
            reuse[number - 1] += 1
        portfolio.append(best_candidate)
    return tuple(portfolio)
