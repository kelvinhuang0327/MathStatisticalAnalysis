from __future__ import annotations

import random
from fractions import Fraction

from lottolab.research.bounded_coverage_optimizer import exact_portfolio_coverage
from lottolab.research.cyclic_sidon_shift import sidon_shift_portfolio
from lottolab.research.exact_coverage_baseline import qualifying_ticket_count
from lottolab.research.exact_coverage_fast_evaluator import (
    clear_cache,
    coverage_with_base,
    fast_exact_portfolio_coverage,
    portfolio_qualifying_draws,
    ticket_qualifying_draws,
)

_B649_POOL = 49
_B649_DRAW = 6

# Deterministic hand-computed case, same fixture convention as
# test_bounded_coverage_optimizer.py's own test.


def test_matches_hand_enumeration_for_one_ticket() -> None:
    # {1,2,3} needs >= 2 of its 3 numbers. K(2) = C(3,2)*C(7,1) + C(3,3)*C(7,0)
    # = 3*7 + 1*1 = 22, out of C(10,3) = 120.
    coverage = fast_exact_portfolio_coverage(10, 3, 2, ((1, 2, 3),))
    assert coverage == Fraction(22, 120)


def test_empty_portfolio_is_zero_coverage() -> None:
    assert fast_exact_portfolio_coverage(10, 3, 2, ()) == Fraction(0, 1)


def test_ticket_order_is_irrelevant() -> None:
    a = fast_exact_portfolio_coverage(10, 3, 2, ((1, 2, 3),))
    b = fast_exact_portfolio_coverage(10, 3, 2, ((3, 1, 2),))
    assert a == b


def test_coverage_is_monotonic_in_portfolio_size() -> None:
    one_ticket = fast_exact_portfolio_coverage(10, 3, 2, ((1, 2, 3),))
    two_tickets = fast_exact_portfolio_coverage(10, 3, 2, ((1, 2, 3), (4, 5, 6)))
    assert two_tickets >= one_ticket


def test_ticket_qualifying_draws_matches_independent_baseline_formula() -> None:
    # qualifying_ticket_count (exact_coverage_baseline.py) counts the same
    # thing via a closed-form combinatorial sum, not enumeration -- an
    # independent cross-check that the generation partitions the winning
    # space correctly (no double-count, no gap) across the full m range.
    ticket = (1, 2, 3, 4, 5)
    pool_size, draw_size = 12, 5
    for minimum_matches in range(0, draw_size + 1):
        draws = ticket_qualifying_draws(pool_size, draw_size, minimum_matches, ticket)
        assert len(draws) == qualifying_ticket_count(pool_size, draw_size, minimum_matches)


# Randomized small-scale parity against the canonical evaluator
# (bounded_coverage_optimizer.exact_portfolio_coverage), the correctness
# authority per the Packet.


def test_randomized_small_scale_parity_against_canonical_evaluator() -> None:
    rng = random.Random(20260815)
    checked = 0
    for _ in range(200):
        pool_size = rng.randint(6, 14)
        draw_size = rng.randint(2, 4)
        if draw_size > pool_size:
            continue
        minimum_matches = rng.randint(0, draw_size)
        ticket_count = rng.randint(0, 5)
        portfolio: list[tuple[int, ...]] = []
        seen: set[tuple[int, ...]] = set()
        attempts = 0
        while len(portfolio) < ticket_count and attempts < 50:
            attempts += 1
            candidate = tuple(sorted(rng.sample(range(1, pool_size + 1), draw_size)))
            if candidate in seen:
                continue
            seen.add(candidate)
            portfolio.append(candidate)
        expected = exact_portfolio_coverage(
            pool_size, draw_size, minimum_matches, tuple(portfolio)
        )
        actual = fast_exact_portfolio_coverage(
            pool_size, draw_size, minimum_matches, tuple(portfolio)
        )
        assert actual == expected, (pool_size, draw_size, minimum_matches, portfolio)
        checked += 1
    assert checked > 150  # the draw_size > pool_size skip should be rare


# B649-native (49, 6) parity. The canonical evaluator re-enumerates all
# 13,983,816 draws per call here, so this is deliberately a small,
# representative set of checks, not exhaustive across the full k ladder --
# see the (uncommitted) benchmark referenced in the task report for the
# full k={1,3,5,10,15,20} x m=3 comparison.


def test_b649_native_parity_across_m3_m4_m5_m6_at_k1() -> None:
    portfolio = sidon_shift_portfolio(1)
    for minimum_matches in (3, 4, 5, 6):
        expected = exact_portfolio_coverage(_B649_POOL, _B649_DRAW, minimum_matches, portfolio)
        actual = fast_exact_portfolio_coverage(_B649_POOL, _B649_DRAW, minimum_matches, portfolio)
        assert actual == expected, minimum_matches


def test_b649_native_parity_primary_event_at_k3() -> None:
    portfolio = sidon_shift_portfolio(3)
    expected = exact_portfolio_coverage(_B649_POOL, _B649_DRAW, 3, portfolio)
    actual = fast_exact_portfolio_coverage(_B649_POOL, _B649_DRAW, 3, portfolio)
    assert actual == expected


# Incremental swap-candidate pattern (coverage_with_base): the design this
# module adds specifically for RESTART_GREEDY_SWAP_COVERAGE_SEARCH_B649_V1's
# call pattern (fixed sub-portfolio + one varying ticket). Must match both
# the flat fast evaluator and the canonical evaluator on the same trial
# portfolio.


def test_coverage_with_base_matches_flat_and_canonical_small_scale() -> None:
    rng = random.Random(9)
    pool_size, draw_size, minimum_matches = 12, 4, 2
    fixed: list[tuple[int, ...]] = []
    seen: set[tuple[int, ...]] = set()
    while len(fixed) < 4:
        candidate = tuple(sorted(rng.sample(range(1, pool_size + 1), draw_size)))
        if candidate in seen:
            continue
        seen.add(candidate)
        fixed.append(candidate)
    base = portfolio_qualifying_draws(pool_size, draw_size, minimum_matches, tuple(fixed))
    checked = 0
    while checked < 20:
        candidate = tuple(sorted(rng.sample(range(1, pool_size + 1), draw_size)))
        if candidate in seen:
            continue
        seen.add(candidate)
        via_base = coverage_with_base(pool_size, draw_size, minimum_matches, base, candidate)
        trial = (*fixed, candidate)
        via_flat = fast_exact_portfolio_coverage(pool_size, draw_size, minimum_matches, trial)
        via_canonical = exact_portfolio_coverage(pool_size, draw_size, minimum_matches, trial)
        assert via_base == via_flat == via_canonical
        checked += 1


def test_coverage_with_base_matches_canonical_evaluator_b649_native() -> None:
    portfolio = sidon_shift_portfolio(5)
    fixed, candidate = portfolio[:4], portfolio[4]
    base = portfolio_qualifying_draws(_B649_POOL, _B649_DRAW, 3, fixed)
    via_base = coverage_with_base(_B649_POOL, _B649_DRAW, 3, base, candidate)
    via_canonical = exact_portfolio_coverage(_B649_POOL, _B649_DRAW, 3, portfolio)
    assert via_base == via_canonical


# Cache correctness: results must not depend on cache state.


def test_clear_cache_does_not_change_results() -> None:
    portfolio = sidon_shift_portfolio(2)
    before = fast_exact_portfolio_coverage(_B649_POOL, _B649_DRAW, 4, portfolio)
    clear_cache()
    after = fast_exact_portfolio_coverage(_B649_POOL, _B649_DRAW, 4, portfolio)
    assert before == after
