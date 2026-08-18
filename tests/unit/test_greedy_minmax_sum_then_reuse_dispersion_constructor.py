from __future__ import annotations

import itertools
import math

import pytest

from lottolab.research.greedy_min_overlap_constructor import greedy_min_overlap_portfolio
from lottolab.research.greedy_minmax_sum_then_reuse_dispersion_constructor import (
    Ticket,
    greedy_minmax_sum_then_reuse_dispersion_portfolio,
    incremental_reuse_dispersion_key,
    pairwise_overlap,
    peak_reuse_after,
    sum_c3_reuse_after,
)
from lottolab.research.greedy_minmax_then_sum_overlap_constructor import (
    greedy_minmax_then_sum_overlap_portfolio,
)


def _reuse_vector(portfolio: tuple[tuple[int, ...], ...], pool_size: int) -> list[int]:
    reuse = [0] * pool_size
    for ticket in portfolio:
        for number in ticket:
            reuse[number - 1] += 1
    return reuse


def _max_sum_overlap(portfolio: tuple[tuple[int, ...], ...]) -> tuple[int, int]:
    pairs = list(itertools.combinations(portfolio, 2))
    if not pairs:
        return (0, 0)
    overlaps = [pairwise_overlap(left, right) for left, right in pairs]
    return (max(overlaps), sum(overlaps))


# --- Structural agreement with Reference E (shared coordinates 1-2 and ticket 0) ---


def test_first_ticket_is_lexicographically_first_subset() -> None:
    portfolio = greedy_minmax_sum_then_reuse_dispersion_portfolio(
        pool_size=10, draw_size=3, ticket_count=1
    )
    assert portfolio == ((1, 2, 3),)


def test_disjoint_phase_matches_reference_e_and_arm_b_sequential_blocks() -> None:
    candidate = greedy_minmax_sum_then_reuse_dispersion_portfolio(
        pool_size=10, draw_size=3, ticket_count=3
    )
    reference_e = greedy_minmax_then_sum_overlap_portfolio(
        pool_size=10, draw_size=3, ticket_count=3
    )
    arm_b = greedy_min_overlap_portfolio(pool_size=10, draw_size=3, ticket_count=3)
    assert candidate == ((1, 2, 3), (4, 5, 6), (7, 8, 9))
    assert candidate == reference_e == arm_b


def test_disjoint_phase_agrees_with_reference_e_at_b649_shaped_toy_scale() -> None:
    # Same disjoint-then-leftover shape as B649 (n = q*d + 1): floor(49/6) = 8
    # full blocks plus one leftover number. At the matching toy scale
    # (pool=13, draw=2 -> floor(13/2)=6 blocks plus leftover 13), every
    # candidate that stays fully disjoint from the existing portfolio ties
    # on all four non-final key coordinates (see the module docstring's
    # early-exit argument), so Candidate F must reproduce Reference E's
    # entire disjoint prefix exactly. One ticket past disjoint capacity,
    # every legal candidate must now spend the leftover number 13 paired
    # with some already-used (and uniformly reuse=1) number, so every such
    # candidate also ties on both reuse coordinates -- Candidate F still
    # agrees with Reference E at this first forced-overlap ticket.
    candidate = greedy_minmax_sum_then_reuse_dispersion_portfolio(
        pool_size=13, draw_size=2, ticket_count=7
    )
    reference_e = greedy_minmax_then_sum_overlap_portfolio(
        pool_size=13, draw_size=2, ticket_count=7
    )
    assert candidate == reference_e
    assert candidate == (
        (1, 2),
        (3, 4),
        (5, 6),
        (7, 8),
        (9, 10),
        (11, 12),
        (1, 13),
    )


# --- Direct key-function tests: reuse coordinates only discriminate among E's own ties ---


def test_worse_max_or_sum_cannot_be_overridden_by_reuse_coordinates() -> None:
    # A ticket with a worse max (or worse sum, at equal max) must lose even
    # if it has a strictly better (lower) peak reuse and sum_c3.
    portfolio = ((1, 2, 3), (4, 5, 6), (7, 8, 9))
    reuse = _reuse_vector(portfolio, pool_size=10)
    better_max = incremental_reuse_dispersion_key((1, 4, 10), portfolio, reuse, current_sum_c3=0)
    worse_max = incremental_reuse_dispersion_key((1, 2, 10), portfolio, reuse, current_sum_c3=0)
    assert better_max[0] == 1 and worse_max[0] == 2
    assert better_max < worse_max


def test_peak_reuse_coordinate_decides_among_max_sum_tied_candidates() -> None:
    # Verified by direct computation (not merely asserted): two candidates
    # tied on (max, sum) = (1, 2) against this portfolio, where the
    # lexicographically smaller ticket (Reference E's pick) touches the
    # portfolio's only reuse=2 number and so raises peak reuse to 3, while
    # the lexicographically larger ticket touches two reuse=1 numbers and
    # keeps peak reuse at 2.
    portfolio = ((1, 2, 3), (1, 4, 5))
    pool_size = 7
    reuse = _reuse_vector(portfolio, pool_size)
    reference_e_pick: Ticket = (1, 6, 7)
    candidate_f_pick: Ticket = (2, 4, 6)
    key_reference_e_pick = incremental_reuse_dispersion_key(
        reference_e_pick, portfolio, reuse, current_sum_c3=0
    )
    key_candidate_f_pick = incremental_reuse_dispersion_key(
        candidate_f_pick, portfolio, reuse, current_sum_c3=0
    )
    assert key_reference_e_pick[:2] == key_candidate_f_pick[:2] == (1, 2)  # (max, sum) tie
    assert peak_reuse_after(reference_e_pick, reuse) == 3
    assert peak_reuse_after(candidate_f_pick, reuse) == 2
    assert key_candidate_f_pick < key_reference_e_pick
    assert min(key_reference_e_pick, key_candidate_f_pick)[4] == candidate_f_pick
    # Lexicographically (E's own tiebreak) reference_e_pick would instead win:
    # (1, 6, 7) < (2, 4, 6).


def test_sum_c3_coordinate_decides_when_peak_reuse_also_ties() -> None:
    # Verified by direct computation. A dominant number (20) reused 5 times
    # by tickets untouched by either candidate pins the portfolio-wide peak
    # at 5 regardless of which candidate is appended, so (max, sum, peak)
    # all tie at (1, 2, 5). The lexicographically smaller candidate (1, 118,
    # 119) touches the one reuse=2 number (1), raising SUM_i C(reuse_i, 3)
    # to 11; the lexicographically larger candidate (2, 3, 118) instead
    # touches two separate reuse=1 numbers (2 and 3), leaving it at 10.
    dominant = tuple((20, 100 + 2 * i, 100 + 2 * i + 1) for i in range(5))
    extra = ((1, 110, 111), (1, 112, 113), (2, 114, 115), (3, 116, 117))
    portfolio = dominant + extra
    pool_size = 120
    reuse = _reuse_vector(portfolio, pool_size)
    current_sum_c3 = sum(math.comb(count, 3) for count in reuse)
    assert current_sum_c3 == 10

    reference_e_pick: Ticket = (1, 118, 119)
    candidate_f_pick: Ticket = (2, 3, 118)
    key_reference_e_pick = incremental_reuse_dispersion_key(
        reference_e_pick, portfolio, reuse, current_sum_c3
    )
    key_candidate_f_pick = incremental_reuse_dispersion_key(
        candidate_f_pick, portfolio, reuse, current_sum_c3
    )
    assert key_reference_e_pick[:3] == key_candidate_f_pick[:3] == (1, 2, 5)  # (max, sum, peak) tie
    assert sum_c3_reuse_after(reference_e_pick, reuse, current_sum_c3) == 11
    assert sum_c3_reuse_after(candidate_f_pick, reuse, current_sum_c3) == 10
    assert key_candidate_f_pick < key_reference_e_pick
    # Lexicographically (E's own tiebreak) reference_e_pick would instead win:
    # (1, 118, 119) < (2, 3, 118).


def test_peak_reuse_after_is_the_larger_of_current_peak_and_candidates_own_bump() -> None:
    reuse = [2, 1, 1, 0]
    assert peak_reuse_after((1, 2), reuse) == 3  # number 1: 2 -> 3
    assert peak_reuse_after((2, 3), reuse) == 2  # numbers 2,3: 1 -> 2, current peak 2 ties


def test_sum_c3_reuse_after_matches_direct_recomputation() -> None:
    reuse = [2, 1, 1, 0, 0]
    current_sum_c3 = sum(math.comb(count, 3) for count in reuse)
    candidate = (1, 4, 5)
    after = sum_c3_reuse_after(candidate, reuse, current_sum_c3)
    recomputed_reuse = list(reuse)
    for number in candidate:
        recomputed_reuse[number - 1] += 1
    recomputed = sum(math.comb(count, 3) for count in recomputed_reuse)
    assert after == recomputed


# --- Full-portfolio invariants (mirrors Reference E's own test conventions) ---


def test_no_duplicate_tickets() -> None:
    portfolio = greedy_minmax_sum_then_reuse_dispersion_portfolio(
        pool_size=10, draw_size=3, ticket_count=10
    )
    assert len(set(portfolio)) == len(portfolio)


def test_every_ticket_has_draw_size_distinct_in_range_numbers() -> None:
    portfolio = greedy_minmax_sum_then_reuse_dispersion_portfolio(
        pool_size=10, draw_size=3, ticket_count=6
    )
    for ticket in portfolio:
        assert len(ticket) == 3
        assert len(set(ticket)) == 3
        assert all(1 <= number <= 10 for number in ticket)
        assert tuple(sorted(ticket)) == ticket


def test_portfolio_is_a_strict_nested_prefix() -> None:
    portfolio_8 = greedy_minmax_sum_then_reuse_dispersion_portfolio(
        pool_size=10, draw_size=3, ticket_count=8
    )
    for ticket_count in (1, 3, 4, 6):
        assert (
            greedy_minmax_sum_then_reuse_dispersion_portfolio(
                pool_size=10, draw_size=3, ticket_count=ticket_count
            )
            == portfolio_8[:ticket_count]
        )


def test_portfolio_of_zero_is_empty() -> None:
    assert (
        greedy_minmax_sum_then_reuse_dispersion_portfolio(pool_size=10, draw_size=3, ticket_count=0)
        == ()
    )


def test_deterministic_across_repeated_calls() -> None:
    first = greedy_minmax_sum_then_reuse_dispersion_portfolio(
        pool_size=10, draw_size=3, ticket_count=9
    )
    second = greedy_minmax_sum_then_reuse_dispersion_portfolio(
        pool_size=10, draw_size=3, ticket_count=9
    )
    assert first == second


def test_rejects_pool_smaller_than_draw_size() -> None:
    with pytest.raises(ValueError, match="pool_size must be >= draw_size"):
        greedy_minmax_sum_then_reuse_dispersion_portfolio(pool_size=2, draw_size=3, ticket_count=1)


def test_rejects_out_of_range_ticket_count() -> None:
    with pytest.raises(ValueError, match="ticket_count must lie in"):
        greedy_minmax_sum_then_reuse_dispersion_portfolio(
            pool_size=10, draw_size=3, ticket_count=121
        )
    with pytest.raises(ValueError, match="ticket_count must lie in"):
        greedy_minmax_sum_then_reuse_dispersion_portfolio(
            pool_size=10, draw_size=3, ticket_count=-1
        )


# --- A naturally-arising divergence at a draw_size=6 toy scale (not hand-constructed) ---


def test_naturally_diverges_from_reference_e_at_a_draw_size_six_toy_scale() -> None:
    # Confirmed by exploratory search (not a hand-built adversarial case):
    # at pool=11, draw=6 -- sharing B649's draw_size -- Reference E and
    # Candidate F first disagree at the 36th ticket. Both stay identical
    # through the first 35 tickets.
    pool_size, draw_size, ticket_count = 11, 6, 36
    reference_e = greedy_minmax_then_sum_overlap_portfolio(pool_size, draw_size, ticket_count)
    candidate_f = greedy_minmax_sum_then_reuse_dispersion_portfolio(
        pool_size, draw_size, ticket_count
    )
    assert reference_e[:35] == candidate_f[:35]
    assert reference_e[35] != candidate_f[35]
    assert len(set(candidate_f)) == len(candidate_f)
    e_max, e_sum = _max_sum_overlap(reference_e)
    f_max, f_sum = _max_sum_overlap(candidate_f)
    # Divergence must not come at the expense of Reference E's own two
    # coordinates over the whole portfolio.
    assert f_max <= e_max
    assert f_sum <= e_sum
