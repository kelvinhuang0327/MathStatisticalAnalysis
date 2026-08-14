"""A deterministic, greedy low-overlap ticket family with no algebraic structure.

Unlike `cyclic_sidon_shift` (a Sidon/B_2 difference-set construction), this
module builds each ticket by direct greedy search over the candidate space:
scan every valid `draw_size`-subset of the pool in lexicographic order and
keep the first one whose worst-case pairwise overlap with every ticket
already in the portfolio is smallest. There is no modular arithmetic, no
pairwise-difference distinctness criterion, and no cyclic shift of a fixed
base set anywhere in this procedure -- the lexicographic candidate order
and the min-max-overlap acceptance rule are the entire mechanism. This
module makes no optimality claim -- it names one specific, disclosed,
greedy low-overlap procedure, nothing more.

This is `STRATEGY_MATRIX_PHASE5_DIVERSIFICATION_CONSTRUCTOR_FRONTIER_DESIGN_R1`
arm B (`NON_SIDON_LOW_OVERLAP`). See
`docs/research/strategy-matrix-phase5-diversification-constructor-frontier-design-r1.md`.
Parametrized by `(pool_size, draw_size)` like `exact_coverage_baseline`; not
invoked at real B649 scale (`pool_size=49, draw_size=6`) by this design task
-- only toy/synthetic sizes, per that document's scope boundary.
"""

from __future__ import annotations

import itertools
import math


def _overlap(a: tuple[int, ...], b: tuple[int, ...]) -> int:
    return len(set(a) & set(b))


def greedy_min_overlap_portfolio(
    pool_size: int, draw_size: int, ticket_count: int
) -> tuple[tuple[int, ...], ...]:
    """The first `ticket_count` tickets built by the greedy min-max-overlap rule.

    Ticket 0 is the lexicographically first `draw_size`-subset of
    `1..pool_size`. Ticket `i` (`i >= 1`) is the lexicographically first
    not-yet-used `draw_size`-subset whose maximum pairwise overlap with any
    of tickets `0..i-1` is smallest among all candidates -- plain greedy
    scan-and-keep-best, ties broken by lexicographic candidate order, no
    backtracking, no revisiting an earlier ticket. A strict prefix
    relationship holds by construction: each ticket is chosen once and
    never revisited, so the portfolio for `ticket_count=k` is always the
    portfolio for `ticket_count=k-1` with exactly one ticket appended.

    A side effect of this rule, not a hard-coded special case: whenever an
    overlap-0 candidate still exists (which is guaranteed while fewer than
    `pool_size // draw_size` disjoint blocks have been used), the search
    finds and keeps the lexicographically first one and stops scanning
    immediately -- so early tickets look like sequential disjoint blocks
    purely as a consequence of the general rule, not because disjointness
    was special-cased.
    """

    if pool_size < draw_size:
        raise ValueError("pool_size must be >= draw_size")
    total = math.comb(pool_size, draw_size)
    if not 0 <= ticket_count <= total:
        raise ValueError(f"ticket_count must lie in [0, {total}]")

    portfolio: list[tuple[int, ...]] = []
    for _ in range(ticket_count):
        used = set(portfolio)
        best_candidate: tuple[int, ...] | None = None
        best_score = draw_size + 1
        for candidate in itertools.combinations(range(1, pool_size + 1), draw_size):
            if candidate in used:
                continue
            score = max((_overlap(candidate, ticket) for ticket in portfolio), default=0)
            if score < best_score:
                best_score = score
                best_candidate = candidate
                if score == 0:
                    break
        assert best_candidate is not None  # a candidate always remains: ticket_count <= total
        portfolio.append(best_candidate)
    return tuple(portfolio)
