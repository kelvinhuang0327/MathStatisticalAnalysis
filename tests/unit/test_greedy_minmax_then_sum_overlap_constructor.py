from __future__ import annotations

import itertools

import pytest

from lottolab.research.greedy_min_overlap_constructor import greedy_min_overlap_portfolio
from lottolab.research.greedy_minmax_then_sum_overlap_constructor import (
    greedy_minmax_then_sum_overlap_portfolio,
    incremental_pairwise_collision_key,
    pairwise_overlap,
)


def _max_sum_overlap(portfolio: tuple[tuple[int, ...], ...]) -> tuple[int, int]:
    pairs = list(itertools.combinations(portfolio, 2))
    if not pairs:
        return (0, 0)
    overlaps = [pairwise_overlap(left, right) for left, right in pairs]
    return (max(overlaps), sum(overlaps))


def test_first_ticket_is_lexicographically_first_subset() -> None:
    portfolio = greedy_minmax_then_sum_overlap_portfolio(pool_size=10, draw_size=3, ticket_count=1)
    assert portfolio == ((1, 2, 3),)


def test_disjoint_phase_matches_arm_b_sequential_blocks() -> None:
    candidate = greedy_minmax_then_sum_overlap_portfolio(pool_size=10, draw_size=3, ticket_count=3)
    arm_b = greedy_min_overlap_portfolio(pool_size=10, draw_size=3, ticket_count=3)
    assert candidate == ((1, 2, 3), (4, 5, 6), (7, 8, 9))
    assert candidate == arm_b


def test_first_forced_overlap_ticket_differs_from_arm_b() -> None:
    # After three disjoint triples the leftover number is 10.  Arm-B keeps
    # the lexicographically first max-overlap-1 transversal (1, 4, 7) and
    # never spends the leftover.  The candidate key prefers any ticket that
    # intersects only two existing blocks, and the lex-smallest such ticket
    # is (1, 4, 10).
    candidate = greedy_minmax_then_sum_overlap_portfolio(pool_size=10, draw_size=3, ticket_count=4)
    arm_b = greedy_min_overlap_portfolio(pool_size=10, draw_size=3, ticket_count=4)
    assert arm_b[3] == (1, 4, 7)
    assert candidate[3] == (1, 4, 10)
    assert candidate != arm_b
    assert candidate[:3] == arm_b[:3]


def test_candidate_uses_leftover_number_that_arm_b_skips() -> None:
    candidate = greedy_minmax_then_sum_overlap_portfolio(pool_size=10, draw_size=3, ticket_count=4)
    arm_b = greedy_min_overlap_portfolio(pool_size=10, draw_size=3, ticket_count=4)
    assert 10 in candidate[3]
    assert 10 not in {number for ticket in arm_b for number in ticket}


def test_candidate_has_strictly_smaller_pairwise_collision_count() -> None:
    candidate = greedy_minmax_then_sum_overlap_portfolio(pool_size=10, draw_size=3, ticket_count=4)
    arm_b = greedy_min_overlap_portfolio(pool_size=10, draw_size=3, ticket_count=4)
    candidate_max, candidate_sum = _max_sum_overlap(candidate)
    arm_b_max, arm_b_sum = _max_sum_overlap(arm_b)
    assert candidate_max == arm_b_max == 1
    assert candidate_sum == 2
    assert arm_b_sum == 3
    assert candidate_sum < arm_b_sum


def test_worse_max_overlap_cannot_beat_better_sum() -> None:
    # A ticket that hits one existing ticket twice has sum 2, the same
    # collision count as (1, 4, 10), but a worse max.  The frozen lex key
    # must reject it.
    portfolio = ((1, 2, 3), (4, 5, 6), (7, 8, 9))
    better = incremental_pairwise_collision_key((1, 4, 10), portfolio)
    worse_max = incremental_pairwise_collision_key((1, 2, 10), portfolio)
    assert better[0] == 1 and better[1] == 2
    assert worse_max[0] == 2 and worse_max[1] == 2
    assert better < worse_max


def test_no_duplicate_tickets() -> None:
    portfolio = greedy_minmax_then_sum_overlap_portfolio(pool_size=10, draw_size=3, ticket_count=10)
    assert len(set(portfolio)) == len(portfolio)


def test_every_ticket_has_draw_size_distinct_in_range_numbers() -> None:
    portfolio = greedy_minmax_then_sum_overlap_portfolio(pool_size=10, draw_size=3, ticket_count=6)
    for ticket in portfolio:
        assert len(ticket) == 3
        assert len(set(ticket)) == 3
        assert all(1 <= number <= 10 for number in ticket)


def test_portfolio_is_a_strict_nested_prefix() -> None:
    portfolio_8 = greedy_minmax_then_sum_overlap_portfolio(
        pool_size=10, draw_size=3, ticket_count=8
    )
    for ticket_count in (1, 3, 4, 6):
        assert (
            greedy_minmax_then_sum_overlap_portfolio(
                pool_size=10, draw_size=3, ticket_count=ticket_count
            )
            == portfolio_8[:ticket_count]
        )


def test_portfolio_of_zero_is_empty() -> None:
    assert greedy_minmax_then_sum_overlap_portfolio(pool_size=10, draw_size=3, ticket_count=0) == ()


def test_deterministic_across_repeated_calls() -> None:
    first = greedy_minmax_then_sum_overlap_portfolio(pool_size=10, draw_size=3, ticket_count=6)
    second = greedy_minmax_then_sum_overlap_portfolio(pool_size=10, draw_size=3, ticket_count=6)
    assert first == second


def test_rejects_pool_smaller_than_draw_size() -> None:
    with pytest.raises(ValueError, match="pool_size must be >= draw_size"):
        greedy_minmax_then_sum_overlap_portfolio(pool_size=2, draw_size=3, ticket_count=1)


def test_rejects_out_of_range_ticket_count() -> None:
    with pytest.raises(ValueError, match="ticket_count must lie in"):
        greedy_minmax_then_sum_overlap_portfolio(pool_size=10, draw_size=3, ticket_count=121)
    with pytest.raises(ValueError, match="ticket_count must lie in"):
        greedy_minmax_then_sum_overlap_portfolio(pool_size=10, draw_size=3, ticket_count=-1)


def test_generalizes_to_a_second_toy_pool_shape() -> None:
    portfolio = greedy_minmax_then_sum_overlap_portfolio(pool_size=8, draw_size=2, ticket_count=5)
    arm_b = greedy_min_overlap_portfolio(pool_size=8, draw_size=2, ticket_count=5)
    assert portfolio[:4] == ((1, 2), (3, 4), (5, 6), (7, 8))
    assert portfolio[:4] == arm_b[:4]
    # After the disjoint matching, Arm-B takes the lex-first 1-overlap pair
    # (1, 3).  The candidate prefers a pair that reuses the fewest existing
    # tickets; with every number already used once, every remaining pair has
    # sum 2, so lex still yields (1, 3) and the constructors agree again.
    assert portfolio[4] == (1, 3)
    assert portfolio == arm_b


def test_b649_shaped_toy_prefers_leftover_over_full_transversal() -> None:
    # Same disjoint-then-leftover geometry as B649 (n = q*d + 1) at a toy
    # scale: 2 blocks of size 3 plus leftover 7.
    candidate = greedy_minmax_then_sum_overlap_portfolio(pool_size=7, draw_size=3, ticket_count=3)
    arm_b = greedy_min_overlap_portfolio(pool_size=7, draw_size=3, ticket_count=3)
    assert candidate[:2] == arm_b[:2] == ((1, 2, 3), (4, 5, 6))
    assert 7 in candidate[2]
    # Here the leftover is small enough that Arm-B's lex-first max-1 ticket
    # already spends it, so the constructors agree.  The pool=10 case above
    # is the one that separates them.
    assert candidate == arm_b
