"""A faster exact portfolio-coverage evaluator, verified parity-equal to
`bounded_coverage_optimizer.exact_portfolio_coverage` (the correctness
authority this module is checked against -- see
`tests/unit/test_exact_coverage_fast_evaluator.py`).

`exact_portfolio_coverage` re-enumerates the complete `C(pool_size,
draw_size)` winning space on every call and checks each draw against every
ticket in the portfolio -- correct, but its cost is dominated entirely by
`pool_size`/`draw_size`, independent of how much of that space a single
ticket could ever match. This module instead generates, per ticket, only
the draws that actually share `>= minimum_matches` numbers with it --
directly, by choosing `j` numbers from the ticket and `draw_size - j` from
its complement for each qualifying `j`, never scanning the draws that
cannot qualify. That count (`qualifying_ticket_count` in
`exact_coverage_baseline.py`) is far smaller than `C(pool_size, draw_size)`
whenever `minimum_matches` is close to `draw_size` -- exactly the regime
`STRATEGY_MATRIX_PHASE5_DIVERSIFICATION_CONSTRUCTOR_FRONTIER_DESIGN_R1`
needs (`M3_PLUS` through `M6` at B649 scale: 260,624 / 13,804 / 259 / 1
qualifying draws per ticket out of 13,983,816 total). Per-ticket results
are cached (keyed by the canonicalized ticket, not portfolio-dependent),
so a portfolio that reuses a ticket across many evaluations -- exactly how
`RESTART_GREEDY_SWAP_COVERAGE_SEARCH_B649_V1`'s construction and swap
phases call the evaluator -- pays the generation cost at most once per
distinct ticket ever seen.

`coverage_with_base` additionally supports the swap-search call pattern
directly: evaluating many single-ticket replacements against an otherwise
fixed portfolio. Rather than re-union every ticket's qualifying draws on
each candidate, it takes the fixed portfolio's already-unioned qualifying
draws once and combines a new candidate's (typically much smaller, always
cached-after-first-use) qualifying-draw set via inclusion-exclusion
(`len(base | candidate) = len(base) + len(candidate) - len(base &
candidate)`), so per-candidate cost is bounded by the candidate's own
qualifying-draw count rather than the size of the base union.

No approximation, no Monte Carlo, no historical draw data: every count
this module produces is exact, via direct combinatorial enumeration.

Memory, not just time, is the tradeoff this design makes: the cache is
unbounded (`functools.cache`) and each cached ticket holds its full
qualifying-draws set in memory -- measured at real B649 scale
(`pool_size=49, draw_size=6, minimum_matches=3`), roughly 26 MB per
distinct ticket, so a run that never calls `clear_cache()` accumulates
memory roughly proportional to the number of *distinct* tickets ever
evaluated, not just the portfolio size. A caller doing many single-restart
evaluations (e.g. a swap search whose rejected candidates are never
revisited) should call `clear_cache()` at a natural boundary -- once per
restart, or once per slot for a tighter bound -- to keep peak memory near
a single slot's working set rather than the whole run's.
"""

from __future__ import annotations

import itertools
import math
from fractions import Fraction
from functools import cache

Ticket = tuple[int, ...]


def ticket_qualifying_draws(
    pool_size: int, draw_size: int, minimum_matches: int, ticket: Ticket
) -> frozenset[Ticket]:
    """All draws (`draw_size`-subsets of `1..pool_size`) sharing
    `>= minimum_matches` numbers with `ticket`, as ascending-sorted tuples.

    Cached by `(pool_size, draw_size, minimum_matches, canonical ticket)`;
    `ticket` may be given in any order, matching
    `exact_portfolio_coverage`'s own order-independence (it only ever reads
    tickets through a bitmask).
    """

    return _cached_ticket_qualifying_draws(
        pool_size, draw_size, minimum_matches, tuple(sorted(ticket))
    )


@cache
def _cached_ticket_qualifying_draws(
    pool_size: int, draw_size: int, minimum_matches: int, ticket: Ticket
) -> frozenset[Ticket]:
    ticket_set = set(ticket)
    complement = [n for n in range(1, pool_size + 1) if n not in ticket_set]
    draws: set[Ticket] = set()
    # Lower-bounded at 0 (not just `minimum_matches`) so a non-positive
    # threshold degrades to "every draw qualifies" -- the same behavior
    # `exact_portfolio_coverage`'s `bit_count() >= minimum_matches` check
    # has for `minimum_matches <= 0` -- rather than passing a negative `r`
    # to `itertools.combinations`. `j` never exceeds `draw_size`, so
    # `draw_size - j` is always `>= 0`.
    for j in range(max(minimum_matches, 0), draw_size + 1):
        need_from_complement = draw_size - j
        if need_from_complement > len(complement):
            continue
        for combo_ticket in itertools.combinations(sorted(ticket_set), j):
            for combo_rest in itertools.combinations(complement, need_from_complement):
                draws.add(tuple(sorted(combo_ticket + combo_rest)))
    return frozenset(draws)


def portfolio_qualifying_draws(
    pool_size: int,
    draw_size: int,
    minimum_matches: int,
    portfolio: tuple[Ticket, ...],
    *,
    base: frozenset[Ticket] | None = None,
) -> frozenset[Ticket]:
    """Union of `ticket_qualifying_draws` over every ticket in `portfolio`,
    optionally seeded with an already-computed `base` union (e.g. from a
    fixed sub-portfolio) so the caller does not need to re-derive it.
    """

    covered: set[Ticket] = set(base) if base is not None else set()
    for ticket in portfolio:
        covered |= ticket_qualifying_draws(pool_size, draw_size, minimum_matches, ticket)
    return frozenset(covered)


def fast_exact_portfolio_coverage(
    pool_size: int,
    draw_size: int,
    minimum_matches: int,
    portfolio: tuple[Ticket, ...],
) -> Fraction:
    """Drop-in, exact-parity replacement for
    `bounded_coverage_optimizer.exact_portfolio_coverage`: identical
    signature, identical `Fraction` result, computed via direct
    combinatorial generation instead of complete winning-space enumeration.
    """

    total_draws = math.comb(pool_size, draw_size)
    covered = portfolio_qualifying_draws(pool_size, draw_size, minimum_matches, portfolio)
    return Fraction(len(covered), total_draws)


def coverage_with_base(
    pool_size: int,
    draw_size: int,
    minimum_matches: int,
    base_draws: frozenset[Ticket],
    candidate: Ticket,
) -> Fraction:
    """Exact coverage of `base_draws` (typically
    `portfolio_qualifying_draws` of a fixed sub-portfolio) plus one more
    `candidate` ticket, via inclusion-exclusion rather than rebuilding the
    full union. `len(base_draws)` is O(1) (frozenset caches its size), so
    per-call cost is bounded by `candidate`'s own qualifying-draw count,
    not by `len(base_draws)` -- this is what makes evaluating many swap
    candidates against one fixed sub-portfolio fast.
    """

    total_draws = math.comb(pool_size, draw_size)
    candidate_draws = ticket_qualifying_draws(pool_size, draw_size, minimum_matches, candidate)
    overlap = len(base_draws & candidate_draws)
    covered_size = len(base_draws) + len(candidate_draws) - overlap
    return Fraction(covered_size, total_draws)


def clear_cache() -> None:
    """Reset the per-ticket qualifying-draws cache.

    Benchmarking/testing only -- correctness never depends on cache state.
    """

    _cached_ticket_qualifying_draws.cache_clear()
