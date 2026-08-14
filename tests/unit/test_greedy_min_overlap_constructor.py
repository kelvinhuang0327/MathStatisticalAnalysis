from __future__ import annotations

import pytest

from lottolab.research.greedy_min_overlap_constructor import greedy_min_overlap_portfolio


def test_first_ticket_is_lexicographically_first_subset() -> None:
    portfolio = greedy_min_overlap_portfolio(pool_size=10, draw_size=3, ticket_count=1)
    assert portfolio == ((1, 2, 3),)


def test_every_ticket_has_draw_size_distinct_in_range_numbers() -> None:
    portfolio = greedy_min_overlap_portfolio(pool_size=10, draw_size=3, ticket_count=6)
    for ticket in portfolio:
        assert len(ticket) == 3
        assert len(set(ticket)) == 3
        assert all(1 <= n <= 10 for n in ticket)


def test_no_duplicate_tickets() -> None:
    portfolio = greedy_min_overlap_portfolio(pool_size=10, draw_size=3, ticket_count=10)
    assert len(set(portfolio)) == len(portfolio)


def test_disjoint_capacity_tickets_have_zero_overlap() -> None:
    # pool_size // draw_size = 3 fully disjoint blocks fit before any
    # candidate is forced to reuse a number -- the general min-max-overlap
    # rule should find them (not because disjointness is special-cased).
    portfolio = greedy_min_overlap_portfolio(pool_size=10, draw_size=3, ticket_count=3)
    for i in range(len(portfolio)):
        for j in range(i + 1, len(portfolio)):
            assert len(set(portfolio[i]) & set(portfolio[j])) == 0


def test_disjoint_capacity_tickets_are_sequential_blocks() -> None:
    portfolio = greedy_min_overlap_portfolio(pool_size=10, draw_size=3, ticket_count=3)
    assert portfolio == ((1, 2, 3), (4, 5, 6), (7, 8, 9))


def test_beyond_disjoint_capacity_overlap_stays_bounded() -> None:
    # Only 1 number (10) remains unused after 3 disjoint blocks -- ticket 4
    # is forced to reuse, but the rule should still minimize the worst
    # overlap against every earlier ticket, not just avoid ticket 3.
    portfolio = greedy_min_overlap_portfolio(pool_size=10, draw_size=3, ticket_count=4)
    fourth = set(portfolio[3])
    max_overlap = max(len(fourth & set(earlier)) for earlier in portfolio[:3])
    assert max_overlap <= 1


def test_portfolio_is_a_strict_nested_prefix() -> None:
    portfolio_8 = greedy_min_overlap_portfolio(pool_size=10, draw_size=3, ticket_count=8)
    for k in (1, 3, 4, 6):
        assert greedy_min_overlap_portfolio(pool_size=10, draw_size=3, ticket_count=k) == (
            portfolio_8[:k]
        )


def test_portfolio_of_zero_is_empty() -> None:
    assert greedy_min_overlap_portfolio(pool_size=10, draw_size=3, ticket_count=0) == ()


def test_deterministic_across_repeated_calls() -> None:
    first = greedy_min_overlap_portfolio(pool_size=10, draw_size=3, ticket_count=6)
    second = greedy_min_overlap_portfolio(pool_size=10, draw_size=3, ticket_count=6)
    assert first == second


def test_rejects_pool_smaller_than_draw_size() -> None:
    with pytest.raises(ValueError, match="pool_size must be >= draw_size"):
        greedy_min_overlap_portfolio(pool_size=2, draw_size=3, ticket_count=1)


def test_rejects_out_of_range_ticket_count() -> None:
    with pytest.raises(ValueError, match="ticket_count must lie in"):
        greedy_min_overlap_portfolio(pool_size=10, draw_size=3, ticket_count=121)
    with pytest.raises(ValueError, match="ticket_count must lie in"):
        greedy_min_overlap_portfolio(pool_size=10, draw_size=3, ticket_count=-1)


def test_generalizes_to_a_second_toy_pool_shape() -> None:
    # A different (pool_size, draw_size) with no code change -- confirms
    # nothing here is tuned to one specific pool size.
    portfolio = greedy_min_overlap_portfolio(pool_size=6, draw_size=2, ticket_count=3)
    assert portfolio == ((1, 2), (3, 4), (5, 6))
