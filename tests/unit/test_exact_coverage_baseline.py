from __future__ import annotations

import itertools
import math
from fractions import Fraction

import pytest

from lottolab.research.exact_coverage_baseline import (
    exact_random_portfolio_coverage,
    qualifying_ticket_count,
)


def test_qualifying_ticket_count_at_zero_matches_is_every_ticket() -> None:
    assert qualifying_ticket_count(49, 6, 0) == math.comb(49, 6)


def test_qualifying_ticket_count_rejects_out_of_range() -> None:
    with pytest.raises(ValueError, match="minimum_matches"):
        qualifying_ticket_count(49, 6, 7)
    with pytest.raises(ValueError, match="minimum_matches"):
        qualifying_ticket_count(49, 6, -1)


def _brute_force_qualifying_count(pool_size: int, draw_size: int, minimum_matches: int) -> int:
    universe = list(itertools.combinations(range(1, pool_size + 1), draw_size))
    winning = set(universe[0])
    return sum(1 for ticket in universe if len(set(ticket) & winning) >= minimum_matches)


def _brute_force_coverage(
    pool_size: int, draw_size: int, minimum_matches: int, ticket_count: int
) -> Fraction:
    universe = list(itertools.combinations(range(1, pool_size + 1), draw_size))
    winning = set(universe[0])
    total = math.comb(pool_size, draw_size)
    qualifying = sum(1 for ticket in universe if len(set(ticket) & winning) >= minimum_matches)
    non_qualifying = total - qualifying
    if ticket_count > non_qualifying:
        return Fraction(1)
    return 1 - Fraction(
        math.comb(non_qualifying, ticket_count), math.comb(total, ticket_count)
    )


@pytest.mark.parametrize("minimum_matches", [0, 1, 2, 3])
def test_qualifying_ticket_count_matches_brute_force_on_a_toy_pool(minimum_matches: int) -> None:
    # pool=9, draw=3 (C(9,3)=84) is small enough to fully enumerate directly,
    # while sharing the exact same combinatorial structure as the real 49/6
    # problem -- this is the same cross-check used to verify the formula
    # before it was trusted for the real pool size.
    assert qualifying_ticket_count(9, 3, minimum_matches) == _brute_force_qualifying_count(
        9, 3, minimum_matches
    )


@pytest.mark.parametrize("k", [0, 1, 2, 3, 5, 10])
def test_exact_coverage_matches_brute_force_on_a_toy_pool(k: int) -> None:
    assert exact_random_portfolio_coverage(9, 3, 2, k) == _brute_force_coverage(9, 3, 2, k)


def test_exact_coverage_at_k_one_equals_marginal_hit_probability() -> None:
    # P(a single random ticket has >= m matches) = K(m) / N, exactly.
    pool_size, draw_size, m = 49, 6, 3
    total = math.comb(pool_size, draw_size)
    expected = Fraction(qualifying_ticket_count(pool_size, draw_size, m), total)
    assert exact_random_portfolio_coverage(pool_size, draw_size, m, 1) == expected


def test_exact_coverage_is_monotonically_nondecreasing_in_k() -> None:
    values = [exact_random_portfolio_coverage(49, 6, 3, k) for k in range(0, 21)]
    assert all(values[i] <= values[i + 1] for i in range(len(values) - 1))


def test_exact_coverage_at_k_one_equals_marginal_hit_probability_for_power_lotto_zone1() -> None:
    # Same identity as the B649 (49,6) case above, confirmed to generalize
    # with no code changes to (pool=38, draw=6) -- POWER_LOTTO Zone-1's own
    # shape, needed before the Sidon-shift diversification design for P638
    # can reuse this module verbatim.
    pool_size, draw_size, m = 38, 6, 3
    total = math.comb(pool_size, draw_size)
    expected = Fraction(qualifying_ticket_count(pool_size, draw_size, m), total)
    assert exact_random_portfolio_coverage(pool_size, draw_size, m, 1) == expected


def test_exact_coverage_is_monotonically_nondecreasing_in_k_for_power_lotto_zone1() -> None:
    values = [exact_random_portfolio_coverage(38, 6, 3, k) for k in range(0, 21)]
    assert all(values[i] <= values[i + 1] for i in range(len(values) - 1))


def test_exact_coverage_at_k_zero_is_zero() -> None:
    assert exact_random_portfolio_coverage(49, 6, 3, 0) == Fraction(0)


def test_exact_coverage_reaches_one_when_k_covers_all_qualifying_complement() -> None:
    # If k exceeds the number of non-qualifying tickets, at least one
    # qualifying ticket is guaranteed among any k distinct tickets.
    pool_size, draw_size, m = 9, 3, 3  # exact match only: very few qualify
    total = math.comb(pool_size, draw_size)
    qualifying = qualifying_ticket_count(pool_size, draw_size, m)
    non_qualifying = total - qualifying
    result = exact_random_portfolio_coverage(pool_size, draw_size, m, non_qualifying + 1)
    assert result == Fraction(1)


def test_exact_coverage_rejects_negative_ticket_count() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        exact_random_portfolio_coverage(49, 6, 3, -1)


def test_exact_coverage_rejects_ticket_count_exceeding_total() -> None:
    with pytest.raises(ValueError, match="cannot exceed"):
        exact_random_portfolio_coverage(9, 3, 0, 1000)
