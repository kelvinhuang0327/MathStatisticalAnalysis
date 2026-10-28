from __future__ import annotations

import itertools
from fractions import Fraction

import pytest

from lottolab.research.b649_k235_tier_specific_portfolio_r1 import (
    BIG_LOTTO_DRAW_SIZE,
    BIG_LOTTO_POOL_SIZE,
    K235_TICKET_COUNTS,
    evaluate_expected_max_main_matches,
    expected_max_union_bound,
    expected_max_union_bound_details,
    optimize_expected_max_local,
    portfolio_cost_ntd,
    zero_overlap_incumbent,
)


def _brute_score(
    pool_size: int,
    draw_size: int,
    portfolio: tuple[tuple[int, ...], ...],
) -> tuple[int, tuple[int, ...], int]:
    maximum_match_sum = 0
    threshold_draw_counts = [0] * draw_size
    draw_count = 0
    for draw in itertools.combinations(range(1, pool_size + 1), draw_size):
        draw_count += 1
        maximum_hits = max(len(set(draw).intersection(ticket)) for ticket in portfolio)
        maximum_match_sum += maximum_hits
        for threshold in range(1, draw_size + 1):
            if maximum_hits >= threshold:
                threshold_draw_counts[threshold - 1] += 1
    return maximum_match_sum, tuple(threshold_draw_counts), draw_count


@pytest.mark.parametrize(
    "portfolio",
    [
        ((1, 2, 3), (3, 4, 5)),
        ((1, 2, 3), (4, 5, 6), (1, 7, 8)),
        ((1, 2, 3), (4, 5, 6), (7, 8, 9)),
    ],
)
def test_incidence_dp_matches_complete_small_universe_enumeration(portfolio) -> None:
    expected_sum, expected_tails, draw_count = _brute_score(9, 3, portfolio)

    actual = evaluate_expected_max_main_matches(9, 3, portfolio)

    assert actual.draw_count == draw_count
    assert actual.maximum_match_sum == expected_sum
    assert actual.threshold_draw_counts == expected_tails
    assert actual.expected_maximum == Fraction(expected_sum, draw_count)
    assert sum(actual.threshold_draw_counts) == actual.maximum_match_sum


@pytest.mark.parametrize("ticket_count", K235_TICKET_COUNTS)
def test_k235_zero_overlap_incumbents_have_fixed_lines_and_cost(ticket_count: int) -> None:
    portfolio = zero_overlap_incumbent(ticket_count)

    assert len(portfolio) == ticket_count
    assert all(len(ticket) == BIG_LOTTO_DRAW_SIZE for ticket in portfolio)
    assert len({number for ticket in portfolio for number in ticket}) == 6 * ticket_count
    assert all(1 <= number <= BIG_LOTTO_POOL_SIZE for ticket in portfolio for number in ticket)
    assert portfolio_cost_ntd(ticket_count) == 50 * ticket_count


@pytest.mark.parametrize("ticket_count", K235_TICKET_COUNTS)
def test_all_zero_overlap_portfolios_have_same_exact_score(ticket_count: int) -> None:
    first = zero_overlap_incumbent(ticket_count)
    shifted = tuple(
        tuple(range(start, start + BIG_LOTTO_DRAW_SIZE))
        for start in range(20, 20 + 6 * ticket_count, 6)
    )

    assert evaluate_expected_max_main_matches(49, 6, first) == (
        evaluate_expected_max_main_matches(49, 6, shifted)
    )


def test_b649_49_choose_6_denominator_and_union_bound() -> None:
    portfolio = zero_overlap_incumbent(2)

    score = evaluate_expected_max_main_matches(49, 6, portfolio)

    assert score.draw_count == 13_983_816
    assert score.expected_maximum <= expected_max_union_bound(49, 6, 2)


@pytest.mark.parametrize(
    "ticket",
    [
        (1, 2, 3, 4, 5, 5),
        (0, 2, 3, 4, 5, 6),
        (1, 2, 3, 4, 5, 50),
        (True, 2, 3, 4, 5, 6),
        (1, 2, 3, 4, 5),
    ],
)
def test_scorer_rejects_illegal_49_choose_6_ticket(ticket) -> None:
    with pytest.raises(ValueError):
        evaluate_expected_max_main_matches(49, 6, (ticket,))


def test_union_bound_exposes_checkable_exact_tail_counts() -> None:
    details = expected_max_union_bound_details(8, 3, 2)

    assert details.draw_count == 56
    assert len(details.single_ticket_tail_draw_counts) == 3
    assert len(details.portfolio_tail_upper_bound_draw_counts) == 3
    assert details.maximum_match_sum_upper_bound == sum(
        details.portfolio_tail_upper_bound_draw_counts
    )
    assert expected_max_union_bound(8, 3, 2) == Fraction(
        details.maximum_match_sum_upper_bound, details.draw_count
    )


def test_local_search_is_seeded_legal_and_never_lowers_start_score() -> None:
    start = ((1, 2, 3), (4, 5, 6))

    first = optimize_expected_max_local(
        start,
        pool_size=9,
        draw_size=3,
        seed=29,
        candidate_samples_per_ticket=5,
        max_passes=2,
    )
    second = optimize_expected_max_local(
        start,
        pool_size=9,
        draw_size=3,
        seed=29,
        candidate_samples_per_ticket=5,
        max_passes=2,
    )

    assert first == second
    assert first.score.maximum_match_sum >= first.start_score.maximum_match_sum
    assert len(first.portfolio) == 2
    assert len(set(first.portfolio)) == 2
    assert all(len(ticket) == 3 and len(set(ticket)) == 3 for ticket in first.portfolio)
    assert all(1 <= number <= 9 for ticket in first.portfolio for number in ticket)
    assert first.evaluations > 0


def test_local_search_rejects_non_k235_portfolio() -> None:
    with pytest.raises(ValueError, match="supports K"):
        optimize_expected_max_local(
            ((1, 2, 3),),
            pool_size=9,
            draw_size=3,
            seed=1,
            candidate_samples_per_ticket=1,
            max_passes=1,
        )
